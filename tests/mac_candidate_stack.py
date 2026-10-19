"""Isolated synthetic candidate stack; never reads original env files or data volumes.

Requires a built candidate frontend image, reviewed dependency backend image,
cached offline model, Docker Compose, requests, and PyMuPDF. Does not install on a Mac.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,os,random,secrets,shutil,subprocess,sys,tempfile,time
from pathlib import Path
import fitz,requests
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get('DOCLENS_CANDIDATE_EVIDENCE', tempfile.mkdtemp(prefix='doclens-mac-candidate-evidence-'))).resolve();OUT.mkdir(parents=True,exist_ok=True)
PRIVATE=Path(tempfile.mkdtemp(prefix='doclens-mac-candidate-private-'));PRIVATE.chmod(0o700)
PROJECT='doclens-ui-candidate-'+secrets.token_hex(5)
DOCKER=['docker','--host=unix:///var/run/docker.sock']
HTTP=requests.Session();HTTP.trust_env=False # loopback test requests only
results={'project':PROJECT,'data':'synthetic-only','tests':{},'private_inputs_exported':False}

def run(*args):return subprocess.check_output(DOCKER+list(args),text=True,stderr=subprocess.PIPE).strip()
def save(): (OUT/'stack-results.json').write_text(json.dumps(results,indent=2)+'\n')
def inventory():return {'containers':run('ps','-a','--format','{{.ID}} {{.Names}}').splitlines(),'volumes':run('volume','ls','--format','{{.Name}}').splitlines()}
def ready(url):
 deadline=time.monotonic()+120
 while time.monotonic()<deadline:
  try:
   if HTTP.get(url,timeout=2).status_code==200:return
  except requests.RequestException:pass
  time.sleep(.2) # condition-based readiness polling, not an application deadline increase
 raise RuntimeError('Fixture readiness failed; inspect component logs')
def pdf(count=2):
 with fitz.open() as doc:
  for n in range(count):doc.new_page().insert_text((30,40),f'Synthetic candidate source evidence, page {n+1}.')
  return doc.tobytes()

def dense_pdf():
 rng=random.Random(320127)
 with fitz.open() as doc:
  for n in range(32):
   page=doc.new_page();text='\n'.join((f'Page {n+1} clause {i}. '+'Synthetic contract evidence and obligations. '*4)[:120] for i in range(45));page.insert_text((24,24),text,fontsize=5)
   page.insert_image(fitz.Rect(24,400,384,766),pixmap=fitz.Pixmap(fitz.csRGB,360,366,rng.randbytes(360*366*3),False))
  return doc.tobytes(deflate=False)

before=inventory();compose=None
assert not run('ps','-a','--filter','label=com.docker.compose.project='+PROJECT,'--format','{{.ID}}'), 'Refuse existing candidate project'
assert not run('network','ls','--filter','label=com.docker.compose.project='+PROJECT,'--format','{{.ID}}'), 'Refuse existing candidate network'
assert PROJECT+'_candidate_qdrant' not in before['volumes'], 'Refuse existing volume'
try:
 backend_image=run('image','inspect',os.environ.get('DOCLENS_CANDIDATE_BACKEND_IMAGE','doclens-mac-upload-freeze:review'),'--format','{{.Id}}')
 frontend_image=run('image','inspect',os.environ.get('DOCLENS_CANDIDATE_FRONTEND_IMAGE','doclens-mac-ui-candidate:review'),'--format','{{.Id}}')
 source=PRIVATE/'backend';source.mkdir()
 for name in subprocess.check_output(['git','ls-files','backend'],cwd=ROOT,text=True).splitlines():
  relative=Path(name).relative_to('backend')
  if relative.name.startswith('.env'):continue
  destination=source/relative;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,destination)
 password=secrets.token_urlsafe(24);secret=secrets.token_urlsafe(40)
 hashed=subprocess.check_output(['node','-e',"process.stdout.write(require('bcryptjs').hashSync(process.env.DOCLENS_TEST_PASSWORD,4))"],cwd=ROOT/'frontend',env={**os.environ,'DOCLENS_TEST_PASSWORD':password},text=True)
 runtime=PRIVATE/'synthetic.env';runtime.write_text(f'DOCLENS_SESSION_SECRET={secret}\nDOCLENS_ADMIN_EMAIL=candidate@synthetic.invalid\nDOCLENS_ADMIN_PASSWORD_HASH={hashed}\nGEMINI_API_KEY=synthetic-not-a-provider-credential\n');runtime.chmod(0o600)
 model=(Path(os.environ.get('HF_HOME','/workspace/.cache/huggingface'))/'hub/models--sentence-transformers--all-MiniLM-L6-v2').resolve();assert model.is_dir(),'Cached offline model required'
 assert not any((model/name).exists() for name in ['token','stored_tokens']), 'Refuse credential-bearing cache path'
 storage=PRIVATE/'qdrant-data';snapshots=PRIVATE/'qdrant-snapshots';storage.mkdir(mode=0o700);snapshots.mkdir(mode=0o700);assert not any(storage.iterdir()) and not any(snapshots.iterdir())
 control=PRIVATE/'control.env';control.write_text(f'CANDIDATE_BACKEND_IMAGE={backend_image}\nCANDIDATE_FRONTEND_IMAGE={frontend_image}\nCANDIDATE_BACKEND_SOURCE={source}\nCANDIDATE_MODEL_CACHE={model}\nCANDIDATE_RUNTIME_ENV={runtime}\nCANDIDATE_QDRANT_DATA={storage}\nCANDIDATE_QDRANT_SNAPSHOTS={snapshots}\nCANDIDATE_UID={os.getuid()}\nCANDIDATE_GID={os.getgid()}\n');control.chmod(0o600)
 compose=DOCKER+['compose','--env-file',str(control),'-p',PROJECT,'-f',str(ROOT/'recovery/mac-ui-candidate/compose.yml')]
 def dc(*args):return subprocess.check_output(compose+list(args),text=True,stderr=subprocess.PIPE).strip()
 dc('up','-d','--no-build','--pull','never')
 endpoints={service:'http://127.0.0.1:'+dc('port',service,str(port)).rsplit(':',1)[1] for service,port in [('frontend',3000),('backend',8000),('qdrant',6333)]}
 ids={service:dc('ps','-q',service) for service in endpoints}
 ready(endpoints['qdrant']+'/readyz');ready(endpoints['backend']+'/');ready(endpoints['frontend']+'/')
 resources={}
 for service,cid in ids.items():
  obj=json.loads(run('inspect',cid))[0];resources[service]={'memory_bytes':obj['HostConfig']['Memory'],'swap_total_bytes':obj['HostConfig']['MemorySwap'],'nano_cpus':obj['HostConfig']['NanoCpus'],'ports':obj['NetworkSettings']['Ports'],'mounts':[{'type':m['Type'],'destination':m['Destination'],'rw':m['RW'],'name':m.get('Name')} for m in obj['Mounts']]}
  assert obj['Config']['Labels']['com.docker.compose.project']==PROJECT
 assert resources['backend']['memory_bytes']==1536*1024**2 and resources['backend']['swap_total_bytes']==1536*1024**2 and resources['backend']['nano_cpus']==2_000_000_000
 assert resources['frontend']['memory_bytes']==512*1024**2 and resources['frontend']['swap_total_bytes']==512*1024**2
 assert all(m['type']=='bind' for m in resources['qdrant']['mounts'])
 assert storage.parent==PRIVATE and snapshots.parent==PRIVATE
 assert all(not m['rw'] for m in resources['backend']['mounts'])
 results.update(images={'frontend':frontend_image,'backend_dependencies':backend_image},resources=resources,endpoints=endpoints,storage='fresh empty temporary directories; no original or Docker named volumes mounted')
 f=endpoints['frontend'];b=endpoints['backend'];q=endpoints['qdrant']
 assert HTTP.post(f+'/api/documents/process',files={'file':('denied.pdf',pdf(),'application/pdf')},timeout=5).status_code==401
 login=HTTP.post(f+'/api/auth/login',json={'email':'candidate@synthetic.invalid','password':password},timeout=10);assert login.status_code==200,f'Frontend login HTTP{login.status_code}'
 cookie=login.cookies['doclens_session'];headers={'Cookie':'doclens_session='+cookie}
 data=pdf();name='preservation-candidate.pdf'
 response=HTTP.post(f+'/api/documents/process',headers=headers,files={'file':(name,data,'application/pdf')},timeout=110);assert response.status_code==200 and response.json()['total_chunks']==2, f'Initial upload HTTP{response.status_code}'
 def points():
  r=HTTP.post(q+'/collections/document_chunks/points/scroll',json={'limit':1000,'with_payload':True,'with_vector':True},timeout=10);r.raise_for_status();return r.json()['result']['points']
 old=points();assert len(old)==2 and {p['payload']['page_number'] for p in old}=={1,2} and all(len(p['vector'])==384 for p in old)
 old_ids={p['id'] for p in old};identity={(p['payload']['document_name'],p['payload']['page_number'],p['payload']['chunk_id']) for p in old}
 for label,bad,expected in [('invalid replacement',b'not PDF',400),('page limit',pdf(301),413)]:
  r=HTTP.post(f+'/api/documents/process',headers=headers,files={'file':(name,bad,'application/pdf')},timeout=10);assert r.status_code==expected,(label,r.status_code)
  assert {p['id'] for p in points()}==old_ids
  results['tests'][label]={'status':r.status_code,'old_point_ids_preserved':True}
 dense=dense_pdf();begin=time.monotonic();latencies=[];timeouts=0
 with ThreadPoolExecutor() as pool:
  future=pool.submit(HTTP.post,f+'/api/documents/process',headers=headers,files={'file':('dense-candidate.pdf',dense,'application/pdf')},timeout=115)
  while not future.done():
   start=time.monotonic()
   try:HTTP.get(b+'/',timeout=.35).raise_for_status();latencies.append(time.monotonic()-start)
   except requests.RequestException:timeouts+=1
   time.sleep(.1)
  r=future.result()
 assert r.status_code==200 and r.json()['total_chunks']==224,(r.status_code,r.text[:100]);assert timeouts==0,timeouts
 results['tests']['dense PDF']={'bytes':len(dense),'pages':32,'sha256':hashlib.sha256(dense).hexdigest(),'chunks':224,'seconds':time.monotonic()-begin,'health_successes':len(latencies),'health_timeouts':timeouts,'health_max_seconds':max(latencies,default=None)}
 fixture=PRIVATE/'browser-candidate.pdf';fixture.write_bytes(data)
 browser_config={'origin':f,'cookie':cookie,'pdf':str(fixture),'screenshot':str(OUT/'container-browser.png')}
 probe=subprocess.run(['node','tests/mac_candidate_container_browser.cjs'],cwd=ROOT,input=json.dumps(browser_config),text=True,capture_output=True)
 (OUT/'container-browser.log').write_text(probe.stdout+probe.stderr);assert probe.returncode==0,'Container browser smoke failed; inspect its log'
 all_points=points();before_restart={p['id'] for p in all_points};catalog=HTTP.post(q+'/collections/doclens_document_publications/points/scroll',json={'limit':1000,'with_payload':True},timeout=10).json()['result']['points']
 save()
 dc('restart','backend','frontend','qdrant')
 endpoints={service:'http://127.0.0.1:'+dc('port',service,str(port)).rsplit(':',1)[1] for service,port in [('frontend',3000),('backend',8000),('qdrant',6333)]}
 f=endpoints['frontend'];b=endpoints['backend'];q=endpoints['qdrant'];results['restart_endpoints']=endpoints
 ready(q+'/readyz');ready(b+'/');ready(f+'/')
 after_points=points();assert {p['id'] for p in after_points}==before_restart
 assert {(p['payload']['document_name'],p['payload']['page_number'],p['payload']['chunk_id']) for p in after_points if p['id'] in old_ids}==identity
 assert HTTP.post(q+'/collections/doclens_document_publications/points/scroll',json={'limit':1000,'with_payload':True},timeout=10).json()['result']['points']==catalog
 results['tests']['restart']={'all_point_ids_preserved':True,'original_citation_identity_preserved':True,'publication_catalog_preserved':True}
 results['tests']['authentication']={'anonymous_upload':401,'synthetic_login':200}
 print(json.dumps(results),flush=True);save()
finally:
 if compose:
  for service in ['frontend','backend','qdrant']:
   logs=subprocess.run(compose+['logs','--no-color',service],text=True,capture_output=True);(OUT/(service+'.log')).write_text(logs.stdout+logs.stderr)
  subprocess.run(compose+['down','--volumes','--remove-orphans'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
 after=inventory();results['original_local_containers_unchanged']=set(before['containers'])==set(after['containers']);results['original_local_volume_names_unchanged']=set(before['volumes'])==set(after['volumes']);save()
 assert results['original_local_containers_unchanged'] and results['original_local_volume_names_unchanged']
 # Only this runner's generated private files are removed; no user files or volumes.
 shutil.rmtree(PRIVATE)
