"""Exercise the built non-root API image against private real SQL/object services."""
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent))
from acceptance import services, fid, pdf, DeterministicEmbeddings, docker
from platform_admin import seed_synthetic
from platform_api import create_app
import psycopg
import requests
from fastapi.testclient import TestClient

with services() as s:
    with psycopg.connect(s['owner']) as conn:
        seed_synthetic(conn,s['password'])
    with TestClient(create_app(s['db'],s['objects'],DeterministicEmbeddings())) as api:
        token=api.post('/session',json={'email':'alice@synthetic.invalid','password':s['password']}).json()['token']
        import json
        response=api.post(f'/workspaces/{fid("a-private")}/documents',headers={'Authorization':'Bearer '+token},
            data={'metadata':json.dumps({'title':'Image synthetic source','source':'Synthetic test fixture','jurisdiction':'Test','received_date':'2026-10-17','synthetic':True})},
            files={'file':('image.pdf',pdf('Synthetic immutable source for image acceptance.'),'application/pdf')})
        assert response.status_code==200,response.status_code
        version_id=response.json()['version_id']
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); chosen=sock.getsockname()[1]
    envfile=Path(s['temp'])/'api.env'
    envfile.write_text('\n'.join(f'{name}={value}' for name,value in {
        'PLATFORM_DATABASE_URL':s['runtime'],'PLATFORM_AUTH_DATABASE_URL':s['auth'],
        'PLATFORM_S3_ENDPOINT':s['endpoint'],'PLATFORM_S3_BUCKET':'originals',
        'PLATFORM_S3_ACCESS_KEY':'doclens-app','PLATFORM_S3_SECRET_KEY':s['object_password'],
        'PLATFORM_SYNTHETIC_HTTP':'1'}.items())+'\n')
    envfile.chmod(0o600)
    name='doclens-m1-api-'+secrets.token_hex(5)
    session=requests.Session(); session.trust_env=False
    base=f'http://127.0.0.1:{chosen}'
    try:
        docker('run','-d','--name',name,'--network','host','--read-only','--tmpfs','/tmp','--env-file',str(envfile),
               'doclens-milestone1-review','uvicorn','platform_api:app','--host','127.0.0.1','--port',str(chosen),'--no-access-log')
        deadline=time.monotonic()+30
        while True:
            try:
                if session.get(base+'/health',timeout=1).status_code==200: break
            except requests.RequestException: pass
            if time.monotonic()>deadline: raise RuntimeError('Non-root API image did not start')
            time.sleep(.1)
        assert docker('exec',name,'id','-u')=='10001'
        docker('exec',name,'python','-m','pip','check')
        auth={'Authorization':'Bearer '+token}
        rows=session.get(base+'/workspaces',headers=auth,timeout=10).json()['workspaces']
        assert [r['name'] for r in rows]==['a-private']
        original=session.get(base+f'/versions/{version_id}/original',headers={**auth,'Range':'bytes=0-9'},timeout=10)
        assert original.status_code==206 and original.content.startswith(b'%PDF-')
        bob=session.post(base+'/session',json={'email':'bob@synthetic.invalid','password':s['password']},timeout=10).json()['token']
        denied=session.get(base+f'/versions/{version_id}/original',headers={'Authorization':'Bearer '+bob,'Range':'bytes=0-9'},timeout=10)
        assert denied.status_code==404
        with psycopg.connect(s['owner']) as conn: conn.execute('UPDATE platform.sessions SET revoked=true')
        assert session.get(base+f'/versions/{version_id}/original',headers=auth,timeout=10).status_code==401
        print('PASS non-root Python 3.11 API image: pip check, live identity/workspace RLS, retained original range, cross-firm denial, revocation')
    finally:
        subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
