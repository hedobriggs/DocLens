#!/usr/bin/env python3
"""Run only remaining baked UI expiry/render gates. No rebuild/runtime mounts."""
import ast
import getpass
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import zipfile

ROOT = Path.home() / 'DocLens-fixed-build.Xmet07'
SOURCE = ROOT / 'source'
OUT = Path(__file__).resolve().parent
IMAGE = 'sha256:4e3a0339cb5e1465701f757ca136039c369ab96fa672401a938e3efa0e5467d8'
COMMIT = '299f3b48bbcd1058845ce14f528fba553d68a783'


def read(args):
    return subprocess.check_output(args, text=True).strip()


def inventory():
    return {kind: read(['docker', *args]).splitlines() for kind, args in {
        'containers': ['ps', '-a', '--format', '{{.ID}} {{.Names}} {{.State}}'],
        'volumes': ['volume', 'ls', '--format', '{{.Name}}']}.items()}


def main():
    os.umask(0o077)
    if OUT.parent != ROOT or not OUT.name.startswith('focus.'):
        raise SystemExit('Use a new focus.* folder under the isolated review folder.')
    if (OUT/'host-results.json').exists():
        raise SystemExit('Attempt already has results; use a NEW folder, preserve this attempt.')
    state = {'image': IMAGE, 'source': COMMIT, 'scope': 'Monitoring-only collector correction; prior question/upload/Prometheus passes retained', 'limitations': ['Held requests are before backend admission, not proof of cancelling accepted processing.', 'Clock scenarios simulate browser time using a valid server-verified short session.', 'Full Compose and actual RunPod/Safari/VoiceOver remain outside this batch.', 'Grafana Go provenance and remaining 137 open original security entries unchanged.']}
    key = os.environ.get('GEMINI_API_KEY', '')
    try:
        original = ROOT/'focus.66Jlsq.zip'
        if not original.is_file() or hashlib.sha256(original.read_bytes()).hexdigest() != '85dd9a97ef9558cdc0efc3f826d2add0c14353a91853ed2592d879e252dc4b26':
            raise RuntimeError('Original failed-run archive missing or checksum mismatch; nothing started.')
        shutil.copyfile(original, OUT/'original-focus.66Jlsq.zip')
        second = ROOT/'focus.d0yA5Q.zip'
        if not second.is_file() or hashlib.sha256(second.read_bytes()).hexdigest() != 'f44a1f1cfedd91268caca2c7a89c5849173a4e0f46f9aa57e11bfca5be0a6adc':
            raise RuntimeError('Second failed-run archive missing or checksum mismatch; nothing started.')
        shutil.copyfile(second, OUT/'original-focus.d0yA5Q.zip')
        third = ROOT/'focus.xMLqet.zip'
        if not third.is_file() or hashlib.sha256(third.read_bytes()).hexdigest() != '66bc705a5d6390d3e591473bd8bb018aa673569c31a07d631abf5719b8bdc804':
            raise RuntimeError('Third archive absent or changed; nothing started.')
        shutil.copyfile(third, OUT/'original-focus.xMLqet.zip')
        state['original_evidence_sha256'] = hashlib.sha256(original.read_bytes()).hexdigest()
        if platform.system() != 'Darwin' or platform.machine() != 'x86_64':
            raise RuntimeError('Expected Intel Mac.')
        if read(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD']) != COMMIT or read(['git', '-C', str(SOURCE), 'status', '--porcelain', '--untracked-files=no']):
            raise RuntimeError('Unexpected/modified source; nothing reset.')
        if not read(['docker', 'context', 'inspect', '--format', '{{.Endpoints.docker.Host}}']).startswith('unix://') or os.environ.get('DOCKER_HOST', '').startswith(('tcp:', 'ssh:')):
            raise RuntimeError('Expected local Docker.')
        if read(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}']) != IMAGE:
            raise RuntimeError('Exact image absent; do not rebuild.')
        cpu, memory = map(int, read(['docker', 'info', '--format', '{{.NCPU}} {{.MemTotal}}']).split())
        if cpu < 2 or memory < 3.5 * 1024**3 or shutil.disk_usage(ROOT).free < 5 * 1024**3:
            raise RuntimeError('Insufficient resources; no settings changed.')
        if read(['docker', 'ps', '-q']):
            raise RuntimeError('Other workloads running; none stopped.')
        cache = ROOT / 'acceptance.vW5s1h/browser-cache'
        if not cache.is_dir() or not (SOURCE/'frontend/node_modules/playwright').is_dir():
            raise RuntimeError('Previous batch browser prerequisites missing; no automatic reinstallation.')
        state['before'] = inventory()
        state['host'] = {'platform': platform.platform(), 'cpu': cpu, 'memory': memory, 'node': read(['node', '--version'])}
        fixture = ast.parse((SOURCE/'deploy/portable/smoke.py').read_text())
        namespace = {}
        exec(compile(ast.Module(body=[n for n in fixture.body if isinstance(n, ast.FunctionDef) and n.name == 'pdf'], type_ignores=[]), '<synthetic fixture>', 'exec'), namespace)
        pdf = OUT/'synthetic-focus.pdf'
        pdf.write_bytes(namespace['pdf'](['Aster Research employed Alex as a research analyst.']))
        key = key or getpass.getpass('Gemini key locally (hidden, needed for real question recovery): ')
        if not key or any(c in key for c in '\r\n\0'):
            raise RuntimeError('Valid private key binding required; no trial started.')
        env = dict(os.environ)
        for name in ['NODE_OPTIONS', 'DOCLENS_MONITORING_RUNTIME', 'DOCLENS_TEST_CA']:
            env.pop(name, None)
        env.update(GEMINI_API_KEY=key, DOCLENS_FOCUS_OUT=str(OUT), DOCLENS_FOCUS_SOURCE=str(SOURCE), DOCLENS_FOCUS_PDF=str(pdf), PLAYWRIGHT_BROWSERS_PATH=str(cache))
        command = ['node', str(OUT/'focused-browser.cjs')]
        (OUT/'command.json').write_text(json.dumps(command, indent=2))
        with (OUT/'browser.log').open('w') as log:
            result = subprocess.run(command, env=env, cwd=SOURCE, stdout=log, stderr=subprocess.STDOUT, text=True)
        state['exit'] = result.returncode
        (OUT/'browser.exit').write_text(str(result.returncode)+'\n')
        state['status'] = 'PASS' if result.returncode == 0 else 'FAIL'
        if result.returncode == 0:
            details = json.loads((OUT/'results.json').read_text())
            expected = set()
            if details.get('image') != IMAGE or {x.get('scenario') for x in details.get('scenarios', [])} != expected or any(x.get('status') != 'PASS' for x in details['scenarios']):
                raise RuntimeError('Missing or inconsistent expiry evidence despite process exit zero.')
            if details.get('monitoring', {}).get('grafana', {}).get('status') != 'PASS' or details.get('monitoring', {}).get('prometheus', {}).get('status') != 'PREVIOUSLY_PASSED':
                raise RuntimeError('Missing successful rendered monitoring evidence.')
        print('Focused tests:', state['status'])
        if result.returncode:
            print((OUT/'browser.log').read_text(errors='replace')[-6000:].replace(key, '[REDACTED]'))
    except Exception as e:
        state['status'] = 'BLOCKED'
        state['error'] = str(e).replace(key, '[REDACTED]') if key else str(e)
        print('STOP:', state['error'])
    finally:
        try:
            state['after'] = inventory()
            if 'before' in state:
                state['preexisting_preserved'] = {k:set(v).issubset(state['after'][k]) for k,v in state['before'].items()}
                state['new_remaining_objects'] = {k:sorted(set(state['after'][k])-set(v)) for k,v in state['before'].items()}
                if not all(state['preexisting_preserved'].values()):
                    state['status'] = 'FAIL';state['inventory_error'] = 'Pre-existing objects changed; no repair attempted.'
        except Exception as e:
            state['inventory_error'] = type(e).__name__;state['status'] = 'FAIL'
        (OUT/'host-results.json').write_text(json.dumps(state, indent=2))
        archive = OUT.parent/(OUT.name+'.zip')
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
            for p in sorted(OUT.rglob('*')):
                if p.is_file():
                    data = p.read_bytes()
                    if key:data = data.replace(key.encode(), b'[REDACTED]')
                    z.writestr(str(p.relative_to(OUT)), data)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        Path(str(archive)+'.sha256').write_text(digest+'  '+archive.name+'\n')
        print('ZIP:', archive, '\nSHA-256:', digest, '\nSecurity/release approval remains blocked.')
    raise SystemExit(0 if state.get('status') == 'PASS' else 1)


if __name__ == '__main__':
    main()
