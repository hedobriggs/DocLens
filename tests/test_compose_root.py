"""Real root `docker compose up/down` acceptance; fresh synthetic project only.

Requires the two built DocLens images and Docker Compose 2.30+. No host ML/Node
packages or provider credential are used. Only this fixture's volumes are removed.
"""
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    project = 'doclens-compose-test-' + secrets.token_hex(5)
    env = dict(os.environ)
    for key in ['COMPOSE_FILE', 'COMPOSE_PROFILES', 'HTTP_PORT', 'BIND_ADDRESS',
                'BACKEND_IMAGE', 'FRONTEND_IMAGE', 'DOMAIN', 'GEMINI_API_KEY']:
        env.pop(key, None)
    env['COMPOSE_PROJECT_NAME'] = project

    def inventory():
        return {kind: set(subprocess.check_output(['docker', *args], env=env, text=True).splitlines())
                for kind, args in {'containers': ['ps', '-a', '--format', '{{.ID}} {{.Names}}'],
                                   'volumes': ['volume', 'ls', '--format', '{{.Name}}']}.items()}
    before = inventory()
    created = False
    with tempfile.TemporaryDirectory(prefix='DocLens-compose-') as temporary:
        root = Path(temporary)
        shutil.copyfile(ROOT/'compose.yaml', root/'compose.yaml')
        package = root/'deploy/portable'
        shutil.copytree(ROOT/'deploy/portable', package,
                        ignore=shutil.ignore_patterns('.runtime', '.runtime-*', '__pycache__', '.launcher.lock'))

        def compose(*args, capture=False):
            return subprocess.run(['docker', 'compose', *args], cwd=root, env=env,
                                  text=True, check=True, capture_output=capture)

        def records():
            code = ("import json,requests; s=requests.Session();s.trust_env=False;out={};\n"
                    "for c in ['document_chunks','doclens_document_publications']:\n"
                    " r=s.post('http://qdrant:6333/collections/'+c+'/points/scroll',"
                    "json={'limit':1000,'with_payload':True},timeout=10);r.raise_for_status();"
                    "out[c]=sorted(r.json()['result']['points'],key=lambda p:str(p['id']))\n"
                    "print(json.dumps(out))")
            return json.loads(compose('exec', '-T', 'backend', 'python', '-c', code, capture=True).stdout)

        try:
            subprocess.run([sys.executable, str(package/'configure.py'), '--synthetic-test',
                            '--project', project, '--port', '0'], cwd=root, env=env, check=True)
            created = True
            # Config contains synthetic secrets; inspect in memory, never export it.
            config = json.loads(compose('config', '--format', 'json', capture=True).stdout)
            assert config['name'] == project
            assert set(config['services']) == {'backend','frontend','qdrant'}
            backend, frontend = [config['services'][s] for s in ['backend','frontend']]
            assert int(backend['mem_limit']) == 1536*1024**2 and float(backend['cpus']) == 2
            assert int(frontend['mem_limit']) == 512*1024**2
            assert not backend.get('ports') and not config['services']['qdrant'].get('ports')
            assert all(p['host_ip']=='127.0.0.1' for p in frontend['ports'])
            assert 'GEMINI_API_KEY' not in frontend['environment']
            assert 'DOCLENS_ADMIN_PASSWORD_HASH' not in backend['environment']
            assert backend['environment']['GEMINI_API_KEY']=='synthetic-not-a-provider-key'
            compose('up', '-d', '--no-build', '--wait', '--wait-timeout', '180')
            subprocess.run([sys.executable, str(package/'smoke.py')], cwd=package, env=env, check=True)
            previous = records()
            compose('down')  # Exactly the requested normal stop command: no -v.
            volumes = inventory()['volumes']
            assert {project+'_index', project+'_snapshots'} <= volumes
            compose('up', '-d', '--no-build', '--wait', '--wait-timeout', '180')
            assert records() == previous, 'up/down changed indexed records or citation/publication identities'
            print('PASS: root Compose, credentials separation, limits, real PDF ingestion and down/up persistence')
        finally:
            if created:
                # Fixture teardown only; never recommend -v for an installation.
                compose('down', '--volumes', '--remove-orphans')
    after = inventory()
    assert before == after, 'Unrelated Docker resources changed'
    print(json.dumps({'project':project,'data':'synthetic only','up_down_preserved_records':True,
                      'unrelated_container_and_volume_inventory_unchanged':True}))


if __name__ == '__main__':
    main()
