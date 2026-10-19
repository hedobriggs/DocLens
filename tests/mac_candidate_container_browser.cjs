// Real built candidate frontend/gateway, actual PDF; no intercepted browser APIs.
const fs=require('node:fs'),path=require('node:path'),{createRequire}=require('node:module');
const req=createRequire(path.resolve(__dirname,'../frontend/package.json')),{chromium}=req('playwright'),{expect}=req('@playwright/test');
let browser;
(async()=>{
 const config=JSON.parse(fs.readFileSync(0,'utf8')),url=new URL(config.origin);
 browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1440,height:900}});await context.addCookies([{name:'doclens_session',value:config.cookie,domain:url.hostname,path:'/',httpOnly:true,secure:false,sameSite:'Lax'}]);
 const page=await context.newPage(),events=[];page.on('filechooser',()=>events.push('filechooser'));
 await page.goto(config.origin+'/dashboard');const upload=page.getByRole('button',{name:'+ Upload PDF',exact:true});await expect(upload).toBeEnabled();await page.bringToFront();await expect.poll(()=>page.evaluate(()=>document.hasFocus())).toBe(true);
 await page.keyboard.press('Tab');await expect(page.getByRole('button',{name:'Log out',exact:true})).toBeFocused();await page.keyboard.press('Tab');await expect(page.locator('summary').filter({hasText:'Text processing limits'})).toBeFocused();await page.keyboard.press('Tab');await expect(upload).toBeFocused();
 const chosen=page.waitForEvent('filechooser',{timeout:5000});await page.keyboard.press('Enter');await (await chosen).setFiles(config.pdf);
 await expect(page.getByRole('status')).toHaveText('browser-candidate.pdf is ready for questions.',{timeout:110000});await expect(page.getByRole('button',{name:/browser-candidate.pdf/})).toHaveAttribute('aria-pressed','true');await expect(page.getByText('Text-based PDFs · up to 32 MiB · 300 pages',{exact:true})).toBeVisible();
 await page.screenshot({path:config.screenshot,fullPage:true});console.log(JSON.stringify({keyboard_filechooser:events.length===1,real_gateway_pdf:'passed',scope:'browser-candidate.pdf',viewport:'1440x900'}));
})().catch(e=>{console.error(e);process.exitCode=1}).finally(async()=>{if(browser)await browser.close()});
