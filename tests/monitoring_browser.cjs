// HTTP-only synthetic fixture. Cookie injection is not a RunPod HTTPS login test.
const {createRequire} = require('node:module');
const path = require('node:path');
const fs = require('node:fs');
const requireFrontend = createRequire(path.resolve(__dirname,'../frontend/package.json'));
const {chromium} = requireFrontend('playwright');
const {expect} = requireFrontend('@playwright/test');
(async () => {
  const base = process.env.DOCLENS_TEST_URL;
  const cookie = process.env.DOCLENS_TEST_COOKIE;
  if (!base || !cookie) throw Error('Synthetic browser fixture configuration missing');
  const output = process.env.DOCLENS_MONITORING_EVIDENCE || '/tmp/doclens-monitoring-browser';
  fs.mkdirSync(output,{recursive:true});
  const browser = await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
  try {
    const anonymous = await browser.newPage();
    await anonymous.goto(base+'/monitoring/d/doclens');
    if (new URL(anonymous.url()).pathname !== '/') throw Error('Anonymous dashboard access was not redirected');
    await anonymous.close();
    for (const [width,height] of [[1280,800],[1440,900],[375,812]]) {
      const context = await browser.newContext({viewport:{width,height}});
      const split = cookie.indexOf('=');
      await context.addCookies([{name:cookie.slice(0,split),value:cookie.slice(split+1),url:base,httpOnly:true,secure:false,sameSite:'Lax'}]);
      const page = await context.newPage();
      await page.goto(base+'/dashboard');
      await expect(page.getByRole('link',{name:'Monitoring',exact:true})).toHaveCount(0);
      const overflow = await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
      if (overflow) throw Error('Dashboard toolbar clips at width '+width);
      await page.screenshot({path:path.join(output,'doclens-'+width+'.png')});
      if (width===1280) {
        const marker=await page.evaluate(()=>{window.__doclensWorkspaceMarker=crypto.randomUUID();return window.__doclensWorkspaceMarker});
        const charts=await context.newPage();
        const query=charts.waitForResponse(r=>r.url().includes('/monitoring/api/ds/query') && r.request().method()==='POST',{timeout:60000});
        await charts.goto(process.env.DOCLENS_GRAFANA_URL || base+'/monitoring/d/doclens');
        await charts.getByText('DocLens Operations',{exact:true}).first().waitFor({state:'visible',timeout:60000});
        await charts.getByText('Service scrape status',{exact:true}).first().waitFor({state:'visible',timeout:60000});
        const response=await query;
        if(response.status()!==200)throw Error('Grafana browser datasource query failed: '+response.status());
        await charts.getByText('qdrant',{exact:true}).first().waitFor({state:'visible',timeout:60000});
        if(new URL(page.url()).pathname!=='/dashboard' || await page.evaluate(()=>window.__doclensWorkspaceMarker)!==marker)throw Error('Monitoring unloaded the document workspace');
        await charts.screenshot({path:path.join(output,'grafana-1280.png'),fullPage:true});
        const prometheus=await context.newPage();
        await prometheus.goto(process.env.DOCLENS_PROMETHEUS_URL || base+'/prometheus/query');
        await expect(prometheus.locator('body')).toContainText('Execute',{timeout:30000});
        await prometheus.screenshot({path:path.join(output,'prometheus-1280.png'),fullPage:true});
        const text=await charts.locator('body').innerText();
        if (/Unable to find datasource plugin|DatasourceError|Origin not allowed/.test(text)) throw Error('Grafana displays a datasource/proxy error');
      }
      // Real built dashboard, synthetic responses: verify long answers scroll
      // the conversation rather than scrolling the document page.
      await page.route('**/api/documents/process',r=>r.fulfill({json:{indexed:true,filename:'synthetic-scroll.pdf',total_chunks:5}}));
      await page.route('**/api/ask',r=>r.fulfill({json:{answer:Array.from({length:45},(_,i)=>'Synthetic evidence paragraph '+i+'.').join('\n\n')+'\n\nEND OF SYNTHETIC ANSWER',citations:[]}}));
      await page.locator('input[type=file]').setInputFiles({name:'synthetic-scroll.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4 synthetic UI fixture')});
      await expect(page.getByRole('status')).toContainText('ready for questions');
      for (const question of ['First synthetic question','Follow-up after reading earlier text']) {
        const conversation=page.getByLabel('Conversation',{exact:true});
        await conversation.evaluate(el=>{el.scrollTop=0});
        await page.getByRole('textbox').fill(question);
        await page.getByRole('button',{name:'Send question'}).click();
        await expect(page.getByRole('textbox')).toBeEnabled();
        await expect(page.getByText('END OF SYNTHETIC ANSWER',{exact:false}).last()).toBeAttached();
        await expect.poll(()=>conversation.evaluate(el=>el.scrollHeight-el.clientHeight)).toBeGreaterThan(100);
        await expect.poll(()=>conversation.evaluate(el=>el.scrollHeight-el.clientHeight-el.scrollTop)).toBeLessThan(3);
        if(await page.evaluate(()=>window.scrollY)>1)throw Error('Answer scrolling moved the document page');
      }
      await page.screenshot({path:path.join(output,'auto-scroll-'+width+'.png')});
      await context.close();
    }
    console.log('PASS browser: anonymous redirect, authenticated Grafana dashboard, separate monitoring page, no dashboard monitoring control; long answers auto-scroll at three viewports');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error.stack);process.exit(1)});
