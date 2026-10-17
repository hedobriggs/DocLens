"""Synthetic real-model/native/container PDF smoke; no hosted generation or customer data.

Requires Docker, requests/PyMuPDF, cached all-MiniLM-L6-v2, built review images.
HF_HOME supplies an existing cache. DOCLENS_MAC_REVIEW_IMAGE supplies the rebuilt image.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time

import fitz
import requests

ROOT = Path(__file__).resolve().parents[1]
QDRANT = 'qdrant/qdrant:v1.15.5@sha256:0fb8897412abc81d1c0430a899b9a81eb8328aa634e7242d1bc804c1fe8fe863'


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True, stderr=subprocess.PIPE).strip()


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def ready(url, process=None):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if process and process.poll() is not None:
            raise RuntimeError('Native application exited; inspect native.log')
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(.25)
    raise RuntimeError('Readiness failed; inspect component logs')


def exercise(base, storage, secret, filename):
    with fitz.open() as document:
        for page in range(2):
            document.new_page().insert_text((72, 72), f'Synthetic Mac upload recovery evidence, page {page + 1}.')
        pdf = document.tobytes()
    headers = {'X-DocLens-Internal-Key': secret}
    assert requests.get(base + '/', timeout=10).json()['message'] == 'DocLens API is running'
    assert requests.post(base + '/documents/process', files={'file': ('denied.pdf', pdf, 'application/pdf')}, timeout=10).status_code == 401
    invalid = requests.post(base + '/documents/process', headers=headers, files={'file': ('invalid.pdf', b'not a PDF', 'application/pdf')}, timeout=10)
    assert invalid.status_code == 400, invalid.status_code
    response = requests.post(base + '/documents/process', headers=headers, files={'file': (filename, pdf, 'application/pdf')}, timeout=120)
    assert response.status_code == 200, response.text
    assert response.json() == {'filename': filename, 'total_chunks': 2, 'indexed': True}, response.text
    points = requests.post(storage + '/collections/document_chunks/points/scroll', json={
        'filter': {'must': [{'key': 'document_name', 'match': {'value': filename}}]},
        'with_payload': True, 'with_vector': True, 'limit': 100,
    }, timeout=10).json()['result']['points']
    assert len(points) == 2 and all(len(point['vector']) == 384 for point in points)
    assert {point['payload']['page_number'] for point in points} == {1, 2}
    extracted = requests.post(base + '/documents/extract', headers=headers, files={'file': (filename, pdf, 'application/pdf')}, timeout=10)
    assert extracted.status_code == 200 and extracted.json()['page_count'] == 2
    assert requests.get(base + '/metrics', timeout=10).status_code == 200
    print(f'PASS {filename}: startup, authentication, invalid-PDF rejection, two-page PDF extraction/indexing, 2 real 384-dimensional vectors and page metadata; PDF SHA256={hashlib.sha256(pdf).hexdigest()}', flush=True)


def gateway(base, secret, evidence):
    """Exercise the built uploaded Next routes with a real signed login session."""
    frontend = ROOT / 'frontend'
    frontend_port = port()
    password = secrets.token_urlsafe(24)
    env = {**os.environ, 'DOCLENS_TEST_PASSWORD': password}
    hashed = subprocess.check_output(['node', '-e', "process.stdout.write(require('bcryptjs').hashSync(process.env.DOCLENS_TEST_PASSWORD,4))"], cwd=frontend, env=env, text=True)
    shim = evidence / 'compose-routing.cjs'
    # A production Compose network resolves backend:8000. Map only that fixture
    # authority for native Next validation; no request/response is simulated.
    shim.write_text("const http=require('node:http'); const original=http.request;\n"
        f"const route=value=>typeof value==='string'?value.replace('http://backend:8000/','{base}/'):value;\n"
        "http.request=function(...args){args[0]=route(args[0]);return original.apply(this,args)};\n"
        "require('node:module').syncBuiltinESMExports(); const fetch=global.fetch; global.fetch=(input,options)=>fetch(route(input),options);\n")
    env.update({'NODE_OPTIONS': '--require ' + str(shim), 'DOCLENS_SESSION_SECRET': secret,
                'DOCLENS_ADMIN_EMAIL': 'mac-review@synthetic.invalid', 'DOCLENS_ADMIN_PASSWORD_HASH': hashed,
                'NEXT_TELEMETRY_DISABLED': '1', 'NO_PROXY': '*', 'no_proxy': '*'})
    for key in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):
        env.pop(key, None)
    with (evidence / 'frontend.log').open('w') as log:
        process = subprocess.Popen(['node', 'node_modules/next/dist/bin/next', 'start', '--hostname', '127.0.0.1', '--port', str(frontend_port)],
                                   cwd=frontend, env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            origin = f'http://127.0.0.1:{frontend_port}'
            ready(origin, process)
            with fitz.open() as document:
                document.new_page().insert_text((72, 72), 'Synthetic upload through the preserved Mac Next gateway.')
                pdf = document.tobytes()
            url = origin + '/api/documents/process'
            assert requests.post(url, files={'file': ('denied.pdf', pdf, 'application/pdf')}, timeout=10).status_code == 401
            login = requests.post(origin + '/api/auth/login', json={'email': 'mac-review@synthetic.invalid', 'password': password}, timeout=15)
            assert login.status_code == 200, login.text
            cookie = login.cookies.get('doclens_session')
            assert cookie
            # Production cookie is Secure; send the genuine signed cookie explicitly
            # for loopback HTTP only. This is not a browser/TLS deployment test.
            response = requests.post(url, headers={'Cookie': 'doclens_session=' + cookie},
                files={'file': ('gateway-synthetic.pdf', pdf, 'application/pdf')}, timeout=120)
            assert response.status_code == 200, response.text
            assert response.json()['indexed'] and response.json()['total_chunks'] == 1, response.text
            print('PASS built Next gateway: anonymous upload denied, genuine admin login/session, multipart PDF forwarding to rebuilt backend and real indexing', flush=True)
        finally:
            process.terminate(); process.wait(timeout=20)


def main():
    suffix = secrets.token_hex(5)
    network = 'doclens-mac-review-' + suffix
    names = ['doclens-mac-qdrant-' + suffix, 'doclens-mac-api-' + suffix]
    secret = secrets.token_urlsafe(40)
    cache = Path(os.environ['HF_HOME']).resolve()
    image = os.environ.get('DOCLENS_MAC_REVIEW_IMAGE', 'doclens-mac-upload-review:fixed')
    evidence = Path(os.environ.get('DOCLENS_MAC_EVIDENCE', tempfile.mkdtemp(prefix='doclens-mac-evidence-')))
    evidence.mkdir(parents=True, exist_ok=True)
    process = None
    try:
        docker('network', 'create', network)
        docker('run', '-d', '--name', names[0], '--network', network, '--network-alias', 'qdrant',
               '-p', '127.0.0.1::6333', QDRANT)
        storage_port = int(docker('port', names[0], '6333').rsplit(':', 1)[1])
        storage = f'http://127.0.0.1:{storage_port}'
        ready(storage + '/readyz')
        native_port = port()
        # The uploaded module hardcodes Compose DNS "qdrant:6333". Resolve only
        # that name/port to the disposable fixture for the native-source run.
        # Storage, model inference and HTTP handlers remain real and unchanged.
        launcher = evidence / 'native_launcher.py'
        launcher.write_text('import socket,runpy\noriginal=socket.getaddrinfo\n'
            f'def resolve(host,port,*args,**kwargs):\n if host=="qdrant": host,port="127.0.0.1",{storage_port}\n return original(host,port,*args,**kwargs)\n'
            'socket.getaddrinfo=resolve\nrunpy.run_module("uvicorn",run_name="__main__")\n')
        env = {**os.environ, 'PYTHONPATH': str(ROOT / 'backend'), 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
               'GEMINI_API_KEY': 'synthetic-not-a-provider-credential', 'DOCLENS_SESSION_SECRET': secret,
               'OMP_NUM_THREADS': '2', 'TOKENIZERS_PARALLELISM': 'false', 'NO_PROXY': '*', 'no_proxy': '*'}
        for key in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):
            env.pop(key, None)
        with (evidence / 'native.log').open('w') as log:
            process = subprocess.Popen([sys.executable, str(launcher), 'main:app', '--host', '127.0.0.1', '--port', str(native_port), '--no-access-log'],
                                       cwd=ROOT / 'backend', env=env, stdout=log, stderr=subprocess.STDOUT)
            ready(f'http://127.0.0.1:{native_port}/', process)
            exercise(f'http://127.0.0.1:{native_port}', storage, secret, 'native-synthetic.pdf')
            process.terminate(); process.wait(timeout=20); process = None
        envfile = evidence / 'synthetic-runtime.env'
        envfile.write_text(f'DOCLENS_SESSION_SECRET={secret}\nGEMINI_API_KEY=synthetic-not-a-provider-credential\nHF_HOME=/models\nHF_HUB_OFFLINE=1\nTRANSFORMERS_OFFLINE=1\nOMP_NUM_THREADS=2\nTOKENIZERS_PARALLELISM=false\nNO_PROXY=*\nno_proxy=*\nHTTP_PROXY=\nHTTPS_PROXY=\nALL_PROXY=\nhttp_proxy=\nhttps_proxy=\nall_proxy=\n')
        envfile.chmod(0o600)
        # Original Mac Dockerfile runs as root; match it when using the verified
        # dependency image (whose default user is non-root).
        # The cloud injects proxy variables even over Docker --env-file values.
        # Clear them inside this fixture process before loading the real app;
        # Compose DNS and real Qdrant networking are unchanged.
        container_launcher = 'import os,sys,runpy; [os.environ.pop(k,None) for k in ("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","http_proxy","https_proxy","all_proxy")]; os.environ.update(NO_PROXY="*",no_proxy="*"); sys.argv=["uvicorn","main:app","--host","0.0.0.0","--port","8000","--no-access-log"]; runpy.run_module("uvicorn",run_name="__main__")'
        docker('run', '-d', '--name', names[1], '--user', '0', '--network', network, '--network-alias', 'backend',
               '--env-file', str(envfile), '-v', str(cache) + ':/models:ro', '-p', '127.0.0.1::8000', image, 'python', '-c', container_launcher)
        api_port = int(docker('port', names[1], '8000').rsplit(':', 1)[1])
        base = f'http://127.0.0.1:{api_port}'
        ready(base + '/')
        probe = docker('exec', names[1], 'python', '-c', 'import os,socket,httpx,json; print(json.dumps({"proxy_nonempty":{k:bool(v) for k,v in os.environ.items() if k.lower().endswith("_proxy")},"qdrant_dns":socket.gethostbyname("qdrant"),"default_status":httpx.get("http://qdrant:6333/readyz").status_code,"direct_status":httpx.get("http://qdrant:6333/readyz",trust_env=False).status_code}))')
        (evidence / 'network-probe.json').write_text(probe + '\n')
        exercise(base, storage, secret, 'container-synthetic.pdf')
        gateway(base, secret, evidence)
        docker('exec', names[1], 'python', '-m', 'pip', 'check')
        (evidence / 'container.log').write_text(docker('logs', names[1]))
        (evidence / 'runtime.json').write_text(json.dumps({'image': docker('image', 'inspect', image, '--format', '{{.Id}}'),
            'qdrant': QDRANT, 'architecture': docker('image', 'inspect', image, '--format', '{{.Architecture}}')}, indent=2) + '\n')
        print('PASS dependency consistency; hosted generation was not invoked. Evidence:', evidence, flush=True)
    finally:
        if process:
            process.terminate(); process.wait(timeout=20)
        for name in names:
            logs = subprocess.run(['docker', 'logs', name], capture_output=True, text=True)
            (evidence / (name.split('-')[2] + '.log')).write_text(logs.stdout + logs.stderr)
            subprocess.run(['docker', 'rm', '-f', '-v', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['docker', 'network', 'rm', network], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
