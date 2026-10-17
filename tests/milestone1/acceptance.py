"""Run explicitly: backend/.venv/bin/python tests/milestone1/acceptance.py.

Real PostgreSQL with non-owner runtime/auth logins and real private MinIO objects.
Only embedding inference is deterministic here; --real-model uses the cached model.
Temporary containers/processes and random synthetic credentials are cleaned up.
"""
import argparse
from contextlib import contextmanager
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.parse import quote
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
import fitz
import psycopg
from psycopg.rows import dict_row
import requests
from fastapi.testclient import TestClient
from platform_admin import fixture_id as fid, migrate, logins, seed_synthetic
from platform_api import create_app
from platform_core import Database, Originals, Embeddings, s3_client

PG_IMAGE='postgres:17-alpine@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24'
S3_IMAGE='bitnamilegacy/minio:2025.7.23-debian-12-r0@sha256:8935e75fa5d11295c17171e4aa49efe390a1193cd7f12e4d21b92af9ffef09d7'


def docker(*args):
    return subprocess.check_output(['docker',*args],text=True,stderr=subprocess.PIPE).strip()


def port(name, target):
    return docker('port',name,str(target)).rsplit(':',1)[1]


def wait_for_services(owner, client, *, timeout=60):
    deadline=time.monotonic()+timeout
    while True:
        component='PostgreSQL readiness'
        try:
            with psycopg.connect(owner,connect_timeout=1): pass
            component='MinIO readiness'
            client.create_bucket(Bucket='originals',ObjectLockEnabledForBucket=True)
            return
        except Exception as error:
            if time.monotonic()>deadline:
                raise RuntimeError(f'{component} failed ({type(error).__name__}).') from None
            time.sleep(.2)


@contextmanager
def services():
    suffix=secrets.token_hex(5); pg='doclens-m1-pg-'+suffix; obj='doclens-m1-s3-'+suffix
    password=secrets.token_urlsafe(24)
    with tempfile.TemporaryDirectory(prefix='doclens-m1-') as temp:
        envfile=Path(temp)/'services.env'
        envfile.write_text(f'POSTGRES_PASSWORD={password}\nMINIO_ROOT_USER=doclens-test-owner\nMINIO_ROOT_PASSWORD={password}\nMINIO_APP_USER=doclens-app\nMINIO_APP_PASSWORD={secrets.token_urlsafe(24)}\n')
        envfile.chmod(0o600)
        try:
            docker('run','-d','--name',pg,'--env-file',str(envfile),'-p','127.0.0.1::5432',PG_IMAGE)
            docker('run','-d','--name',obj,'--user','0','--env-file',str(envfile),'-p','127.0.0.1::9000',
                   '--entrypoint','/opt/bitnami/minio/bin/minio',S3_IMAGE,'server','/data')
            owner=f'postgresql://postgres:{quote(password)}@127.0.0.1:{port(pg,5432)}/postgres'
            endpoint=f'http://127.0.0.1:{port(obj,9000)}'
            # Configuration failures must not be hidden by the readiness retry loop.
            client=s3_client(endpoint=endpoint,access_key='doclens-test-owner',secret_key=password)
            wait_for_services(owner,client)
            policy={'Version':'2012-10-17','Statement':[{'Effect':'Allow','Action':[
                's3:PutObject','s3:GetObject','s3:GetObjectVersion','s3:PutObjectRetention','s3:PutObjectLegalHold'],
                'Resource':['arn:aws:s3:::originals/*']}]}
            policyfile=Path(temp)/'objects-policy.json'; policyfile.write_text(json.dumps(policy))
            docker('cp',str(policyfile),obj+':/tmp/objects-policy.json')
            docker('exec',obj,'sh','-c', '''mc=/opt/bitnami/minio-client/bin/mc
"$mc" --config-dir /tmp/mc alias set local http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null &&
"$mc" --config-dir /tmp/mc admin user add local "$MINIO_APP_USER" "$MINIO_APP_PASSWORD" >/dev/null &&
"$mc" --config-dir /tmp/mc admin policy create local originals-only /tmp/objects-policy.json >/dev/null &&
"$mc" --config-dir /tmp/mc admin policy attach local originals-only --user "$MINIO_APP_USER" >/dev/null''')
            app_password=next(line.split('=',1)[1] for line in envfile.read_text().splitlines() if line.startswith('MINIO_APP_PASSWORD='))
            with psycopg.connect(owner,autocommit=True) as conn:
                migrate(conn); logins(conn,password,password)
            runtime=owner.replace('postgres:'+quote(password),'doclens_web:'+quote(password),1)
            auth=owner.replace('postgres:'+quote(password),'doclens_identity:'+quote(password),1)
            os.environ['PLATFORM_SYNTHETIC_HTTP']='1'
            db=Database(runtime,auth,max_size=1)  # force reuse to expose context leakage
            objects=Originals(endpoint=endpoint,bucket='originals',access_key='doclens-app',secret_key=app_password)
            yield {'owner':owner,'runtime':runtime,'auth':auth,'db':db,'objects':objects,'endpoint':endpoint,
                   'password':password,'object_password':app_password,'temp':temp,'s3':client}
        finally:
            if 'db' in locals(): db.close()
            for name in (pg,obj):
                subprocess.run(['docker','rm','-f','-v',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


class DeterministicEmbeddings:
    name='test-only-deterministic-384'
    def encode(self,texts):
        return [[1.0]+[0.0]*383 for text in texts]


def pdf(text):
    with fitz.open() as document:
        document.new_page().insert_text((50,72),text)
        return document.tobytes()


class Acceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx=services(); cls.s=cls.ctx.__enter__()
        cls.model=Embeddings() if REAL_MODEL else DeterministicEmbeddings()
        cls.app=create_app(cls.s['db'],cls.s['objects'],cls.model)
        cls.api=TestClient(cls.app); cls.api.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.api.__exit__(None,None,None); cls.ctx.__exit__(None,None,None)

    def setUp(self):
        with psycopg.connect(self.s['owner'],autocommit=True) as conn:
            conn.execute('TRUNCATE platform.users,platform.organisations,platform.login_attempts CASCADE')
            with conn.transaction(): seed_synthetic(conn,self.s['password'])
        self.tokens={}

    def headers(self,user='alice'):
        if user not in self.tokens:
            result=self.api.post('/session',json={'email':f'{user}@synthetic.invalid','password':self.s['password']})
            self.assertEqual(result.status_code,200,result.text)
            self.tokens[user]=result.json()['token']
        return {'Authorization':'Bearer '+self.tokens[user]}

    def upload(self, user='alice', ws='a-private', text='Blue synthetic property evidence.', **metadata):
        kind=metadata.pop('kind','workspaces')
        body={'title':'Synthetic policy','source':'Author-owned synthetic fixture','jurisdiction':'Test jurisdiction',
              'received_date':date.today().isoformat(),'synthetic':True,**metadata}
        return self.api.post(f'/{kind}/{fid(ws)}/documents',headers=self.headers(user),
                             data={'metadata':json.dumps(body)},files={'file':('same.pdf',pdf(text),'application/pdf')})

    def saved(self,**kwargs):
        result=self.upload(**kwargs); self.assertEqual(result.status_code,200,result.text)
        data=result.json()
        if kwargs.get('kind')=='libraries':
            self.owner('INSERT INTO platform.reference_approvals(version_id,reviewed_by,source_authority) VALUES (%s,%s,%s)',
                       (data['version_id'],fid(kwargs.get('user','alice')),'Synthetic author-reviewed fixture'))
        return data

    def owner(self,query,params=()):
        with psycopg.connect(self.s['owner'],row_factory=dict_row) as conn:
            return conn.execute(query,params).fetchall() if query.lstrip().upper().startswith('SELECT') else conn.execute(query,params)

    def test_01_workspace_lists_and_admin_without_content_grant(self):
        for user,expected in [('alice',['a-private']),('carol',['a-restricted']),('bob',['b-private']),('org-admin',[]),('reader',['a-private']),('reviewer',['a-private'])]:
            response=self.api.get('/workspaces',headers=self.headers(user))
            self.assertEqual(response.status_code,200)
            self.assertEqual([r['name'] for r in response.json()['workspaces']],expected)

    def test_02_cross_firm_and_restricted_ids_are_indistinguishable(self):
        saved=self.saved()
        for user in ('bob','carol','org-admin'):
            for path in [f'/workspaces/{fid("a-private")}/documents',f'/documents/{saved["document_id"]}/versions',
                         f'/versions/{saved["version_id"]}/passages',f'/versions/{saved["version_id"]}/original',
                         f'/versions/{uuid4()}/original']:
                response=self.api.get(path,headers={**self.headers(user),'Range':'bytes=0-10'})
                self.assertEqual((response.status_code,response.json()),(404,{'detail':'Not found.'}))

    def test_03_auth_and_scope_denied_before_body_consumption(self):
        self.headers('bob')
        consumed=[]
        def stream():
            consumed.append(True)
            yield b'body must not be read'
        for headers in ({},self.headers('bob'),self.headers('reader')):
            response=self.api.post(f'/workspaces/{fid("a-private")}/documents',headers={**headers,'Content-Type':'multipart/form-data; boundary=x'},content=stream())
            self.assertIn(response.status_code,(401,404))
            self.assertEqual(consumed,[])
        response=self.api.post(f'/workspaces/{fid("a-private")}/search',headers=self.headers('bob'),content=stream())
        self.assertEqual(response.status_code,404); self.assertEqual(consumed,[])

    def test_04_version_identity_provenance_and_pinned_original(self):
        first=self.saved(text='First original immutable evidence.')
        second=self.saved(text='Second original replacement evidence.',document_id=first['document_id'],expected_version_id=first['version_id'])
        self.assertEqual(first['document_id'],second['document_id']); self.assertNotEqual(first['version_id'],second['version_id'])
        versions=self.api.get(f'/documents/{first["document_id"]}/versions',headers=self.headers()).json()['versions']
        self.assertEqual(len(versions),2); self.assertEqual(versions[0]['source'],'Author-owned synthetic fixture')
        for saved,marker in [(first,'First original'),(second,'Second original')]:
            response=self.api.get(f'/versions/{saved["version_id"]}/original',headers=self.headers())
            self.assertEqual(hashlib.sha256(response.content).hexdigest(),saved['sha256'])
            with fitz.open(stream=response.content,filetype='pdf') as doc:
                self.assertIn(marker,doc[0].get_text())
            passages=self.api.get(f'/versions/{saved["version_id"]}/passages',headers=self.headers()).json()
            self.assertIsNone(passages['coordinates']); self.assertEqual(passages['document_sha256'],saved['sha256'])
            self.assertEqual(passages['passages'][0]['excerpt_sha256'],hashlib.sha256(passages['passages'][0]['text'].encode()).hexdigest())

    def test_05_compare_and_swap_preserves_active_version(self):
        first=self.saved()
        stale=self.upload(document_id=first['document_id'],expected_version_id=str(uuid4()))
        self.assertEqual(stale.status_code,409)
        visible=self.api.get(f'/workspaces/{fid("a-private")}/documents',headers=self.headers()).json()['documents']
        self.assertEqual(visible[0]['active_version_id'],first['version_id'])
        # Same filename creates a distinct stable document unless an ID is supplied.
        other=self.saved(); self.assertNotEqual(first['document_id'],other['document_id'])

    def test_06_range_downloads_and_private_object_store(self):
        saved=self.saved(); url=f'/versions/{saved["version_id"]}/original'
        full=self.api.get(url,headers=self.headers()).content
        for header,expected in [('bytes=0-9',full[:10]),('bytes=-5',full[-5:]),('bytes=10-',full[10:])]:
            response=self.api.get(url,headers={**self.headers(),'Range':header})
            self.assertEqual(response.status_code,206); self.assertEqual(response.content,expected)
        for header in ('bytes=1000000-','bytes=-0','bytes=4-1','bytes=0-2,5-7'):
            self.assertEqual(self.api.get(url,headers={**self.headers(),'Range':header}).status_code,416)
        key=self.owner('SELECT object_key FROM platform.versions WHERE id=%s',(saved['version_id'],))[0]['object_key']
        session=requests.Session(); session.trust_env=False
        self.assertEqual(session.get(self.s['endpoint']+'/originals/'+key,timeout=5).status_code,403)
        with self.assertRaises(Exception): self.s['objects'].put(key,b'overwritten')
        self.assertEqual(self.api.get(url,headers=self.headers()).content,full)

    def test_07_revoke_membership_blocks_live_sessions_and_ranges(self):
        saved=self.saved()
        self.owner('DELETE FROM platform.workspace_memberships WHERE user_id=%s',(fid('alice'),))
        for tail in ('original','passages'):
            self.assertEqual(self.api.get(f'/versions/{saved["version_id"]}/{tail}',headers={**self.headers(),'Range':'bytes=0-9'}).status_code,404)
        self.assertEqual(self.api.get('/workspaces',headers=self.headers()).json()['workspaces'],[])

    def test_08_expired_revoked_and_forged_sessions(self):
        headers=self.headers()
        self.owner("UPDATE platform.sessions SET expires_at=now()-interval '1 second'")
        self.assertEqual(self.api.get('/workspaces',headers=headers).status_code,401)
        self.assertEqual(self.api.get('/workspaces',headers={'Authorization':'Bearer '+secrets.token_urlsafe(32),'X-User-ID':str(fid('alice'))}).status_code,401)
        self.tokens.clear(); headers=self.headers()
        self.assertEqual(self.api.delete('/session',headers=headers).status_code,204)
        self.assertEqual(self.api.get('/workspaces',headers=headers).status_code,401)

    def test_09_database_rls_no_context_and_connection_reuse(self):
        self.saved(); self.saved(user='bob',ws='b-private')
        with self.s['db'].pool.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM platform.documents').fetchone()['n'],0)
        for user,scope_name in [('alice','a-private'),('bob','b-private'),('org-admin',None),('alice','a-private')]:
            identity=self.s['db'].identity(self.headers(user)['Authorization'][7:])
            with self.s['db'].transaction(identity) as conn:
                rows=conn.execute('SELECT workspace_id FROM platform.documents').fetchall()
                self.assertEqual([r['workspace_id'] for r in rows],[fid(scope_name)] if scope_name else [])
        with self.s['db'].pool.connection() as conn:
            self.assertIn(conn.execute("SELECT current_setting('doclens.principal',true) AS p").fetchone()['p'],(None,''))
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM platform.passages').fetchone()['n'],0)

    def test_10_forged_scope_fields_and_reader_write_denied(self):
        for user in ('reader','reviewer','org-admin','bob'):
            self.assertEqual(self.upload(user=user).status_code,404)
        self.assertEqual(self.upload(organisation_id=str(fid('firm-b'))).status_code,400)
        self.assertEqual(self.upload(synthetic=False).status_code,400)
        foreign=self.saved(user='bob',ws='b-private')
        self.assertEqual(self.upload(document_id=foreign['document_id'],expected_version_id=foreign['version_id']).status_code,404)

    def test_11_dense_and_lexical_search_isolation_and_replacement(self):
        private=self.saved(text='Blue first old contract.')
        foreign=self.saved(user='bob',ws='b-private',text='Confidential Bob contract.')
        restricted=self.saved(user='carol',ws='a-restricted',text='Confidential Carol contract.')
        current=self.saved(text='Blue current new contract.',document_id=private['document_id'],expected_version_id=private['version_id'])
        for mode in ('dense','lexical'):
            response=self.api.post(f'/workspaces/{fid("a-private")}/search',headers=self.headers(),json={'query':'contract','mode':mode})
            self.assertEqual(response.status_code,200,response.text)
            results=response.json()['results']; self.assertTrue(results)
            self.assertEqual({r['version_id'] for r in results},{current['version_id']})
            self.assertEqual(self.api.post(f'/workspaces/{fid("a-private")}/search',headers=self.headers('bob'),json={'query':'Blue','mode':mode}).status_code,404)

    def test_12_library_exact_version_selection_and_grant_revocation(self):
        ref=self.saved(kind='libraries',ws='a-library',text='Library reference contract.')
        other=self.saved(user='bob',kind='libraries',ws='b-library',text='Bob library contract.')
        self.assertEqual(self.api.post(f'/workspaces/{fid("a-private")}/references/{other["version_id"]}',headers=self.headers()).status_code,404)
        self.assertEqual(self.api.post(f'/workspaces/{fid("a-private")}/references/{ref["version_id"]}',headers=self.headers()).status_code,200)
        newer=self.saved(kind='libraries',ws='a-library',text='New library reference contract.',document_id=ref['document_id'],expected_version_id=ref['version_id'])
        for mode in ('dense','lexical'):
            results=self.api.post(f'/workspaces/{fid("a-private")}/search',headers=self.headers(),json={'query':'contract','mode':mode}).json()['results']
            self.assertEqual({r['version_id'] for r in results},{ref['version_id']})
        # A workspace reader without an explicit library grant gets no reference text.
        results=self.api.post(f'/workspaces/{fid("a-private")}/search',headers=self.headers('reader'),json={'query':'contract','mode':'lexical'}).json()['results']
        self.assertEqual(results,[])
        self.owner('DELETE FROM platform.library_grants WHERE user_id=%s',(fid('alice'),))
        self.assertEqual(self.api.get(f'/versions/{ref["version_id"]}/original',headers=self.headers()).status_code,404)
        results=self.api.post(f'/workspaces/{fid("a-private")}/search',headers=self.headers(),json={'query':'contract','mode':'lexical'}).json()['results']
        self.assertEqual(results,[])

    def test_13_immutable_metadata_audit_and_nonowner_runtime(self):
        saved=self.saved(); identity=self.s['db'].identity(self.headers()['Authorization'][7:])
        for table in ('versions','passages','audit_events'):
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with self.s['db'].transaction(identity) as conn: conn.execute(f'DELETE FROM platform.{table}')
        with self.assertRaises(RuntimeError): Database(self.s['owner'],self.s['auth'])
        self.assertEqual(self.owner('SELECT count(*) AS n FROM platform.audit_events')[0]['n'],1)

    def test_14_unimplemented_routes_and_legacy_admin_do_not_grant_access(self):
        for path in ('/jobs/'+str(uuid4()),'/reports/'+str(uuid4()),'/exports/'+str(uuid4()),'/ask','/documents/process'):
            self.assertEqual(self.api.get(path,headers=self.headers('bob')).status_code,404)
            self.assertEqual(self.api.get(path,headers={'X-DocLens-Internal-Key':'legacy-shared-admin'}).status_code,401)

    def test_15_original_integrity_failure_and_failed_storage_leave_no_publication(self):
        saved=self.saved(); row=self.owner('SELECT object_key FROM platform.versions WHERE id=%s',(saved['version_id'],))[0]
        # Even a privileged extra object version cannot silently replace the pinned original.
        self.s['s3'].put_object(Bucket='originals',Key=row['object_key'],Body=b'corrupt new key version')
        original=self.api.get(f'/versions/{saved["version_id"]}/original',headers=self.headers())
        self.assertEqual(original.status_code,200)
        self.assertEqual(hashlib.sha256(original.content).hexdigest(),saved['sha256'])
        from unittest.mock import patch
        import io
        with patch.object(self.s['objects'].client,'get_object',return_value={'Body':io.BytesIO(b'corrupt transfer')}):
            self.assertEqual(self.api.get(f'/versions/{saved["version_id"]}/original',headers=self.headers()).status_code,503)
        from unittest.mock import patch
        with patch.object(self.s['objects'],'put',side_effect=RuntimeError('synthetic storage outage')):
            self.assertEqual(self.upload(document_id=saved['document_id'],expected_version_id=saved['version_id']).status_code,503)
        rows=self.owner('SELECT active_version_id FROM platform.documents WHERE id=%s',(saved['document_id'],))
        self.assertEqual(str(rows[0]['active_version_id']),saved['version_id'])
        self.assertEqual(self.owner('SELECT count(*) AS n FROM platform.versions')[0]['n'],1)

    def test_16_session_throttling_and_input_not_reflected(self):
        for attempt in range(11):
            result=self.api.post('/session',json={'email':'missing@synthetic.invalid','password':'never-log-this-value'})
        self.assertEqual(result.status_code,429); self.assertNotIn('never-log',result.text)
        result=self.api.post('/session',json={'email':'x','password':'never-log-this-value','organisation_id':str(fid('firm-a'))})
        self.assertEqual(result.status_code,400); self.assertNotIn('never-log',result.text)

    def test_17_revocation_during_upload_rolls_back_metadata_and_publication(self):
        original=self.saved()
        real_put=self.s['objects'].put
        def revoke_then_put(*args,**kwargs):
            result=real_put(*args,**kwargs)
            self.owner('DELETE FROM platform.workspace_memberships WHERE user_id=%s',(fid('alice'),))
            return result
        from unittest.mock import patch
        with patch.object(self.s['objects'],'put',side_effect=revoke_then_put):
            response=self.upload(document_id=original['document_id'],expected_version_id=original['version_id'])
        self.assertEqual(response.status_code,404)
        self.assertEqual(self.owner('SELECT count(*) AS n FROM platform.versions')[0]['n'],1)
        self.assertEqual(str(self.owner('SELECT active_version_id FROM platform.documents')[0]['active_version_id']),original['version_id'])

    def test_18_revocation_during_dense_search_and_original_io(self):
        saved=self.saved()
        model=self.app.state.embeddings
        original_encode=model.encode
        def revoke_encode(texts):
            result=original_encode(texts)
            self.owner('DELETE FROM platform.workspace_memberships WHERE user_id=%s',(fid('alice'),))
            return result
        from unittest.mock import patch
        with patch.object(model,'encode',side_effect=revoke_encode):
            response=self.api.post(f'/workspaces/{fid("a-private")}/search',headers=self.headers(),json={'query':'Blue','mode':'dense'})
        self.assertEqual(response.status_code,404)
        self.owner("INSERT INTO platform.workspace_memberships VALUES (%s,%s,'editor')",(fid('a-private'),fid('alice')))
        real_get=self.s['objects'].get
        def revoke_session(*args):
            data=real_get(*args)
            self.owner('UPDATE platform.sessions SET revoked=true')
            return data
        with patch.object(self.s['objects'],'get',side_effect=revoke_session):
            response=self.api.get(f'/versions/{saved["version_id"]}/original',headers=self.headers())
        self.assertEqual(response.status_code,401)
        self.assertNotIn(b'%PDF',response.content)

    def test_19_object_retention_legal_hold_and_restricted_credentials(self):
        self.owner('UPDATE platform.workspaces SET legal_hold=true WHERE id=%s',(fid('a-private'),))
        saved=self.saved()
        row=self.owner('SELECT object_key,object_version_id FROM platform.versions WHERE id=%s',(saved['version_id'],))[0]
        lock=self.s['s3'].get_object_retention(Bucket='originals',Key=row['object_key'],VersionId=row['object_version_id'])
        self.assertEqual(lock['Retention']['Mode'],'COMPLIANCE')
        hold=self.s['s3'].get_object_legal_hold(Bucket='originals',Key=row['object_key'],VersionId=row['object_version_id'])
        self.assertEqual(hold['LegalHold']['Status'],'ON')
        with self.assertRaises(Exception):
            self.s['objects'].client.delete_object(Bucket='originals',Key=row['object_key'],VersionId=row['object_version_id'])
        with self.assertRaises(Exception): self.s['objects'].client.list_buckets()
        with self.assertRaises(Exception):
            self.s['s3'].delete_object(Bucket='originals',Key=row['object_key'],VersionId=row['object_version_id'])

    def test_20_unreviewed_library_and_disabled_identity(self):
        reference=self.saved(kind='libraries',ws='a-library')
        self.owner('UPDATE platform.libraries SET reviewed=false WHERE id=%s',(fid('a-library'),))
        self.assertEqual(self.api.get(f'/versions/{reference["version_id"]}/original',headers=self.headers()).status_code,404)
        self.owner('UPDATE platform.users SET active=false WHERE id=%s',(fid('alice'),))
        self.assertEqual(self.api.get('/workspaces',headers=self.headers()).status_code,401)
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            with self.s['db'].pool.connection() as conn: conn.execute('SELECT * FROM platform.sessions')

    def test_21_reference_selection_requires_exact_version_approval(self):
        response=self.upload(kind='libraries',ws='a-library')
        self.assertEqual(response.status_code,200,response.text)
        reference=response.json()
        path=f'/workspaces/{fid("a-private")}/references/{reference["version_id"]}'
        self.assertEqual(self.api.post(path,headers=self.headers()).status_code,404)
        self.owner('INSERT INTO platform.reference_approvals(version_id,reviewed_by,source_authority) VALUES (%s,%s,%s)',
                   (reference['version_id'],fid('alice'),'Synthetic reviewed authority'))
        self.assertEqual(self.api.post(path,headers=self.headers()).status_code,200)
        self.owner('DELETE FROM platform.reference_approvals WHERE version_id=%s',(reference['version_id'],))
        results=self.api.post(f'/workspaces/{fid("a-private")}/search',headers=self.headers(),json={'query':'Blue','mode':'dense'})
        self.assertEqual(results.json()['results'],[])
        with self.s['db'].pool.connection() as conn:
            self.assertFalse(conn.execute("SELECT has_table_privilege(current_user,'platform.reference_approvals','INSERT') AS allowed").fetchone()['allowed'])

    def test_22_failure_responses_and_logs_exclude_exception_content(self):
        from unittest.mock import patch
        sensitive='private-filename-password-passage-must-not-appear'
        with patch.object(self.s['objects'],'put',side_effect=RuntimeError(sensitive)):
            with self.assertLogs('doclens.platform',level='WARNING') as logs:
                response=self.upload()
        self.assertEqual(response.status_code,503)
        self.assertNotIn(sensitive,response.text)
        self.assertNotIn(sensitive,' '.join(logs.output))

    def test_23_multi_organisation_membership_cannot_mix_reference_sources(self):
        reference=self.saved(user='bob',kind='libraries',ws='b-library',text='Foreign contract reference.')
        self.owner("INSERT INTO platform.organisation_memberships VALUES (%s,%s,'member')",(fid('firm-b'),fid('alice')))
        self.owner("INSERT INTO platform.library_grants VALUES (%s,%s,'reader')",(fid('b-library'),fid('alice')))
        # Alice may read this explicitly granted library, but cannot select it into firm A.
        self.assertEqual(self.api.get(f'/versions/{reference["version_id"]}/original',headers=self.headers()).status_code,200)
        self.assertEqual(self.api.post(f'/workspaces/{fid("a-private")}/references/{reference["version_id"]}',headers=self.headers()).status_code,404)
        # Even an erroneous privileged row cannot make the cross-org selection readable.
        self.owner('INSERT INTO platform.workspace_references VALUES (%s,%s)',(fid('a-private'),reference['version_id']))
        for mode in ('dense','lexical'):
            response=self.api.post(f'/workspaces/{fid("a-private")}/search',headers=self.headers(),json={'query':'contract','mode':mode})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['results'],[])


REAL_MODEL=False
if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--real-model',action='store_true')
    args,remaining=parser.parse_known_args(); REAL_MODEL=args.real_model
    unittest.main(argv=[sys.argv[0],*remaining],verbosity=2)
