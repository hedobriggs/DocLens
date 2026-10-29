#!/usr/bin/env python3
"""Narrow exact-image, no-volume check; no chmod or capability escalation."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

IMAGE = 'sha256:a16cdbc1657012fd60dc1ac67b44ce9c643d16e2912e8ad4ff146a304e06bbee'
SOURCE = 'a2986c786ed50d271fb99ad787218695e9fd4d82'
ROOT = Path.home() / 'DocLens-review-a2986c7.8yU9F9'
PROBE = r'''
import hashlib, json, os, pathlib, stat
out = {'euid': os.geteuid(), 'egid': os.getegid(), 'files': []}
for name in ['/opt/frontend/package.json', '/opt/frontend/next.config.ts']:
    p = pathlib.Path(name); row = {'path': name}
    try:
        s = p.lstat()
        row.update(mode=oct(stat.S_IMODE(s.st_mode)), uid=s.st_uid,
                   gid=s.st_gid, regular=stat.S_ISREG(s.st_mode))
        if not stat.S_ISREG(s.st_mode):
            row['read_skipped'] = 'not a regular file'
        else:
            with p.open('rb') as f:
                data = f.read(1024 * 1024 + 1)
            if len(data) > 1024 * 1024:
                row['read_skipped'] = 'exceeds inspection bound'
            else:
                row.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                           elf=data.startswith(b'\x7fELF'))
    except OSError as e:
        row.update(exception=type(e).__name__, errno=e.errno, message=e.strerror)
    out['files'].append(row)
print(json.dumps(out, indent=2))
'''


def main():
    actual = subprocess.check_output(['git', '-C', str(ROOT / 'source'), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != SOURCE:
        raise SystemExit('Unexpected source; stopping.')
    identity = subprocess.check_output(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'], text=True).strip()
    if identity != IMAGE:
        raise SystemExit('Unexpected image; stopping.')
    out = Path(tempfile.mkdtemp(prefix='frontend-permissions.', dir=str(ROOT)))
    print('Evidence:', out, flush=True)
    (out / 'probe.py').write_text(PROBE)
    expected = {}
    for name in ['package.json', 'next.config.ts']:
        data = subprocess.check_output(['git', '-C', str(ROOT / 'source'), 'show', SOURCE + ':frontend/' + name])
        expected['/opt/frontend/' + name] = hashlib.sha256(data).hexdigest()
    (out / 'source-hashes.json').write_text(json.dumps(expected, indent=2))
    commands = []
    for uid in ['0:0', '1000:1000']:
        command = ['docker', 'run', '--rm', '-i', '--network', 'none', '--read-only',
                   '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                   '--pids-limit', '32', '--memory', '128m', '--cpus', '1',
                   '--user', uid, '--entrypoint', 'python', IMAGE, '-']
        commands.append(command)
        label = 'uid-' + uid.split(':')[0]
        with (out / (label + '.json')).open('w') as stdout, (out / (label + '.stderr.log')).open('w') as stderr:
            result = subprocess.run(command, input=PROBE, text=True, stdout=stdout, stderr=stderr)
        (out / (label + '.exit')).write_text(str(result.returncode) + '\n')
        if result.returncode:
            (out / 'commands.json').write_text(json.dumps(commands, indent=2))
            raise SystemExit('Probe failed; retain ' + str(out))
        data = json.loads((out / (label + '.json')).read_text())
        for row in data['files']:
            if 'sha256' in row:
                row['matches_exact_source'] = row['sha256'] == expected[row['path']]
        (out / (label + '.json')).write_text(json.dumps(data, indent=2))
    (out / 'commands.json').write_text(json.dumps(commands, indent=2))
    archive = shutil.make_archive(str(out), 'zip', root_dir=str(out))
    checksum = hashlib.sha256(Path(archive).read_bytes()).hexdigest()
    Path(archive + '.sha256').write_text(checksum + '  ' + Path(archive).name + '\n')
    print('ZIP:', archive, '\nSHA-256:', checksum)
    print('Collection only. A successful process exit does not clear recorded read errors or security findings.')


if __name__ == '__main__':
    main()
