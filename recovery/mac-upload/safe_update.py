#!/usr/bin/env python3
"""Selective local Mac update. No merges, resets, cleans, env writes, or volume deletion."""
import argparse
import gzip
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tarfile
import time
import uuid

BASE = 'e800f34018474c411ba609654c13ccf4d59cb05f'
MAC = 'c0509bbd6c5648876c3699306b5f7ad1ae29a584'
INDENT = '497394bf03f00f73256e3e70cb7283e7ce33c342'
REVIEWED = '76b81c1bf5a23fd62e344e893b1bff45e24e8cb4'
ORIGINALS = ('backend/embeddings.py', 'backend/generation.py', 'backend/main.py',
             'backend/vector_store.py', 'docker-compose.yml',
             'frontend/app/api/auth/login/route.ts',
             'frontend/app/api/documents/process/route.ts', 'frontend/app/dashboard/page.tsx')
UPDATE = ('backend/embeddings.py', 'backend/main.py', 'backend/vector_store.py',
          'backend/document_publication.py', 'backend/upload_processing.py',
          'docker-compose.yml', 'frontend/app/api/documents/process/route.ts',
          'frontend/app/dashboard/page.tsx', 'frontend/package.json', 'frontend/package-lock.json')
CONTAINERS = ('doclens-backend', 'doclens-frontend', 'doclens-qdrant')


def run(args, cwd, data=None):
    result = subprocess.run(args, cwd=cwd, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        # Commands involving Compose can include interpolated credentials in stderr.
        raise RuntimeError(f'{args[0]} {args[1]} failed (exit {result.returncode}); no source changes should be assumed complete')
    return result.stdout


def git(repo, *args):
    return run(['git', *args], repo)


def blob(repo, rev, path):
    return git(repo, 'show', f'{rev}:{path}')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inside(path, parent):
    return path == parent or parent in path.parents


def check_sources(repo):
    if git(repo, 'rev-parse', '--show-toplevel').decode().strip() != str(repo):
        raise RuntimeError('Run from the root of the Mac checkout')
    if git(repo, 'rev-parse', 'HEAD').decode().strip() != BASE:
        raise RuntimeError('HEAD is not the expected Mac baseline e800f34. Stop and share git status --short and git rev-parse HEAD; do not reset')
    tracked = git(repo, 'ls-tree', '-r', '--name-only', BASE).decode().splitlines()
    staged = set(git(repo, 'ls-files', '-z').decode().strip('\0').split('\0'))
    if staged != set(tracked):
        raise RuntimeError('The Git index contains added/deleted files outside the expected baseline')
    mismatch = []
    for name in tracked:
        expected = [blob(repo, MAC if name in ORIGINALS else BASE, name)]
        if name == 'backend/main.py':
            expected.append(blob(repo, INDENT, name))
        path = repo / name
        if path.is_symlink() or not path.is_file() or path.read_bytes() not in expected:
            mismatch.append(name)
    for name in UPDATE:
        path = repo / name
        if any(p.is_symlink() for p in [path, *path.parents] if inside(p, repo)):
            mismatch.append(name + ' (symlink)')
        if name not in tracked and path.exists():
            mismatch.append(name + ' (untracked collision)')
    if mismatch:
        raise RuntimeError('Starting files differ; nothing applied. Preserve these files for reconciliation: ' + ', '.join(mismatch))
    return {name: blob(repo, REVIEWED, name) for name in UPDATE}


def save(backup, state):
    (backup / 'state.json').write_text(json.dumps(state, indent=2) + '\n')


def inspect(repo, name):
    return json.loads(run(['docker', 'inspect', name], repo))[0]


def context(repo):
    details = {name: inspect(repo, name) for name in CONTAINERS}
    projects = {x['Config']['Labels'].get('com.docker.compose.project') for x in details.values()}
    if len(projects) != 1 or None in projects:
        raise RuntimeError('Containers do not belong to one Compose project')
    project = projects.pop()
    config = json.loads(run(['docker', 'compose', '-f', str(repo / 'docker-compose.yml'), '-p', project, 'config', '--format', 'json'], repo))
    mounts = [m for m in details['doclens-qdrant']['Mounts'] if m['Destination'] == '/qdrant/storage']
    expected = config.get('volumes', {}).get('qdrant_server_data', {}).get('name')
    if len(mounts) != 1 or mounts[0]['Type'] != 'volume' or mounts[0].get('Name') != expected:
        raise RuntimeError('Qdrant volume differs from the expected existing Compose volume; do not recreate it')
    for name, service in zip(CONTAINERS, ('backend', 'frontend', 'qdrant')):
        if details[name]['Config']['Labels'].get('com.docker.compose.service') != service:
            raise RuntimeError('Unexpected container service identity')
    return project, mounts[0]['Name'], details


def prepare(repo, backup):
    if backup.exists() or inside(backup, repo) or inside(repo, backup):
        raise RuntimeError('Choose a new backup directory outside the checkout')
    backup.mkdir(mode=0o700)
    state = {'repo': str(repo), 'reviewed': REVIEWED, 'phase': 'backup-started'}
    save(backup, state)
    (backup / 'update-helper.py').write_bytes(Path(__file__).read_bytes())
    # Keep resolved copies too when Compose credentials are symlinks outside
    # the checkout. Preserve the original links and their targets in place.
    for name, destination in (('.env', 'root-env.private'), ('backend/.env', 'backend-env.private')):
        path = repo / name
        if path.is_file():
            (backup / destination).write_bytes(path.read_bytes())
    # Include .git, ignored credentials, all untracked backups, and generated files.
    with tarfile.open(backup / 'checkout.tgz', 'w:gz', dereference=False) as archive:
        archive.add(repo, arcname='DocLens')
    with gzip.open(backup / 'checkout.tgz', 'rb') as archive:
        while archive.read(1024 * 1024):
            pass
    print('PASS: complete private checkout backup (including ignored and untracked files)', flush=True)
    payload = check_sources(repo)
    print('PASS: all starting tracked files match the preserved Mac snapshot; original or approved indentation accepted', flush=True)
    project, volume, details = context(repo)
    # WAL files can be sparse: Docker cp may need their full logical size.
    if details['doclens-qdrant']['State']['Running']:
        sizes = run(['docker', 'exec', 'doclens-qdrant', 'find', '/qdrant/storage', '-type', 'f', '-printf', '%s\n'], repo)
        logical = sum(int(n) for n in sizes.splitlines())
        if shutil.disk_usage(backup).free < logical + 2 * 1024**3:
            raise RuntimeError('Insufficient backup-disk space for Qdrant logical file sizes plus 2 GiB reserve. Keep the checkout backup; choose a fresh destination with more space')
        state['qdrant_logical_backup_bytes'] = logical
    state.update(project=project, volume=volume,
                 images={name: value['Image'] for name, value in details.items()},
                 running={name: value['State']['Running'] for name, value in details.items()})
    tag = 'mac-backup-' + uuid.uuid4().hex[:12]
    state['image_tags'] = {}
    for name in CONTAINERS[:2]:
        target = name + ':' + tag
        run(['docker', 'image', 'tag', state['images'][name], target], repo)
        state['image_tags'][name] = target
    save(backup, state)
    # Stop writers first. Back up the existing volume cold, never create a new volume.
    run(['docker', 'stop', '-t', '60', *CONTAINERS[:2]], repo)
    run(['docker', 'stop', '-t', '60', CONTAINERS[2]], repo)
    state['phase'] = 'services-stopped'
    save(backup, state)
    print('Copying stopped Qdrant storage to the private backup; this may take several minutes', flush=True)
    run(['docker', 'cp', 'doclens-qdrant:/qdrant/storage', str(backup / 'qdrant-storage')], repo)
    storage = backup / 'qdrant-storage'
    if not storage.is_dir() or not any(storage.iterdir()):
        raise RuntimeError('Qdrant backup is empty; stop here')
    manifest = {}
    for path in storage.rglob('*'):
        if path.is_file():
            with path.open('rb') as source:
                digest = hashlib.file_digest(source, 'sha256') if hasattr(hashlib, 'file_digest') else None
                if digest is None:
                    digest = hashlib.sha256()
                    while block := source.read(1024 * 1024):
                        digest.update(block)
            manifest[str(path.relative_to(storage))] = digest.hexdigest()
    (backup / 'qdrant-backup-sha256.json').write_text(json.dumps(manifest, indent=2) + '\n')
    state['phase'] = 'backed-up'
    save(backup, state)
    # Recheck after backup: never overwrite concurrent local edits.
    if payload != check_sources(repo):
        raise RuntimeError('Sources changed during backup')
    branch = 'local/mac-reviewed-' + uuid.uuid4().hex[:12]
    git(repo, 'switch', '-c', branch)
    for name, data in payload.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    state.update(phase='prepared', branch=branch, source_sha256={k: sha(v) for k, v in payload.items()})
    save(backup, state)
    print('PASS: selective reviewed files applied on ' + branch)
    print('Backup: ' + str(backup))
    print('Services are stopped. Continue with rebuild; no source commit or merge was made.')


def load(repo, backup):
    state = json.loads((backup / 'state.json').read_text())
    if state['repo'] != str(repo) or state['reviewed'] != REVIEWED or state['phase'] not in ('prepared', 'rebuilt', 'verified'):
        raise RuntimeError('This backup is not a completed preparation for this checkout')
    if git(repo, 'branch', '--show-current').decode().strip() != state['branch']:
        raise RuntimeError('Local update branch has changed')
    for name, digest in state['source_sha256'].items():
        if sha((repo / name).read_bytes()) != digest:
            raise RuntimeError('Reviewed source changed: ' + name)
    project, volume, _ = context(repo)
    if project != state['project'] or volume != state['volume']:
        raise RuntimeError('Compose project or Qdrant volume changed')
    return state


def logged(args, repo, target):
    with target.open('wb') as log:
        result = subprocess.run(args, cwd=repo, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError('Build/start failed; private evidence: ' + str(target))


def rebuild(repo, backup):
    state = load(repo, backup)
    compose = ['docker', 'compose', '-f', str(repo / 'docker-compose.yml'), '-p', state['project']]
    logged([*compose, 'build', 'backend', 'frontend'], repo, backup / 'build.log')
    # Start the exact existing data container; do not pull or recreate Qdrant.
    run(['docker', 'start', 'doclens-qdrant'], repo)
    logged([*compose, 'up', '-d', '--no-deps', '--no-build', 'backend', 'frontend'], repo, backup / 'startup.log')
    _, volume, details = context(repo)
    if volume != state['volume'] or details['doclens-qdrant']['Image'] != state['images']['doclens-qdrant']:
        raise RuntimeError('Qdrant identity changed')
    state['phase'] = 'rebuilt'
    save(backup, state)
    print('PASS: rebuilt backend/frontend; existing Qdrant container and volume reused')
    print('Continue with verify. A successful build alone does not validate startup.')


VERIFY = r'''
import concurrent.futures, json, os, pathlib, threading, time, urllib.request, urllib.error
import fitz
from qdrant_client import QdrantClient
key=os.environ.get('DOCLENS_SESSION_SECRET')
if not key: raise RuntimeError('Backend authentication configuration missing')
base='http://127.0.0.1:8000'
for attempt in range(240):
 try:
  with urllib.request.urlopen(base+'/', timeout=2) as r:
   if json.load(r).get('message')=='DocLens API is running': break
 except Exception: time.sleep(1)
else: raise RuntimeError('Backend readiness failed after 240 attempts')
client=QdrantClient(url='http://qdrant:6333', timeout=10)
from document_publication import visible_filter
collection='document_chunks'
count=lambda: client.count(collection, exact=True).count if client.collection_exists(collection) else 0
before=count()
name='doclens-synthetic-'+str(time.time_ns())+'.pdf'
path=pathlib.Path('/tmp')/name
with fitz.open() as d:
 text='\n'.join(('Clause %02d. '%i+'Synthetic property wording supporting evidence and contractual obligations. '*2)[:120] for i in range(45))
 for i in range(40): d.new_page().insert_text((24,24),text,fontsize=5)
 path.write_bytes(d.tobytes())
with fitz.open(path) as d:
 chars=sum(len(p.get_text()) for p in d)
 if chars<200000: raise RuntimeError('Synthetic fixture is not text-heavy')
def upload(data):
 boundary='DocLensSyntheticBoundary'
 body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\nContent-Type: application/pdf\r\n\r\n'.encode()+data+f'\r\n--{boundary}--\r\n'.encode())
 request=urllib.request.Request(base+'/documents/process',body,headers={'Content-Type':'multipart/form-data; boundary='+boundary,'X-DocLens-Internal-Key':key})
 with urllib.request.urlopen(request,timeout=110) as response: return json.load(response)
latencies=[];failures=0;peak=0;start=time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
 future=pool.submit(upload,path.read_bytes())
 while not future.done():
  try:
   t=time.monotonic()
   with urllib.request.urlopen(base+'/',timeout=.5) as r:
    if r.status!=200: raise RuntimeError('Health failed')
   latencies.append(time.monotonic()-t)
  except Exception: failures+=1
  for line in pathlib.Path('/proc/1/status').read_text().splitlines():
   if line.startswith(('VmRSS:', 'VmHWM:')): peak=max(peak,int(line.split()[1]))
  time.sleep(.1)
 result=future.result()
if result.get('indexed') is not True or result.get('total_chunks',0)<1: raise RuntimeError('Synthetic indexing response invalid')
if failures or not latencies: raise RuntimeError('Health probes failed during synthetic processing')
if count()!=before+result['total_chunks']: raise RuntimeError('Unexpected point-count change; stop before customer upload')
def visible(): return {str(p.id) for p in client.scroll(collection,scroll_filter=visible_filter(client,name),limit=2000)[0]}
old=visible()
try: upload(b'%PDF-invalid synthetic replacement')
except urllib.error.HTTPError as e:
 if e.code!=400: raise
else: raise RuntimeError('Invalid replacement was accepted')
if visible()!=old: raise RuntimeError('Invalid replacement changed synthetic publication')
print(json.dumps({'pass':True,'filename':name,'pages':40,'characters':chars,'chunks':result['total_chunks'],'seconds':time.monotonic()-start,'health_samples':len(latencies),'health_failures':failures,'health_max_seconds':max(latencies),'peak_backend_rss_kib':peak,'existing_point_count':before,'after_point_count':count(),'failed_replacement_preserved_ids':True}))
client.close()
'''


def verify(repo, backup):
    state = load(repo, backup)
    if state['phase'] not in ('rebuilt', 'verified'):
        raise RuntimeError('Rebuild must succeed before verify')
    attempt = subprocess.run(['docker', 'exec', '-i', 'doclens-backend', 'python', '-'], cwd=repo, input=VERIFY.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (backup / 'verify-private-stderr.log').write_bytes(attempt.stderr)
    output = attempt.stdout
    if attempt.returncode:
        (backup / 'verify-failed-output.log').write_bytes(output)
        raise RuntimeError('Synthetic verification failed; inspect private verify-private-stderr.log and backend logs locally before sharing redacted errors')
    # Store evidence privately, never include environment variables or login data.
    (backup / 'synthetic-verification.json').write_bytes(output)
    result = json.loads(output)
    run(['docker', 'cp', 'doclens-backend:/tmp/' + result['filename'], str(backup / result['filename'])], repo)
    (backup / 'doclens-invalid-synthetic.pdf').write_bytes(b'%PDF-invalid synthetic file')
    state['phase'] = 'verified'
    save(backup, state)
    print('PASS: backend startup, dense 40-page upload, health probes, existing point count, and failed replacement')
    print(json.dumps(result, indent=2))
    print('NEXT: sign in at http://localhost:3000 and complete the browser checks in the procedure before retrying your PDF.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'rebuild', 'verify'))
    parser.add_argument('--backup', required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    repo = Path.cwd().resolve()
    backup = args.backup.expanduser().resolve()
    try:
        {'prepare': prepare, 'rebuild': rebuild, 'verify': verify}[args.phase](repo, backup)
    except Exception as error:
        print('STOP: ' + str(error), file=sys.stderr)
        print('Do not reset, clean, delete volumes, restore old readers, or retry your document. Keep the private backup and report the failed phase.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
