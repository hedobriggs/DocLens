import concurrent.futures,json,os,subprocess,sys,time,secrets,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from mac_upload_recovery_smoke import docker,ready,port
import requests
root=Path(os.environ['DOCLENS_FREEZE_FIXTURES']).resolve();mode=sys.argv[1];backend=Path(sys.argv[2]).resolve();suffix=secrets.token_hex(4)
name='doclens-freeze-qdrant-'+suffix;proc=None;results={};secret=secrets.token_urlsafe(32)
try:
 docker('run','-d','--name',name,'-p','127.0.0.1::6333','qdrant/qdrant:v1.15.5')
 qp=int(docker('port',name,'6333').rsplit(':',1)[1]);ready(f'http://127.0.0.1:{qp}/readyz')
 launcher=root/(mode+'-launcher.py');launcher.write_text('import socket,runpy\noriginal=socket.getaddrinfo\ndef resolve(host,port,*args,**kwargs):\n if host=="qdrant":host,port="127.0.0.1",'+str(qp)+'\n return original(host,port,*args,**kwargs)\nsocket.getaddrinfo=resolve\nrunpy.run_module("uvicorn",run_name="__main__")\n')
 env={**os.environ,'PYTHONPATH':str(backend),'HF_HOME':os.environ.get('HF_HOME',str(Path.home()/'.cache/huggingface')),'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','GEMINI_API_KEY':'synthetic-not-a-provider-credential','DOCLENS_SESSION_SECRET':secret,'OMP_NUM_THREADS':'2','TOKENIZERS_PARALLELISM':'false','NO_PROXY':'*','no_proxy':'*'}
 for k in ('HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy','ALL_PROXY','all_proxy'):env.pop(k,None)
 bp=port();base=f'http://127.0.0.1:{bp}'
 with (root/(mode+'-backend.log')).open('w') as log:
  proc=subprocess.Popen([sys.executable,str(launcher),'main:app','--host','127.0.0.1','--port',str(bp),'--no-access-log'],cwd=backend,env=env,stdout=log,stderr=subprocess.STDOUT);ready(base+'/',proc)
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   for filename in sys.argv[3:]:
    path=root/filename;data=path.read_bytes();samples=[];latencies=[];timeouts=0;begin=time.perf_counter()
    def upload():
     try:
      response=requests.post(base+'/documents/process',headers={'X-DocLens-Internal-Key':secret},files={'file':(filename,data,'application/pdf')},timeout=35 if mode=='baseline' else 110)
      return {'status':response.status_code,'body':response.text[:300]}
     except requests.RequestException as e:return {'exception':type(e).__name__}
    future=pool.submit(upload)
    while not future.done() and time.perf_counter()-begin<(10 if mode=='baseline' and '28mib' in filename and 'text-heavy' in filename else 115):
     status=Path(f'/proc/{proc.pid}/status').read_text();samples.append({line.split(':')[0]:int(line.split()[1]) for line in status.splitlines() if line.startswith(('VmRSS:','VmHWM:','VmSize:'))})
     start=time.perf_counter()
     try:requests.get(base+'/',timeout=.35).raise_for_status();latencies.append(time.perf_counter()-start)
     except requests.RequestException:timeouts+=1
     time.sleep(.1)
    result={'seconds':time.perf_counter()-begin,'peak_rss_kib':max(x['VmRSS'] for x in samples) if samples else None,'peak_vmsize_kib':max(x['VmSize'] for x in samples) if samples else None,'health_successes':len(latencies),'health_timeouts':timeouts,'health_max_seconds':max(latencies,default=None)}
    if future.done():result.update(future.result())
    else:
     result['stopped_observation_early']=True;proc.kill();proc.wait(timeout=10);future.result();proc=None
    results[filename]=result;print(json.dumps({filename:result}),flush=True)
    (root/(mode+'-measurements.json')).write_text(json.dumps(results,indent=2)+'\n')
    if proc is None:break
finally:
 if proc:
  proc.terminate()
  try:proc.wait(timeout=2)
  except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=10)
 subprocess.run(['docker','rm','-f','-v',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
