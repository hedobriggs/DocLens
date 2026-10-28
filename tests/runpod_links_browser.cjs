// Real built image, browser form logins, no cookie injection or API stubs.
const {createRequire} = require('node:module');
const path = require('node:path');
const fs = require('node:fs');
const requireFrontend = createRequire(path.resolve(__dirname, '../frontend/package.json'));
const {chromium} = requireFrontend('playwright');
const {expect} = requireFrontend('@playwright/test');

(async () => {
  const output = process.env.DOCLENS_MONITORING_EVIDENCE || '/tmp/doclens-links-browser';
  fs.mkdirSync(output, {recursive:true});
  const browser = await chromium.launch({executablePath:'/usr/bin/chromium', args:['--no-sandbox']});
  try {
    const results = [];
    for (const [service, base] of [
      ['DocLens', process.env.DOCLENS_TEST_URL],
      ['Grafana', process.env.DOCLENS_GRAFANA_URL],
      ['Prometheus', process.env.DOCLENS_PROMETHEUS_URL],
    ]) {
      if (!base) throw Error('Missing URL for ' + service);
      // Separate contexts model RunPod's separate port hostnames. Localhost
      // Secure-cookie exception is not proof of provider HTTPS behavior.
      const context = await browser.newContext({viewport:{width:1280,height:800}});
      const page = await context.newPage();
      const failedAssets = [], assets = [];
      page.on('response', response => {
        if (['script','stylesheet'].includes(response.request().resourceType())) {
          assets.push(new URL(response.url()).pathname);
          if (response.status() >= 400) failedAssets.push([response.status(),new URL(response.url()).pathname]);
        }
      });
      page.on('requestfailed', request => {
        if (['script','stylesheet'].includes(request.resourceType())) failedAssets.push([request.failure().errorText,new URL(request.url()).pathname]);
      });
      await page.goto(base + '/');
      await expect(page.getByLabel('Email', {exact:true})).toBeVisible();
      await page.getByLabel('Email', {exact:true}).fill('trial@synthetic.invalid');
      await page.getByLabel('Password', {exact:true}).fill('Synthetic-$literal-Password-2026');
      const login = page.waitForResponse(r => new URL(r.url()).pathname === '/api/auth/login' && r.request().method() === 'POST');
      await page.getByRole('button', {name:'Sign in',exact:true}).click();
      if ((await login).status() !== 200) throw Error(service + ' form login failed');
      if (service === 'DocLens') {
        await page.waitForURL('**/dashboard');
      } else if (service === 'Grafana') {
        await page.getByText('DocLens Operations', {exact:true}).first().waitFor();
        await page.getByText('Service scrape status', {exact:true}).first().waitFor();
        await page.getByText('qdrant', {exact:true}).first().waitFor({timeout:60000});
      } else {
        await expect(page.locator('body')).toContainText('Execute');
      }
      const cookies = await context.cookies();
      if (!cookies.some(c => c.httpOnly && c.secure && c.sameSite === 'Lax')) throw Error(service + ' session cookie flags missing');
      await page.reload();
      if (service === 'Grafana') await page.getByText('DocLens Operations',{exact:true}).first().waitFor();
      else if (service === 'Prometheus') await expect(page.locator('body')).toContainText('Execute');
      else await page.waitForURL('**/dashboard');
      if (failedAssets.length) throw Error(service + ' failed assets: ' + JSON.stringify(failedAssets));
      if (!assets.length) throw Error(service + ' did not load scripts/styles');
      await page.screenshot({path:path.join(output,service.toLowerCase()+'.png'),fullPage:true});
      results.push({service,login:'passed',reloadSession:'passed',assets: [...new Set(assets)],failedAssets});
      await context.close();
    }
    fs.writeFileSync(path.join(output,'browser-results.json'),JSON.stringify(results,null,2)+'\n');
    console.log('PASS three root links, independent browser form logins, Secure/HttpOnly cookies, real dashboards/assets and reload sessions');
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error);process.exit(1);});
