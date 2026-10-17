"""Disposable cloud-only helper validation; refuses any existing application containers.

Run with HF_HOME pointing to the already verified model cache. Does not perform
or certify a fresh Mac Dockerfile build. Never run this in the live Mac project.
"""
import importlib.util,subprocess,tempfile,pathlib,json,time,os,sys
repo=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('safe',repo/'recovery/mac-upload/safe_update.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
sys.path.insert(0,str(repo/'tests'));from mac_upload_recovery_smoke import docker,ready,QDRANT
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams,Distance,PointStruct
suffix=str(time.time_ns());project='doclens-safe-'+suffix;volume=project+'_qdrant_server_data';network=project
names=m.CONTAINERS
assert not set(names)&set(docker('ps','-a','--format','{{.Names}}').splitlines()),'Existing application found; refusing fixture'
root=pathlib.Path(tempfile.mkdtemp(prefix='safe-update-live-',dir='/tmp'));checkout=root/'DocLens';backup=root/'backup';created=[];tags=[]
try:
 subprocess.run(['git','clone','--shared','--no-checkout',str(repo),str(checkout)],check=True,capture_output=True)
 subprocess.run(['git','-C',str(checkout),'checkout','--detach',m.BASE],check=True,capture_output=True)
 for name in m.ORIGINALS:(checkout/name).write_bytes(m.blob(repo,m.MAC,name))
 (checkout/'backend/main.py').write_bytes(m.blob(repo,m.INDENT,'backend/main.py'))
 (checkout/'.env').write_text('GRAFANA_ADMIN_PASSWORD=synthetic-local-only\nDOCLENS_SESSION_SECRET=synthetic-local-only\n')
 (checkout/'backend/.env').write_text('GEMINI_API_KEY=synthetic-not-a-provider-credential\n')
 (checkout/'backend/main.py.backup').write_text('Exact original private backup\n')
 docker('network','create',network);docker('volume','create',volume)
 def labels(service):return ['--label','com.docker.compose.project='+project,'--label','com.docker.compose.service='+service]
 docker('run','-d','--name',names[2],'--network',network,'--network-alias','qdrant',*labels('qdrant'),'-e','QDRANT__STORAGE__WAL__WAL_CAPACITY_MB=1','-v',volume+':/qdrant/storage','-p','127.0.0.1::6333',QDRANT);created.append(names[2])
 url='http://127.0.0.1:'+docker('port',names[2],'6333').rsplit(':',1)[1];ready(url+'/readyz')
 c=QdrantClient(url=url,trust_env=False)
 c.create_collection('document_chunks',vectors_config=VectorParams(size=384,distance=Distance.COSINE))
 original='11111111-1111-4111-8111-111111111111'
 c.upsert('document_chunks',points=[PointStruct(id=original,vector=[1.0]+[0.0]*383,payload={'text':'Pre-existing synthetic original','document_name':'existing-synthetic.pdf','page_number':1,'chunk_id':'p1-c1'})],wait=True)
 for name,service in zip(names[:2],('backend','frontend')):
  docker('run','-d','--name',name,'--network',network,*labels(service),'--entrypoint','sh',QDRANT,'-c','trap "exit 0" TERM; while :; do sleep 1; done');created.append(name)
 m.prepare(checkout,backup)
 state=json.loads((backup/'state.json').read_text());tags=list(state['image_tags'].values())
 assert state['volume']==volume and list((backup/'qdrant-storage').iterdir())
 assert (checkout/'backend/main.py.backup').read_text()=='Exact original private backup\n'
 assert json.loads(docker('inspect',names[2]))[0]['State']['Running'] is False
 docker('start',names[2]);url='http://127.0.0.1:'+docker('port',names[2],'6333').rsplit(':',1)[1];ready(url+'/readyz');c.close();c=QdrantClient(url=url,trust_env=False)
 assert c.retrieve('document_chunks',ids=[original])[0].payload['text']=='Pre-existing synthetic original'
 docker('rm',names[0]);created.remove(names[0])
 envfile=root/'synthetic.env';envfile.write_text('DOCLENS_SESSION_SECRET=synthetic-local-only\nGEMINI_API_KEY=synthetic-not-a-provider-credential\nHF_HOME=/models\nHF_HUB_OFFLINE=1\nTRANSFORMERS_OFFLINE=1\nDOCLENS_INFERENCE_THREADS=2\nOMP_NUM_THREADS=2\nTOKENIZERS_PARALLELISM=false\n')
 launch='import os,runpy,sys; [os.environ.pop(k,None) for k in ("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","http_proxy","https_proxy","all_proxy")];os.environ.update(NO_PROXY="*",no_proxy="*");sys.argv=["uvicorn","main:app","--host","0.0.0.0","--port","8000"];runpy.run_module("uvicorn",run_name="__main__")'
 docker('run','-d','--name',names[0],'--user','0','--network',network,*labels('backend'),'--cpus','2','--memory','1536m','--memory-swap','1536m','--env-file',str(envfile),'-v',str(checkout/'backend')+':/app:ro','-v',str(pathlib.Path(os.environ['HF_HOME']).resolve())+':/models:ro','doclens-mac-upload-freeze:review','python','-c',launch);created.append(names[0])
 state['phase']='rebuilt';m.save(backup,state)
 # Cloud proxy injection also affects exec processes. Only this harness clears it.
 original_verify=m.VERIFY
 m.VERIFY='import os\n[os.environ.pop(k,None) for k in ("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","http_proxy","https_proxy","all_proxy")]\nos.environ.update(NO_PROXY="*",no_proxy="*")\n'+original_verify
 m.verify(checkout,backup)
 assert c.retrieve('document_chunks',ids=[original])[0].payload['text']=='Pre-existing synthetic original'
 c.close()
 print('PASS: real Docker cold backup, unchanged Qdrant volume/original point, selective update, reviewed-source startup and exact synthetic verify command')
 print('Evidence:',backup)
finally:
 for name in created:
  if name==names[0]:
   result=subprocess.run(['docker','logs',name],capture_output=True);(root/'backend.log').write_bytes(result.stdout+result.stderr)
  subprocess.run(['docker','rm','-f',name],check=True,capture_output=True)
 subprocess.run(['docker','volume','rm',volume],check=True,capture_output=True)
 subprocess.run(['docker','network','rm',network],check=True,capture_output=True)
 for tag in tags:subprocess.run(['docker','image','rm',tag],check=True,capture_output=True)
