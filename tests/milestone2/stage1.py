"""Stage 1: real PostgreSQL/MinIO, legacy upgrades and durable admission failures.

Run explicitly. Synthetic fixtures only; no worker or deletion is exercised.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
sys.path.insert(0,str(ROOT/'tests/milestone1'))
import acceptance as m1
import psycopg
from psycopg.types.json import Jsonb
from fastapi import HTTPException
from fastapi.testclient import TestClient
from platform_admin import migrate, seed_synthetic, fixture_id as fid
from platform_api import create_app, Metadata
from platform_jobs import Jobs, call


def metadata(**extra):
    return Metadata(title='Durable synthetic source',source='Author-owned synthetic fixture',jurisdiction='Test',
                    received_date=date(2026,10,17),synthetic=True,**extra)


class DurableAdmission(unittest.TestCase):
    headers=m1.Acceptance.headers
    owner=m1.Acceptance.owner
    saved=m1.Acceptance.saved
    upload=m1.Acceptance.upload

    @classmethod
    def setUpClass(cls):
        cls.feature=patch.dict(os.environ,{'PLATFORM_DURABLE_JOBS_ENABLED':'1'});cls.feature.start()
        cls.ctx=m1.services();cls.s=cls.ctx.__enter__()
        cls.app=create_app(cls.s['db'],cls.s['objects'],m1.DeterministicEmbeddings())
        cls.api=TestClient(cls.app);cls.api.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.api.__exit__(None,None,None);cls.ctx.__exit__(None,None,None);cls.feature.stop()

    def setUp(self):
        m1.Acceptance.setUp(self)
        self.data=m1.pdf('Durable synthetic property evidence.')
        self.initial_objects=len(self.s['s3'].list_object_versions(Bucket='originals').get('Versions',[]))

    def enqueue(self,*,key=None,user='alice',ws='a-private',kind='workspaces',data=None,meta=None):
        return self.api.post(f'/{kind}/{fid(ws)}/ingestions',headers={**self.headers(user),'Idempotency-Key':key or str(uuid4())},
            data={'metadata':(meta or metadata()).model_dump_json()},files={'file':('durable.pdf',data or self.data,'application/pdf')})

    def accepted(self,**kwargs):
        response=self.enqueue(**kwargs);self.assertEqual(response.status_code,202,response.text);return response.json()

    def test_01_accepted_job_is_durable_but_not_published(self):
        job=self.accepted()
        self.assertEqual((job['state'],job['stage'],job['attempt_count']),('queued','queued',0))
        self.assertEqual(self.api.get('/jobs/'+job['job_id'],headers=self.headers()).json(),job)
        for table in ('ingestion_reservations','ingestion_submissions','ingestion_jobs','ingestion_events'):
            self.assertEqual(self.owner(f'SELECT count(*) AS n FROM platform.{table}')[0]['n'],1)
        for table in ('documents','versions','passages'):
            self.assertEqual(self.owner(f'SELECT count(*) AS n FROM platform.{table}')[0]['n'],0)
        self.assertEqual(self.api.get('/versions/'+job['version_id']+'/original',headers=self.headers()).status_code,404)
        row=self.owner('SELECT * FROM platform.ingestion_reservations')[0]
        self.assertEqual(self.s['objects'].get(row['object_key'],row['original_sha256'],row['object_version_id']),self.data)
        self.assertIn('@',row['processing_manifest']['embedding_model'])

    def test_02_idempotent_replay_and_changed_request_conflict(self):
        key=str(uuid4());first=self.accepted(key=key)
        self.assertEqual(self.accepted(key=key),first)
        self.assertEqual(self.enqueue(key=key,data=m1.pdf('Changed content')).status_code,409)
        changed=metadata();changed.title='Changed title'
        self.assertEqual(self.enqueue(key=key,meta=changed).status_code,409)
        self.assertEqual(self.owner('SELECT count(*) AS n FROM platform.ingestion_jobs')[0]['n'],1)
        self.assertEqual(len(self.s['s3'].list_object_versions(Bucket='originals').get('Versions',[]))-self.initial_objects,1)

    def test_03_identity_scope_and_key_checked_before_body(self):
        consumed=[]
        def stream(): consumed.append(True);yield b'must not be parsed'
        for user,expected in [('bob',404),('reader',404),('org-admin',404)]:
            response=self.api.post(f'/workspaces/{fid("a-private")}/ingestions',headers={**self.headers(user),'Idempotency-Key':str(uuid4())},content=stream())
            self.assertEqual(response.status_code,expected);self.assertEqual(consumed,[])
        response=self.api.post(f'/workspaces/{fid("a-private")}/ingestions',headers=self.headers(),content=stream())
        self.assertEqual(response.status_code,400);self.assertEqual(consumed,[])
        with patch.dict(os.environ,{'PLATFORM_DURABLE_JOBS_ENABLED':'0'}):
            response=self.api.post(f'/workspaces/{fid("a-private")}/ingestions',headers=self.headers(),content=stream())
            self.assertEqual(response.status_code,404);self.assertEqual(consumed,[])
        self.assertEqual(self.owner('SELECT count(*) AS n FROM platform.ingestion_reservations')[0]['n'],0)

    def test_04_job_status_uses_current_permissions(self):
        job=self.accepted();path='/jobs/'+job['job_id']
        for user in ('bob','carol','org-admin'):
            response=self.api.get(path,headers=self.headers(user))
            self.assertEqual((response.status_code,response.json()),(404,{'detail':'Not found.'}))
        self.assertEqual(self.api.get(path,headers=self.headers('reader')).status_code,200)
        self.owner('DELETE FROM platform.workspace_memberships WHERE user_id=%s',(fid('alice'),))
        self.assertEqual(self.api.get(path,headers=self.headers()).status_code,404)
        self.assertEqual(self.owner('SELECT count(*) AS n FROM platform.ingestion_jobs')[0]['n'],1)

    def test_05_same_org_key_cannot_reveal_other_workspace_submission(self):
        key=str(uuid4());job=self.accepted(key=key,user='carol',ws='a-restricted')
        response=self.enqueue(key=key)
        self.assertEqual(response.status_code,409);self.assertNotIn(job['job_id'],response.text)
        self.assertEqual(self.api.get('/jobs/'+job['job_id'],headers=self.headers()).status_code,404)

    def test_06_shared_organisation_quota_includes_hidden_workspaces(self):
        for _ in range(4):self.accepted()
        for _ in range(4):self.accepted(user='carol',ws='a-restricted')
        self.assertEqual(self.enqueue().status_code,429)
        self.assertEqual(self.owner('SELECT count(*) AS n FROM platform.ingestion_jobs')[0]['n'],8)
        self.assertEqual(len(self.s['s3'].list_object_versions(Bucket='originals').get('Versions',[]))-self.initial_objects,8)

    def test_07_concurrent_admission_across_instances_respects_shared_quota(self):
        identity=self.s['db'].identity(self.headers()['Authorization'][7:])
        def submit(_):
            try:
                return Jobs(self.s['db'],self.s['objects']).submit(identity,'workspaces',fid('a-private'),str(uuid4()),metadata(),self.data,'durable.pdf')['state']
            except HTTPException as error:return error.status_code
        with ThreadPoolExecutor(max_workers=8) as pool: results=list(pool.map(submit,range(12)))
        self.assertEqual(results.count('queued'),8,results);self.assertEqual(results.count(429),4,results)
        self.assertEqual(self.owner('SELECT count(*) AS n FROM platform.ingestion_jobs')[0]['n'],8)

    def test_08_original_put_response_loss_reuses_retained_storage_version(self):
        key=str(uuid4());real=self.s['objects'].put
        def lost_response(*args,**kwargs):real(*args,**kwargs);raise RuntimeError('private simulated response loss')
        with patch.object(self.s['objects'],'put',side_effect=lost_response):
            self.assertEqual(self.enqueue(key=key).status_code,503)
        reservation=self.owner('SELECT * FROM platform.ingestion_reservations')[0]
        self.assertEqual(reservation['state'],'receiving')
        self.accepted(key=key)
        self.assertEqual(len(self.s['s3'].list_object_versions(Bucket='originals',Prefix=reservation['object_key']).get('Versions',[])),1)

    def test_09_acceptance_transaction_rolls_back_all_job_records(self):
        self.owner("""CREATE FUNCTION platform.test_reject_acceptance() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN IF NEW.state='accepted' THEN RAISE EXCEPTION 'synthetic acceptance failure';END IF;RETURN NEW;END $$""")
        self.owner('CREATE TRIGGER test_reject_acceptance BEFORE UPDATE ON platform.ingestion_reservations FOR EACH ROW EXECUTE FUNCTION platform.test_reject_acceptance()')
        key=str(uuid4())
        try:self.assertEqual(self.enqueue(key=key).status_code,503)
        finally:
            self.owner('DROP TRIGGER test_reject_acceptance ON platform.ingestion_reservations')
            self.owner('DROP FUNCTION platform.test_reject_acceptance()')
        for table in ('ingestion_submissions','ingestion_jobs','ingestion_events'):
            self.assertEqual(self.owner(f'SELECT count(*) AS n FROM platform.{table}')[0]['n'],0)
        self.assertEqual(self.owner('SELECT count(*) AS n FROM platform.ingestion_reservations')[0]['n'],1)
        self.accepted(key=key)
        self.assertEqual(len(self.s['s3'].list_object_versions(Bucket='originals').get('Versions',[]))-self.initial_objects,1)

    def test_10_fresh_process_can_read_accepted_job_after_submitter_session_expiry(self):
        job=self.accepted()
        self.owner("UPDATE platform.sessions SET expires_at=now()-interval '1 second'")
        self.tokens.clear();token=self.headers()['Authorization'][7:]
        code="""import os,sys
sys.path.insert(0,os.environ['M2_BACKEND'])
from platform_core import Database
from platform_jobs import Jobs
db=Database(os.environ['M2_RUNTIME'],os.environ['M2_AUTH'])
try:
 row=Jobs(db,None).status(db.identity(os.environ['M2_TOKEN']),os.environ['M2_JOB'])
 print(str(row['job_id']),row['state'])
finally:db.close()
"""
        env={**os.environ,'M2_BACKEND':str(ROOT/'backend'),'M2_RUNTIME':self.s['runtime'],'M2_AUTH':self.s['auth'],'M2_TOKEN':token,'M2_JOB':job['job_id']}
        result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.strip(),job['job_id']+' queued')

    def test_11_readonly_job_tables_and_no_delete_or_role_escalation(self):
        self.accepted();identity=self.s['db'].identity(self.headers()['Authorization'][7:])
        for table in ('ingestion_reservations','ingestion_submissions','ingestion_jobs','ingestion_attempts','ingestion_events'):
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with self.s['db'].transaction(identity) as conn:conn.execute(f'DELETE FROM platform.{table}')
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.s['db'].transaction(identity) as conn:conn.execute('SET ROLE doclens_job_control')
        with self.s['db'].pool.connection() as conn:
            for table in ('ingestion_jobs','ingestion_attempts','ingestion_submissions'):
                self.assertFalse(conn.execute("SELECT has_table_privilege(current_user,%s,'INSERT') AS allowed",('platform.'+table,)).fetchone()['allowed'])
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM platform.ingestion_jobs').fetchone()['n'],0)

    def test_12_replacement_captures_revision_and_preserves_old_citations(self):
        old=self.saved();r1=self.owner('SELECT publication_revision FROM platform.documents')[0]['publication_revision']
        job=self.accepted(meta=metadata(document_id=old['document_id'],expected_version_id=old['version_id']))
        current=self.saved(text='New legacy-path synthetic version',document_id=old['document_id'],expected_version_id=old['version_id'])
        reservation=self.owner('SELECT * FROM platform.ingestion_reservations')[0]
        self.assertEqual(reservation['expected_publication_revision'],r1)
        self.assertEqual(str(reservation['expected_active_version_id']),old['version_id'])
        self.assertEqual(str(self.owner('SELECT active_version_id FROM platform.documents')[0]['active_version_id']),current['version_id'])
        self.assertEqual(self.api.get('/versions/'+old['version_id']+'/original',headers=self.headers()).status_code,200)
        self.assertEqual(self.api.get('/jobs/'+job['job_id'],headers=self.headers()).json()['state'],'queued')
        self.assertEqual(self.owner('SELECT publication_revision FROM platform.documents')[0]['publication_revision'],r1+1)

    def test_13_revocation_during_storage_cannot_accept_job(self):
        real=self.s['objects'].put
        def revoke(*args,**kwargs):
            result=real(*args,**kwargs)
            self.owner('DELETE FROM platform.workspace_memberships WHERE user_id=%s',(fid('alice'),))
            return result
        with patch.object(self.s['objects'],'put',side_effect=revoke):
            self.assertEqual(self.enqueue().status_code,404)
        self.assertEqual(self.owner('SELECT count(*) AS n FROM platform.ingestion_jobs')[0]['n'],0)
        self.assertEqual(self.owner('SELECT count(*) AS n FROM platform.ingestion_reservations')[0]['n'],1)

    def test_14_forged_scope_and_customer_data_flag_rejected(self):
        bad=json.loads(metadata().model_dump_json());bad['organisation_id']=str(fid('firm-b'))
        response=self.api.post(f'/workspaces/{fid("a-private")}/ingestions',headers={**self.headers(),'Idempotency-Key':str(uuid4())},
            data={'metadata':json.dumps(bad)},files={'file':('durable.pdf',self.data,'application/pdf')})
        self.assertEqual(response.status_code,400)
        meta=metadata();meta.synthetic=False
        self.assertEqual(self.enqueue(meta=meta).status_code,400)
        self.assertEqual(self.owner('SELECT count(*) AS n FROM platform.ingestion_reservations')[0]['n'],0)

    def test_15_originals_are_retained_and_cleanup_has_no_delete_capability(self):
        self.owner('UPDATE platform.workspaces SET legal_hold=true WHERE id=%s',(fid('a-private'),))
        self.accepted();r=self.owner('SELECT * FROM platform.ingestion_reservations')[0]
        hold=self.s['s3'].get_object_legal_hold(Bucket='originals',Key=r['object_key'],VersionId=r['object_version_id'])
        self.assertEqual(hold['LegalHold']['Status'],'ON')
        with self.assertRaises(Exception):self.s['objects'].client.delete_object(Bucket='originals',Key=r['object_key'],VersionId=r['object_version_id'])

    def test_16_process_death_after_reservation_and_after_put_is_recoverable(self):
        for boundary in ('before_put','after_put'):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as tmp:
                key=str(uuid4());path=Path(tmp)/'fixture.pdf';path.write_bytes(self.data)
                token=self.headers()['Authorization'][7:]
                code="""import os,sys
sys.path.insert(0,os.environ['M2_BACKEND'])
from platform_core import Database,Originals
from platform_jobs import Jobs
from platform_api import Metadata
from pathlib import Path
from uuid import UUID
db=Database(os.environ['M2_RUNTIME'],os.environ['M2_AUTH'])
obj=Originals(endpoint=os.environ['M2_ENDPOINT'],bucket='originals',access_key='doclens-app',secret_key=os.environ['M2_OBJECT_SECRET'])
real=obj.put
def crash(*args,**kwargs):
 if os.environ['M2_BOUNDARY']=='after_put':real(*args,**kwargs)
 os._exit(23)
obj.put=crash
Jobs(db,obj).submit(db.identity(os.environ['M2_TOKEN']),'workspaces',UUID(os.environ['M2_SCOPE']),os.environ['M2_KEY'],Metadata.model_validate_json(os.environ['M2_METADATA']),Path(os.environ['M2_PDF']).read_bytes(),'durable.pdf')
"""
                env={**os.environ,'M2_BACKEND':str(ROOT/'backend'),'M2_RUNTIME':self.s['runtime'],'M2_AUTH':self.s['auth'],
                     'M2_ENDPOINT':self.s['endpoint'],'M2_OBJECT_SECRET':self.s['object_password'],'M2_TOKEN':token,
                     'M2_BOUNDARY':boundary,'M2_SCOPE':str(fid('a-private')),'M2_KEY':key,'M2_METADATA':metadata().model_dump_json(),'M2_PDF':str(path)}
                result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,23,result.stderr)
                r=self.owner('SELECT * FROM platform.ingestion_reservations WHERE idempotency_key=%s',(key,))[0]
                self.assertEqual(r['state'],'receiving')
                self.owner("UPDATE platform.ingestion_reservations SET lease_expires_at=now()-interval '1 second' WHERE id=%s",(r['id'],))
                self.accepted(key=key)
                self.assertEqual(len(self.s['s3'].list_object_versions(Bucket='originals',Prefix=r['object_key']).get('Versions',[])),1)

    def test_17_global_quota_is_shared_across_organisations(self):
        identity=self.s['db'].identity(self.headers()['Authorization'][7:])
        scopes=[]
        for index in range(5):
            org,ws=uuid4(),uuid4();scopes.append(ws)
            self.owner('INSERT INTO platform.organisations VALUES (%s,%s)',(org,'synthetic capacity firm'))
            self.owner("INSERT INTO platform.organisation_memberships VALUES (%s,%s,'member')",(org,fid('alice')))
            self.owner('INSERT INTO platform.workspaces(id,organisation_id,name,retention_days) VALUES (%s,%s,%s,365)',(ws,org,'synthetic capacity workspace'))
            self.owner("INSERT INTO platform.workspace_memberships VALUES (%s,%s,'editor')",(ws,fid('alice')))
            if index<4:
                for _ in range(8):Jobs(self.s['db'],self.s['objects']).submit(identity,'workspaces',ws,str(uuid4()),metadata(),self.data,'durable.pdf')
        with self.assertRaises(HTTPException) as error:
            Jobs(self.s['db'],self.s['objects']).submit(identity,'workspaces',scopes[-1],str(uuid4()),metadata(),self.data,'durable.pdf')
        self.assertEqual(error.exception.status_code,429)
        self.assertEqual(self.owner('SELECT count(*) AS n FROM platform.ingestion_jobs')[0]['n'],32)

    def test_18_expired_upload_token_is_fenced_after_reservation_reclaim(self):
        key=str(uuid4())
        with patch.object(self.s['objects'],'put',side_effect=RuntimeError('synthetic storage failure')):
            self.assertEqual(self.enqueue(key=key).status_code,503)
        old=self.owner('SELECT * FROM platform.ingestion_reservations')[0]
        identity=self.s['db'].identity(self.headers()['Authorization'][7:])
        with self.s['db'].transaction(identity) as conn:
            new=call(conn,'SELECT * FROM platform.reserve_ingestion(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                ('workspaces',fid('a-private'),key,old['request_sha256'],None,None,old['original_sha256'],old['byte_size'],old['filename'],Jsonb(old['metadata']),Jsonb(old['processing_manifest'])))
        self.assertNotEqual(old['upload_token'],new['upload_token'])
        with self.assertRaises(HTTPException) as error:
            with self.s['db'].transaction(identity) as conn:
                call(conn,'SELECT * FROM platform.accept_ingestion(%s,%s,%s)',(old['id'],old['upload_token'],'not-an-object-version'))
        self.assertEqual(error.exception.status_code,409)
        with self.s['db'].transaction(identity) as conn:
            conn.execute('SELECT platform.release_ingestion(%s,%s)',(old['id'],old['upload_token']))
        self.assertEqual(self.owner('SELECT lease_expires_at FROM platform.ingestion_reservations')[0]['lease_expires_at'],new['lease_expires_at'])
        self.assertEqual(self.owner('SELECT count(*) AS n FROM platform.ingestion_jobs')[0]['n'],0)

    def test_19_acceptance_expiry_is_enforced_without_changing_original_versions(self):
        key=str(uuid4())
        with patch.object(self.s['objects'],'put',side_effect=RuntimeError('synthetic storage failure')):
            self.assertEqual(self.enqueue(key=key).status_code,503)
        r=self.owner('SELECT * FROM platform.ingestion_reservations')[0]
        identity=self.s['db'].identity(self.headers()['Authorization'][7:])
        with self.assertRaises(HTTPException) as error:
            with self.s['db'].transaction(identity) as conn:
                call(conn,'SELECT * FROM platform.accept_ingestion(%s,%s,%s)',(r['id'],r['upload_token'],'not-an-object-version'))
        self.assertEqual(error.exception.status_code,409)
        self.assertEqual(self.owner('SELECT count(*) AS n FROM platform.ingestion_submissions')[0]['n'],0)
        self.accepted(key=key)

    def test_20_upload_token_and_raw_submission_metadata_are_not_runtime_selectable(self):
        self.accepted();identity=self.s['db'].identity(self.headers()['Authorization'][7:])
        for query in ('SELECT upload_token FROM platform.ingestion_reservations',
                      'SELECT metadata FROM platform.ingestion_reservations',
                      'SELECT object_version_id FROM platform.ingestion_submissions'):
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with self.s['db'].transaction(identity) as conn:conn.execute(query)

    def test_21_server_manifest_update_does_not_retarget_an_idempotent_replay(self):
        key=str(uuid4());job=self.accepted(key=key)
        original=self.owner('SELECT processing_manifest FROM platform.ingestion_reservations')[0]['processing_manifest']
        with patch('platform_jobs.Embeddings.name','test-new-model@new-revision'):
            self.assertEqual(self.accepted(key=key),job)
        self.assertEqual(self.owner('SELECT processing_manifest FROM platform.ingestion_reservations')[0]['processing_manifest'],original)
        self.assertEqual(len(self.s['s3'].list_object_versions(Bucket='originals').get('Versions',[]))-self.initial_objects,1)

    def test_22_replay_remains_stable_after_document_pointer_changes(self):
        old=self.saved();key=str(uuid4());meta=metadata(document_id=old['document_id'],expected_version_id=old['version_id'])
        job=self.accepted(key=key,meta=meta)
        new=self.saved(text='A later synchronous replacement',document_id=old['document_id'],expected_version_id=old['version_id'])
        self.assertEqual(self.accepted(key=key,meta=meta),job)
        self.assertEqual(str(self.owner('SELECT active_version_id FROM platform.documents')[0]['active_version_id']),new['version_id'])


class MigrationUpgrade(unittest.TestCase):
    def test_01_legacy_v1_upgrade_preserves_all_old_rows_and_citation_bytes(self):
        with m1.services(legacy_v1=True) as s:
            with psycopg.connect(s['owner']) as conn:seed_synthetic(conn,s['password'])
            with TestClient(create_app(s['db'],s['objects'],m1.DeterministicEmbeddings())) as api:
                token=api.post('/session',json={'email':'alice@synthetic.invalid','password':s['password']}).json()['token']
                headers={'Authorization':'Bearer '+token}
                response=api.post(f'/workspaces/{fid("a-private")}/documents',headers=headers,
                    data={'metadata':metadata().model_dump_json()},files={'file':('legacy.pdf',m1.pdf('Pinned legacy citation source.'),'application/pdf')})
                self.assertEqual(response.status_code,200,response.text);old=response.json()
                original=api.get('/versions/'+old['version_id']+'/original',headers=headers).content
                with psycopg.connect(s['owner']) as conn:
                    tables=['users','sessions','organisations','organisation_memberships','workspaces','workspace_memberships','libraries','library_grants','documents','versions','passages','reference_approvals','workspace_references','audit_events']
                    snapshot={table:conn.execute(f'SELECT row_to_json(t)::text FROM platform.{table} t ORDER BY row_to_json(t)::text').fetchall() for table in tables}
                with psycopg.connect(s['owner'],autocommit=True) as conn:migrate(conn);migrate(conn)
                with psycopg.connect(s['owner']) as conn:
                    for table in tables:
                        expression="(to_jsonb(t)-'publication_revision')::text" if table=='documents' else 'row_to_json(t)::text'
                        actual=conn.execute(f'SELECT {expression} FROM platform.{table} t ORDER BY {expression}').fetchall()
                        if table=='documents':
                            self.assertEqual([json.loads(r[0]) for r in actual],[json.loads(r[0]) for r in snapshot[table]])
                        else:self.assertEqual(actual,snapshot[table],table)
                    self.assertEqual(conn.execute('SELECT version FROM platform.schema_migrations ORDER BY version').fetchall(),[(1,),(2,)])
                    provenance=conn.execute('SELECT sha256,provenance FROM platform.migration_history WHERE version=1').fetchone()
                    self.assertEqual(provenance,(None,'legacy-unverified'))
                self.assertEqual(api.get('/versions/'+old['version_id']+'/original',headers=headers).content,original)

    def test_02_failed_upgrade_rolls_back_and_retry_succeeds(self):
        with m1.services(legacy_v1=True) as s, tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            for path in (ROOT/'backend/platform_migrations').glob('*.sql'):shutil.copy(path,directory/path.name)
            with (directory/'002_durable_jobs.sql').open('a') as f:f.write('\nSELECT undefined_migration_function();\n')
            with psycopg.connect(s['owner'],autocommit=True) as conn:
                with self.assertRaises(psycopg.Error):migrate(conn,migrations_dir=directory)
                self.assertIsNone(conn.execute("SELECT to_regclass('platform.ingestion_jobs')").fetchone()[0])
                self.assertIsNone(conn.execute("SELECT to_regclass('platform.migration_history')").fetchone()[0])
                self.assertIsNone(conn.execute("SELECT 1 FROM pg_roles WHERE rolname='doclens_job_control'").fetchone())
                self.assertEqual(conn.execute('SELECT version FROM platform.schema_migrations').fetchall(),[(1,)])
                migrate(conn)
                self.assertIsNotNone(conn.execute("SELECT to_regclass('platform.ingestion_jobs')").fetchone()[0])

    def test_03_changed_applied_migration_and_downgrade_are_rejected(self):
        with m1.services() as s, tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            for path in (ROOT/'backend/platform_migrations').glob('*.sql'):shutil.copy(path,directory/path.name)
            with (directory/'002_durable_jobs.sql').open('a') as f:f.write('\n-- unexpected changed migration\n')
            with psycopg.connect(s['owner'],autocommit=True) as conn:
                with self.assertRaisesRegex(RuntimeError,'checksum changed'):migrate(conn,migrations_dir=directory)
                with self.assertRaisesRegex(RuntimeError,'newer'):migrate(conn,target=1)
                self.assertEqual(conn.execute('SELECT count(*) FROM platform.migration_history').fetchone()[0],2)

    def test_04_concurrent_migration_runners_serialize(self):
        with m1.services(legacy_v1=True) as s:
            def upgrade(_):
                with psycopg.connect(s['owner'],autocommit=True) as conn:migrate(conn)
            with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(upgrade,range(2)))
            with psycopg.connect(s['owner']) as conn:
                self.assertEqual(conn.execute('SELECT version FROM platform.schema_migrations ORDER BY version').fetchall(),[(1,),(2,)])
                self.assertEqual(conn.execute('SELECT count(*) FROM platform.migration_history').fetchone()[0],2)


if __name__=='__main__':unittest.main(verbosity=2)
