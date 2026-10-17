import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
const fixtures = process.env.PLATFORM_BROWSER_FIXTURE_DIR!;
const seed = () => JSON.parse(readFileSync(join(fixtures, "fixture.json"), "utf8"));
async function login(page: import("@playwright/test").Page, user: string) {
  await page.goto("/workspaces");
  await page.getByLabel("Email", { exact: true }).fill(`${user}@synthetic.invalid`);
  await page.getByLabel("Password", { exact: true }).fill(process.env.PLATFORM_FIXTURE_PASSWORD!);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("combobox", { name: "Workspace", exact: true })).toBeVisible();
}

test("sign in, workspace upload, immutable version and citation original", async ({ page }) => {
  await login(page,"alice");
  const workspace = page.getByRole("combobox", { name: "Workspace", exact: true });
  await expect(workspace.locator("option")).toHaveText(["Select a permitted workspace", "firm-a / a-private"]);
  await workspace.selectOption({ label: "firm-a / a-private" });
  await page.getByLabel("Title", { exact: true }).fill("Browser synthetic original");
  await page.getByLabel("Source and provenance").fill("Browser authored fixture");
  await page.getByLabel("Jurisdiction", { exact: true }).fill("Synthetic jurisdiction");
  await page.getByLabel("Received date").fill("2026-10-17");
  await page.getByLabel("PDF (up to 10 MiB, 100 pages)").setInputFiles(join(fixtures,"fixture.pdf"));
  await page.getByLabel("I confirm this document is synthetic.").check();
  await page.getByRole("button", { name: "Save version", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Version saved");
  await page.getByRole("button", { name: "Browser synthetic original", exact: true }).click();
  await expect(page.getByText("Fresh synthetic upload citation evidence.", { exact: true })).toBeVisible();
  const original = page.getByRole("link", { name: /Open immutable original/ });
  const url = (await original.getAttribute("href"))!;
  const response = await page.request.get(url.split("#")[0], { headers: { Range: "bytes=0-9" } });
  expect(response.status()).toBe(206); expect((await response.body()).toString()).toContain("%PDF-");
  expect(response.headers()["cache-control"]).toBe("no-store");
  await page.getByLabel("Search text").fill("citation");
  await page.getByRole("button", { name: "Find passages" }).click();
  await expect(page.getByRole("button", { name: "Open source, page 1" })).toHaveCount(2);
});

test("cross-firm guessed original, passage, document and legacy paths are denied", async ({ page }) => {
  await login(page,"bob"); const fixture=seed();
  const ws = page.getByRole("combobox", { name: "Workspace", exact: true });
  await expect(ws.locator("option")).toHaveText(["Select a permitted workspace", "firm-b / b-private"]);
  for (const path of [`/api/platform/versions/${fixture.version_id}/original`, `/api/platform/versions/${fixture.version_id}/passages`, `/api/platform/documents/${fixture.document_id}/versions`]) {
    const response = await page.request.get(path,{headers:{Range:"bytes=0-9"}});
    expect(response.status()).toBe(404); expect(await response.json()).toEqual({detail:"Not found."});
  }
  expect((await page.request.post("/api/documents/process", { headers: { Origin: "http://127.0.0.1:3200" }, data: "unread" })).status()).toBe(404);
  for (const path of ["/api/ask","/api/auth/login","/dashboard","/monitoring"]) expect((await page.request.get(path)).status()).toBe(404);
});

test("organisation admin has no implicit restricted-workspace access", async ({ page }) => {
  await login(page,"org-admin");
  await expect(page.getByText("No workspaces are available. Ask your administrator for membership.")).toBeVisible();
  expect((await page.request.get(`/api/platform/versions/${seed().version_id}/original`)).status()).toBe(404);
});

test("reader can open permitted sources, cannot upload, and logout revokes access", async ({ page }) => {
  await login(page,"reader");
  await page.getByRole("combobox",{name:"Workspace",exact:true}).selectOption({label:"firm-a / a-private"});
  await expect(page.getByRole("heading",{name:"Upload an immutable version"})).toHaveCount(0);
  await page.getByRole("button",{name:"Alice private fixture",exact:true}).click();
  await expect(page.getByText("Blue synthetic workspace citation evidence.",{exact:true})).toBeVisible();
  await page.getByRole("button",{name:"Sign out",exact:true}).click();
  await expect(page.getByRole("button",{name:"Sign in",exact:true})).toBeVisible();
  expect((await page.request.get(`/api/platform/versions/${seed().version_id}/original`)).status()).toBe(401);
});

test("cross-origin mutations and missing identity fail before forwarding",async ({page})=>{
  await page.goto("/workspaces");
  const denied=await page.request.post("/api/platform/session",{headers:{Origin:"https://untrusted.invalid"},data:{email:"alice@synthetic.invalid",password:"unused"}});
  expect(denied.status()).toBe(403);
  expect((await page.request.post("/api/platform/workspaces/00000000-0000-0000-0000-000000000000/documents",{headers:{Origin:"http://127.0.0.1:3200"},data:"unread"})).status()).toBe(401);
});

test("streaming gateway preserves a 10 MiB PDF and rejects an oversized original", async ({page})=>{
  await login(page,"alice");
  const listed=await page.request.get('/api/platform/workspaces');
  const workspace=(await listed.json()).workspaces[0].id;
  const original=readFileSync(join(fixtures,'fixture.pdf'));
  const metadata=JSON.stringify({title:'Transport boundary fixture',source:'Padded synthetic transport fixture, not a dense document',jurisdiction:'Test',received_date:'2026-10-17',synthetic:true});
  for(const [size,status] of [[10*1024*1024,200],[10*1024*1024+1,413]]) {
    const buffer=Buffer.concat([original,Buffer.alloc(size-original.length,32)]);
    const response=await page.request.post(`/api/platform/workspaces/${workspace}/documents`,{
      headers:{Origin:'http://127.0.0.1:3200'},multipart:{metadata,file:{name:'transport.pdf',mimeType:'application/pdf',buffer}}
    });
    expect(response.status()).toBe(status);
  }
});


test("opt-in durable admission forwards idempotency and protects queued status", async ({page})=>{
  await login(page,"alice");
  const workspace=(await (await page.request.get('/api/platform/workspaces')).json()).workspaces[0].id;
  const key='browser-durable-'+Date.now();
  const data={metadata:JSON.stringify({title:'Queued synthetic source',source:'Synthetic durable browser fixture',jurisdiction:'Test',received_date:'2026-10-17',synthetic:true}),
    file:{name:'queued.pdf',mimeType:'application/pdf',buffer:readFileSync(join(fixtures,'fixture.pdf'))}};
  const options={headers:{Origin:'http://127.0.0.1:3200','Idempotency-Key':key},multipart:data};
  const first=await page.request.post(`/api/platform/workspaces/${workspace}/ingestions`,options);
  expect(first.status()).toBe(202);
  const job=await first.json();expect(job.state).toBe('queued');
  const replay=await page.request.post(`/api/platform/workspaces/${workspace}/ingestions`,options);
  expect(replay.status()).toBe(202);expect((await replay.json()).job_id).toBe(job.job_id);
  expect((await (await page.request.get(`/api/platform/jobs/${job.job_id}`)).json()).state).toBe('queued');
  expect((await page.request.get(`/api/platform/versions/${job.version_id}/original`)).status()).toBe(404);
  await page.getByRole('button',{name:'Sign out',exact:true}).click();
  await login(page,'bob');
  expect((await page.request.get(`/api/platform/jobs/${job.job_id}`)).status()).toBe(404);
});
