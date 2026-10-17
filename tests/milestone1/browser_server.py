"""Private local acceptance harness, never a deployment entry point."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

sys.path.insert(0,str(Path(__file__).resolve().parent))
from acceptance import services, ROOT, fid, DeterministicEmbeddings, pdf
from platform_admin import seed_synthetic
from platform_api import create_app
import psycopg
import uvicorn
from fastapi.testclient import TestClient


def main():
    with services() as s:
        with psycopg.connect(s['owner']) as conn:
            seed_synthetic(conn,os.environ['PLATFORM_FIXTURE_PASSWORD'])
        app=create_app(s['db'],s['objects'],DeterministicEmbeddings())
        with TestClient(app) as api:
            token=api.post('/session',json={'email':'alice@synthetic.invalid','password':os.environ['PLATFORM_FIXTURE_PASSWORD']}).json()['token']
            fixture=api.post(f'/workspaces/{fid("a-private")}/documents',headers={'Authorization':'Bearer '+token},
                data={'metadata':json.dumps({'title':'Alice private fixture','source':'Synthetic fixture','jurisdiction':'Test',
                      'received_date':'2026-10-17','synthetic':True})},
                files={'file':('fixture.pdf',pdf('Blue synthetic workspace citation evidence.'),'application/pdf')})
            if fixture.status_code!=200: raise RuntimeError('Browser fixture upload failed')
            directory=Path(os.environ['PLATFORM_BROWSER_FIXTURE_DIR']); directory.mkdir(exist_ok=True,parents=True)
            (directory/'fixture.json').write_text(json.dumps(fixture.json()))
            (directory/'fixture.pdf').write_bytes(pdf('Fresh synthetic upload citation evidence.'))
            server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8102,log_level='warning',access_log=False))
            thread=threading.Thread(target=server.run,daemon=True); thread.start()
            deadline=time.monotonic()+10
            while not server.started:
                if time.monotonic()>deadline: raise RuntimeError('API did not start')
                time.sleep(.05)
            env={**os.environ,'DOCLENS_PLATFORM_ENABLED':'1','PLATFORM_API_URL':'http://127.0.0.1:8102','PLATFORM_PUBLIC_ORIGIN':'http://127.0.0.1:3200'}
            frontend=subprocess.Popen(['node','node_modules/next/dist/bin/next','start','-p','3200'],cwd=ROOT/'frontend',env=env)
            def stop(signum,frame):
                frontend.terminate()
            signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGINT,stop)
            try:
                frontend.wait()
            finally:
                frontend.terminate()
                try: frontend.wait(timeout=10)
                except subprocess.TimeoutExpired: frontend.kill(); frontend.wait()
                server.should_exit=True; thread.join(timeout=10)


if __name__=='__main__': main()
