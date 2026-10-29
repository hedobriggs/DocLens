#!/usr/bin/env python3
"""Collect from the exact synthetic candidate; never attach application volumes."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

IMAGE = 'sha256:a16cdbc1657012fd60dc1ac67b44ce9c643d16e2912e8ad4ff146a304e06bbee'
SOURCE = 'a2986c786ed50d271fb99ad787218695e9fd4d82'
ROOT = Path.home() / 'DocLens-review-a2986c7.8yU9F9'

# This inspects a new, read-only container with no application data mounted.
# Symbol absence cannot prove absence of statically linked or stripped code.
PROBE = r'''
import hashlib, importlib.metadata, json, os, pathlib, sqlite3, subprocess, zlib
out = {'sqlite_runtime': sqlite3.sqlite_version, 'zlib_runtime': zlib.ZLIB_RUNTIME_VERSION,
       'sqlite_compile_options': list(sqlite3.connect(':memory:').execute('pragma compile_options')),
       'packages': [], 'native_files': [], 'errors': []}
out['dpkg'] = subprocess.run(['dpkg-query', '-W', '-f=${binary:Package}\t${Version}\n'],
    capture_output=True, text=True, check=True).stdout
for d in importlib.metadata.distributions():
    out['packages'].append({'name': d.metadata['Name'], 'version': d.version})
markers = [b'zipOpenNewFileInZip4_64', b'zipOpenNewFileInZip4', b'unzOpen64',
           b'sqlite3KeyInfoFromExprList', b'SQLite format 3']
roots = ['/usr/local/lib', '/usr/lib/x86_64-linux-gnu', '/opt/qdrant',
         '/opt/grafana', '/opt/prometheus', '/opt/frontend']
seen = set()
for root in roots:
    for directory, _, files in os.walk(root):
        for name in files:
            p = pathlib.Path(directory) / name
            try:
                if p.is_symlink(): continue
                with p.open('rb') as f:
                    if f.read(4) != b'\x7fELF': continue
                    real = str(p.resolve())
                    if real in seen: continue
                    seen.add(real); f.seek(0); digest = hashlib.sha256(); found = set(); tail = b''
                    while True:
                        block = f.read(1024 * 1024)
                        if not block: break
                        digest.update(block); window = tail + block
                        found.update(m.decode() for m in markers if m in window)
                        tail = window[-128:]
                out['native_files'].append({'path': str(p), 'bytes': p.stat().st_size,
                    'sha256': digest.hexdigest(), 'markers': sorted(found)})
            except (OSError, ValueError) as e:
                out['errors'].append({'path': str(p), 'exception': type(e).__name__})
out['loaded_mappings_after_sqlite_import'] = pathlib.Path('/proc/self/maps').read_text()
print(json.dumps(out, indent=2))
'''


def main():
    if not ROOT.is_dir():
        raise SystemExit('Expected isolated review folder is missing; no action taken.')
    actual = subprocess.check_output(['git', '-C', str(ROOT / 'source'), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != SOURCE:
        raise SystemExit('Unexpected source commit; no action taken.')
    identity = subprocess.check_output(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'], text=True).strip()
    if identity != IMAGE:
        raise SystemExit('Unexpected image; no action taken.')
    output = Path(tempfile.mkdtemp(prefix='native-assessment.', dir=str(ROOT)))
    print('Evidence folder:', output, flush=True)
    cache = ROOT / 'security.RoWmtn' / 'cache' / 'db' / 'metadata.json'
    if cache.is_file():
        data = cache.read_bytes()
        json.loads(data)  # Preserve the original bytes; do not refresh this DB.
        (output / 'original-cache-db-metadata.json').write_bytes(data)
        (output / 'cache-provenance.json').write_text(json.dumps({
            'path': str(cache), 'mtime_ns': cache.stat().st_mtime_ns,
            'sha256': hashlib.sha256(data).hexdigest(),
            'note': 'Current bytes at original cache path; compare dates with original scan. Unchanged since scan is not assumed.'
        }, indent=2))
    else:
        (output / 'original-cache-unavailable.txt').write_text(
            'Original DB metadata unavailable at expected cache path. No fresh scan performed.\n')
    command = ['docker', 'run', '--rm', '-i', '--network', 'none', '--read-only',
               '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
               '--pids-limit', '64', '--memory', '512m', '--cpus', '1',
               '--entrypoint', 'python', IMAGE, '-']
    (output / 'commands.json').write_text(json.dumps({'source': SOURCE, 'image': IMAGE, 'probe_command': command}, indent=2))
    (output / 'probe.py').write_text(PROBE)
    with (output / 'native-inventory.json').open('w') as stdout, (output / 'probe.stderr.log').open('w') as stderr:
        result = subprocess.run(command, input=PROBE, text=True, stdout=stdout, stderr=stderr)
    (output / 'probe.exit').write_text(str(result.returncode) + '\n')
    if result.returncode:
        raise SystemExit('Probe failed; retain this evidence folder. No automatic retry.')
    inventory = json.loads((output / 'native-inventory.json').read_text())
    (output / 'collection-status.txt').write_text(
        'Collection only, not security clearance or functional acceptance.\n'
        'Probe filesystem errors: ' + str(len(inventory['errors'])) + '\n'
        'No application volumes, secrets or ports supplied. Original failed-run logs not inferred.\n')
    archive = shutil.make_archive(str(output), 'zip', root_dir=str(output))
    digest = hashlib.sha256(Path(archive).read_bytes()).hexdigest()
    Path(archive + '.sha256').write_text(digest + '  ' + Path(archive).name + '\n')
    print('ZIP:', archive, '\nSHA-256:', digest)


if __name__ == '__main__':
    main()
