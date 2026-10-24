// HTTP-only synthetic fixture. Cookie injection is not a RunPod HTTPS login test.
const {createRequire} = require('node:module');
const path = require('node:path');
const fs = require('node:fs');
const {chromium} = createRequire(path.resolve(__dirname,'../frontend/package.json'))('playwright');
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
    for (const [width,height] of [[1280,800],[375,812]]) {
      const context = await browser.newContext({viewport:{width,height}});
      const split = cookie.indexOf('=');
      await context.addCookies([{name:cookie.slice(0,split),value:cookie.slice(split+1),url:base,httpOnly:true,secure:false,sameSite:'Lax'}]);
      const page = await context.newPage();
      await page.goto(base+'/dashboard');
      const link = page.getByRole('link',{name:'Monitoring',exact:true});
      await link.waitFor({state:'visible'});
      const overflow = await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
      if (overflow) throw Error('Dashboard toolbar clips at width '+width);
      await page.screenshot({path:path.join(output,'doclens-'+width+'.png')});
      if (width===1280) {
        const query = page.waitForResponse(r => r.url().includes('/monitoring/api/ds/query') && r.request().method()==='POST', {timeout:60000});
        await link.click();
        await page.getByText('DocLens Operations',{exact:true}).first().waitFor({state:'visible',timeout:60000});
        await page.getByText('Service scrape status',{exact:true}).first().waitFor({state:'visible',timeout:60000});
        const response = await query;
        if (response.status() !== 200) throw Error('Grafana browser datasource query failed: '+response.status());
        await page.getByText('qdrant',{exact:true}).first().waitFor({state:'visible',timeout:60000});
        await page.screenshot({path:path.join(output,'grafana-1280.png'),fullPage:true});
        const text=await page.locator('body').innerText();
        if (/Unable to find datasource plugin|DatasourceError|Origin not allowed/.test(text)) throw Error('Grafana displays a datasource/proxy error');
      }
      await context.close();
    }
    console.log('PASS browser: anonymous redirect, authenticated Grafana dashboard, desktop/mobile monitoring link without horizontal overflow');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error.stack);process.exit(1)});
