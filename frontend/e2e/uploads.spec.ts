import { test, expect } from '@playwright/test';
import { SignJWT } from 'jose';
import { writeFile, unlink } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
async function session(role: string) {
  return new SignJWT({role}).setProtectedHeader({alg:'HS256'}).setIssuer('doclens').setAudience('doclens-frontend').setExpirationTime('5m').sign(new TextEncoder().encode('automated-tests-only-32-character-key'));
}
test('monitoring requires admin and provides a link, not a popup', async ({page, context}) => {
  await page.goto('/monitoring'); await expect(page).toHaveURL('http://127.0.0.1:3100/');
  await context.addCookies([{name:'doclens_session',value:await session('viewer'),url:'http://127.0.0.1:3100'}]);
  await page.goto('/monitoring'); await expect(page).toHaveURL('http://127.0.0.1:3100/');
  await page.goto('/dashboard'); await expect(page).toHaveURL('http://127.0.0.1:3100/');
  await context.addCookies([{name:'doclens_session',value:await session('admin'),url:'http://127.0.0.1:3100'}]);
  await page.goto('/dashboard'); await expect(page.getByRole('link',{name:'Monitoring',exact:true})).toBeVisible();
  await page.getByRole('link',{name:'Monitoring',exact:true}).click();
  await expect(page.getByRole('link',{name:'Open Grafana overview'})).toHaveAttribute('href','http://localhost:3001/d/doclens');
  await expect(page.getByText(/separate administrator sign-in/)).toBeVisible();
});
for (const [file,status,message] of [
  ['slow.pdf',200,''], ['timeout.pdf',504,'supported deadline'],
  ['bodytimeout.pdf',504,'supported deadline'], ['failure.pdf',503,'Index capacity exhausted'],['invalid.pdf',502,'invalid response'],
  ['disconnect.pdf',502,'service is unavailable'], ['schema.pdf',502,'invalid response']
] as const) {
  test(`${file}: real proxy status and UI resets`, async ({page,context,request})=>{
    const token=await session('admin');
    const response=await request.post('/api/documents/process',{headers:{cookie:`doclens_session=${token}`},multipart:{file:{name:file,mimeType:'application/pdf',buffer:Buffer.from('%PDF-test')}}});
    expect(response.status()).toBe(status);
    const body=await response.json();
    if(status!==200) expect(body.detail).toContain(message);
    else expect(body.indexed).toBe(true);
    await context.addCookies([{name:'doclens_session',value:token,url:'http://127.0.0.1:3100'}]);
    await page.goto('/dashboard');
    await page.locator('input[type=file]').setInputFiles({name:file,mimeType:'application/pdf',buffer:Buffer.from('%PDF-test')});
    await expect(page.getByRole('button',{name:'+ Upload PDF',exact:true})).toBeEnabled({timeout:10000});
    expect(await page.locator('input[type=file]').inputValue()).toBe('');
    if(status!==200) await expect(page.getByText(message,{exact:false})).toBeVisible();
  });
}
for (const mode of ['network','non-json','unauthorized','oversize'] as const) {
  test(`UI clears uploading state: ${mode}`, async ({page,context})=>{
    await context.addCookies([{name:'doclens_session',value:await session('admin'),url:'http://127.0.0.1:3100'}]);
    await page.goto('/dashboard');
    await page.route('**/api/documents/process', route=>mode==='network' ? route.abort() : route.fulfill({status:mode==='unauthorized'?401:502,contentType:mode==='non-json'?'text/plain':'application/json',body:mode==='non-json'?'Bad gateway':JSON.stringify({detail:'Please sign in again.'})}));
    if (mode === 'oversize') {
      const path=join(tmpdir(),`doclens-oversize-${process.pid}.pdf`);
      await writeFile(path, Buffer.alloc(50*1024*1024+1));
      try { await page.locator('input[type=file]').setInputFiles(path); }
      finally { await unlink(path); }
    } else {
      await page.locator('input[type=file]').setInputFiles({name:'sample.pdf',mimeType:'application/pdf',buffer:Buffer.alloc(10)});
    }
    await expect(page.getByRole('button',{name:'+ Upload PDF',exact:true})).toBeEnabled();
    expect(await page.locator('input[type=file]').inputValue()).toBe('');
    await expect(page.locator('p.text-red-400')).toBeVisible();
  });
}

test('25 MiB request forwards and invalid requests have distinct status codes', async ({request})=>{
  const token=await session('admin');
  const headers={cookie:`doclens_session=${token}`};
  const large=await request.post('/api/documents/process',{headers,multipart:{file:{name:'large.pdf',mimeType:'application/pdf',buffer:Buffer.alloc(25*1024*1024)}}});
  expect(large.status()).toBe(200);
  const malformed=await request.post('/api/documents/process',{headers:{...headers,'Content-Type':'multipart/form-data; boundary=missing'},data:'invalid'});
  expect(malformed.status()).toBe(400);
  const absent=await request.post('/api/documents/process',{headers,multipart:{other:'none'}});
  expect(absent.status()).toBe(400);
  const unauthorized=await request.post('/api/documents/process',{multipart:{other:'none'}});
  expect(unauthorized.status()).toBe(401);
  const oversized=await request.post('/api/documents/process',{headers,multipart:{file:{name:'huge.pdf',mimeType:'application/pdf',buffer:Buffer.alloc(50*1024*1024+1)}}});
  expect(oversized.status()).toBe(413);
});
