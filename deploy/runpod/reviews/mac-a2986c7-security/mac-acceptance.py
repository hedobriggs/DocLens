#!/usr/bin/env python3
"""Mac-only synthetic acceptance driver; no application files/image are changed."""
import getpass
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import uuid
import zipfile

ROOT = Path.home() / 'DocLens-fixed-build.Xmet07'
SOURCE = ROOT / 'source'
COMMIT = '299f3b48bbcd1058845ce14f528fba553d68a783'
IMAGE = 'sha256:4e3a0339cb5e1465701f757ca136039c369ab96fa672401a938e3efa0e5467d8'
OUT = Path(__file__).resolve().parent
NATIVE = '''
import json,sqlite3,ssl,torch,numpy as np,scipy,fitz,cryptography
from PIL import Image
from pathlib import Path
from sentence_transformers import SentenceTransformer,CrossEncoder
assert sqlite3.sqlite_version_info >= (3,41,2)
assert torch.version.cuda is None
pairs=[('sentence-transformers/all-MiniLM-L6-v2','1110a243fdf4706b3f48f1d95db1a4f5529b4d41'),('cross-encoder/ms-marco-MiniLM-L-6-v2','233902d25c440f23af6f7d6e94d2946bac0bee0a')]
for name,revision in pairs:
 assert (Path('/opt/models/hub')/('models--'+name.replace('/','--'))/'refs/main').read_text().strip()==revision
torch.set_num_threads(2);torch.set_num_interop_threads(1)
texts=['Aster Research employed Alex as a research analyst.','Birch Analytics employed Alex as a data engineer.','Cobalt Systems employed Alex as a support specialist.','Delta Robotics employed Alex as a technical consultant.','Elm Computing employed Alex as a systems administrator.']
m=SentenceTransformer(pairs[0][0],device='cpu');v=m.encode(texts)
assert v.shape==(5,384) and np.isfinite(v).all()
r=CrossEncoder(pairs[1][0],device='cpu');scores=r.predict([('Where did Alex work as a research analyst?',t) for t in texts])
assert int(np.argmax(scores))==0
with fitz.open() as d:
 d.new_page().insert_text((30,40),'Synthetic PDF evidence')
 data=d.tobytes()
with fitz.open(stream=data,filetype='pdf') as d: assert 'Synthetic PDF' in d[0].get_text()
print(json.dumps({'native_inference':'PASS','pdf_parser':'PASS','sqlite':sqlite3.sqlite_version,'torch':torch.__version__,'ssl':ssl.OPENSSL_VERSION,'model_revisions':pairs,'scores':scores.tolist()}))
'''
DEPENDENCIES = '''
import json,os,pathlib,sys,unittest
modules=json.load(sys.stdin);p=pathlib.Path('/tmp/acceptance-tests');p.mkdir()
for name,code in modules.items(): (p/name).write_text(code)
sys.path.insert(0,str(p));os.environ['PYTHONPATH']=str(p)
suite=unittest.defaultTestLoader.loadTestsFromNames([name[:-3] for name in modules])
r=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not r.wasSuccessful())
'''
ADAPTER = '''
const {createRequire}=require('node:module');
const path=require('node:path');
const req=createRequire(path.join(process.env.DOCLENS_ACCEPTANCE_SOURCE,'frontend/package.json'));
const {chromium}=req('playwright');
const launch=chromium.launch.bind(chromium);
chromium.launch=options=>launch({...options,executablePath:chromium.executablePath(),args:[...(options.args||[]),'--host-resolver-rules=MAP doclens.localhost 127.0.0.1, MAP grafana.localhost 127.0.0.1, MAP prometheus.localhost 127.0.0.1']});
'''


def read(command):
    return subprocess.check_output(command, text=True).strip()


def inventory():
    return {kind: read(['docker', *args]).splitlines() for kind, args in {
        'containers': ['ps','-a','--format','{{.ID}} {{.Names}} {{.State}}'],
        'volumes': ['volume','ls','--format','{{.Name}}']}.items()}


def main():
    os.umask(0o077)
    # The downloaded driver must itself reside in a NEW acceptance folder.
    if OUT.parent != ROOT or not OUT.name.startswith('acceptance.'):
        raise SystemExit('Place this driver in a new acceptance.* folder under the isolated review folder.')
    if (OUT/'results.json').exists():
        raise SystemExit('This attempt has results already. Use a NEW acceptance folder; do not overwrite failures.')
    state = {'image':IMAGE,'source':COMMIT,'results':{},'limitations':[
        'Baked-frontend expiry/busy-state recovery is a separate pending test.',
        'Full Compose monitoring and actual RunPod HTTPS/storage are not covered.',
        'Local Chromium is not Safari/VoiceOver acceptance. Security approval remains blocked.']}
    key = os.environ.get('GEMINI_API_KEY', '')
    (OUT/'private-raw').mkdir()
    commands=[]
    env=dict(os.environ)
    env.pop('GEMINI_API_KEY', None)
    for k in ['DOCLENS_MONITORING_RUNTIME','NODE_OPTIONS','DOCLENS_TEST_BACK_LINK_ONLY','DOCLENS_TEST_CA']:
        env.pop(k,None)

    def run(label, command, child_env=None, data=None):
        commands.append({'label':label,'argv':command,'cwd':str(SOURCE)})
        (OUT/'commands.json').write_text(json.dumps(commands,indent=2))
        log=OUT/'private-raw'/(label+'.log')
        print('RUN:',label,flush=True)
        with log.open('w') as f:
            p=subprocess.Popen(command,cwd=SOURCE,env=child_env or env,stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,text=True)
            p.communicate(input=data)
        code=p.returncode
        (OUT/'private-raw'/(label+'.exit')).write_text(str(code)+'\n')
        state['results'][label]={'exit':code,'status':'PASS' if code==0 else 'FAIL'}
        print(label,':',state['results'][label]['status'],flush=True)
        if code: print(log.read_text(errors='replace')[-6000:].replace(key,'[REDACTED]') if key else log.read_text(errors='replace')[-6000:],flush=True)
        return code

    try:
        if platform.system()!='Darwin' or platform.machine()!='x86_64': raise RuntimeError('Expected Intel Mac.')
        if read(['git','-C',str(SOURCE),'rev-parse','HEAD'])!=COMMIT: raise RuntimeError('Unexpected source HEAD.')
        if read(['git','-C',str(SOURCE),'status','--porcelain','--untracked-files=no']): raise RuntimeError('Tracked source changed; do not overwrite it.')
        if not read(['docker','context','inspect','--format','{{.Endpoints.docker.Host}}']).startswith('unix://') or os.environ.get('DOCKER_HOST','').startswith(('tcp:','ssh:')): raise RuntimeError('Expected local Docker context.')
        if read(['docker','image','inspect',IMAGE,'--format','{{.Id}}'])!=IMAGE: raise RuntimeError('Wrong/missing image.')
        cpu,mem=map(int,read(['docker','info','--format','{{.NCPU}} {{.MemTotal}}']).split())
        if cpu<2 or mem<3.5*1024**3: raise RuntimeError('Insufficient Docker resources; no settings changed.')
        if read(['docker','ps','-q']): raise RuntimeError('Running containers exist; none stopped. Run when resources are idle.')
        if shutil.disk_usage(ROOT).free<10*1024**3: raise RuntimeError('Less than 10 GiB host free space.')
        state['before']=inventory();state['host']={'platform':platform.platform(),'cpu_limit':cpu,'docker_memory_bytes':mem}
        for tool in ['python3','node','npm']:
            if not shutil.which(tool): raise RuntimeError('Missing local test prerequisite: '+tool)
        state['versions']={tool:read([tool,'--version'])for tool in ['python3','node','npm']}
        base=['docker','run','--rm','-i','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','2g','--cpus','2','--pids-limit','128','--tmpfs','/tmp:rw,nosuid,nodev,size=512m','--entrypoint','python',IMAGE]
        run('baked-native',base+['-'],data=NATIVE)
        modules={n:(SOURCE/'tests'/n).read_text()for n in ['test_dependency_network.py','test_dependency_config.py','test_dependency_framework.py']}
        (OUT/'dependency-test-input.json').write_text(json.dumps(modules))
        run('baked-tls-dependencies',base+['-c',DEPENDENCIES],data=json.dumps(modules))
        env['PLAYWRIGHT_BROWSERS_PATH']=str(OUT/'browser-cache')
        if run('browser-npm',['npm','--prefix',str(SOURCE/'frontend'),'ci','--cache',str(OUT/'npm-cache'),'--no-audit','--no-fund']): raise RuntimeError('Browser dependencies failed; original logs retained.')
        if run('browser-install',['node',str(SOURCE/'frontend/node_modules/playwright/cli.js'),'install','chromium']): raise RuntimeError('Browser installation failed; original logs retained.')
        adapter=OUT/'mac-launcher.cjs';adapter.write_text(ADAPTER)
        env.update(NODE_OPTIONS='--require='+str(adapter),DOCLENS_ACCEPTANCE_SOURCE=str(SOURCE),DOCLENS_TEST_IMAGE=IMAGE)
        core=OUT/'private-raw'/'core';core.mkdir()
        env['DOCLENS_RUNPOD_EVIDENCE']=str(core)
        env['DOCLENS_MONITORING_EVIDENCE']=str(core/'browser')
        key=key or getpass.getpass('Gemini API key locally (hidden; Enter skips live answers): ')
        args=['python3',str(SOURCE/'tests/test_runpod.py'),'--browser']
        if key: env['GEMINI_API_KEY']=key;args.append('--live-answers')
        else: env.pop('GEMINI_API_KEY',None);state['limitations'].append('Live Gemini answers/citations NOT RUN: no key provided.')
        run('baked-core',args,child_env=env)
        state['live_answers_requested']=bool(key)
        if read(['git','-C',str(SOURCE),'status','--porcelain','--untracked-files=no']): raise RuntimeError('Tracked source changed during test setup; inspect before further action.')
    except Exception as e:
        state['blocked']=type(e).__name__+': '+str(e)
        print('STOP:',state['blocked'].replace(key,'[REDACTED]') if key else state['blocked'],flush=True)
    finally:
        try:
            state['after']=inventory()
            if 'before'in state:
                state['preexisting_preserved']={k:set(state['before'][k]).issubset(state['after'][k])for k in state['before']}
                state['new_remaining_objects']={k:sorted(set(state['after'][k])-set(state['before'][k]))for k in state['before']}
                if not all(state['preexisting_preserved'].values()):
                    state['blocked']='Pre-existing inventory changed; inspect before cleanup. No repair or cleanup attempted.'
        except Exception as e: state['inventory_error']=type(e).__name__
        state['complete_acceptance']=False  # Expiry/recovery and additional gates above are not implied passed.
        (OUT/'results.json').write_text(json.dumps(state,indent=2))
        archive=OUT.parent/(OUT.name+'.zip')
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for p in sorted(OUT.rglob('*')):
                if not p.is_file() or any(x in ['browser-cache','npm-cache']for x in p.relative_to(OUT).parts): continue
                data=p.read_bytes()
                if key: data=data.replace(key.encode(),b'[REDACTED]')
                z.writestr(str(p.relative_to(OUT)),data)
        digest=hashlib.sha256(archive.read_bytes()).hexdigest()
        Path(str(archive)+'.sha256').write_text(digest+'  '+archive.name+'\n')
        print('ZIP:',archive,'\nSHA-256:',digest,'\nExpiry/recovery and security approval remain pending.',flush=True)
    raise SystemExit(1 if state.get('blocked') or any(v['status']=='FAIL'for v in state['results'].values()) else 0)

if __name__=='__main__':
    main()
