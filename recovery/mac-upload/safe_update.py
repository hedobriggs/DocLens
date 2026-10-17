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


def private_bytes(path, data):
    """New sensitive artifact only; never follow or overwrite an existing path."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as target:
        target.write(data)


def file_sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def private_docker(repo, folder, label, args, *, source=None, destination=None):
    """Stream archives to disk; stdout/stderr may contain credentials."""
    from contextlib import ExitStack
    with ExitStack() as stack:
        incoming = stack.enter_context(source.open('rb')) if source else subprocess.DEVNULL
        outgoing = subprocess.PIPE
        if destination:
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            outgoing = stack.enter_context(os.fdopen(fd, 'wb'))
        result = subprocess.run(['docker', *args], cwd=repo, stdin=incoming,
                                stdout=outgoing, stderr=subprocess.PIPE)
    private_bytes(folder / (label + '.stderr.private'), result.stderr)
    if result.returncode or (destination and result.stderr.strip()):
        raise RuntimeError('Frontend recovery ' + label + ' failed; inspect private evidence locally')
    return result.stdout or b''


def image_available(repo, image):
    result = subprocess.run(['docker', 'image', 'inspect', image], cwd=repo,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        if result.returncode == 1 and (b'No such image:' in result.stderr or b'No such object:' in result.stderr):
            return False
        raise RuntimeError('Image availability check failed; no recovery fallback attempted')
    if json.loads(result.stdout)[0]['Id'] != image:
        raise RuntimeError('Image identity mismatch')
    return True


def private_backup(repo, backup):
    info = backup.lstat()
    if backup.is_symlink() or not backup.is_dir() or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError('Recovery requires an owned private backup directory (mode 700)')
    if inside(backup, repo) or inside(repo, backup):
        raise RuntimeError('Recovery backup must be outside the checkout')


def compose_literal(value):
    # Compose interpolates dollars even in JSON. Preserve literal credentials,
    # commands and paths, including $ and ${...}, without putting them in argv.
    if isinstance(value, str):
        return value.replace('$', '$$')
    if isinstance(value, list):
        return [compose_literal(v) for v in value]
    if isinstance(value, dict):
        return {k: compose_literal(v) for k, v in value.items()}
    return value


FRONTEND_PROBE = r'''
const http=require('node:http');
function get(path,method){return new Promise((resolve,reject)=>{
 const r=http.request({host:'127.0.0.1',port:3000,path,method,timeout:2000},res=>{
  let body='';res.on('data',x=>{body+=x;if(body.length>1048576)r.destroy(new Error('Response too large'))});
  res.on('end',()=>resolve({status:res.statusCode,type:res.headers['content-type']||'',body}));res.on('error',reject);
 });r.on('timeout',()=>r.destroy(new Error('Timeout')));r.on('error',reject);r.end();
})}
(async()=>{try{
 const root=await get('/','GET'),denied=await get('/api/documents/process','POST');
 if(root.status!==200||!root.type.includes('text/html')||!root.body.toLowerCase().includes('<html')||denied.status!==401)throw new Error('Frontend contract failed');
 console.log(JSON.stringify({root_status:root.status,html:true,anonymous_upload_status:denied.status}));
}catch(e){process.exitCode=1}})();
'''


def archive_inventory(path):
    """Compare mounted contents/ownership without exposing names or bytes."""
    result = {}
    with tarfile.open(path) as archive:
        for member in archive:
            if (member.name.startswith('/') or '..' in Path(member.name).parts or
                not (member.isfile() or member.isdir() or member.issym() or member.islnk())):
                raise RuntimeError('Unsupported entry in frontend mount snapshot')
            digest = hashlib.sha256()
            if member.isfile():
                with archive.extractfile(member) as source:
                    while block := source.read(1024 * 1024):
                        digest.update(block)
            result[member.name.rstrip('/')] = [member.type.decode(), member.mode, member.uid,
                member.gid, member.linkname, digest.hexdigest() if member.isfile() else None]
    return result


def restore_frontend_capture(repo, folder):
    """Rebuild only from private artifacts; never use the missing original image."""
    manifest = json.loads((folder / 'manifest.private.json').read_text())
    for name, digest in manifest['files'].items():
        if Path(name).name != name or file_sha(folder / name) != digest:
            raise RuntimeError('Frontend recovery artifact integrity check failed')
    original = json.loads((folder / 'container-inspect.private.json').read_text())
    runtime = manifest['runtime']
    token = uuid.uuid4().hex
    base_tag = 'doclens-private-frontend:rootfs-' + token
    restored_tag = 'doclens-private-frontend:filesystem-' + token
    final_tag = 'doclens-private-frontend:verified-' + token
    bootstrap = 'doclens-private-restore-' + token
    project = 'doclens-private-probe-' + token
    probe_name = project + '-frontend'
    compose_file = folder / ('probe-' + token + '.private.json')
    created_bootstrap = created_probe = False
    try:
        imported = private_docker(repo, folder, token+'-import',
            ['import', '--platform', runtime['platform']+'/'+runtime['arch'], '-', base_tag], source=folder/'rootfs.private.tar').decode().strip()
        if not imported.startswith('sha256:'):
            raise RuntimeError('Frontend recovery import did not return an image identity')
        private_docker(repo, folder, token+'-create-bootstrap', [
            'create', '--pull', 'never', '--name', bootstrap, '--network', 'none', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--memory', '512m', '--cpus', '1',
            '--entrypoint', runtime['execPath'], imported, '-e',
            'setInterval(()=>{},1000);process.on("SIGTERM",()=>process.exit(0))'])
        created_bootstrap = True
        if inspect(repo, bootstrap)['Mounts']:
            raise RuntimeError('Recovery bootstrap unexpectedly has mounts')
        run(['docker', 'start', bootstrap], repo)
        for i, mount in enumerate(manifest['mounts']):
            destination = mount['Destination']
            # This removes only copied image paths in our new, unmounted,
            # network-isolated bootstrap. Never operate on original mounts.
            run(['docker', 'exec', '--user', '0', bootstrap, runtime['execPath'], '-e',
                 'const fs=require("fs"),p=require("path"),d=process.argv[1];fs.rmSync(d,{recursive:true,force:true});fs.mkdirSync(p.dirname(d),{recursive:true})', destination], repo)
            private_docker(repo, folder, token+f'-restore-mount-{i}',
                ['cp', '-a', '-', bootstrap+':'+str(Path(destination).parent)], source=folder/mount['archive'])
            checked = folder / (token+f'-restored-mount-{i}.private.tar')
            private_docker(repo, folder, token+f'-read-restored-mount-{i}',
                ['cp', bootstrap+':'+destination, '-'], destination=checked)
            if archive_inventory(checked) != archive_inventory(folder/mount['archive']):
                raise RuntimeError('Recovered mounted data/ownership did not match the snapshot')
        run(['docker', 'stop', '-t', '10', bootstrap], repo)
        restored = private_docker(repo, folder, token+'-commit-restored',
            ['commit', bootstrap, restored_tag]).decode().strip()
        config = original['Config']
        environment = {}
        for assignment in config.get('Env') or []:
            key, sep, value = assignment.partition('=')
            if not sep or key in environment:
                raise RuntimeError('Unsupported duplicate or invalid frontend environment entry')
            environment[key] = value
        service = {
            'image': restored, 'container_name': probe_name, 'network_mode': 'none',
            'entrypoint': config.get('Entrypoint') or [], 'command': config.get('Cmd') or [],
            'working_dir': config.get('WorkingDir') or '/', 'user': config.get('User') or '',
            'environment': environment, 'restart': 'no', 'cap_drop': ['ALL'],
            'security_opt': ['no-new-privileges:true'], 'mem_limit': '512m', 'cpus': 1,
        }
        private_bytes(compose_file, json.dumps(compose_literal({'services': {'frontend': service}})).encode())
        args = ['compose', '--env-file', os.devnull, '-f', str(compose_file), '-p', project]
        # create and inspect isolation before executing the captured command.
        private_docker(repo, folder, token+'-create-probe', [*args, 'create', '--no-build', '--pull', 'never', 'frontend'])
        created_probe = True
        probe = inspect(repo, probe_name)
        if (probe['Mounts'] or probe['HostConfig']['NetworkMode'] != 'none' or
            probe['HostConfig'].get('PortBindings') or probe['HostConfig']['Privileged']):
            raise RuntimeError('Recovery probe isolation check failed')
        replay_env = dict(item.split('=', 1) for item in probe['Config'].get('Env') or [])
        if any(replay_env.get(k) != v for k, v in environment.items()):
            raise RuntimeError('Recovery environment was not preserved exactly')
        # Commit the stopped runtime-configured container, then test the final
        # image's defaults. The filesystem bootstrap command is never advertised
        # as a runnable frontend recovery image.
        final_image = private_docker(repo, folder, token+'-commit-runtime',
            ['commit', probe_name, final_tag]).decode().strip()
        run(['docker', 'rm', '-f', probe_name], repo)
        created_probe = False
        private_docker(repo, folder, token+'-create-default-probe', [
            'create', '--pull', 'never', '--name', probe_name, '--network', 'none', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges', '--memory', '512m', '--cpus', '1', final_image])
        created_probe = True
        probe = inspect(repo, probe_name)
        if (probe['Mounts'] or probe['HostConfig']['NetworkMode'] != 'none' or
            probe['HostConfig'].get('PortBindings') or probe['HostConfig']['Privileged'] or
            probe['Config']['Cmd'] != config.get('Cmd') or
            (probe['Config'].get('Entrypoint') or []) != (config.get('Entrypoint') or []) or
            probe['Config'].get('WorkingDir') != (config.get('WorkingDir') or '/') or
            (probe['Config'].get('User') or '') != (config.get('User') or '')):
            raise RuntimeError('Final frontend recovery defaults/isolation did not match')
        final_env = dict(item.split('=', 1) for item in probe['Config'].get('Env') or [])
        if any(final_env.get(k) != v for k, v in environment.items()):
            raise RuntimeError('Final frontend recovery environment changed')
        run(['docker', 'start', probe_name], repo)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            attempt = subprocess.run(['docker', 'exec', probe_name, runtime['execPath'], '-e', FRONTEND_PROBE], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if attempt.returncode == 0:
                contract = json.loads(attempt.stdout)
                if contract != {'root_status':200, 'html':True, 'anonymous_upload_status':401}:
                    raise RuntimeError('Recovery probe returned an unexpected result')
                break
            if not inspect(repo, probe_name)['State']['Running']:
                raise RuntimeError('Recovered frontend exited; inspect private probe logs')
            time.sleep(.25)
        else:
            raise RuntimeError('Recovered frontend startup/anonymous-auth probe failed')
        # Retain private logs, never print a captured application's output.
        logs = subprocess.run(['docker', 'logs', probe_name], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        private_bytes(folder / (token+'-probe-log.private'), logs.stdout+logs.stderr)
        return {'image_tag': final_tag, 'restored_image_id': final_image,
                'filesystem_image_tag': restored_tag,
                'rootfs_image_tag': base_tag, 'verified': True, 'probe': contract,
                'capture_dir': str(folder), 'source_container_id': original['Id'],
                'source_image_id': original['Image']}
    finally:
        # Clean up only helper-created isolated containers. Keep private images
        # and artifacts for recovery; never delete originals, volumes or tags.
        if created_probe:
            logs = subprocess.run(['docker', 'logs', probe_name], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            path = folder / (token+'-final-probe-log.private')
            private_bytes(path, logs.stdout+logs.stderr)
            run(['docker', 'rm', '-f', probe_name], repo)
        if created_bootstrap:
            run(['docker', 'rm', '-f', bootstrap], repo)


def capture_frontend(repo, backup, *, quiescent_mounts=False, expected_image=None, expected_container=None):
    private_backup(repo, backup)
    original = inspect(repo, 'doclens-frontend')
    if (expected_image is not None and original['Image'] != expected_image) or (expected_container is not None and original['Id'] != expected_container):
        raise RuntimeError('Running frontend identity does not match the expected original; nothing captured or paused')
    if not original['State']['Running'] or original['State'].get('Paused'):
        raise RuntimeError('Frontend recovery requires the original container running and unpaused')
    mounts = sorted(original.get('Mounts') or [], key=lambda m: m['Destination'].count('/'))
    if mounts and not quiescent_mounts:
        raise RuntimeError('Frontend has mounts; quiesce outside writers and explicitly declare --quiescent-mounts before capture')
    for mount in mounts:
        destination = mount['Destination']
        parts = Path(destination).parts
        if (mount['Type'] not in ('bind', 'volume') or not destination.startswith('/') or
            '..' in parts or destination == '/' or parts[1] in ('proc','sys','dev','bin','sbin','usr','lib','lib64')):
            raise RuntimeError('Unsupported frontend mount; requires a separate recovery plan')
        if mount['Type'] == 'bind' and inside(backup, Path(mount['Source']).resolve()):
            raise RuntimeError('Backup directory is inside a frontend bind mount')
    runtime = json.loads(run(['docker','exec',original['Id'],'node','-p',
        '(()=>{const s=require("fs").statfsSync("/");return JSON.stringify({arch:process.arch,platform:process.platform,execPath:process.execPath,freeBytes:s.bavail*s.bsize})})()'],repo))
    if runtime['platform'] != 'linux' or runtime['arch'] not in ('x64','arm64'):
        raise RuntimeError('Unsupported frontend recovery platform')
    runtime['arch'] = {'x64':'amd64','arm64':'arm64'}[runtime['arch']]
    folder = backup / ('frontend-recovery-'+uuid.uuid4().hex)
    folder.mkdir(mode=0o700)
    private_bytes(folder/'container-inspect.private.json',json.dumps(original).encode())
    private_bytes(folder/'recovery-helper.private.py',Path(__file__).read_bytes())
    paused = False
    captures = []
    try:
        run(['docker','pause',original['Id']],repo)
        paused = True
        private_docker(repo,folder,'export',['export',original['Id']],destination=folder/'rootfs.private.tar')
        for i, mount in enumerate(mounts):
            archive = f'mount-{i}.private.tar'
            check = f'mount-{i}-check.private.tar'
            for filename in (archive,check):
                private_docker(repo,folder,filename,['cp',original['Id']+':'+mount['Destination'],'-'],destination=folder/filename)
            if file_sha(folder/archive) != file_sha(folder/check):
                raise RuntimeError('Frontend mounted files changed during capture; recovery is not verified')
            archive_inventory(folder/archive)
            captures.append({'Destination':mount['Destination'],'archive':archive})
        current = inspect(repo,'doclens-frontend')
        identity = {'container':current['Id'] == original['Id'],
                    'configuration':current['Config'] == original['Config'],
                    'mounts':sorted(current['Mounts'], key=lambda m:m['Destination']) == sorted(original['Mounts'], key=lambda m:m['Destination'])}
        private_bytes(folder/'identity-check.private.json',json.dumps(identity).encode())
        if not all(identity.values()):
            raise RuntimeError('Frontend identity/configuration changed during capture')
    finally:
        if paused:
            run(['docker','unpause',original['Id']],repo)
    # Import/commit/probes may duplicate layers (especially Docker's vfs driver).
    # This is a conservative preflight, not a concurrent disk-space guarantee.
    logical = (folder/'rootfs.private.tar').stat().st_size + sum((folder/m['archive']).stat().st_size for m in captures)
    if runtime.get('freeBytes', 0) < 8*logical + 512*1024**2:
        raise RuntimeError('Insufficient Docker filesystem space for isolated frontend recovery; original was unpaused')
    if shutil.disk_usage(folder).free < 2*logical + 512*1024**2:
        raise RuntimeError('Insufficient backup disk space for frontend recovery verification; original was unpaused')
    files = {p.name:file_sha(p) for p in folder.iterdir() if p.is_file()}
    private_bytes(folder/'manifest.private.json',json.dumps({'files':files,'runtime':runtime,'mounts':captures}).encode())
    recovery = restore_frontend_capture(repo,folder)
    after = inspect(repo,'doclens-frontend')
    if after['Id'] != original['Id'] or not after['State']['Running'] or after['State'].get('Paused'):
        raise RuntimeError('Original frontend did not remain running after recovery verification')
    private_bytes(folder/'verified.private.json',json.dumps(recovery).encode())
    print('PASS: private frontend recovery captured and isolated startup/auth probe verified; original remains running',flush=True)
    return recovery


def preserve_frontend(repo, backup, *, quiescent_mounts=False, expected_image=None):
    """Capture-only phase for the failed old preparation; no source or service stop."""
    private_backup(repo,backup)
    state = json.loads((backup/'state.json').read_text())
    if state.get('repo') != str(repo) or state.get('reviewed') != REVIEWED or state.get('phase') != 'backup-started':
        raise RuntimeError('Capture-only requires the original failed preparation backup')
    # Never overwrite the old state, helper, checkout archive or credential copies.
    if expected_image is None:
        raise RuntimeError('Capture-only requires --expected-frontend-image from the reported original container')
    recovery = capture_frontend(repo,backup,quiescent_mounts=quiescent_mounts,expected_image=expected_image)
    print('Private recovery directory: ' + recovery['capture_dir'])


def verify_frontend_recovery(repo, backup):
    """Reconstruct from a private capture, without the original image/container."""
    private_backup(repo, backup)
    recovery = restore_frontend_capture(repo, backup)
    private_bytes(backup/('reverified-'+uuid.uuid4().hex+'.private.json'),json.dumps(recovery).encode())
    print('PASS: frontend recovery reverified from private artifacts; no original container or mount used')


def prepare(repo, backup, *, quiescent_mounts=False):
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
        save(backup, state)
        if image_available(repo, state['images'][name]):
            run(['docker', 'image', 'tag', state['images'][name], target], repo)
            state['image_tags'][name] = target
        elif name == 'doclens-frontend':
            recovery = capture_frontend(repo, backup, quiescent_mounts=quiescent_mounts, expected_image=state['images'][name], expected_container=details[name]['Id'])
            if not recovery.get('verified') or recovery.get('source_image_id') != state['images'][name] or recovery.get('source_container_id') != details[name]['Id']:
                raise RuntimeError('Frontend recovery identity/verification did not match')
            state['frontend_recovery'] = recovery
            state['image_tags'][name] = recovery['image_tag']
        else:
            raise RuntimeError('Backend original image is unavailable; stop for a separate recovery plan')
        save(backup, state)
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
    parser.add_argument('phase', choices=('prepare', 'rebuild', 'verify', 'preserve-frontend', 'verify-frontend-recovery'))
    parser.add_argument('--backup', required=True, type=Path)
    parser.add_argument('--quiescent-mounts', action='store_true', help='Declare all outside writers to frontend mounts are quiesced; required for mounted-file capture')
    parser.add_argument('--expected-frontend-image', help='Required for capture-only: the original reported frontend image ID')
    args = parser.parse_args()
    os.umask(0o077)
    repo = Path.cwd().resolve()
    backup = args.backup.expanduser().resolve()
    try:
        if args.phase == 'preserve-frontend':
            preserve_frontend(repo,backup,quiescent_mounts=args.quiescent_mounts,expected_image=args.expected_frontend_image)
        elif args.expected_frontend_image:
            raise RuntimeError('--expected-frontend-image applies only to capture-only')
        elif args.phase == 'prepare':
            prepare(repo,backup,quiescent_mounts=args.quiescent_mounts)
        else:
            if args.quiescent_mounts:
                raise RuntimeError('--quiescent-mounts applies only to frontend capture/preparation')
            {'rebuild':rebuild,'verify':verify,'verify-frontend-recovery':verify_frontend_recovery}[args.phase](repo,backup)
    except Exception as error:
        print('STOP: ' + str(error), file=sys.stderr)
        print('Do not reset, clean, delete volumes, restore old readers, or retry your document. Keep the private backup and report the failed phase.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
