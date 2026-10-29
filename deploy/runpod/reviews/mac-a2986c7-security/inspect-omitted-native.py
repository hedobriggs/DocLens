#!/usr/bin/env python3
"""Bounded supplement; inspect immutable binaries, never mounted user data."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

IMAGE = 'sha256:a16cdbc1657012fd60dc1ac67b44ce9c643d16e2912e8ad4ff146a304e06bbee'
SOURCE = 'a2986c786ed50d271fb99ad787218695e9fd4d82'
ROOT = Path.home() / 'DocLens-review-a2986c7.8yU9F9'
PROBE = r'''
import hashlib, json, os, pathlib, time
roots = ['/usr/local/bin', '/usr/local/sbin', '/usr/bin', '/usr/sbin', '/usr/lib', '/usr/lib64', '/opt/qdrant/lib']
out = {'roots': roots, 'files': [], 'errors': [], 'symlinks': [], 'bounded_stop': None}
start = time.monotonic(); total = 0; seen = set()
markers = [b'zipOpenNewFileInZip4_64', b'unzOpen64', b'sqlite3KeyInfoFromExprList']
class Budget(Exception): pass
def check():
    if time.monotonic() - start > 120 or total >= 2 * 1024**3 or len(seen) >= 10000:
        raise Budget('120 seconds / 2 GiB native bytes / 10000 native files limit')
def error(e):
    out['errors'].append({'path': e.filename, 'exception': type(e).__name__, 'errno': e.errno})
try:
    for root in roots:
        for directory, dirs, names in os.walk(root, onerror=error, followlinks=False):
            check()
            # Do not silently treat skipped directory symlinks as scanned.
            for name in dirs:
                p = pathlib.Path(directory) / name
                if p.is_symlink(): out['symlinks'].append({'path': str(p), 'target': os.readlink(p)})
            for name in names:
                check(); p = pathlib.Path(directory) / name
                try:
                    if p.is_symlink():
                        out['symlinks'].append({'path': str(p), 'target': os.readlink(p)})
                        continue
                    if not p.is_file(): continue
                    with p.open('rb') as f:
                        if f.read(4) != b'\x7fELF': continue
                        key = (p.stat().st_dev, p.stat().st_ino)
                        if key in seen: continue
                        seen.add(key); f.seek(0); h = hashlib.sha256(); found = set(); tail = b''
                        while True:
                            check(); block = f.read(1024 * 1024)
                            if not block: break
                            total += len(block); h.update(block); window = tail + block
                            found.update(m.decode() for m in markers if m in window)
                            tail = window[-128:]
                    out['files'].append({'path': str(p), 'bytes': p.stat().st_size,
                        'sha256': h.hexdigest(), 'markers': sorted(found)})
                except OSError as e: error(e)
except Budget as e: out['bounded_stop'] = str(e)
out.update(elapsed_seconds=time.monotonic()-start, native_bytes_read=total)
out['coverage_complete'] = out['bounded_stop'] is None and not out['errors']
out['limitations'] = 'Symlinks are recorded, not followed. Missing markers do not prove absent static/stripped code. Selected roots only.'
print(json.dumps(out, indent=2))
'''


def main():
    actual = subprocess.check_output(['git', '-C', str(ROOT / 'source'), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != SOURCE:
        raise SystemExit('Unexpected source; no probe started.')
    identity = subprocess.check_output(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'], text=True).strip()
    if identity != IMAGE:
        raise SystemExit('Unexpected image; no probe started.')
    out = Path(tempfile.mkdtemp(prefix='native-supplement.', dir=str(ROOT)))
    print('Evidence:', out, flush=True)
    name = 'doclens-native-probe-' + uuid.uuid4().hex
    command = ['docker', 'run', '--rm', '--name', name, '-i', '--network', 'none', '--read-only',
               '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
               '--pids-limit', '32', '--memory', '256m', '--cpus', '1',
               '--entrypoint', 'python', IMAGE, '-']
    (out / 'probe.py').write_text(PROBE)
    (out / 'command.json').write_text(json.dumps(command, indent=2))
    with (out / 'inventory.json').open('w') as stdout, (out / 'stderr.log').open('w') as stderr:
        try:
            result = subprocess.run(command, input=PROBE, text=True, stdout=stdout, stderr=stderr, timeout=180)
        except subprocess.TimeoutExpired:
            cleanup = subprocess.run(['docker', 'rm', '-f', name], capture_output=True, text=True)
            (out / 'timeout-cleanup.json').write_text(json.dumps({
                'command': ['docker', 'rm', '-f', name], 'exit': cleanup.returncode,
                'stdout': cleanup.stdout, 'stderr': cleanup.stderr}, indent=2))
            (out / 'exit.txt').write_text('Docker CLI timed out; own unique probe cleanup attempted; inspect cleanup evidence before retry.\n')
            raise SystemExit('Docker CLI timeout; retain ' + str(out))
    (out / 'exit.txt').write_text(str(result.returncode) + '\n')
    if result.returncode:
        raise SystemExit('Probe failed; retain ' + str(out))
    json.loads((out / 'inventory.json').read_text())
    archive = shutil.make_archive(str(out), 'zip', root_dir=str(out))
    digest = hashlib.sha256(Path(archive).read_bytes()).hexdigest()
    Path(archive + '.sha256').write_text(digest + '  ' + Path(archive).name + '\n')
    print('ZIP:', archive, '\nSHA-256:', digest)
    print('Collection only; inspect errors and bounded_stop before interpreting coverage.')


if __name__ == '__main__':
    main()
