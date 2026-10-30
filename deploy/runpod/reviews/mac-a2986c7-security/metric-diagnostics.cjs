// Host-only focused tests against the unchanged baked image. No response stubs.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto'),net=require('node:net');
const {execFileSync}=require('node:child_process');
const {createRequire}=require('node:module');
const IMAGE='sha256:4e3a0339cb5e1465701f757ca136039c369ab96fa672401a938e3efa0e5467d8';
const out=process.env.DOCLENS_FOCUS_OUT,source=process.env.DOCLENS_FOCUS_SOURCE,key=process.env.GEMINI_API_KEY;
const email='trial@synthetic.invalid',password='Synthetic-$literal-Password-2026';
let secret='',browser,containerCreated=false,volumeCreated=false;
const runId=crypto.randomBytes(16).toString('hex'),name='doclens-focus-'+runId,volume=name+'-data';
const tokens=new Set(),commands=[],results={image:IMAGE,scenarios:[],monitoring:{},orchestration:'Requests are held BEFORE dispatch, then genuinely rejected by baked auth or aborted by client timer. No response stubs; not a test of cancellation after backend admission.'};
function clean(s){let text=String(s);for(const v of [key,secret,...tokens])if(v)text=text.split(v).join('[REDACTED]');return text.replace(/[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{20,}/g,'[REDACTED_JWT]');}
function save(file,value){fs.writeFileSync(path.join(out,file),clean(typeof value==='string'?value:JSON.stringify(value,null,2)));}
function docker(...args){commands.push(args);save('docker-commands.json',commands);return execFileSync('docker',args,{encoding:'utf8',timeout:60000,stdio:['ignore','pipe','pipe']}).trim();}
function tokenFor(s,seconds){const enc=x=>Buffer.from(JSON.stringify(x)).toString('base64url');const n=Math.floor(Date.now()/1000);const unsigned=enc({alg:'HS256',typ:'JWT'})+'.'+enc({role:'admin',iss:'doclens',aud:'doclens-frontend',iat:n,exp:n+seconds});return unsigned+'.'+crypto.createHmac('sha256',s).update(unsigned).digest('base64url');}
function token(seconds){const t=tokenFor(secret,seconds);tokens.add(t);return t;}
function records(){return docker('exec',name,'python','-c',`import json,urllib.request;o=urllib.request.build_opener(urllib.request.ProxyHandler({}));out={}\nfor c in ['document_chunks','doclens_document_publications']:\n r=o.open(urllib.request.Request('http://127.0.0.1:6333/collections/'+c+'/points/scroll',data=b'{"limit":1000,"with_payload":true}',headers={'Content-Type':'application/json'}));out[c]=sorted(json.load(r)['result']['points'],key=lambda p:str(p['id']))\nprint(json.dumps(out,sort_keys=True))`);}
async function unusedPort(){const server=net.createServer();await new Promise((r,j)=>{server.once('error',j);server.listen(0,'127.0.0.1',r);});const p=server.address().port;await new Promise(r=>server.close(r));return p;}
function monitoringCollector(page,saveRecord){
 const epochs={initial:[], 'post-reload':[]},requests=new Map(),pending=new Set();let epoch='initial',sequence=0;
 const persist=e=>saveRecord('grafana-'+e+'-query-responses.json',epochs[e]);
 page.on('request',request=>{if(!new URL(request.url()).pathname.endsWith('/api/ds/query'))return;const record={id:'query-'+(++sequence),epoch,url:request.url(),method:request.method(),startedAt:new Date().toISOString(),timing:request.timing(),requestBody:request.postData(),state:'requested'};epochs[epoch].push(record);requests.set(request,record);persist(epoch);});
 page.on('response',response=>{const request=response.request(),record=requests.get(request);if(!record)return;record.status=response.status();record.responseAt=new Date().toISOString();record.timing=request.timing();record.state='reading';persist(record.epoch);
 const read=response.json().then(body=>{record.body=body;record.state='complete';}).catch(error=>{record.error=String(error.message);record.state='collection-error';}).finally(()=>{record.timing=request.timing();pending.delete(read);persist(record.epoch);});pending.add(read);
 });
 page.on('requestfinished',request=>{const r=requests.get(request);if(r){r.finished=true;r.timing=request.timing();persist(r.epoch);}});
 page.on('requestfailed',request=>{const r=requests.get(request);if(r){r.finished=true;r.requestFailure=request.failure();r.state='request-failed';persist(r.epoch);}});
 return {epochs,async drain(expect){await expect.poll(()=>pending.size+Object.values(epochs).flat().filter(r=>!r.finished).length,{timeout:90000}).toBe(0);},next(){epoch='post-reload';}};
}
async function main(){
 const req=createRequire(path.join(source,'frontend/package.json')),{chromium}=req('playwright'),{expect}=req('@playwright/test');
 const fixture={name:'synthetic-focus.pdf',mimeType:'application/pdf',buffer:fs.readFileSync(process.env.DOCLENS_FOCUS_PDF)};
 let context;
 async function login(page,base){await page.goto(base+'/');await expect(page.getByLabel('Email',{exact:true})).toBeVisible();await page.getByLabel('Email',{exact:true}).fill(email);await page.getByLabel('Password',{exact:true}).fill(password);const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/auth/login'&&r.request().method()==='POST');await page.getByRole('button',{name:'Sign in',exact:true}).click();if((await response).status()!==200)throw Error('Real form login failed');}
 async function upload(page){const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/documents/process'&&r.request().method()==='POST',{timeout:150000});await page.locator('input[type=file]').setInputFiles(fixture);const r=await response;const text=await r.text();save('upload-response-'+Date.now()+'-'+crypto.randomBytes(3).toString('hex')+'.txt',text);if(r.status()!==200)throw Error('Real upload status '+r.status());const body=JSON.parse(text);if(body.indexed!==true)throw Error('Real upload not indexed');await expect(page.getByRole('status')).toContainText('ready for questions',{timeout:150000});return {status:r.status(),pages:body.total_pages,chunks:body.total_chunks};}
 try{
  docker('volume','create','--label','doclens.acceptance.run='+runId,volume);
  if(docker('volume','inspect','--format','{{ index .Labels "doclens.acceptance.run" }}',volume)!==runId)throw Error('Volume ownership label mismatch; refusing attachment');
  volumeCreated=true;
  const port=await unusedPort(),doc='http://doclens.localhost:'+port;
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'DocLens-focus-secret-'));fs.chmodSync(temp,0o700);const envFile=path.join(temp,'secrets.env');
  try{fs.writeFileSync(envFile,`DOCLENS_ADMIN_EMAIL=${email}\nDOCLENS_ADMIN_PASSWORD=${password}\nGEMINI_API_KEY=${key}\n`,{mode:0o600});containerCreated=true;docker('run','-d','--name',name,'--label','doclens.acceptance.run='+runId,'--cpus','2','--memory','4g','--memory-swap','4g','--env-file',envFile,'-e','DOCLENS_PUBLIC_ORIGIN='+doc,'-v',volume+':/workspace','-p','127.0.0.1:'+port+':3000','-p','127.0.0.1::3001','-p','127.0.0.1::9090',IMAGE);}finally{fs.rmSync(temp,{recursive:true,force:true});}
  await expect.poll(()=>{const state=JSON.parse(docker('inspect','--format','{{json .State}}',name));if(!state.Running)throw Error('Fresh trial exited during startup');return state.Health?.Status;},{timeout:240000,intervals:[500,1000]}).toBe('healthy');
  secret=JSON.parse(docker('exec','--user','1000:1000',name,'python','-c',"from pathlib import Path;print(Path('/config/frontend/settings.json').read_text())")).DOCLENS_SESSION_SECRET;
  if(typeof secret!=='string'||secret.length<32)throw Error('Synthetic trial signing key unavailable');
  const grafana='http://grafana.localhost:'+docker('port',name,'3001/tcp').split(':').pop(),prom='http://prometheus.localhost:'+docker('port',name,'9090/tcp').split(':').pop();
  browser=await chromium.launch({executablePath:chromium.executablePath(),args:['--host-resolver-rules=MAP doclens.localhost 127.0.0.1, MAP grafana.localhost 127.0.0.1, MAP prometheus.localhost 127.0.0.1']});
  results.browserVersion=browser.version();results.urls={doc,grafana,prom};
  // Seed one genuine failed auth event for the failed-login metric, not a fake series.
  context=await browser.newContext();let seed=await context.newPage();await seed.goto(doc+'/');const negative=await seed.evaluate(async()=>{const r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'trial@synthetic.invalid',password:'wrong-synthetic'})});return r.status;});if(negative!==401)throw Error('Negative auth seed expected 401');await context.close();context=null;
  // Upload-only diagnostics; no Gemini call or accepted recovery tests.
  function probe(label, queries){
   const code=`import json,urllib.request,urllib.parse,time
o=urllib.request.build_opener(urllib.request.ProxyHandler({}));out={'at':time.time(),'queries':{}}
def get(url):
 try:
  r=o.open(url,timeout=10);b=r.read().decode();return {'status':r.status,'body':b}
 except Exception as e:return {'error':type(e).__name__+': '+str(e)}
out['metrics']=get('http://127.0.0.1:8000/metrics')
out['targets']=get('http://127.0.0.1:19090/api/v1/targets')
for name,q in json.loads(${JSON.stringify(JSON.stringify(queries))}).items():
 out['queries'][name]=get('http://127.0.0.1:19090/api/v1/query?'+urllib.parse.urlencode({'query':q}))
print(json.dumps(out))`;
   const data=JSON.parse(docker('exec',name,'python','-c',code));save(label+'.json',data);return data;
  }
  const queries={
   allRequests:'http_requests_total{job="doclens"}',
   uploadCounter:'http_requests_total{job="doclens",handler="/documents/process"}',
   uploadRaw:'http_requests_total{job="doclens",handler="/documents/process"}[5m]',
   uploadDurationRaw:'http_request_duration_seconds_bucket{job="doclens",handler="/documents/process"}[5m]',
   sampleCount:'count_over_time(http_requests_total{job="doclens",handler="/documents/process"}[1m])',
   panel3:'sum by (status) (rate(http_requests_total{job="doclens",handler="/documents/process"}[1m]))',
   panel4:'histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{job="doclens",handler="/documents/process"}[1m])))',
   scrapeUp:'up{job="doclens"}',scrapeTimestamp:'timestamp(up{job="doclens"})'
  };
  save('baked-monitoring-config.json',JSON.parse(docker('exec',name,'python','-c',"import json,pathlib,importlib.metadata; print(json.dumps({'files':{p:pathlib.Path(p).read_text() for p in ['/opt/monitoring/prometheus.yml','/opt/monitoring/dashboards/doclens.json','/run/doclens-monitoring/dashboards/doclens.json']},'instrumentator_version':importlib.metadata.version('prometheus-fastapi-instrumentator')}))")));
  probe('metrics-before-upload',queries);
  context=await browser.newContext();seed=await context.newPage();await login(seed,doc);await seed.waitForURL('**/dashboard');const began=new Date().toISOString();const uploaded=await upload(seed);save('diagnostic-upload.json',{began,completed:new Date().toISOString(),...uploaded});await context.close();context=null;
  probe('metrics-after-upload',queries);
  let attempt=0;
  try{await expect.poll(()=>{const data=probe('sample-poll-'+(++attempt),{sampleCount:queries.sampleCount,panel3:queries.panel3,panel4:queries.panel4});return ['panel3','panel4'].every(n=>{try{const b=JSON.parse(data.queries[n].body);return b.status==='success'&&b.data.result.some(x=>Number.isFinite(Number(x.value?.[1])));}catch{return false;}});},{timeout:90000,intervals:[1000,2000,5000]}).toBe(true);results.diagnosticReadiness='finite panel3 and panel4 values observed';}catch(e){results.diagnosticReadiness='not observed within bounded condition polling';results.readinessError=clean(e.message);}
  probe('metrics-final',queries);results.diagnostics={status:'COLLECTED',scope:'Upload metrics, actual Prometheus targets, raw timestamped samples, exact expanded panel queries. No Grafana or question acceptance rerun.'};
 }catch(e){results.blocked=clean(e.stack||e);}
 finally{
  if(context)await context.close().catch(()=>{});if(browser)await browser.close().catch(()=>{});
  if(containerCreated){try{if(docker('inspect','--format','{{ index .Config.Labels "doclens.acceptance.run" }}',name)!==runId)throw Error('Container ownership mismatch; not removed');save('container.log',docker('logs',name));docker('rm','-f',name);}catch(e){results.cleanupContainer=clean(e.message);}}
  if(volumeCreated){try{if(docker('volume','inspect','--format','{{ index .Labels "doclens.acceptance.run" }}',volume)!==runId)throw Error('Volume ownership mismatch; not removed');docker('volume','rm',volume);}catch(e){results.cleanupVolume=clean(e.message);}}
  save('results.json',results);console.log(clean(JSON.stringify({scenarios:results.scenarios.map(x=>({scenario:x.scenario,status:x.status})),monitoring:results.monitoring,blocked:results.blocked,diagnostics:results.diagnostics,readiness:results.diagnosticReadiness},null,2)));
 }
 process.exitCode=results.blocked||results.cleanupContainer||results.cleanupVolume||results.diagnostics?.status!=='COLLECTED'?1:0;
}
module.exports={tokenFor,monitoringCollector};if(require.main===module)main().catch(e=>{console.error(clean(e.stack||e));process.exitCode=1;});
