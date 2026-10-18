// Public DOM readiness, controlled script admission, and trusted keyboard activation.
// No elapsed-time sleeps, React private properties, automatic retries, or stored data.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),crypto=require('node:crypto');
const {spawn}=require('node:child_process'),{createRequire}=require('node:module');
const root='/workspace/DocLens',req=createRequire(path.join(root,'frontend/package.json'));
const {chromium}=req('playwright'),{expect}=req('@playwright/test');
const out=path.resolve(process.argv[2]||'/tmp/doclens-keyboard-review');fs.mkdirSync(out,{recursive:true});let child,browser;
const results={cases:[],errors:[],method:'Hold hydration scripts; require disabled SSR Upload, release scripts, await enabled; trusted Tab/Enter after document focus. 20 new browser contexts, no retry or fixed sleeps.'};
const save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2)+'\n');
(async()=>{
 const {SignJWT}=await import(req.resolve('jose')),secret=crypto.randomBytes(32).toString('hex');
 const token=await new SignJWT({role:'admin'}).setProtectedHeader({alg:'HS256'}).setIssuer('doclens').setAudience('doclens-frontend').setIssuedAt().setExpirationTime('1h').sign(new TextEncoder().encode(secret));
 const socket=http.createServer();await new Promise(r=>socket.listen(0,'127.0.0.1',r));const port=socket.address().port;await new Promise(r=>socket.close(r));const origin=`http://127.0.0.1:${port}`;
 const log=fs.openSync(path.join(out,'next.log'),'w');child=spawn('node',['node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port',String(port)],{cwd:path.join(root,'frontend'),env:{...process.env,DOCLENS_SESSION_SECRET:secret,DOCLENS_PLATFORM_ENABLED:'0',NEXT_TELEMETRY_DISABLED:'1'},stdio:['ignore',log,log]});
 await expect.poll(async()=>{if(child.exitCode!==null)throw Error('Next exited');try{return (await fetch(origin)).status}catch{return 0}},{timeout:20000}).toBe(200);
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 for(const viewport of [{width:1280,height:800},{width:1440,height:900}])for(let iteration=0;iteration<10;iteration++){
  const context=await browser.newContext({viewport});await context.addCookies([{name:'doclens_session',value:token,domain:'127.0.0.1',path:'/',httpOnly:true,secure:false,sameSite:'Lax'}]);
  const page=await context.newPage(),entry={viewport,iteration,controlledHydration:iteration===0,events:[]};results.cases.push(entry);let release;
  await page.addInitScript(()=>{window.keyboardEvidence=[];for(const type of ['keydown','click','focusin','focusout'])document.addEventListener(type,e=>window.keyboardEvidence.push({type,key:e.key,trusted:e.isTrusted,target:e.target.tagName,text:(e.target.textContent||'').slice(0,50),documentFocus:document.hasFocus(),userActivation:navigator.userActivation.isActive}),true)});
  // Diagnostic: intentionally register interception only in waitForEvent immediately before Enter.
  if(entry.controlledHydration){const gate=new Promise(r=>release=r);await page.route('**/_next/**/*.js',async r=>{await gate;await r.continue()});}
  try{
   await page.goto(origin+'/dashboard',{waitUntil:'commit'});const upload=page.getByRole('button',{name:'+ Upload PDF',exact:true});await expect(upload).toBeVisible();
   if(release){entry.beforeHydration={disabled:await upload.isDisabled()};save();await expect(upload).toBeDisabled();release();}
   await expect(upload).toBeEnabled();await page.bringToFront();await expect.poll(()=>page.evaluate(()=>document.hasFocus())).toBe(true);
   await page.keyboard.press('Tab');await expect(page.getByRole('link',{name:'Monitoring',exact:true})).toBeFocused();await page.keyboard.press('Tab');await expect(page.getByRole('button',{name:'Log out',exact:true})).toBeFocused();await page.keyboard.press('Tab');await expect(upload).toBeFocused();
   entry.beforeEnter=await page.evaluate(()=>({documentFocus:document.hasFocus(),activeText:document.activeElement.textContent,disabled:document.activeElement.disabled}));
   await page.screenshot({path:path.join(out,`focus-${viewport.width}-${iteration}.png`)});await expect(upload).toBeFocused();const chooser=page.waitForEvent('filechooser',{timeout:5000});await page.keyboard.press('Enter');await (await chooser).setFiles([]);entry.pass=true;
  }catch(error){entry.error=String(error);entry.pass=false;await page.screenshot({path:path.join(out,`failed-${viewport.width}-${iteration}.png`)});throw error;
  }finally{if(release)release();entry.domEvents=await page.evaluate(()=>window.keyboardEvidence||[]).catch(()=>[]);save();await context.close();}
 }
 console.log(JSON.stringify({passed:results.cases.filter(x=>x.pass).length,controlledHydration:results.cases.filter(x=>x.controlledHydration).length,viewports:['1280x800','1440x900']}));
})().catch(e=>{results.errors.push(String(e));save();console.error(e);process.exitCode=1}).finally(async()=>{if(browser)await browser.close();if(child)child.kill('SIGTERM')});
