"""Disposable Docker recovery checks. Refuses an existing doclens-frontend.

Synthetic credentials only. No Mac/customer data. Original-image absence is
injected only if Docker refuses deleting an image used by a running fixture.
"""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('recovery',ROOT/'recovery/mac-upload/safe_update.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
NODE='node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293'
SECRET='SYNTHETIC_ENV_$literal-${DO_NOT_EXPAND}=quote"\\end'
CMD_SECRET='SYNTHETIC_CMD_$literal-${DO_NOT_EXPAND}'


def docker(*args):
    return subprocess.check_output(['docker',*args],stderr=subprocess.PIPE).decode().strip()


def main():
    os.umask(0o077)
    if 'doclens-frontend' in docker('ps','-a','--format','{{.Names}}').splitlines():
        raise RuntimeError('Existing frontend found; refusing to touch it')
    root=Path(tempfile.mkdtemp(prefix='doclens-frontend-recovery-'))
    os.environ['BUILDX_CONFIG']=str(root/'buildx')
    source=root/'source';source.mkdir(mode=0o700)
    backup=root/'backup';backup.mkdir(mode=0o700)
    tag='doclens-private-fixture:'+uuid4().hex
    wrong='doclens-private-fixture-wrong:'+uuid4().hex
    volume='doclens-private-fixture-'+uuid4().hex
    initial_tags=set(docker('image','ls','--format','{{.Repository}}:{{.Tag}}').splitlines())
    envfile=root/'fixture.env';envfile.write_text('CAPTURE_SECRET='+SECRET+'\n')
    bind=root/'private-bind';bind.write_text('SYNTHETIC_BIND_SECRET');bind.chmod(0o600)
    (source/'server.cjs').write_text('''const http=require('node:http'),fs=require('node:fs');
const expected='''+json.dumps(SECRET)+''';
http.createServer((req,res)=>{try{
 if(process.argv[3]!=='SYNTHETIC_CMD_$literal-${DO_NOT_EXPAND}'||process.env.CAPTURE_SECRET!==expected||fs.readFileSync('/app/.env','utf8')!=='SYNTHETIC_BAKED_SECRET'||fs.readFileSync('/app/runtime.txt','utf8')!=='CURRENT_WRITABLE_LAYER')throw Error('Runtime mismatch');
 if(process.env.MOUNTED==='yes'&&(fs.readFileSync('/run/private.env','utf8')!=='SYNTHETIC_BIND_SECRET'||fs.readFileSync('/app/private-volume/credential','utf8')!=='SYNTHETIC_VOLUME_SECRET'))throw Error('Mount mismatch');
 res.writeHead(req.url==='/api/documents/process'?401:200,{'content-type':req.url==='/api/documents/process'?'application/json':'text/html'});res.end(req.url==='/api/documents/process'?'{}':'<html>synthetic frontend</html>');
}catch(e){res.writeHead(500);res.end('Component mismatch')}}).listen(3000,'0.0.0.0');
''')
    (source/'.env').write_text('SYNTHETIC_BAKED_SECRET')
    (source/'runtime.txt').write_text('OLD_IMAGE_LAYER')
    (source/'Dockerfile').write_text('FROM '+NODE+'\nWORKDIR /app\nCOPY --chown=1000:1000 . /app/\nUSER node\nENTRYPOINT ["node"]\nCMD ["server.cjs","--fixture-secret","SYNTHETIC_CMD_$literal-${DO_NOT_EXPAND}"]\n')
    subprocess.run(['docker','build','-t',tag,str(source)],check=True,stdout=(root/'build.log').open('wb'),stderr=subprocess.STDOUT)
    docker('tag',NODE,wrong)
    docker('volume','create',volume)
    docker('run','--rm','--user','0','-v',volume+':/fixture',NODE,'node','-e',
           'const fs=require("fs");fs.writeFileSync("/fixture/credential","SYNTHETIC_VOLUME_SECRET");fs.chownSync("/fixture/credential",1000,1000);fs.chmodSync("/fixture/credential",0o600)')
    results=[]
    try:
        for mounted in (False,True):
            # The second case may rebuild a deliberately deleted fixture image.
            if not subprocess.run(['docker','image','inspect',tag],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
                subprocess.run(['docker','build','-t',tag,str(source)],check=True,stdout=(root/'rebuild.log').open('wb'),stderr=subprocess.STDOUT)
            args=['run','-d','--name','doclens-frontend','--env-file',str(envfile)]
            if mounted:args+=['-e','MOUNTED=yes','-v',str(bind)+':/run/private.env:ro','-v',volume+':/app/private-volume']
            docker(*args,tag)
            original=helper.inspect(ROOT,'doclens-frontend')
            docker('exec','doclens-frontend','node','-e','require("fs").writeFileSync("/app/runtime.txt","CURRENT_WRITABLE_LAYER")')
            image_id=original['Image']
            removal=subprocess.run(['docker','image','rm','-f',image_id],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            real_absence=not subprocess.run(['docker','image','inspect',image_id],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
            # No helper operation below references tag/wrong/latest: export and
            # reconstruction consume the running container and private archives.
            output=io.StringIO()
            original_run=helper.subprocess.run
            def no_secret_argv(args,*extra,**kwargs):
                if any(SECRET in str(arg) or CMD_SECRET in str(arg) for arg in args):
                    raise AssertionError('Captured credential leaked into host CLI arguments')
                return original_run(args,*extra,**kwargs)
            with contextlib.redirect_stdout(output), patch.object(helper.subprocess,'run',side_effect=no_secret_argv):
                recovery=helper.capture_frontend(ROOT,backup,quiescent_mounts=mounted)
            if SECRET in output.getvalue():raise AssertionError('Credential leaked to progress output')
            folder=Path(recovery['capture_dir'])
            before=helper.inspect(ROOT,'doclens-frontend')
            assert before['Id']==original['Id'] and before['State']['Running'] and not before['State']['Paused']
            metadata=json.loads((folder/'container-inspect.private.json').read_text())
            assert 'CAPTURE_SECRET='+SECRET in metadata['Config']['Env']
            assert all(p.stat().st_mode&0o077==0 for p in folder.iterdir() if p.is_file())
            assert (folder/'container-inspect.private.json').stat().st_mode&0o777==0o600
            # Retire only this disposable source fixture, then prove that the
            # retained helper/artifacts recover without either source dependency.
            if mounted:
                assert docker('exec','doclens-frontend','node','-p','require("fs").readFileSync("/app/private-volume/credential","utf8")')=='SYNTHETIC_VOLUME_SECRET'
            docker('rm','-f','doclens-frontend')
            if subprocess.run(['docker','image','inspect',image_id],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
                docker('image','rm','-f',image_id)
            assert subprocess.run(['docker','image','inspect',image_id],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
            second=subprocess.run([sys.executable,str(folder/'recovery-helper.private.py'),
                'verify-frontend-recovery','--backup',str(folder)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            if second.returncode:
                (root/'reverify-failure.private.log').write_bytes(second.stdout+second.stderr)
                raise RuntimeError('Retained-helper artifact-only verification failed')
            assert b'PASS:' in second.stdout and SECRET.encode() not in second.stdout and CMD_SECRET.encode() not in second.stdout
            assert bind.read_text()=='SYNTHETIC_BIND_SECRET'
            results.append({'mounted':mounted,'real_missing_image':real_absence,
                'image_removal_exit':removal.returncode,'original_still_running_after_capture':True,
                'default_image_startup_auth_probe':recovery['probe'],
                'second_restore_from_private_archives':True,'source_container_and_image_absent_during_second_restore':True,'metadata_permissions':'0600',
                'credential_literal_preserved':True,'credential_stdout_leak':False,'credential_argv_leak':False})
        print(json.dumps(results,indent=2));print('PASS: two independent restore runs per case; no original mounts attached to probes')
        print('Synthetic private evidence:',root)
    finally:
        if 'doclens-frontend' in docker('ps','-a','--format','{{.Names}}').splitlines():docker('rm','-f','doclens-frontend')
        docker('volume','rm',volume)
        tags=set(docker('image','ls','--format','{{.Repository}}:{{.Tag}}').splitlines())-initial_tags
        for candidate in tags:
            if candidate.startswith(('doclens-private-frontend:','doclens-private-fixture:', 'doclens-private-fixture-wrong:')):
                subprocess.run(['docker','image','rm',candidate],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


if __name__=='__main__':main()
