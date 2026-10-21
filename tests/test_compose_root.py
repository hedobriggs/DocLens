"""Real root `docker compose up/down` acceptance; fresh synthetic project only.

Requires built DocLens images (optional DOCLENS_TEST_BACKEND_IMAGE /
DOCLENS_TEST_FRONTEND_IMAGE) and Docker Compose 2.30+. No host ML/Node
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
    for service in ['BACKEND','FRONTEND']:
        selected=os.environ.get('DOCLENS_TEST_'+service+'_IMAGE')
        env[service+'_IMAGE']=selected or 'doclens-portable-'+service.lower()+':compose-auto'

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
            password='Synthetic-$literal-Password-2026'
            private=root/'.env'
            private.write_text("GEMINI_API_KEY=synthetic-not-a-provider-key\nDOCLENS_ADMIN_EMAIL=trial@synthetic.invalid\nDOCLENS_ADMIN_PASSWORD='"+password+"'\n")
            private.chmod(0o600)
            (package/'.runtime').mkdir(mode=0o700)
            login=package/'.runtime/test-login.json'
            login.write_text(json.dumps({'email':'trial@synthetic.invalid','password':password}));login.chmod(0o600)
            # Reuse the existing synthetic exercise against the root workflow,
            # without invoking its legacy .runtime/compose.env wrapper.
            (package/'doclens').write_text('#!/usr/bin/env bash\nset -euo pipefail\ncd -- "$(dirname -- "$0")/../.."\nexec docker compose "$@"\n')
            (package/'doclens').chmod(0o700)
            env['HTTP_PORT']='0'
            created = True
            # Config is kept in memory; private inputs are never exported.
            config = json.loads(compose('config', '--format', 'json', capture=True).stdout)
            assert config['name'] == project
            assert set(config['services']) == {'setup','backend','frontend','qdrant'}
            backend, frontend = [config['services'][s] for s in ['backend','frontend']]
            assert int(backend['mem_limit']) == 1536*1024**2 and float(backend['cpus']) == 2
            assert int(frontend['mem_limit']) == 512*1024**2
            assert not backend.get('ports') and not config['services']['qdrant'].get('ports')
            assert all(p['host_ip']=='127.0.0.1' for p in frontend['ports'])
            assert 'GEMINI_API_KEY' not in frontend['environment']
            assert 'DOCLENS_ADMIN_PASSWORD_HASH' not in backend['environment']
            assert 'GEMINI_API_KEY' not in backend['environment']
            assert config['services']['setup']['network_mode']=='none'
            assert not frontend.get('secrets') and not backend.get('secrets')
            compose('up', '-d', '--no-build', '--wait', '--wait-timeout', '180')
            subprocess.run([sys.executable, str(package/'smoke.py')], cwd=package, env=env, check=True)
            previous = records()
            # Unprivileged apps can read their own settings but not the other role.
            compose('exec','-T','frontend','node','-e',"const fs=require('fs');try{fs.readFileSync('/config/backend/settings.json');process.exit(9)}catch(e){if(e.code!=='EACCES')throw e}")
            backend_digest="import hashlib;print(hashlib.sha256(open('/config/backend/settings.json','rb').read()).hexdigest())"
            before_config=compose('exec','-T','backend','python','-c',backend_digest,capture=True).stdout
            compose('exec','-T','backend','python','-c',"from pathlib import Path;import sys;\ntry:Path('/config/frontend/settings.json').read_text();sys.exit(9)\nexcept PermissionError:pass")
            compose('down')  # Exactly the requested normal stop command: no -v.
            volumes = inventory()['volumes']
            assert {project+'_index', project+'_snapshots'} <= volumes
            compose('up', '-d', '--no-build', '--wait', '--wait-timeout', '180')
            assert records() == previous, 'up/down changed indexed records or citation/publication identities'
            assert compose('exec','-T','backend','python','-c',backend_digest,capture=True).stdout==before_config
            compose('down')
            original=private.read_text();private.write_text(original.replace(password,'Changed-$literal-Password-2026'))
            failure=subprocess.run(['docker','compose','up','-d','--no-build','--wait','--wait-timeout','30'],cwd=root,env=env,text=True,capture_output=True)
            assert failure.returncode!=0, 'Changed credentials silently replaced saved configuration'
            private.write_text(original)
            compose('up','-d','--no-build','--wait','--wait-timeout','180')
            assert records()==previous
            assert compose('exec','-T','backend','python','-c',backend_digest,capture=True).stdout==before_config
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
