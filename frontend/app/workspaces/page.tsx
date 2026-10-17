"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

type Workspace = { id: string; name: string; organisation_name: string; can_edit: boolean; retention_days: number; legal_hold: boolean };
type Library = { id: string; name: string; rights_basis: string };
type Document = { id: string; title: string; active_version_id: string };
type Version = { id: string; document_id: string; filename: string; sha256: string; source: string; jurisdiction: string; received_date: string; effective_date: string | null; created_at: string };
type Passage = { id: string; version_id: string; page_number: number; text: string; excerpt_sha256: string };
const base = "/api/platform";
const field = "rounded border border-slate-600 bg-slate-900 p-2 text-white";
const button = "rounded bg-blue-600 px-4 py-2 text-white disabled:opacity-50";

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${base}/${path}`, { ...options, cache: "no-store" });
  if (response.status === 401) { window.dispatchEvent(new Event("doclens:session-ended")); throw new Error("Please sign in."); }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || "Unable to complete the request.");
  }
  return response.status === 204 ? undefined as T : response.json();
}

export default function Workspaces() {
  const [signedIn, setSignedIn] = useState(false);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [workspace, setWorkspace] = useState("");
  const [library, setLibrary] = useState("");
  const [documents, setDocuments] = useState<Document[]>([]);
  const [libraryDocuments, setLibraryDocuments] = useState<Document[]>([]);
  const [versions, setVersions] = useState<Version[]>([]);
  const [selectedVersion, setSelectedVersion] = useState("");
  const [passages, setPassages] = useState<Passage[]>([]);
  const [results, setResults] = useState<Passage[]>([]);
  const [page, setPage] = useState(1);
  const [replacement, setReplacement] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const scopeGeneration = useRef(0);
  const selected = workspaces.find(w => w.id === workspace);

  const refresh = useCallback(async () => {
    try {
      const [ws, libs] = await Promise.all([api<{ workspaces: Workspace[] }>("workspaces"), api<{ libraries: Library[] }>("libraries")]);
      setWorkspaces(ws.workspaces); setLibraries(libs.libraries); setSignedIn(true);
    } catch { setSignedIn(false); }
  }, []);
  const clearIdentity = useCallback(() => {
    ++scopeGeneration.current; setSignedIn(false); setWorkspace(""); setLibrary(""); setWorkspaces([]); setLibraries([]);
    setDocuments([]); setLibraryDocuments([]); setVersions([]); setSelectedVersion(""); setPassages([]); setResults([]); setNotice("");
  }, []);
  useEffect(() => {
    window.addEventListener("doclens:session-ended", clearIdentity);
    return () => window.removeEventListener("doclens:session-ended", clearIdentity);
  }, [clearIdentity]);
  useEffect(() => { void Promise.resolve().then(refresh); }, [refresh]);
  useEffect(() => {
    const generation = ++scopeGeneration.current;
    if (workspace) api<{ documents: Document[] }>(`workspaces/${workspace}/documents`)
      .then(data => { if (generation === scopeGeneration.current) setDocuments(data.documents); })
      .catch(error => { if (generation === scopeGeneration.current) setError(error.message); });
  }, [workspace]);
  useEffect(() => {
    let active = true;
    if (library) api<{ documents: Document[] }>(`libraries/${library}/documents`)
      .then(data => { if (active) setLibraryDocuments(data.documents); })
      .catch(error => { if (active) setError(error.message); });
    return () => { active = false; };
  }, [library]);

  async function login(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    setBusy(true); setError("");
    try {
      await api("session", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: data.get("email"), password: data.get("password") }) });
      form.reset(); await refresh();
    } catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  async function openDocument(document: Document) {
    setError(""); setBusy(true); setSelectedVersion(""); setPassages([]);
    const generation = scopeGeneration.current;
    try {
      const data = await api<{ versions: Version[] }>(`documents/${document.id}/versions`);
      if (generation === scopeGeneration.current) { setVersions(data.versions); setPage(1); setSelectedVersion(document.active_version_id); }
    } catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  useEffect(() => {
    let active = true;
    if (selectedVersion) api<{ passages: Passage[] }>(`versions/${selectedVersion}/passages`)
      .then(data => { if (active) setPassages(data.passages); })
      .catch(error => { if (active) { setSelectedVersion(""); setError(error.message); } });
    return () => { active = false; };
  }, [selectedVersion]);

  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const values = new FormData(form);
    const old = documents.find(d => d.id === replacement);
    const payload = new FormData(); payload.set("file", values.get("file")!);
    payload.set("metadata", JSON.stringify({ title: values.get("title"), source: values.get("source"), jurisdiction: values.get("jurisdiction"),
      received_date: values.get("received_date"), effective_date: values.get("effective_date") || null, synthetic: values.get("synthetic") === "on",
      document_id: old?.id || null, expected_version_id: old?.active_version_id || null }));
    setBusy(true); setError(""); setNotice("");
    try {
      await api(`workspaces/${workspace}/documents`, { method: "POST", body: payload });
      const data = await api<{ documents: Document[] }>(`workspaces/${workspace}/documents`);
      setDocuments(data.documents); setVersions([]); setSelectedVersion(""); setResults([]); form.reset(); setReplacement("");
      setNotice("Version saved. Earlier originals and citations are preserved.");
    } catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget); setBusy(true); setError(""); setResults([]);
    try {
      const found = await api<{ results: Passage[] }>(`workspaces/${workspace}/search`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query: data.get("query"), mode: data.get("mode") }) });
      setResults(found.results); if (!found.results.length) setNotice("No matching passages in the permitted sources.");
    } catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }

  return <main className="min-h-screen bg-slate-950 p-6 text-slate-100 md:p-10">
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="flex items-center justify-between"><h1 className="text-3xl font-semibold">DocLens workspaces</h1>{signedIn && <button className={button} disabled={busy} onClick={async () => { setBusy(true); try { await api("session", { method: "DELETE" }); clearIdentity(); } catch (error) { setError((error as Error).message); } finally { setBusy(false); } }}>Sign out</button>}</header>
      <p className="rounded border border-amber-700 bg-amber-950/40 p-3">Synthetic documents only. Search returns source passages; hosted AI generation is disabled.</p>
      {error && <p role="alert" className="rounded bg-red-950 p-3">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {!signedIn ? <form onSubmit={login} className="flex max-w-md flex-col gap-4">
        <h2 className="text-xl">Sign in to your organisation</h2>
        <label className="grid gap-1">Email<input className={field} name="email" type="email" required autoComplete="username" /></label>
        <label className="grid gap-1">Password<input className={field} name="password" type="password" required autoComplete="current-password" /></label>
        <button className={button} disabled={busy}>Sign in</button>
      </form> : <>
        <label className="grid max-w-lg gap-1">Workspace<select className={field} value={workspace} disabled={busy} onChange={e => { ++scopeGeneration.current; setDocuments([]); setVersions([]); setSelectedVersion(""); setPassages([]); setResults([]); setReplacement(""); setError(""); setNotice(""); setWorkspace(e.target.value); }}>
          <option value="">Select a permitted workspace</option>{workspaces.map(w => <option key={w.id} value={w.id}>{w.organisation_name} / {w.name}</option>)}
        </select></label>
        {!workspaces.length && <p>No workspaces are available. Ask your administrator for membership.</p>}
        {selected && <>
          <p>Retention: {selected.retention_days} days minimum. Legal hold: {selected.legal_hold ? "active" : "inactive"}. Originals are retained; automatic deletion is disabled.</p>
          <div className="grid gap-8 lg:grid-cols-2">
            <section className="space-y-4"><h2 className="text-xl font-semibold">Workspace documents</h2>
              <ul className="space-y-2">{documents.map(d => <li key={d.id}><button className="text-blue-300 underline" disabled={busy} onClick={() => void openDocument(d)}>{d.title}</button></li>)}</ul>
              {!documents.length && <p>No documents in this workspace.</p>}
              {selected.can_edit && <form onSubmit={upload} className="grid gap-3 rounded border border-slate-700 p-4">
                <h3 className="text-lg">Upload an immutable version</h3>
                <label className="grid gap-1">Document<select className={field} value={replacement} onChange={e => setReplacement(e.target.value)}><option value="">Create a new document</option>{documents.map(d => <option key={d.id} value={d.id}>Replace: {d.title}</option>)}</select></label>
                <label className="grid gap-1">Title<input className={field} name="title" maxLength={255} required /></label>
                <label className="grid gap-1">Source and provenance<input className={field} name="source" maxLength={1000} required /></label>
                <label className="grid gap-1">Jurisdiction<input className={field} name="jurisdiction" maxLength={100} required /></label>
                <label className="grid gap-1">Received date<input className={field} name="received_date" type="date" required /></label>
                <label className="grid gap-1">Effective date (optional)<input className={field} name="effective_date" type="date" /></label>
                <label className="grid gap-1">PDF (up to 10 MiB, 100 pages)<input name="file" type="file" accept="application/pdf" required /></label>
                <label><input name="synthetic" type="checkbox" required /> I confirm this document is synthetic.</label>
                <button className={button} disabled={busy}>{busy ? "Working…" : "Save version"}</button>
              </form>}
              <form onSubmit={search} className="grid gap-3"><h3 className="text-lg">Search permitted sources</h3>
                <label className="grid gap-1">Search text<input className={field} name="query" required maxLength={1000} /></label>
                <label className="grid gap-1">Search method<select className={field} name="mode"><option value="lexical">Keyword</option><option value="dense">Semantic</option></select></label>
                <button className={button} disabled={busy}>Find passages</button>
              </form>
              {results.map(p => <article key={p.id} className="rounded border border-slate-700 p-3"><p>{p.text}</p><button className="text-blue-300 underline" onClick={() => { setVersions([]); setPassages([]); setSelectedVersion(p.version_id); setPage(p.page_number); }}>Open source, page {p.page_number}</button></article>)}
              <section className="grid gap-2"><h3 className="text-lg">Authorised reference libraries</h3>
                <select aria-label="Reference library" className={field} value={library} onChange={e => { setLibraryDocuments([]); setLibrary(e.target.value); }}><option value="">Select a library</option>{libraries.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}</select>
                {libraryDocuments.map(d => <div key={d.id} className="flex gap-3"><button className="text-blue-300 underline" disabled={busy} onClick={() => void openDocument(d)}>{d.title}</button>
                  {selected.can_edit && <button className={button} disabled={busy} onClick={async () => { setError(""); try { await api(`workspaces/${workspace}/references/${d.active_version_id}`, { method: "POST" }); setNotice("Exact reference version selected. Current library permission is still required to use it."); } catch (error) { setError((error as Error).message); } }}>Use this version</button>}</div>)}
              </section>
            </section>
            <section className="space-y-3"><h2 className="text-xl font-semibold">Exact-version source viewer</h2>
              {!!versions.length && <label className="grid gap-1">Document version<select className={field} value={selectedVersion} onChange={e => { setPassages([]); setPage(1); setSelectedVersion(e.target.value); }}>{versions.map(v => <option key={v.id} value={v.id}>{v.created_at} — {v.filename}</option>)}</select></label>}
              {versions.filter(v => v.id === selectedVersion).map(v => <div key={v.id} className="break-all text-sm"><p>Source: {v.source}; {v.jurisdiction}; received {v.received_date}</p><p>SHA-256: {v.sha256}</p></div>)}
              {selectedVersion && <>
                <a className="text-blue-300 underline" href={`${base}/versions/${selectedVersion}/original#page=${page}`} target="_blank" rel="noreferrer">Open immutable original at page {page}</a>
                <iframe title="Immutable PDF original" className="h-[36rem] w-full rounded border border-slate-700" src={`${base}/versions/${selectedVersion}/original#page=${page}`} />
                <p className="text-sm text-slate-400">Page and exact extracted excerpt are available. Glyph coordinates and OCR are not provided.</p>
                <ul className="max-h-96 space-y-3 overflow-auto">{passages.map(p => <li key={p.id} className="rounded border border-slate-700 p-3"><button className="text-blue-300 underline" onClick={() => setPage(p.page_number)}>Page {p.page_number}</button><p className="whitespace-pre-wrap">{p.text}</p><p className="break-all text-xs text-slate-400">Excerpt SHA-256: {p.excerpt_sha256}</p></li>)}</ul>
              </>}
            </section>
          </div>
        </>}
      </>}
    </div>
  </main>;
}
