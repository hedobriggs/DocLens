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
  for(const kind of ['question-401','question-clock']){
   const result={scenario:kind,status:'RUNNING'},isQuestion=kind.startsWith('question');let page,pending;
   try{
    context=await browser.newContext({viewport:{width:1280,height:800}});page=await context.newPage();
    const netlog=[];page.on('response',r=>{const u=new URL(r.url());if(u.pathname.startsWith('/api/'))netlog.push({path:u.pathname,status:r.status(),contentType:r.headers()['content-type'],method:r.request().method(),timing:r.request().timing()});save(kind+'-network.json',netlog);});
    await login(page,doc);await page.waitForURL('**/dashboard');
    if(kind.endsWith('clock')){await page.clock.install();const original=(await context.cookies(doc)).find(c=>c.name==='doclens_session');if(!original)throw Error('Session cookie missing');tokens.add(original.value);await context.addCookies([{...original,value:token(60)}]);await page.reload();await page.waitForURL('**/dashboard');}
    await expect(page.getByRole('button',{name:'Choose PDF',exact:true})).toBeEnabled();
    result.seed=await upload(page);const before=records();save(kind+'-before-records.json',before);
    let seen;const intercepted=new Promise(r=>{seen=r;});const target=isQuestion?'**/api/ask':'**/api/documents/process';
    await page.route(target,route=>{pending=route;seen();});
    const question='Which organization employed Alex?';
    if(isQuestion){await page.getByRole('textbox').fill(question);await page.getByRole('button',{name:'Send question',exact:true}).click();}else await page.locator('input[type=file]').setInputFiles(fixture);
    await Promise.race([intercepted,page.waitForEvent('close').then(()=>{throw Error('Page closed before request interception');})]);
    await expect(page.getByRole('button',{name:isQuestion?'Stop generating':'Cancel upload',exact:true})).toBeVisible();await page.screenshot({path:path.join(out,kind+'-busy.png'),fullPage:true});
    if(kind.endsWith('401')){const expired=token(-60);const r=page.waitForResponse(r=>new URL(r.url()).pathname===(isQuestion?'/api/ask':'/api/documents/process'));const original=(await context.cookies(doc)).find(c=>c.name==='doclens_session');if(!original)throw Error('Missing cookie before expiry injection');await context.addCookies([{...original,value:expired}]);if((await context.cookies(doc)).find(c=>c.name==='doclens_session')?.value!==expired)throw Error('Expired browser cookie not installed');await pending.continue();if((await r).status()!==401)throw Error('Baked auth did not reject expired signed JWT');result.expiry='Real baked frontend 401; request forwarded with expired signed synthetic JWT';}
    else{await page.clock.fastForward(61000);result.expiry='Deterministic client timer from server-verified 60s signed JWT; browser clock only';}
    const signIn=page.locator('.legal-session-control').getByRole('link',{name:'Sign in',exact:true});
    await expect(signIn).toBeVisible();await expect(page.getByRole('button',{name:'Log out',exact:true})).toHaveCount(0);await expect(page.getByRole('alert').getByRole('link',{name:'Sign in',exact:true})).toBeVisible();
    await expect(page.getByRole('button',{name:'Cancel upload',exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'Stop generating',exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'Send question',exact:true})).toBeDisabled();await expect(page.getByRole('button',{name:'+ Upload PDF',exact:true})).toBeDisabled();
    if(isQuestion)await expect(page.getByRole('textbox')).toHaveValue(question);
    const after=records();save(kind+'-after-expiry-records.json',after);if(before!==after)throw Error('Expired/aborted request changed published records');result.expiryPreservedRecords=true;
    await page.screenshot({path:path.join(out,kind+'-expired.png'),fullPage:true});
    if(kind.endsWith('clock'))await pending.abort().catch(e=>{result.pendingAbort='Request already cancelled: '+clean(e.message);});await page.unroute(target);
    await signIn.focus();await page.keyboard.press('Enter');await expect(page.getByLabel('Email',{exact:true})).toBeVisible();
    await page.getByLabel('Email',{exact:true}).fill(email);await page.getByLabel('Password',{exact:true}).fill(password);const auth=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/auth/login'&&r.request().method()==='POST');await page.getByRole('button',{name:'Sign in',exact:true}).click();if((await auth).status()!==200)throw Error('Recovery login failed');await page.waitForURL('**/dashboard');
    result.recoveryUpload=await upload(page);
    if(isQuestion){const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/ask'&&r.request().method()==='POST',{timeout:150000});await page.getByRole('textbox').fill(question);await page.getByRole('button',{name:'Send question',exact:true}).click();const r=await response;const text=await r.text();save(kind+'-recovery-question-response.txt',text);if(r.status()!==200)throw Error('Recovery question status '+r.status());const body=JSON.parse(text);if(!body.answer?.includes('Aster')||!body.citations?.some(c=>c.page_number===1))throw Error('Recovery live answer/citation mismatch');await expect(page.getByRole('button',{name:'Stop generating',exact:true})).toHaveCount(0,{timeout:150000});await expect(page.getByRole('textbox')).toHaveValue('');await expect(page.getByRole('button',{name:'Send question',exact:true})).toBeDisabled();await expect(page.getByText(body.answer,{exact:true})).toBeVisible({timeout:150000});save(kind+'-recovery-dom.html',await page.content());await expect(page.locator('details.legal-citation > summary').filter({hasText:'synthetic-focus.pdf'}).filter({hasText:/Page\s+1/})).toBeVisible();await page.getByRole('textbox').fill('Another synthetic question');await expect(page.getByRole('button',{name:'Send question',exact:true})).toBeEnabled();await page.getByRole('textbox').fill('');result.recoveryQuestion={status:200,answer:body.answer,citations:body.citations};}
    await page.screenshot({path:path.join(out,kind+'-reauthenticated.png'),fullPage:true});save(kind+'-network.json',netlog);result.status='PASS';
   }catch(e){result.status='FAIL';result.error=clean(e.stack||e);if(page&&!page.isClosed()){save(kind+'-failure-dom.html',await page.content());}if(page&&!page.isClosed())await page.screenshot({path:path.join(out,kind+'-failure.png'),fullPage:true}).catch(()=>{});}
   finally{results.scenarios.push(result);save('results.json',results);if(context)await context.close();context=null;}
  }
  // New context, real clock: observe data AFTER reload and each panel's rendering.
  try{
   context=await browser.newContext({viewport:{width:1280,height:800}});const page=await context.newPage(),responses=[],reads=[];let phase='initial';
   page.on('response',r=>{if(new URL(r.url()).pathname.endsWith('/api/ds/query')){const epoch=phase;const p=r.json().then(body=>{responses.push({status:r.status(),body});save('grafana-'+epoch+'-query-responses.json',responses);}).catch(e=>{responses.push({error:clean(e.message)});save('grafana-'+epoch+'-query-responses.json',responses);});reads.push(p);}});
   await login(page,grafana);await expect(page.getByText('DocLens Operations',{exact:true}).first()).toBeVisible({timeout:90000});
   // Synchronize first load before defining the post-reload evidence epoch.
   await expect(page.getByText('qdrant',{exact:true}).first()).toBeVisible({timeout:90000});await Promise.all(reads);responses.length=0;reads.length=0;phase='post-reload';
   await page.reload();await expect(page.getByText('DocLens Operations',{exact:true}).first()).toBeVisible({timeout:90000});await expect(page.getByText('qdrant',{exact:true}).first()).toBeVisible({timeout:90000});await expect(page.getByText('doclens',{exact:true}).first()).toBeVisible({timeout:90000});
   const model=await page.evaluate(async()=>{const r=await fetch('/monitoring/api/dashboards/uid/doclens');if(!r.ok)throw Error('Dashboard API '+r.status);return r.json();});save('grafana-dashboard-model.json',model);
   const panels=[];
   for(const p of model.dashboard.panels){// Resolve against the live DOM, not a guessed accessible-name suffix.
    await expect.poll(async()=>page.evaluate(({title,id})=>{
     const titles=[...document.querySelectorAll('*')].filter(n=>n.textContent.trim()===title&&![...n.children].some(c=>c.textContent.trim()===title));
     if(titles.length!==1)return 'title matches '+titles.length;
     for(let n=titles[0].parentElement;n&&n!==document.body;n=n.parentElement){
      const contents=[...n.querySelectorAll('[data-testid]')].filter(c=>/panel content/i.test(c.getAttribute('data-testid')));
      if(contents.length===1){n.setAttribute('data-focus-panel',String(id));contents[0].setAttribute('data-focus-content',String(id));return 'unique panel';}
      if(contents.length>1)return 'ambiguous panel content';
     }return 'panel content not yet present';
    },{title:p.title,id:p.id}),{timeout:90000}).toBe('unique panel');
    const panel=page.locator('[data-focus-panel="'+p.id+'"]');await expect(panel).toHaveCount(1);save('grafana-panel-'+p.id+'-dom.html',await panel.evaluate(n=>n.outerHTML));await panel.scrollIntoViewIfNeeded();await expect(panel).toBeVisible();await expect(panel.getByLabel('Panel loading bar',{exact:true}).or(panel.getByTestId('Panel loading bar')).first()).toBeHidden({timeout:90000});
    const content=panel.locator('[data-focus-content="'+p.id+'"]');await expect(content).toBeVisible({timeout:90000});
    await expect.poll(async()=>{if((await content.innerText()).includes('No data'))return false;if(p.type==='stat')return (await content.innerText()).includes('qdrant');return content.locator('canvas').evaluateAll(nodes=>nodes.some(n=>n.width>0&&n.height>0));},{timeout:90000}).toBe(true);
    await expect(page.getByRole('button',{name:'Cancel',exact:true})).toHaveCount(0,{timeout:90000});await panel.screenshot({path:path.join(out,'grafana-panel-'+p.id+'.png')});panels.push({id:p.id,title:p.title,type:p.type,text:await content.innerText(),visibleCanvasCount:await content.locator('canvas').count()});}
   await Promise.all(reads);if(!responses.length||responses.some(x=>x.error||x.status!==200||Object.values(x.body.results||{}).some(v=>v.error)))throw Error('Grafana query response failure');
   if(!responses.some(x=>Object.values(x.body.results||{}).some(v=>(v.frames||[]).some(f=>(f.data?.values||[]).some(a=>Array.isArray(a)&&a.length)))))throw Error('No Grafana data frames after reload');
   save('grafana-post-reload-query-responses.json',responses);save('grafana-panels.json',panels);results.monitoring.grafana={status:'PASS',panels:panels.length,conditions:'Post-reload qdrant/doclens visible; per-panel loading hidden; nonempty stat or visible canvas; no No data; actual query frames.'};
  }catch(e){results.monitoring.grafana={status:'FAIL',error:clean(e.stack||e)};if(context){const p=context.pages()[0];if(p){save('grafana-failure-dom.html',await p.content());await p.screenshot({path:path.join(out,'grafana-failure.png'),fullPage:true}).catch(()=>{});}}}
  finally{save('results.json',results);if(context)await context.close();context=null;}
  results.monitoring.prometheus={status:'PREVIOUSLY_PASSED',evidence:'focus.66Jlsq.zip; not rerun'};
 }catch(e){results.blocked=clean(e.stack||e);}
 finally{
  if(context)await context.close().catch(()=>{});if(browser)await browser.close().catch(()=>{});
  if(containerCreated){try{if(docker('inspect','--format','{{ index .Config.Labels "doclens.acceptance.run" }}',name)!==runId)throw Error('Container ownership mismatch; not removed');save('container.log',docker('logs',name));docker('rm','-f',name);}catch(e){results.cleanupContainer=clean(e.message);}}
  if(volumeCreated){try{if(docker('volume','inspect','--format','{{ index .Labels "doclens.acceptance.run" }}',volume)!==runId)throw Error('Volume ownership mismatch; not removed');docker('volume','rm',volume);}catch(e){results.cleanupVolume=clean(e.message);}}
  save('results.json',results);console.log(clean(JSON.stringify({scenarios:results.scenarios.map(x=>({scenario:x.scenario,status:x.status})),monitoring:results.monitoring,blocked:results.blocked},null,2)));
 }
 process.exitCode=results.blocked||results.cleanupContainer||results.cleanupVolume||results.scenarios.length!==2||results.scenarios.some(x=>x.status!=='PASS')||results.monitoring.grafana?.status!=='PASS'||results.monitoring.prometheus?.status!=='PREVIOUSLY_PASSED'?1:0;
}
module.exports={tokenFor};if(require.main===module)main().catch(e=>{console.error(clean(e.stack||e));process.exitCode=1;});
