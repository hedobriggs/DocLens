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
    const backOnly = process.env.DOCLENS_TEST_BACK_LINK_ONLY === '1';
    for (const [service, base] of [
      ['DocLens', process.env.DOCLENS_TEST_URL],
      ['Grafana', process.env.DOCLENS_GRAFANA_URL],
      ['Prometheus', process.env.DOCLENS_PROMETHEUS_URL],
    ].filter(([service]) => !backOnly || service === 'Grafana')) {
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
        if (!backOnly) await page.getByText('qdrant', {exact:true}).first().waitFor({timeout:60000});
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
      if (service === 'Grafana') {
        const target = new URL(process.env.DOCLENS_TEST_URL);
        const monitoringHost = new URL(base).hostname;
        if (target.hostname !== monitoringHost) {
          if ((await context.cookies(target.origin)).length) throw Error('Monitoring session leaked to DocLens hostname before navigation');
        }
        const backLink = page.getByRole('link', {name:'Back to DocLens',exact:true});
        const backHref = await backLink.getAttribute('href');
        const previousURL = page.url();
        await backLink.click();
        await page.waitForURL(url => url.href !== previousURL);
        if (new URL(page.url()).origin !== target.origin) {
          await page.screenshot({path:path.join(output,'back-to-doclens-failure.png'),fullPage:true});
          throw Error('Back to DocLens stayed on monitoring origin: ' + page.url() + '; href=' + backHref);
        }
        if (target.hostname !== monitoringHost) {
          await expect(page.getByLabel('Email', {exact:true})).toBeVisible();
          if ((await context.cookies(target.origin)).length) throw Error('Back link transferred a monitoring cookie');
          await page.getByLabel('Email', {exact:true}).fill('trial@synthetic.invalid');
          await page.getByLabel('Password', {exact:true}).fill('Synthetic-$literal-Password-2026');
          await page.getByRole('button', {name:'Sign in',exact:true}).click();
        }
        await page.waitForURL(url => url.origin === target.origin && url.pathname === '/dashboard');
        await expect(page.locator('body')).toContainText('Upload PDF');
        const destinationAssets = [...new Set(assets.filter(asset => asset.startsWith('/_next/')))];
        if (failedAssets.length || !destinationAssets.length) throw Error('DocLens destination assets did not load correctly');
        const destinationCookies = await context.cookies(target.origin);
        if (!destinationCookies.some(cookie => cookie.httpOnly && cookie.secure && cookie.domain === target.hostname)) throw Error('DocLens host-only session cookie missing');
        await page.screenshot({path:path.join(output,'back-to-doclens.png'),fullPage:true});
        results[results.length-1].backToDocLens = {navigation:'passed',href:backHref,origin:target.origin,destinationAssets,hostOnlySessionBoundary:target.hostname !== monitoringHost ? 'verified with separate form login' : 'same-host local ports; separate-host coverage not claimed'};
      }
      await context.close();
    }
    fs.writeFileSync(path.join(output,'browser-results.json'),JSON.stringify(results,null,2)+'\n');
    console.log(backOnly ? 'PASS real Grafana Back to DocLens click, destination login/dashboard, host-only cookies and assets' : 'PASS three root links, independent browser form logins, Secure/HttpOnly cookies, real dashboards/assets, reload sessions and Back to DocLens click');
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error);process.exit(1);});
