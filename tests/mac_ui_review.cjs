// Built real dashboard; API responses controlled in-browser, no customer data or inference.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),crypto=require('node:crypto');
const {spawn}=require('node:child_process'),{createRequire}=require('node:module');
const root=path.resolve(__dirname,'..'),req=createRequire(path.join(root,'frontend/package.json'));
const {chromium}=req('playwright'),{expect}=req('@playwright/test');
const mode=process.argv[2]||'after',out=path.resolve(process.argv[3]||path.join(root,'validation/mac-ui'));
fs.mkdirSync(path.join(out,'screenshots'),{recursive:true});let child,browser;
(async()=>{
 const secret=crypto.randomBytes(32).toString('hex');const {SignJWT}=await import(req.resolve('jose'));
 const token=await new SignJWT({role:'admin'}).setProtectedHeader({alg:'HS256'}).setIssuer('doclens').setAudience('doclens-frontend').setIssuedAt().setExpirationTime('1h').sign(new TextEncoder().encode(secret));
 const socket=http.createServer();await new Promise(r=>socket.listen(0,'127.0.0.1',r));const port=socket.address().port;await new Promise(r=>socket.close(r));
 const log=fs.openSync(path.join(out,mode+'-next.log'),'w');
 child=spawn('node',['node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port',String(port)],{cwd:path.join(root,'frontend'),env:{...process.env,DOCLENS_SESSION_SECRET:secret,NEXT_TELEMETRY_DISABLED:'1'},stdio:['ignore',log,log]});
 const origin='http://127.0.0.1:'+port;
 for(let i=0;i<150;i++){if(child.exitCode!==null)throw Error('Next exited');try{if((await fetch(origin)).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1440,height:900},deviceScaleFactor:1});
 await context.addCookies([{name:'doclens_session',value:token,domain:'127.0.0.1',path:'/',httpOnly:true,secure:false,sameSite:'Lax'}]);
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 let behavior='success',calls=0,askBody;
 await page.route('**/api/documents/process',async route=>{calls++;if(behavior==='hang')return; if(behavior==='network')return route.abort(); if(behavior==='error')return route.fulfill({status:413,json:{detail:'Synthetic upload rejection.'}});return route.fulfill({json:{filename:'synthetic-contract.pdf',total_chunks:224,indexed:true}});});
 await page.route('**/api/ask',async route=>{askBody=route.request().postDataJSON();return route.fulfill({json:{answer:'The agreement requires **written notice**.',citations:[{document_name:'synthetic-contract.pdf',page_number:7,chunk_id:'p7-c1'},{document_name:'synthetic-contract.pdf',page_number:7,chunk_id:'p7-c2'}]}});});
 const shots=[];async function shot(state){const file=`${mode}-${state}.png`;await page.screenshot({path:path.join(out,'screenshots',file),fullPage:true});shots.push(file);}
 const contrast=[];
 async function measure(state){contrast.push(...await page.evaluate(state=>{
  const c=document.createElement('canvas').getContext('2d');function rgba(s){c.clearRect(0,0,1,1);c.fillStyle=s;c.fillRect(0,0,1,1);return [...c.getImageData(0,0,1,1).data].map((x,i)=>i===3?x/255:x/255);}
  function over(a,b){return [0,1,2].map(i=>a[i]*a[3]+b[i]*(1-a[3])).concat(1);}
  function bg(el){const nodes=[];for(let x=el;x;x=x.parentElement)nodes.unshift(x);return nodes.reduce((b,x)=>over(rgba(getComputedStyle(x).backgroundColor),b),[1,1,1,1]);}
  function lum(a){return a.slice(0,3).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);}
  function ratio(a,b){const x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
  const results=[],walker=document.createTreeWalker(document.querySelector('main'),NodeFilter.SHOW_TEXT);
  while(walker.nextNode()){const n=walker.currentNode,el=n.parentElement,text=n.textContent.trim();if(!text||!el.checkVisibility()||el.closest('button:disabled,textarea:disabled'))continue;const style=getComputedStyle(el),background=bg(el),color=over(rgba(style.color),background);const large=parseFloat(style.fontSize)>=24||(parseFloat(style.fontSize)>=18.66&&parseInt(style.fontWeight)>=700);results.push({state,text:text.slice(0,100),ratio:ratio(color,background),minimum:large?3:4.5,color:style.color,background:background.slice(0,3)});}
  const textarea=document.querySelector('textarea');if(textarea&&!textarea.disabled&&!textarea.value){const style=getComputedStyle(textarea,'::placeholder'),background=bg(textarea);results.push({state,text:'textarea placeholder',ratio:ratio(over(rgba(style.color),background),background),minimum:4.5});}
  const active=document.activeElement;
  if(active&&active.matches(':focus-visible')){const style=getComputedStyle(active);if(style.outlineStyle==='solid')results.push({state,text:'keyboard focus outline',ratio:ratio(rgba(style.outlineColor),bg(active.parentElement)),minimum:3});}
  return results;
 },state));}
 await page.goto(origin+'/dashboard');await expect(page.getByRole('button',{name:'+ Upload PDF',exact:true})).toBeVisible();await shot('empty');await measure('empty');
 const keyboard=[];await page.keyboard.press('Tab');await expect(page.getByRole('button',{name:'Log out',exact:true})).toBeFocused();keyboard.push('Tab reaches Log out');await page.keyboard.press('Tab');if(mode==='after'){await expect(page.locator('summary').filter({hasText:'Text processing limits'})).toBeFocused();await page.keyboard.press('Enter');await expect(page.getByText(/1,000,000 extracted characters/)).toBeVisible();await page.keyboard.press('Enter');keyboard.push('Tab/Enter opens and closes processing limits');await page.keyboard.press('Tab');}await expect(page.getByRole('button',{name:'+ Upload PDF',exact:true})).toBeFocused();
 const focus=await page.evaluate(()=>{const s=getComputedStyle(document.activeElement);return {style:s.outlineStyle,width:s.outlineWidth,color:s.outlineColor}});keyboard.push('Tab reaches Upload PDF');await shot('keyboard-focus');await measure('keyboard-focus');if(mode==='after'){const chosen=page.waitForEvent('filechooser');await page.keyboard.press('Enter');await (await chosen).setFiles([]);keyboard.push('Enter opens native file chooser from Upload');}
 const input=page.locator('input[type=file]'),file={name:'synthetic-contract.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF controlled browser fixture')};
 behavior='hang';await input.setInputFiles(file);await expect(page.getByRole('button',{name:'Cancel upload',exact:true})).toBeVisible();await shot('processing');await measure('processing');
 if(mode==='after'){await expect(page.getByText('synthetic-contract.pdf',{exact:true})).toBeVisible();await expect(page.getByText(/Waiting for confirmation/)).toBeVisible();await expect(page.getByRole('progressbar')).toHaveCount(0);await expect(page.getByRole('button',{name:'Cancel upload'})).toHaveCSS('border-top-style','solid');}
 const cancel=page.getByRole('button',{name:'Cancel upload',exact:true});await cancel.focus();await page.keyboard.press('Enter');await expect(page.getByText(/Upload cancelled/)).toBeVisible();await shot('cancellation');await measure('cancellation');keyboard.push('Enter activates Cancel upload; busy state clears');
 behavior='success';await input.setInputFiles(file);await expect(page.getByRole('button',{name:'+ Upload PDF',exact:true})).toBeEnabled();await expect(page.getByRole('button',{name:/synthetic-contract.pdf/})).toBeVisible();await shot('success');await measure('success');
 behavior='error';await input.setInputFiles(file);await expect(page.getByText('Synthetic upload rejection.',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:/synthetic-contract.pdf/})).toBeVisible();await expect(page.getByRole('button',{name:'+ Upload PDF',exact:true})).toBeEnabled();await shot('error');await measure('error');
 behavior='network';await input.setInputFiles(file);await expect(page.getByRole('button',{name:'+ Upload PDF',exact:true})).toBeEnabled();await expect(page.getByRole('button',{name:/synthetic-contract.pdf/})).toBeVisible();
 behavior='success';await input.setInputFiles(file);await expect(page.getByRole('button',{name:'+ Upload PDF',exact:true})).toBeEnabled();
 const text=page.getByRole('textbox');if(mode==='after'){await expect(text).toHaveAccessibleName('Question about the selected document');await expect(page.getByText(/questions and retrieved passages are sent to Google Gemini/i)).toBeVisible();await expect(page.getByRole('combobox')).toHaveCount(0);}
 await text.fill('What notice is required?');await page.getByRole('button',{name:'Send question'}).click();await expect(page.getByText('written notice',{exact:true})).toBeVisible();if(askBody.document_name!=='synthetic-contract.pdf'||askBody.question!=='What notice is required?')throw Error('Search scope changed');await shot('answer-citations');await measure('answer-citations');
 if(mode==='after'){
  const summary=page.locator('summary').filter({hasText:'Show source reference'});await expect(summary).toHaveCount(1);await summary.focus();await page.keyboard.press('Enter');await expect(page.getByText(/Original-page viewing is not available/)).toBeVisible();keyboard.push('Enter expands deduplicated citation reference');await shot('citation-expanded');await measure('citation-expanded');
  await text.fill('A follow-up question');await expect(page.getByRole('button',{name:'Send question'})).toBeEnabled();await text.focus();await page.keyboard.press('Tab');await expect(page.getByRole('button',{name:'Send question'})).toBeFocused();keyboard.push('Tab reaches Send question from question field');
  for(const size of [{width:1280,height:800},{width:1440,height:900}]){await page.setViewportSize(size);const geometry=await page.evaluate(()=>({viewport:innerWidth,width:document.documentElement.scrollWidth,height:innerHeight,send:document.querySelector('button[aria-label="Send question"]').getBoundingClientRect().bottom}));if(geometry.width>geometry.viewport||geometry.send>geometry.height)throw Error('Viewport overflow: '+JSON.stringify(geometry));await shot(`answer-${size.width}x${size.height}`);}
  if(focus.style!=='solid'||parseFloat(focus.width)<3)throw Error('Missing visible focus ring');
 }
 const failures=contrast.filter(x=>x.ratio<x.minimum);if(mode==='after'&&failures.length)throw Error('Contrast failures: '+JSON.stringify(failures));if(errors.length)throw Error(errors.join('\n'));
 fs.writeFileSync(path.join(out,mode+'-results.json'),JSON.stringify({mode,viewports:mode==='after'?['1440x900','1280x800']:['1440x900'],screenshots:shots,keyboard,focus,contrast,contrast_failures:failures,upload_calls:calls,api:'browser-intercepted synthetic responses; real built dashboard, no backend storage or Gemini calls',console_errors:errors},null,2)+'\n');console.log(JSON.stringify({mode,screenshots:shots.length,contrast_measurements:contrast.length,contrast_failures:failures.length,keyboard}));
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{if(browser)await browser.close();if(child)child.kill('SIGTERM');});
