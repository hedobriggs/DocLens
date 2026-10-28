"""Synthetic single-container integration test; no RunPod account required.
Run: python3 tests/test_runpod.py [--live-answers]
Creates/removes only its randomly named container and synthetic volume.
"""
import ast
import json
import os
from pathlib import Path
import subprocess
import socket
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
image = os.environ.get('DOCLENS_TEST_IMAGE', 'doclens-runpod:candidate')
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
            raise AssertionError('Container exited: ' + docker('logs', name))
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


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def monitor(path, cookie=None, data=None, spoof=False, method=None):
    port = docker('port', name, '3000/tcp').rsplit(':', 1)[1]
    origin = 'http://127.0.0.1:' + port
    headers = {'Content-Type':'application/json', 'Origin':origin}
    if cookie: headers['Cookie'] = cookie
    if spoof: headers['X-DocLens-Grafana-User'] = str(spoof) if isinstance(spoof,str) else 'admin'
    req = urllib.request.Request(origin + '/monitoring/' + path, data=data, headers=headers, method=method)
    try:
        response = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect()).open(req, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    body = response.read()
    try: body = json.loads(body)
    except ValueError: pass
    return response.status, body


def metric(query, cookie, timestamp=None):
    import urllib.parse
    params = {'query':query}
    if timestamp is not None: params['time'] = str(timestamp)
    status, body = monitor('api/datasources/proxy/uid/doclens-prometheus/api/v1/query?' + urllib.parse.urlencode(params), cookie)
    assert status == 200 and body['status'] == 'success', (status, body)
    return body['data']['result']


def public_monitoring():
    """Exercise actual published gateways, never raw internal service ports."""
    for service_port, prefix, api in [(3001, '/monitoring', '/api/dashboards/uid/doclens'),
                                      (9090, '/prometheus', '/api/v1/query?query=up')]:
        port = docker('port', name, str(service_port) + '/tcp').rsplit(':', 1)[1]
        base = 'http://127.0.0.1:' + port
        no_redirect = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        def get(path, headers=None):
            try:
                response = no_redirect.open(urllib.request.Request(base + path, headers=headers or {}), timeout=30)
            except urllib.error.HTTPError as error:
                response = error
            return response.status, response.headers, response.read()
        status, headers, _ = get('/')
        assert status == 303 and headers['Location'].startswith(prefix + '/')
        status, headers, _ = get(headers['Location'])
        assert status == 303 and headers['Location'] == '/login'
        assert b'DocLens monitoring' in get('/login')[2]
        assert get(prefix + api, {'X-DocLens-Grafana-User': 'admin'})[0] == 401
        status, _, raw = get(prefix + api, {'Cookie': cookie})
        assert status == 200, (service_port, status, raw[:200])
        body = json.loads(raw)
        if service_port == 3001:
            assert body['dashboard']['uid'] == 'doclens'
        else:
            assert body['status'] == 'success' and body['data']['result']
        assert get('/metrics', {'Cookie': cookie})[0] == 404
        if service_port == 3001:
            # Simulate TLS termination headers; this is not provider HTTPS proof.
            req = urllib.request.Request(base + '/monitoring/api/user/preferences',
                data=b'{"timezone":"utc"}', method='PUT', headers={
                    'Content-Type':'application/json', 'Cookie':cookie,
                    'Host':'synthetic-monitor.invalid',
                    'Origin':'https://synthetic-monitor.invalid', 'X-Forwarded-Proto':'https'})
            try:
                response = no_redirect.open(req, timeout=30)
            except urllib.error.HTTPError as error:
                response = error
            assert response.status == 200, ('HTTPS-offload Origin check', response.status, response.read())
    print('PASS published 3001/9090 roots, anonymous/spoof rejection, authenticated dashboard/query and raw-route denial', flush=True)


try:
    with tempfile.TemporaryDirectory(prefix='doclens-runpod-secret-') as tmp:
        env = Path(tmp) / 'secrets.env'
        key = os.environ.get('GEMINI_API_KEY') if live else 'synthetic-no-provider-call'
        assert key, 'Live Gemini key binding required'
        env.write_text('DOCLENS_ADMIN_EMAIL=trial@synthetic.invalid\nDOCLENS_ADMIN_PASSWORD=Synthetic-$literal-Password-2026\nGEMINI_API_KEY=' + key + '\n')
        env.chmod(0o600)
        trial_environment = env.read_text()
        docker('volume', 'create', volume)
        # Missing mount must fail before storage writes.
        result = subprocess.run(['docker', 'run', '--rm', '--env-file', str(env), image], capture_output=True)
        assert result.returncode != 0 and b'ValueError' in result.stderr, (result.returncode, result.stderr.decode(errors='replace'))
        print('PASS missing persistent mount refusal', flush=True)
        result = subprocess.run(['docker', 'run', '--rm', '-v', volume + ':/workspace', image], capture_output=True)
        assert result.returncode != 0 and b'ValueError' in result.stderr, (result.returncode, result.stderr.decode(errors='replace'))
        print('PASS missing private secrets refusal', flush=True)
        # Keep a stable public frontend origin across container recreation.
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            frontend_port = str(reservation.getsockname()[1])
        trust = ['-e', 'DOCLENS_PUBLIC_ORIGIN=http://doclens.localhost:' + frontend_port]
        if os.environ.get('DOCLENS_TEST_CA'):
            trust = ['-v', os.environ['DOCLENS_TEST_CA'] + ':/run/test-ca.pem:ro', '-e', 'SSL_CERT_FILE=/run/test-ca.pem', '-e', 'REQUESTS_CA_BUNDLE=/run/test-ca.pem']
        fixture = os.environ.get('DOCLENS_MONITORING_RUNTIME')
        if fixture:
            for source,target in [(Path(fixture)/'grafana','/opt/grafana'), (Path(fixture)/'prometheus','/opt/prometheus'),
                                  (ROOT/'deploy/monitoring','/opt/monitoring'), (ROOT/'frontend/.next','/opt/frontend/.next'),
                                  (ROOT/'deploy/runpod/supervisor.py','/opt/runpod/supervisor.py')]:
                trust += ['-v', str(source) + ':' + target + ':ro']
            trust += ['-e','DOCLENS_MONITORING=1']
        docker('run', '-d', *trust, '--name', name, '--cpus', '2', '--memory', '4g', '--memory-swap', '4g', '--env-file', str(env), '-v', volume + ':/workspace', '-p', '127.0.0.1:' + frontend_port + ':3000', '-p', '127.0.0.1::3001', '-p', '127.0.0.1::9090', image)
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
    # Confirm listeners and filesystem separation; child launch policy is unit tested.
    docker('exec', '-u', '1000', name, 'node', '-e', "const fs=require('fs');try{fs.readFileSync('/config/backend/settings.json');process.exit(1)}catch(e){if(e.code!=='EACCES')throw e}")
    listeners = docker('exec', name, 'python', '-c', "from pathlib import Path; print(Path('/proc/net/tcp').read_text())")
    for port in [8000, 6333, 6334, 13001, 19090]:
        lines = [line for line in listeners.splitlines() if ':' + format(port, '04X') in line.split()[1] and line.split()[3] == '0A']
        assert lines and all('0100007F:' in line for line in lines), (port, lines)
    docker('exec', name, 'python', '-c', "import fcntl;f=open('/workspace/doclens/run.lock','a');\ntry: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)\nexcept BlockingIOError: pass\nelse: raise AssertionError('Second writer acquired lock')")
    print('PASS API/Qdrant loopback listeners, frontend config isolation and single-writer lock', flush=True)
    print('PERSISTED_BYTES ' + docker('exec', name, 'python', '-c', "from pathlib import Path;print(sum(p.stat().st_size for p in Path('/workspace/doclens').rglob('*') if p.is_file()))"), flush=True)
    print('MEMORY_PEAK_BYTES ' + docker('exec', name, 'python', '-c', "from pathlib import Path;print(Path('/sys/fs/cgroup/memory.peak').read_text().strip())"), flush=True)
    print('RESOURCE ' + docker('stats', '--no-stream', '--format', '{{.MemUsage}} CPU={{.CPUPerc}}', name), flush=True)
    monitoring = docker('exec', name, 'python', '-c', "import os;print(os.environ.get('DOCLENS_MONITORING','0'))") == '1'
    if monitoring:
        assert monitor('api/dashboards/uid/doclens', spoof=True)[0] == 401
        assert monitor('api/dashboards/uid/doclens', cookie)[1]['dashboard']['title'] == 'DocLens Operations'
        deadline = time.monotonic() + 60
        while True:
            results = metric('doclens_auth_login_success_total{job="doclens"}', cookie)
            if results and float(results[0]['value'][1]) >= 1: break
            assert time.monotonic() < deadline, 'Live authentication metrics not scraped'
            time.sleep(1)
        assert float(metric('doclens_auth_login_failure_total{job="doclens"}', cookie)[0]['value'][1]) >= 1
        assert float(metric('up{job="qdrant"}', cookie)[0]['value'][1]) == 1
        for panel in json.loads((ROOT/'deploy/monitoring/dashboards/doclens.json').read_text())['panels']:
            metric(panel['targets'][0]['expr'].replace('$__rate_interval','1m'), cookie)
        assert monitor('api/ds/query', cookie, b'x'*(2*1024*1024+1))[0] == 413
        assert monitor('api/user', cookie, spoof='untrusted-client')[1]['login'] == 'admin'
        deadline = time.monotonic()+75
        while not metric('sum(rate(http_requests_total{job="doclens"}[1m]))',cookie):
            assert time.monotonic()<deadline, 'HTTP rate metrics missing after scrape warmup'
            time.sleep(1)
        if '--browser' in sys.argv:
            port = docker('port', name, '3000/tcp').rsplit(':',1)[1]
            browser_env = dict(os.environ, DOCLENS_TEST_URL='http://doclens.localhost:'+port, DOCLENS_TEST_COOKIE=cookie)
            browser_env.update({
                'DOCLENS_GRAFANA_URL': 'http://grafana.localhost:' + docker('port', name, '3001/tcp').rsplit(':',1)[1],
                'DOCLENS_PROMETHEUS_URL': 'http://prometheus.localhost:' + docker('port', name, '9090/tcp').rsplit(':',1)[1],
            })
            subprocess.run(['node',str(ROOT/'tests/runpod_links_browser.cjs')],env=browser_env,check=True)
        history_time = time.time()
        history_value = metric('doclens_auth_login_success_total{job="doclens"}', cookie, history_time)
        status, body = monitor('api/user/preferences', cookie, json.dumps({'timezone':'utc','homeDashboardUID':'doclens'}).encode(), method='PUT')
        assert status == 200, (status, body)
        # Spoofed proxy identity cannot bypass the DocLens session check.
        assert monitor('api/dashboards/uid/doclens', spoof=True)[0] == 401
        print('PASS private Grafana gateway, provisioned dashboard, live app/Qdrant metrics, CSRF-aware preferences write', flush=True)
    if monitoring:
        public_monitoring()
    settings_code = "from pathlib import Path;import hashlib,json;print(json.dumps({str(p.relative_to('/config')):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('/config').rglob('*') if p.is_file()},sort_keys=True))"
    saved_settings = docker('exec', name, 'python', '-c', settings_code)
    # Reproduce interruption after a private input was created but before finally
    # removed it. The old fixed pathname survives killing/restarting this container.
    docker('exec', name, 'python', '-c', "import os;from pathlib import Path;p=Path('/run/doclens-initial.env');p.write_text('stale-synthetic-input');p.chmod(0o600)")
    docker('kill', '--signal', 'KILL', name)
    docker('start', name)
    wait()
    assert records() == before, 'Interrupted-startup recovery changed documents'
    assert docker('exec', name, 'python', '-c', settings_code) == saved_settings, 'Interrupted-startup recovery changed saved configuration'
    assert upload(b'bad replacement', cookie)[0] == 400
    docker('exec', name, 'python', '-c', "from pathlib import Path;assert not Path('/run/doclens-initial.env').exists()")
    print('PASS stale private input plus forced restart: startup, exact saved settings, documents, citations and session preserved', flush=True)
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
    if monitoring:
        assert metric('doclens_auth_login_success_total{job="doclens"}', cookie, history_time) == history_value
        assert monitor('api/user/preferences', cookie)[1]['timezone'] == 'utc'
        assert monitor('api/dashboards/uid/doclens', spoof=True)[0] == 401
        public_monitoring()
        print('PASS Grafana settings and Prometheus historical samples survive forced and graceful restart', flush=True)
    print('PASS restart persistence: exact point/payload/publication/citation identities, existing session and live answer', flush=True)
    # Recreate only this synthetic container, retaining its unique volume and
    # exact image. No runtime source mounts, copying or manual listeners.
    if os.environ.get('DOCLENS_RUNPOD_EVIDENCE'):
        (Path(os.environ['DOCLENS_RUNPOD_EVIDENCE']) / 'before-recreation-container.log').write_text(docker('logs', name))
    docker('stop', '-t', '30', name)
    docker('rm', name)
    with tempfile.TemporaryDirectory(prefix='doclens-recreate-secret-') as tmp:
        env = Path(tmp) / 'secrets.env'
        env.write_text(trial_environment)
        env.chmod(0o600)
        docker('run', '-d', *trust, '--name', name, '--cpus', '2', '--memory', '4g',
               '--memory-swap', '4g', '--env-file', str(env), '-v', volume + ':/workspace',
               '-p', '127.0.0.1:' + frontend_port + ':3000', '-p', '127.0.0.1::3001', '-p', '127.0.0.1::9090', image)
        wait()
    assert records() == before
    assert docker('exec', name, 'python', '-c', settings_code) == saved_settings
    assert upload(b'bad replacement', cookie)[0] == 400
    if monitoring:
        public_monitoring()
        assert metric('doclens_auth_login_success_total{job="doclens"}', cookie, history_time) == history_value
    print('PASS container recreation: baked-in listeners, existing sessions, exact documents/configuration and metrics history', flush=True)

    if monitoring:
        docker('exec', name, 'python', '-c', "import os,signal;from pathlib import Path;p=next(p for p in Path('/proc').iterdir() if p.name.isdigit() and p.stat().st_uid==10004 and b'/opt/grafana/bin/grafana' in (p/'cmdline').read_bytes());os.kill(int(p.name),signal.SIGTERM)")
        deadline = time.monotonic()+20
        while monitor('api/dashboards/uid/doclens',cookie)[0] != 502:
            assert time.monotonic()<deadline
            time.sleep(.25)
        assert upload(b'bad replacement',cookie)[0] == 400
        assert records() == before
        docker('restart','-t','30',name)
        wait()
        assert monitor('api/user/preferences',cookie)[1]['timezone']=='utc'
        print('PASS monitoring failure leaves uploads/API available; restart recovers Grafana without changing documents',flush=True)
    docker('exec', name, 'python', '-c', "import os,signal; from pathlib import Path; p=next(p for p in Path('/proc').iterdir() if p.name.isdigit() and b'/opt/qdrant/qdrant' in (p/'cmdline').read_bytes() and p.stat().st_uid==10002);os.kill(int(p.name),signal.SIGTERM)")
    deadline = time.monotonic() + 40
    while json.loads(docker('inspect', '--format', '{{json .State.Running}}', name)) and time.monotonic() < deadline:
        time.sleep(.5)
    assert docker('inspect', '--format', '{{.State.Running}}', name) == 'false'
    print('PASS child failure terminates whole container', flush=True)
finally:
    try:
        evidence = os.environ.get('DOCLENS_RUNPOD_EVIDENCE')
        if evidence:
            Path(evidence).mkdir(parents=True, exist_ok=True)
            (Path(evidence) / 'container.log').write_text(docker('logs', name, check=False))
    except OSError as error:
        print('Evidence capture failed (' + type(error).__name__ + '); retaining original test outcome', file=sys.stderr)
    finally:
        docker('rm', '-f', name, check=False)
        docker('volume', 'rm', volume, check=False)
