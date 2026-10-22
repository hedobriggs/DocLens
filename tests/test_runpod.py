"""Synthetic single-container integration test; no RunPod account required.
Run: python3 tests/test_runpod.py [--live-answers]
Creates/removes only its randomly named container and synthetic volume.
"""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
# Reuse the exact portable PDF generator, without executing the CLI smoke test.
module = ast.parse((ROOT / 'deploy/portable/smoke.py').read_text())
namespace = {}
exec(compile(ast.Module(body=[n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'pdf'], type_ignores=[]), '<portable PDF fixture>', 'exec'), namespace)
pdf = namespace['pdf']
EMPLOYERS = ['Aster Research', 'Birch Analytics', 'Cobalt Systems', 'Delta Robotics', 'Elm Computing']
name = 'doclens-runpod-test-' + uuid.uuid4().hex[:10]
volume = name + '-data'
live = '--live-answers' in sys.argv
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def docker(*args, check=True):
    result = subprocess.run(['docker', *args], text=True, capture_output=True)
    if check and result.returncode:
        raise AssertionError('Docker ' + args[0] + ' failed: ' + result.stderr)
    return (result.stdout + (result.stderr if args[0] == 'logs' else '')).strip()


def wait():
    end = time.monotonic() + 200
    while time.monotonic() < end:
        state = json.loads(docker('inspect', '--format', '{{json .State}}', name))
        if not state['Running']:
            raise AssertionError('Container exited: ' + docker('logs', name)[-1200:])
        if state.get('Health', {}).get('Status') == 'healthy':
            return
        time.sleep(0.5)
    raise AssertionError('Container readiness deadline exceeded')


def request(path, data=None, cookie=None, content_type='application/json'):
    port = docker('port', name, '3000/tcp').rsplit(':', 1)[1]
    headers = {'Content-Type': content_type}
    if cookie:
        headers['Cookie'] = cookie
    req = urllib.request.Request('http://127.0.0.1:' + port + path, data=data, headers=headers)
    try:
        response = opener.open(req, timeout=150)
    except urllib.error.HTTPError as error:
        response = error
    return response.status, response.headers, json.loads(response.read())


def upload(data, cookie=None):
    boundary = 'doclens-runpod-fixture'
    body = ('--' + boundary + '\r\nContent-Disposition: form-data; name="file"; filename="synthetic.pdf"\r\nContent-Type: application/pdf\r\n\r\n').encode() + data + ('\r\n--' + boundary + '--\r\n').encode()
    return request('/api/documents/process', body, cookie, 'multipart/form-data; boundary=' + boundary)


def records():
    return docker('exec', name, 'python', '-c', "import json,urllib.request; o=urllib.request.build_opener(urllib.request.ProxyHandler({})); out={};\nfor c in ['document_chunks','doclens_document_publications']:\n r=o.open(urllib.request.Request('http://127.0.0.1:6333/collections/'+c+'/points/scroll',data=b'{\"limit\":1000,\"with_payload\":true}',headers={'Content-Type':'application/json'}));out[c]=sorted(json.load(r)['result']['points'],key=lambda p:str(p['id']))\nprint(json.dumps(out,sort_keys=True))")


try:
    with tempfile.TemporaryDirectory(prefix='doclens-runpod-secret-') as tmp:
        env = Path(tmp) / 'secrets.env'
        key = os.environ.get('GEMINI_API_KEY') if live else 'synthetic-no-provider-call'
        assert key, 'Live Gemini key binding required'
        env.write_text('DOCLENS_ADMIN_EMAIL=trial@synthetic.invalid\nDOCLENS_ADMIN_PASSWORD=Synthetic-$literal-Password-2026\nGEMINI_API_KEY=' + key + '\n')
        env.chmod(0o600)
        docker('volume', 'create', volume)
        # Missing mount must fail before storage writes.
        result = subprocess.run(['docker', 'run', '--rm', '--env-file', str(env), 'doclens-runpod:candidate'], capture_output=True)
        assert result.returncode != 0 and b'ValueError' in result.stderr
        print('PASS missing persistent mount refusal', flush=True)
        result = subprocess.run(['docker', 'run', '--rm', '-v', volume + ':/workspace', 'doclens-runpod:candidate'], capture_output=True)
        assert result.returncode != 0 and b'ValueError' in result.stderr
        print('PASS missing private secrets refusal', flush=True)
        trust = []
        if os.environ.get('DOCLENS_TEST_CA'):
            trust = ['-v', os.environ['DOCLENS_TEST_CA'] + ':/run/test-ca.pem:ro', '-e', 'SSL_CERT_FILE=/run/test-ca.pem', '-e', 'REQUESTS_CA_BUNDLE=/run/test-ca.pem']
        docker('run', '-d', *trust, '--name', name, '--cpus', '2', '--memory', '4g', '--memory-swap', '4g', '--env-file', str(env), '-v', volume + ':/workspace', '-p', '127.0.0.1::3000', 'doclens-runpod:candidate')
        wait()
    assert upload(pdf(['Anonymous']))[0] == 401
    assert request('/api/auth/login', json.dumps({'email': 'trial@synthetic.invalid', 'password': 'wrong'}).encode())[0] == 401
    status, headers, _ = request('/api/auth/login', json.dumps({'email': 'trial@synthetic.invalid', 'password': 'Synthetic-$literal-Password-2026'}).encode())
    assert status == 200
    assert 'Secure' in headers['Set-Cookie'] and 'HttpOnly' in headers['Set-Cookie']
    cookie = headers['Set-Cookie'].split(';', 1)[0]
    status, _, body = upload(pdf(['Employer: ' + employer for employer in EMPLOYERS]), cookie)
    assert status == 200 and body['indexed'] and body['total_chunks'] == 5, (status, body)
    before = records()
    for bad, expected in [(b'not PDF', 400), (pdf(['Page'] * 301), 413)]:
        assert upload(bad, cookie)[0] == expected
        assert records() == before
    print('PASS login, anonymous denial, five-page real-model upload, failed replacements preserved', flush=True)
    if live:
        status, _, body = request('/api/ask', json.dumps({'question': 'List all employers in this CV', 'document_name': 'synthetic.pdf'}).encode(), cookie)
        assert status == 200 and all(e in body.get('answer', '') for e in EMPLOYERS), (status, body)
        assert {c['page_number'] for c in body.get('citations', [])} == {1, 2, 3, 4, 5}
        print('PASS live Gemini all five employers and page citations', flush=True)
    # Confirm listeners, UID separation and no provider/password inherited by frontend.
    docker('exec', '-u', '1000', name, 'node', '-e', "const fs=require('fs');try{fs.readFileSync('/config/backend/settings.json');process.exit(1)}catch(e){if(e.code!=='EACCES')throw e}")
    listeners = docker('exec', name, 'python', '-c', "from pathlib import Path; print(Path('/proc/net/tcp').read_text())")
    for port in [8000, 6333, 6334]:
        lines = [line for line in listeners.splitlines() if ':' + format(port, '04X') in line.split()[1] and line.split()[3] == '0A']
        assert lines and all('0100007F:' in line for line in lines), (port, lines)
    docker('exec', name, 'python', '-c', "import fcntl;f=open('/workspace/doclens/run.lock','a');\ntry: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)\nexcept BlockingIOError: pass\nelse: raise AssertionError('Second writer acquired lock')")
    print('PASS API/Qdrant loopback listeners, frontend config isolation and single-writer lock', flush=True)
    print('PERSISTED_BYTES ' + docker('exec', name, 'python', '-c', "from pathlib import Path;print(sum(p.stat().st_size for p in Path('/workspace/doclens').rglob('*') if p.is_file()))"), flush=True)
    print('MEMORY_PEAK_BYTES ' + docker('exec', name, 'python', '-c', "from pathlib import Path;print(Path('/sys/fs/cgroup/memory.peak').read_text().strip())"), flush=True)
    print('RESOURCE ' + docker('stats', '--no-stream', '--format', '{{.MemUsage}} CPU={{.CPUPerc}}', name), flush=True)
    docker('restart', '-t', '30', name)
    wait()
    assert records() == before
    # Existing browser session remains valid after restart.
    assert upload(b'bad replacement', cookie)[0] == 400
    assert records() == before
    if live:
        status, _, body = request('/api/ask', json.dumps({'question': 'List all employers in this CV', 'document_name': 'synthetic.pdf'}).encode(), cookie)
        assert status == 200 and all(e in body.get('answer', '') for e in EMPLOYERS), (status, body)
        assert {c['page_number'] for c in body.get('citations', [])} == {1, 2, 3, 4, 5}
    print('PASS restart persistence: exact point/payload/publication/citation identities, existing session and live answer', flush=True)
    docker('exec', name, 'python', '-c', "import os,signal; from pathlib import Path; p=next(p for p in Path('/proc').iterdir() if p.name.isdigit() and b'/opt/qdrant/qdrant' in (p/'cmdline').read_bytes() and p.stat().st_uid==10002);os.kill(int(p.name),signal.SIGTERM)")
    deadline = time.monotonic() + 40
    while json.loads(docker('inspect', '--format', '{{json .State.Running}}', name)) and time.monotonic() < deadline:
        time.sleep(.5)
    assert docker('inspect', '--format', '{{.State.Running}}', name) == 'false'
    print('PASS child failure terminates whole container', flush=True)
finally:
    docker('rm', '-f', name, check=False)
    docker('volume', 'rm', volume, check=False)
