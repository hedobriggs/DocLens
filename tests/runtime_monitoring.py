"""Live acceptance check: real models/backend, Docker exporters/Prometheus/Grafana.

Requires Linux Docker with host networking/mount permissions, installed Python
requirements, and the two Hugging Face models cached in HF_HOME. No Gemini key
is required; missing-key errors are measured. All test containers/processes are
removed. No credentials or raw environment are printed.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--python', default=str(Path('backend/.venv/bin/python').resolve()))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    prefix = 'doclens-validation-' + secrets.token_hex(4)
    containers = []
    backend = None
    admin_password, viewer_password, internal_key = (secrets.token_hex(24) for _ in range(3))
    auth = 'Basic ' + base64.b64encode(('admin:' + admin_password).encode()).decode()

    def docker(*arguments):
        result = subprocess.run(['docker', *arguments], capture_output=True, text=True)
        if result.returncode:
            # Commands can contain passwords. Print only Docker's diagnostic, not argv.
            raise RuntimeError(result.stderr[-4000:])
        return result.stdout.strip()

    def run(name, image, *arguments, options=()):
        full_name = prefix + '-' + name
        containers.append(full_name)
        docker('run', '-d', '--name', full_name, '--network', 'host', *options, image, *arguments)

    def request(url, *, body=None, headers=None, method=None):
        data = json.dumps(body).encode() if body is not None else None
        with urlopen(Request(url, data=data, method=method,
                             headers={'Content-Type': 'application/json', **(headers or {})}), timeout=10) as response:
            return json.load(response)

    def wait_for(predicate, description, seconds=90):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                value = predicate()
                if value:
                    return value
            except (URLError, TimeoutError, ConnectionError, json.JSONDecodeError):
                pass
            time.sleep(1)
        raise RuntimeError('Timed out waiting for ' + description)

    def query(expression):
        value = request('http://127.0.0.1:9090/api/v1/query?' + urlencode({'query': expression}))
        assert value['status'] == 'success', value
        return value['data']['result']

    with tempfile.TemporaryDirectory(prefix='doclens-runtime-') as tmp:
        tmp = Path(tmp)
        log = (tmp/'backend.log').open('w+')
        try:
            environment = {**os.environ, 'DOCLENS_SESSION_SECRET': internal_key,
                           'OMP_NUM_THREADS': '2', 'HF_HUB_OFFLINE': '1'}
            environment.pop('GEMINI_API_KEY', None)
            backend = subprocess.Popen([args.python, '-m', 'uvicorn', 'main:app', '--app-dir', str(root/'backend'), '--host', '0.0.0.0', '--port', '8000'], cwd=tmp, env=environment, stdout=log, stderr=log)
            wait_for(lambda: request('http://127.0.0.1:8000/'), 'real backend')
            print('PASS real backend health', flush=True)
            # Generate a valid 25 MiB PDF, upload it, then exercise real retrieval/reranking.
            activity = r'''
import os, fitz, httpx
with fitz.open() as doc:
    doc.new_page().insert_text((72,72),'Approved DocLens documents use blue folders.')
    pdf=doc.tobytes()
pdf += b' '*(25*1024*1024-len(pdf))
with httpx.Client(timeout=120, trust_env=False) as client:
    headers={'X-DocLens-Internal-Key':os.environ['DOCLENS_SESSION_SECRET']}
    r=client.post('http://127.0.0.1:8000/documents/process',headers=headers,files={'file':('runtime.pdf',pdf,'application/pdf')})
    assert r.status_code==200, r.text
    assert r.json()['indexed']
    r=client.post('http://127.0.0.1:8000/ask',headers=headers,json={'question':'What color are the folders?','document_name':'runtime.pdf'})
    assert r.status_code==500  # Deliberately missing Gemini key: actual error instrumentation.
print('PASS 25 MiB real-model indexing, retrieval/reranking and missing-Gemini error')
'''
            subprocess.run([args.python, '-c', activity], env=environment, check=True)
            run('node', 'prom/node-exporter:v1.9.1', '--path.rootfs=/host', options=('--pid','host','-v','/:/host:ro,rslave'))
            run('cadvisor', 'gcr.io/cadvisor/cadvisor:v0.52.1', options=('-v','/:/rootfs:ro','-v','/var/run:/var/run:ro','-v','/sys:/sys:ro','-v','/var/lib/docker:/var/lib/docker:ro'))
            run('prometheus', 'prom/prometheus:v3.5.0', '--config.file=/etc/prometheus/prometheus.yml', options=('--add-host','backend:127.0.0.1','--add-host','node-exporter:127.0.0.1','--add-host','cadvisor:127.0.0.1','-v',f'{root}/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro'))
            run('grafana', 'grafana/grafana:12.1.1', options=(
                '--add-host','prometheus:127.0.0.1','-e','GF_SERVER_HTTP_PORT=3301',
                '-e',f'GF_SECURITY_ADMIN_PASSWORD={admin_password}',
                '-e','GF_AUTH_ANONYMOUS_ENABLED=false','-e','GF_USERS_ALLOW_SIGN_UP=false','-e','GF_PLUGINS_PREINSTALL_DISABLED=true',
                '-v',f'{root}/monitoring/grafana/datasources.yml:/etc/grafana/provisioning/datasources/datasources.yml:ro',
                '-v',f'{root}/monitoring/grafana/dashboards.yml:/etc/grafana/provisioning/dashboards/dashboards.yml:ro',
                '-v',f'{root}/monitoring/grafana/dashboards:/etc/grafana/dashboards:ro',
                '-v',f'{root}/monitoring/grafana/doclens.json:/etc/grafana/dashboards/doclens.json:ro'))
            wait_for(lambda: request('http://127.0.0.1:3301/api/health'), 'Grafana')
            subprocess.run([args.python, str(root/'monitoring/grafana/admin_permissions.py')], env={**os.environ,'GRAFANA_ADMIN_PASSWORD':admin_password,'GRAFANA_URL':'http://127.0.0.1:3301'}, check=True)
            dashboards = request('http://127.0.0.1:3301/api/search', headers={'Authorization':auth})
            uids = {d['uid'] for d in dashboards}
            assert {'doclens','doclens-system','doclens-ai','doclens-application','doclens-storage'}.issubset(uids), uids
            request('http://127.0.0.1:3301/api/admin/users', headers={'Authorization':auth}, body={'name':'Acceptance viewer','login':'acceptance-viewer','email':'viewer@example.invalid','password':viewer_password})
            viewer_auth = 'Basic ' + base64.b64encode(('acceptance-viewer:' + viewer_password).encode()).decode()
            for headers in ({}, {'Authorization':viewer_auth}):
                try:
                    request('http://127.0.0.1:3301/api/dashboards/uid/doclens', headers=headers)
                except HTTPError as error:
                    assert error.code in (401,403,404), error.code
                else:
                    raise AssertionError('Non-admin could read monitoring dashboard')
            print('PASS five dashboards provisioned; admin allowed, anonymous/viewer denied', flush=True)
            wait_for(lambda: query('up{job="doclens-backend",instance="backend:8000"}') and query('up{job="doclens-backend"}')[0]['value'][1]=='1', 'Prometheus scraping backend:8000')
            print('PASS Prometheus up{instance="backend:8000"}=1', flush=True)
            required = {
                'overview':'sum(http_requests_total)',
                'application':'sum(http_request_duration_seconds_count)',
                'embedding':'doclens_operation_duration_seconds_count{operation="embedding"}',
                'reranking':'doclens_operation_duration_seconds_count{operation="reranking"}',
                'gemini-error':'doclens_operations_total{operation="gemini",outcome="error"}',
                'documents':'doclens_documents', 'chunks':'doclens_chunks',
                'qdrant-bytes':'doclens_qdrant_storage_bytes',
                'host-memory':'node_memory_MemTotal_bytes',
                'host-disk':'node_filesystem_avail_bytes',
                'host-cpu':'rate(node_cpu_seconds_total{mode="idle"}[5m])',
                'container-health':'container_last_seen',
            }
            for label, expression in required.items():
                wait_for(lambda: query(expression), label + ' samples', seconds=60)
                # Execute the same query through the provisioned Grafana datasource.
                data = request('http://127.0.0.1:3301/api/datasources/proxy/uid/prometheus/api/v1/query?' + urlencode({'query':expression}), headers={'Authorization':auth})
                assert data['data']['result'], label
                print('PASS Grafana datasource query: ' + label, flush=True)
            assert not query('doclens_gemini_tokens_total')
            assert not query('doclens_gemini_estimated_cost_usd_total')
            print('PASS unavailable provider token/cost metrics absent, not zero', flush=True)
        except Exception:
            log.flush(); log.seek(0)
            # Backend log contains only synthetic acceptance activity and exception names.
            print(log.read()[-5000:], flush=True)
            raise
        finally:
            for name in reversed(containers):
                subprocess.run(['docker','rm','-f',name], capture_output=True)
            if backend:
                backend.terminate()
                try: backend.wait(timeout=10)
                except subprocess.TimeoutExpired: backend.kill(); backend.wait()
            log.close()

if __name__ == '__main__':
    main()
