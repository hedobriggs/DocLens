// Real production Next authentication rejection plus deterministic client expiry.
// Upload success is a synthetic fixture; no backend, Gemini or customer data.
const {createRequire}=require('node:module'),path=require('node:path'),fs=require('node:fs');
const {spawn}=require('node:child_process'),crypto=require('node:crypto'),net=require('node:net');
const root=path.resolve(__dirname,'..'),req=createRequire(path.join(root,'frontend/package.json'));
const {chromium}=req('playwright'),{expect}=req('@playwright/test');
const out=path.resolve(process.argv[2]||'/tmp/doclens-session-evidence');fs.mkdirSync(out,{recursive:true});
let server,browser;
(async()=>{
 const secret=crypto.randomBytes(32).toString('hex');
 const {SignJWT}=await import(req.resolve('jose'));
 const token=seconds=>new SignJWT({role:'admin'}).setProtectedHeader({alg:'HS256'}).setIssuer('doclens').setAudience('doclens-frontend').setIssuedAt().setExpirationTime(Math.floor(Date.now()/1000)+seconds).sign(new TextEncoder().encode(secret));
 const socket=net.createServer();await new Promise(r=>socket.listen(0,'127.0.0.1',r));const port=socket.address().port;await new Promise(r=>socket.close(r));
 const log=fs.openSync(path.join(out,'next.log'),'w');
 server=spawn('node',['node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port',String(port)],{cwd:path.join(root,'frontend'),env:{...process.env,DOCLENS_SESSION_SECRET:secret,DOCLENS_PLATFORM_ENABLED:'0',NEXT_TELEMETRY_DISABLED:'1'},stdio:['ignore',log,log]});
 const base='http://127.0.0.1:'+port;
 await expect.poll(async()=>{if(server.exitCode!==null)throw Error('Next exited');try{return(await fetch(base)).status}catch{return 0}},{timeout:20000}).toBe(200);
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
 const results=[];
 for(const kind of ['upload-401','question-401','upload-clock','question-clock']){
  const context=await browser.newContext({viewport:{width:1280,height:800}}),page=await context.newPage();
  if(kind.endsWith('clock'))await page.clock.install({time:new Date()});
  await context.addCookies([{name:'doclens_session',value:await token(kind.endsWith('clock')?60:3600),domain:'127.0.0.1',path:'/',httpOnly:true,secure:false,sameSite:'Lax'}]);
  await page.goto(base+'/dashboard');await expect(page.getByRole('button',{name:'+ Upload PDF',exact:true})).toBeEnabled();
  const isQuestion=kind.startsWith('question');
  if(isQuestion){
   await page.route('**/api/documents/process',r=>r.fulfill({json:{indexed:true,filename:'synthetic-session.pdf',total_chunks:2}}));
   await page.locator('input[type=file]').setInputFiles({name:'synthetic-session.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF synthetic')});
   await expect(page.getByRole('status')).toContainText('ready for questions');
  }
  let release;const intercepted=new Promise(resolve=>{release=resolve;});let pending;
  await page.route(isQuestion?'**/api/ask':'**/api/documents/process',route=>{pending=route;release();});
  if(isQuestion){await page.getByRole('textbox').fill('Preserve this synthetic question');await page.getByRole('button',{name:'Send question'}).click();}
  else await page.locator('input[type=file]').setInputFiles({name:'pending-synthetic.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF synthetic')});
  await intercepted;
  if(isQuestion)await expect(page.getByRole('button',{name:'Stop generating'})).toBeVisible();
  else await expect(page.getByRole('button',{name:'Cancel upload',exact:true})).toBeVisible();
  await page.screenshot({path:path.join(out,kind+'-busy.png'),fullPage:true});
  if(kind.endsWith('401')){
   const expired=await token(-60);
   await context.addCookies([{name:'doclens_session',value:expired,domain:'127.0.0.1',path:'/',httpOnly:true,secure:false,sameSite:'Lax'}]);
   const rejected=page.waitForResponse(r=>new URL(r.url()).pathname===(isQuestion?'/api/ask':'/api/documents/process'));
   await pending.continue({headers:{...pending.request().headers(),cookie:'doclens_session='+expired}});
   expect((await rejected).status()).toBe(401); // Actual Next JWT rejection, no 401 stub.
  }else{
   await page.clock.fastForward(61000); // Server-provided 60s expiry; upload deadline is still 135s.
  }
  const signIn=page.locator('header').getByRole('link',{name:'Sign in',exact:true});
  await expect(signIn).toBeVisible();await expect(signIn).toHaveAttribute('href','/');
  await expect(page.getByRole('button',{name:'Log out',exact:true})).toHaveCount(0);
  await expect(page.getByRole('alert').getByRole('link',{name:'Sign in',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Cancel upload',exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Stop generating'})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Send question'})).toBeDisabled();
  await expect(page.getByRole('button',{name:'+ Upload PDF',exact:true})).toBeDisabled();
  if(isQuestion){await expect(page.getByRole('textbox')).toHaveValue('Preserve this synthetic question');await expect(page.getByTitle('synthetic-session.pdf')).toBeVisible();}
  await page.screenshot({path:path.join(out,kind+'-recovered.png'),fullPage:true});
  if(kind.endsWith('clock'))await pending.abort().catch(()=>{});
  await signIn.focus();await page.keyboard.press('Enter');
  await expect(page.getByLabel('Email',{exact:true})).toBeVisible();
  results.push({scenario:kind,signInLink:'clicked with Enter; login form reached',busyRecovery:'passed',header:'Sign in replaces Log out',auth:kind.endsWith('401')?'real server rejects expired signed JWT':'deterministic browser timer from verified server expiry',data:'synthetic UI fixtures only; no backend storage/provider'});
  await context.close();
 }
 fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2)+'\n');console.log('PASS four upload/question expiry scenarios, safe busy recovery and actionable keyboard Sign in');
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(server)server.kill('SIGTERM');});
