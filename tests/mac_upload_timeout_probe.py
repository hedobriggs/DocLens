"""Real dense PDF work after a gateway timeout, and cooperative disconnect stop.

Baseline only scales the original 600000ms socket timer to 500ms so the test
needn't wait ten minutes. It leaves application code and CPU work unchanged.
Fixed mode disconnects the frontend client at 500ms without changing deadlines.
"""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

import fitz
import requests
from mac_upload_recovery_smoke import docker, port, ready

ROOT=Path(__file__).resolve().parents[1]
mode=sys.argv[1];app=Path(sys.argv[2]).resolve();out=Path(sys.argv[3]).resolve();out.mkdir(parents=True,exist_ok=True)
fixtures=Path(os.environ['DOCLENS_FREEZE_FIXTURES']);name='doclens-timeout-probe-'+secrets.token_hex(5)
secret=secrets.token_urlsafe(32);password=secrets.token_urlsafe(24);processes=[]

def clean_env():
    env={**os.environ,'HF_HOME':os.environ['HF_HOME'],'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1',
        'GEMINI_API_KEY':'synthetic-not-a-provider-credential','DOCLENS_SESSION_SECRET':secret,
        'OMP_NUM_THREADS':'2','TOKENIZERS_PARALLELISM':'false','NO_PROXY':'*','no_proxy':'*'}
    for key in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):env.pop(key,None)
    return env

try:
    docker('run','-d','--name',name,'-p','127.0.0.1::6333','qdrant/qdrant:v1.15.5')
    qp=int(docker('port',name,'6333').rsplit(':',1)[1]);storage=f'http://127.0.0.1:{qp}';ready(storage+'/readyz')
    launcher=out/'native-launcher.py'
    launcher.write_text('import socket,runpy\noriginal=socket.getaddrinfo\ndef resolve(host,port,*args,**kwargs):\n if host=="qdrant":host,port="127.0.0.1",'+str(qp)+'\n return original(host,port,*args,**kwargs)\nsocket.getaddrinfo=resolve\nrunpy.run_module("uvicorn",run_name="__main__")\n')
    env=clean_env();env['PYTHONPATH']=str(app/'backend');bp=port();base=f'http://127.0.0.1:{bp}'
    backend_log=(out/'backend.log').open('w');proc=subprocess.Popen([sys.executable,str(launcher),'main:app','--host','127.0.0.1','--port',str(bp),'--no-access-log'],cwd=app/'backend',env=env,stdout=backend_log,stderr=subprocess.STDOUT);processes.append(proc);ready(base+'/',proc)
    with fitz.open() as d:
        d.new_page().insert_text((20,30),'Original synthetic indexed document.');pdf=d.tobytes()
    assert requests.post(base+'/documents/process',headers={'X-DocLens-Internal-Key':secret},files={'file':('replacement.pdf',pdf,'application/pdf')},timeout=20).status_code==200
    def points():
        return requests.post(storage+'/collections/document_chunks/points/scroll',json={'limit':1000,'with_payload':True,'with_vector':False},timeout=5).json()['result']['points']
    old_ids={p['id'] for p in points()}
    shim=out/'routing.cjs'
    shim.write_text("const h=require('node:http');const original=h.request;const route=x=>typeof x==='string'?x.replace('http://backend:8000/','"+base+"/'):x;h.request=function(...a){a[0]=route(a[0]);return original.apply(this,a)};require('node:module').syncBuiltinESMExports();const f=global.fetch;global.fetch=(x,o)=>f(route(x),o);\n"+(
        'const timeout=h.ClientRequest.prototype.setTimeout;h.ClientRequest.prototype.setTimeout=function(ms,cb){return timeout.call(this,ms===600000?500:ms,cb)};\n' if mode=='baseline' else ''))
    env=clean_env();env['DOCLENS_TEST_PASSWORD']=password
    hashed=subprocess.check_output(['node','-e',"process.stdout.write(require('bcryptjs').hashSync(process.env.DOCLENS_TEST_PASSWORD,4))"],cwd=ROOT/'frontend',env=env,text=True)
    env.update(NODE_OPTIONS='--require '+str(shim),DOCLENS_ADMIN_EMAIL='probe@synthetic.invalid',DOCLENS_ADMIN_PASSWORD_HASH=hashed,NEXT_TELEMETRY_DISABLED='1')
    fp=port();origin=f'http://127.0.0.1:{fp}';frontend_log=(out/'frontend.log').open('w')
    front=subprocess.Popen(['node',str(ROOT/'frontend/node_modules/next/dist/bin/next'),'start','--hostname','127.0.0.1','--port',str(fp)],cwd=app/'frontend',env=env,stdout=frontend_log,stderr=subprocess.STDOUT);processes.append(front);ready(origin,front)
    login=requests.post(origin+'/api/auth/login',json={'email':'probe@synthetic.invalid','password':password},timeout=10);assert login.status_code==200,login.text
    cookie=login.cookies.get('doclens_session');start=time.monotonic()
    try:
        response=requests.post(origin+'/api/documents/process',headers={'Cookie':'doclens_session='+cookie},files={'file':('replacement.pdf',(fixtures/'text-heavy-40pages.pdf').read_bytes(),'application/pdf')},timeout=30 if mode=='baseline' else .5)
        outcome={'status':response.status_code,'body':response.json()}
        assert mode=='baseline' and response.status_code==504,outcome
    except requests.Timeout:
        assert mode=='fixed';outcome={'client_disconnected_at_seconds':.5}
    outcome['frontend_elapsed_seconds']=time.monotonic()-start
    health_timeouts=0;latencies=[];observations=[];deadline=time.monotonic()+25
    while time.monotonic()<deadline:
        health=time.monotonic()
        try:requests.get(base+'/',timeout=.3).raise_for_status();latencies.append(time.monotonic()-health)
        except requests.RequestException:health_timeouts+=1
        current=points();observations.append({'seconds_after_frontend':time.monotonic()-start,'point_count':len(current)})
        log=(out/'backend.log').read_text()
        if mode=='baseline' and len(current)==280:break
        if mode=='fixed' and '504 Gateway Timeout' in log:break
        if mode=='fixed' and time.monotonic()-start>3:
            # A cancelled worker does not write a response to the closed socket;
            # its cancellation counter is independent evidence it stopped.
            metrics=requests.get(base+'/metrics',timeout=3).text
            if 'doclens_upload_failures_total{kind="limit_or_cancel",stage="embedding"} 1.0' in metrics:break
        time.sleep(.1)
    current=points();outcome.update(health_timeouts=health_timeouts,health_successes=len(latencies),health_max_seconds=max(latencies,default=None),
        old_points_retained=old_ids.issubset({p['id'] for p in current}),points_after=len(current),observations=observations)
    if mode=='baseline':
        assert len(current)==280
        outcome['processing_completed_after_frontend_timeout']=True
    else:
        assert {p['id'] for p in current}==old_ids
        assert health_timeouts==0
        response=requests.post(base+'/documents/process',headers={'X-DocLens-Internal-Key':secret},files={'file':('new.pdf',pdf,'application/pdf')},timeout=10)
        assert response.status_code==200,response.text
        outcome['worker_released_and_next_upload_succeeded']=True
    (out/'results.json').write_text(json.dumps(outcome,indent=2)+'\n');print(json.dumps(outcome),flush=True)
finally:
    for process in reversed(processes):
        process.terminate()
        try:process.wait(timeout=3)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
    subprocess.run(['docker','rm','-f','-v',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
