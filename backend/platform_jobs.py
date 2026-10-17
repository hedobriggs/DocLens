"""Durable admission only: no claiming, processing, publication or deletion here."""
from contextlib import contextmanager
import hashlib
import json
import logging
import re

import fitz
import psycopg
from psycopg.types.json import Jsonb
from botocore.exceptions import ClientError
from fastapi import HTTPException

from platform_core import Embeddings


ERRORS={
    'DL001':(409,'Request conflicts with the existing submission or document state.'),
    'DL002':(429,'Ingestion capacity reached. Try again later.'),
    'DL003':(404,'Not found.'),
    'DL004':(409,'Upload is in progress. Retry the same request and key later.'),
    'DL005':(409,'Upload lease expired. Retry the same request and key.'),
}


def call(conn,query,params):
    try:
        return conn.execute(query,params).fetchone()
    except psycopg.Error as error:
        if error.sqlstate in ERRORS:
            status,detail=ERRORS[error.sqlstate]
            raise HTTPException(status,detail) from None
        raise


def stage_original(originals,reservation,data):
    try:
        return originals.put(reservation['object_key'],data,
                             retention_days=reservation['retention_days'],legal_hold=reservation['legal_hold'])
    except ClientError as error:
        if error.response.get('Error',{}).get('Code') not in ('PreconditionFailed','412'):
            raise
        # An earlier PUT can have succeeded even if its response/SQL commit was lost.
        # Never overwrite it. Pin its storage version only after checking actual bytes.
        result=originals.client.head_object(Bucket=originals.bucket,Key=reservation['object_key'])
        object_version=result.get('VersionId')
        if not object_version:
            raise HTTPException(503,'Original storage must provide retained versions.') from None
        originals.get(reservation['object_key'],reservation['original_sha256'],object_version)
        return object_version


class Jobs:
    def __init__(self,database,originals):
        self.database=database
        self.originals=originals

    @contextmanager
    def transaction(self,identity):
        with self.database.transaction(identity) as conn:
            # Admission locks must not hang all organisations behind a stalled client.
            conn.execute("SET LOCAL lock_timeout='5s'")
            conn.execute("SET LOCAL statement_timeout='10s'")
            conn.execute("SET LOCAL idle_in_transaction_session_timeout='15s'")
            yield conn

    def submit(self,identity,kind,scope_id,key,metadata,data,filename):
        if not key or not re.fullmatch(r'[A-Za-z0-9._:-]{16,128}',key):
            raise HTTPException(400,'A 16–128 character Idempotency-Key is required.')
        manifest={'pipeline':'doclens-ingestion/v1','extractor':f'PyMuPDF/{fitz.VersionBind}',
                  'chunker':'doclens-boundary-1000-overlap-200/v1','embedding_model':Embeddings.name}
        digest=hashlib.sha256(data).hexdigest()
        canonical={'scope_kind':kind,'scope_id':str(scope_id),'actor_id':str(identity.user_id),
                   'metadata':metadata.model_dump(mode='json'),'filename':filename,
                   'sha256':digest}
        # Server pipeline changes must not turn an identical client replay into a
        # different request. The first reservation separately pins its manifest.
        fingerprint=hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        with self.transaction(identity) as conn:
            reservation=call(conn,'''SELECT * FROM platform.reserve_ingestion(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                             (kind,scope_id,key,fingerprint,metadata.document_id,metadata.expected_version_id,
                              digest,len(data),filename,Jsonb(canonical['metadata']),Jsonb(manifest)))
        if reservation['state']=='accepted':
            return self.status(identity,reservation['accepted_job_id'])
        try:
            object_version=stage_original(self.originals,reservation,data)
            with self.transaction(identity) as conn:
                job=call(conn,'SELECT * FROM platform.accept_ingestion(%s,%s,%s)',
                         (reservation['id'],reservation['upload_token'],object_version))
            return self.status(identity,job['id'])
        except Exception:
            # Release only our upload token; keep the reservation/original for retry
            # and later inventory. A DB outage or revocation can leave it until expiry.
            try:
                with self.transaction(identity) as conn:
                    conn.execute('SELECT platform.release_ingestion(%s,%s)',(reservation['id'],reservation['upload_token']))
            except Exception as release_error:
                logging.getLogger('doclens.platform').warning('Upload reservation release failed (%s)',type(release_error).__name__)
            raise

    def status(self,identity,job_id):
        with self.transaction(identity) as conn:
            row=conn.execute('''SELECT j.id AS job_id,j.state,j.stage,j.attempt_count,j.created_at,
              r.document_id,r.version_id FROM platform.ingestion_jobs j
              JOIN platform.ingestion_submissions s ON s.id=j.submission_id
              JOIN platform.ingestion_reservations r ON r.id=s.reservation_id WHERE j.id=%s''',(job_id,)).fetchone()
            if not row:
                raise HTTPException(404,'Not found.')
            return row
