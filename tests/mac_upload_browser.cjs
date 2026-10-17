// Real built Next routes/browser state; controlled backend failures and virtual
// browser time are explicit. The fixed gateway deadline uses real wall time.
const fs=require('node:fs');const path=require('node:path');const http=require('node:http');
const {spawn}=require('node:child_process');const {createRequire}=require('node:module');const crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');const frontRequire=createRequire(path.join(root,'frontend/package.json'));
const {chromium}=frontRequire('playwright');const {expect}=frontRequire('@playwright/test');
const mode=process.argv[2]||'fixed';const frontend=path.resolve(process.argv[3]||path.join(root,'frontend'));
const out=path.resolve(process.argv[4]||'/tmp/doclens-browser-evidence');fs.mkdirSync(out,{recursive:true});
const results={mode};const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let behavior='success',closed=false;let child,browser;const intervals=new Set();
const server=http.createServer((req,res)=>{
 if(req.url==='/internal/auth-event'){req.resume();res.end('{}');return;}
 let total=0;req.on('data',chunk=>{total+=chunk.length;if(behavior==='slow'){req.pause();setTimeout(()=>req.resume(),10);}});
 req.on('end',()=>{
  if(behavior==='hang'||behavior==='trickle'){
   closed=false;res.on('close',()=>{closed=true;});
   if(behavior==='trickle'){
    res.writeHead(200,{'Content-Type':'application/json'});res.write('{');
    const timer=setInterval(()=>res.write(' '),200);intervals.add(timer);res.on('close',()=>{clearInterval(timer);intervals.delete(timer);});
   }
   return;
  }
  if(behavior==='invalid'){res.end('not json');return;}
  if(behavior==='oversize'){res.end('x'.repeat(70000));return;}
  if(behavior==='broken'){res.destroy();return;}
  res.setHeader('Content-Type','application/json');res.end(JSON.stringify({filename:'existing.pdf',total_chunks:3,indexed:true,received_bytes:total}));
 });
});
function rss(){try{return Number(fs.readFileSync(`/proc/${child.pid}/status`,'utf8').match(/^VmRSS:\s+(\d+)/m)[1]);}catch{return 0;}}
async function waitReady(origin){for(let i=0;i<200;i++){if(child.exitCode!==null)throw new Error('Next exited');try{if((await fetch(origin)).ok)return;}catch{}await sleep(100);}throw new Error('Next readiness timeout');}
(async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const backend=`http://127.0.0.1:${server.address().port}`;
 const shim=path.join(out,'routing.cjs');fs.writeFileSync(shim,`const h=require('node:http');const r=h.request;const route=x=>typeof x==='string'?x.replace('http://backend:8000/','${backend}/'):x;h.request=function(...a){a[0]=route(a[0]);return r.apply(this,a)};require('node:module').syncBuiltinESMExports();const f=global.fetch;global.fetch=(x,o)=>f(route(x),o);`);
 const secret=crypto.randomBytes(32).toString('hex'),password=crypto.randomBytes(16).toString('hex');
 const passwordHash=frontRequire('bcryptjs').hashSync(password,4);
 const socket=http.createServer();await new Promise(r=>socket.listen(0,'127.0.0.1',r));const port=socket.address().port;await new Promise(r=>socket.close(r));
 const env={...process.env,NODE_OPTIONS:'--require '+shim,DOCLENS_SESSION_SECRET:secret,DOCLENS_ADMIN_EMAIL:'review@synthetic.invalid',DOCLENS_ADMIN_PASSWORD_HASH:passwordHash,NEXT_TELEMETRY_DISABLED:'1'};
 for(const k of ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'])delete env[k];env.NO_PROXY='*';env.no_proxy='*';
 const log=fs.openSync(path.join(out,'next.log'),'w');child=spawn('node',[path.join(root,'frontend/node_modules/next/dist/bin/next'),'start','--hostname','127.0.0.1','--port',String(port)],{cwd:frontend,env,stdio:['ignore',log,log]});
 const origin=`http://127.0.0.1:${port}`;await waitReady(origin);
 const login=await fetch(origin+'/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:'review@synthetic.invalid',password})});
 if(login.status!==200)throw new Error('Login failed');const cookie=login.headers.get('set-cookie').split(';')[0];
 behavior='slow';const form=new FormData();form.append('file',new Blob([fs.readFileSync(path.join(process.env.DOCLENS_FREEZE_FIXTURES||'/workspace/mac-upload-freeze','padded-28mib.pdf'))],{type:'application/pdf'}),'existing.pdf');
 const before=rss();let peak=before;const sampler=setInterval(()=>peak=Math.max(peak,rss()),20);const start=performance.now();
 const response=await fetch(origin+'/api/documents/process',{method:'POST',headers:{Cookie:cookie},body:form});
 const data=await response.json();clearInterval(sampler);if(response.status!==200||!data.indexed||data.received_bytes<28*1024*1024)throw new Error('28 MiB gateway transfer failed: '+JSON.stringify(data));
 results.gateway_28mib={status:response.status,received_bytes:data.received_bytes,seconds:(performance.now()-start)/1000,rss_before_kib:before,rss_peak_kib:peak,rss_delta_kib:peak-before};
 browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||(fs.existsSync('/usr/bin/chromium')?'/usr/bin/chromium':undefined),args:['--no-sandbox']});const context=await browser.newContext({viewport:{width:1280,height:900}});
 await context.addCookies([{name:'doclens_session',value:cookie.split('=')[1],domain:'127.0.0.1',path:'/',httpOnly:true,secure:false,sameSite:'Lax'}]);
 const page=await context.newPage();await page.goto(origin+'/dashboard');await page.clock.install();
 let ui='success',calls=0;
 await page.route('**/api/documents/process',async route=>{
  calls++;
  if(ui==='hang')return new Promise(()=>{});
  if(ui==='network'){await route.abort('failed');return;}
  if(ui==='invalidjson'){await route.fulfill({status:502,contentType:'text/plain',body:'Bad gateway'});return;}
  if(ui==='shape'){await route.fulfill({status:200,json:{indexed:false}});return;}
  if(ui!=='success'){await route.fulfill({status:Number(ui),json:{detail:'synthetic '+ui+' failure'}});return;}
  await route.fulfill({status:200,json:{filename:'existing.pdf',total_chunks:3,indexed:true}});
 });
 const input=page.locator('input[type=file]');const file={name:'existing.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF synthetic UI fixture; real PDF parsing is tested separately')};
 await input.setInputFiles(file);await expect(page.getByRole('button',{name:'+ Upload PDF',exact:true})).toBeEnabled();await expect(page.getByText('Ready · 3 chunks',{exact:true})).toBeVisible();
 if(mode==='baseline'){
  ui='hang';await input.setInputFiles(file);await expect(page.getByRole('button',{name:'Processing...',exact:true})).toBeDisabled();
  await page.clock.fastForward(11*60*1000);await expect(page.getByRole('button',{name:'Processing...',exact:true})).toBeDisabled();
  results.ui_busy_after_virtual_11_minutes=true;
 }else{
  const cases=[];
  for(const name of ['401','413','429','503','504','network','invalidjson','shape']){
   ui=name;await input.setInputFiles(file);await expect(page.getByRole('button',{name:'+ Upload PDF',exact:true})).toBeEnabled();
   await expect(page.getByText('Ready · 3 chunks',{exact:true})).toBeVisible();if(await input.inputValue()!=='')throw new Error('Input not reset');cases.push(name);
  }
  ui='hang';await input.setInputFiles(file);await expect(page.getByRole('button',{name:'Processing...',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Cancel upload',exact:true}).click();await expect(page.getByText(/Upload cancelled/)).toBeVisible();await expect(page.getByRole('button',{name:'+ Upload PDF',exact:true})).toBeEnabled();cases.push('cancel');
  await input.setInputFiles(file);await expect(page.getByRole('button',{name:'Processing...',exact:true})).toBeDisabled();await page.clock.fastForward(135001);
  await expect(page.getByText(/Upload timed out/)).toBeVisible();await expect(page.getByRole('button',{name:'+ Upload PDF',exact:true})).toBeEnabled();cases.push('135-second browser deadline, virtual clock');
  const previous=calls;await input.setInputFiles({name:'too-large.pdf',mimeType:'application/pdf',buffer:Buffer.alloc(32*1024*1024+1)});
  await expect(page.getByText(/32 MiB/)).toBeVisible();if(calls!==previous)throw new Error('Oversize file was transmitted');cases.push('client size limit');
  await page.evaluate(()=>{window.savedFormData=window.FormData;window.FormData=class{constructor(){throw new Error('synthetic FormData failure')}};});
  await input.setInputFiles(file);await expect(page.getByText('synthetic FormData failure',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'+ Upload PDF',exact:true})).toBeEnabled();
  await page.evaluate(()=>{window.FormData=window.savedFormData;});cases.push('synchronous FormData failure');results.ui_recovery_cases=cases;
  // The real gateway is tested independently of browser interception.
  results.gateway_failures=[];
  for(const failure of ['invalid','oversize','broken']){
   behavior=failure;const errorForm=new FormData();errorForm.append('file',new Blob(['synthetic'],{type:'application/pdf'}),'error.pdf');
   const errorResponse=await fetch(origin+'/api/documents/process',{method:'POST',headers:{Cookie:cookie},body:errorForm});
   if(errorResponse.status!==502)throw new Error('Unbounded/malformed gateway response not rejected');results.gateway_failures.push(failure);
  }
  behavior='hang';closed=false;const controller=new AbortController();const cancelForm=new FormData();cancelForm.append('file',new Blob(['synthetic'],{type:'application/pdf'}),'cancel.pdf');
  const pending=fetch(origin+'/api/documents/process',{method:'POST',headers:{Cookie:cookie},body:cancelForm,signal:controller.signal}).catch(()=>null);
  await sleep(300);controller.abort();await pending;for(let i=0;i<30&&!closed;i++)await sleep(100);if(!closed)throw new Error('Gateway did not close upstream on disconnect');results.gateway_disconnect_closed_upstream=true;
  behavior='trickle';const timeoutForm=new FormData();timeoutForm.append('file',new Blob(['synthetic'],{type:'application/pdf'}),'timeout.pdf');
  const began=performance.now();const timeoutResponse=await fetch(origin+'/api/documents/process',{method:'POST',headers:{Cookie:cookie},body:timeoutForm});const timeoutBody=await timeoutResponse.json();const seconds=(performance.now()-began)/1000;
  if(timeoutResponse.status!==504||seconds<119||seconds>125)throw new Error('Absolute deadline failed '+seconds+' '+timeoutResponse.status);
  results.gateway_absolute_deadline={seconds,status:timeoutResponse.status,detail:timeoutBody.detail,trickle_interval_ms:200};
 }
 fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2)+'\n');console.log(JSON.stringify(results));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{for(const interval of intervals)clearInterval(interval);if(browser)await browser.close();if(child)child.kill('SIGTERM');server.closeAllConnections();server.close();});
