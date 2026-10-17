"""Secret isolation and failure-path regressions; no live Docker needed."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('recovery',ROOT/'recovery/mac-upload/safe_update.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)


class FrontendRecovery(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.repo=self.root/'repo';self.repo.mkdir()
        self.backup=self.root/'backup';self.backup.mkdir(mode=0o700)
        self.original={'Id':'original-container','Image':'sha256:missing',
            'State':{'Running':True,'Paused':False},'Mounts':[],
            'Config':{'Env':['SECRET=SYNTHETIC_PRIVATE_CREDENTIAL']}}

    def test_unexpected_original_identity_is_rejected_before_pause(self):
        with patch.object(helper,'inspect',return_value=self.original),patch.object(helper,'run') as command:
            with self.assertRaisesRegex(RuntimeError,'expected original'):helper.capture_frontend(self.repo,self.backup,expected_image='sha256:different')
            command.assert_not_called()
        self.assertEqual(list(self.backup.iterdir()),[])

    def test_only_explicit_missing_image_activates_fallback(self):
        with patch.object(helper.subprocess,'run',return_value=subprocess.CompletedProcess([],1,b'',b'Error: No such image: sha256:missing')):
            self.assertFalse(helper.image_available(self.repo,'sha256:missing'))
        with patch.object(helper.subprocess,'run',return_value=subprocess.CompletedProcess([],1,b'',b'Docker daemon unavailable')):
            with self.assertRaisesRegex(RuntimeError,'no recovery fallback'):helper.image_available(self.repo,'sha256:missing')

    def test_export_failure_always_unpauses_original_and_hides_stderr(self):
        calls=[]
        def run(args,cwd,data=None):
            calls.append(args)
            if args[1]=='exec':return json.dumps({'arch':'arm64','platform':'linux','execPath':'/usr/local/bin/node','freeBytes':16*1024**3}).encode()
            return b''
        def fail(*args,**kwargs):raise RuntimeError('Frontend recovery export failed')
        with patch.object(helper,'inspect',return_value=self.original), patch.object(helper,'run',side_effect=run), patch.object(helper,'private_docker',side_effect=fail):
            with self.assertRaisesRegex(RuntimeError,'export failed'):helper.capture_frontend(self.repo,self.backup)
        self.assertEqual([c[1] for c in calls],['exec','pause','unpause'])
        self.assertEqual(calls[-1][-1],self.original['Id'])
        folders=list(self.backup.glob('frontend-recovery-*'));self.assertEqual(len(folders),1)
        metadata=folders[0]/'container-inspect.private.json'
        self.assertEqual(metadata.stat().st_mode&0o777,0o600)
        self.assertIn('SYNTHETIC_PRIVATE_CREDENTIAL',metadata.read_text())

    def test_mounts_need_explicit_quiescence_and_unsupported_mounts_fail_before_pause(self):
        self.original['Mounts']=[{'Destination':'/run/secret','Source':'/private/secret','Type':'bind'}]
        with patch.object(helper,'inspect',return_value=self.original),patch.object(helper,'run') as command:
            with self.assertRaisesRegex(RuntimeError,'quiesce outside writers'):helper.capture_frontend(self.repo,self.backup)
            command.assert_not_called()
        for kind,destination in [('tmpfs','/run/secret'),('bind','/'),('bind','/proc/data')]:
            self.original['Mounts']=[{'Destination':destination,'Source':'/private/secret','Type':kind}]
            with patch.object(helper,'inspect',return_value=self.original),patch.object(helper,'run') as command:
                with self.assertRaisesRegex(RuntimeError,'Unsupported frontend mount'):helper.capture_frontend(self.repo,self.backup,quiescent_mounts=True)
                command.assert_not_called()

    def test_mount_change_and_snapshot_warning_unpause_without_restoring(self):
        self.original['Mounts']=[{'Destination':'/run/secret','Source':'/outside/secret','Type':'bind'}]
        calls=[];copies=0
        def run(args,cwd,data=None):
            calls.append(args)
            if args[1]=='exec':return json.dumps({'arch':'x64','platform':'linux','execPath':'/usr/local/bin/node','freeBytes':16*1024**3}).encode()
            return b''
        def capture(repo,folder,label,args,**kwargs):
            nonlocal copies
            copies+=1
            helper.private_bytes(kwargs['destination'],str(copies).encode())
            return b''
        with patch.object(helper,'inspect',return_value=self.original),patch.object(helper,'run',side_effect=run), \
             patch.object(helper,'private_docker',side_effect=capture),patch.object(helper,'restore_frontend_capture') as restore:
            with self.assertRaisesRegex(RuntimeError,'mounted files changed'):helper.capture_frontend(self.repo,self.backup,quiescent_mounts=True)
            restore.assert_not_called()
        self.assertEqual(calls[-1],['docker','unpause','original-container'])
        with patch.object(helper.subprocess,'run',return_value=subprocess.CompletedProcess([],0,None,b'Archive warning')):
            with self.assertRaisesRegex(RuntimeError,'failed'):helper.private_docker(self.repo,self.backup,'warning',['cp','source','-'],destination=self.backup/'warning.tar')

    def test_mount_inspect_order_does_not_report_false_identity_change(self):
        import io,tarfile
        self.original['Mounts']=[{'Destination':'/run/a','Source':'/outside/a','Type':'bind'},
                                 {'Destination':'/run/b','Source':'/outside/b','Type':'bind'}]
        reversed_mounts={**self.original,'Mounts':list(reversed(self.original['Mounts']))}
        def run(args,cwd,data=None):
            if args[1]=='exec':return json.dumps({'arch':'arm64','platform':'linux','execPath':'/usr/local/bin/node','freeBytes':16*1024**3}).encode()
            return b''
        def capture(repo,folder,label,args,**kwargs):
            data=io.BytesIO()
            with tarfile.open(fileobj=data,mode='w') as archive:
                part=tarfile.TarInfo('fixture');part.size=4;archive.addfile(part,io.BytesIO(b'data'))
            helper.private_bytes(kwargs['destination'],data.getvalue());return b''
        with patch.object(helper,'inspect',side_effect=[self.original,reversed_mounts,reversed_mounts]), \
             patch.object(helper,'run',side_effect=run),patch.object(helper,'private_docker',side_effect=capture), \
             patch.object(helper,'restore_frontend_capture',return_value={'verified':True}):
            self.assertTrue(helper.capture_frontend(self.repo,self.backup,quiescent_mounts=True)['verified'])

    def test_sensitive_command_errors_are_private_and_files_are_exclusive(self):
        secret=b'SYNTHETIC_PRIVATE_CREDENTIAL'
        with patch.object(helper.subprocess,'run',return_value=subprocess.CompletedProcess([],1,secret,secret)):
            with self.assertRaises(RuntimeError) as error:helper.private_docker(self.repo,self.backup,'export',['export','original'],destination=self.backup/'rootfs.tar')
        self.assertNotIn(secret.decode(),str(error.exception))
        path=self.backup/'export.stderr.private'
        self.assertEqual(path.read_bytes(),secret);self.assertEqual(path.stat().st_mode&0o777,0o600)
        with self.assertRaises(FileExistsError):helper.private_bytes(path,b'overwrite')
        self.assertEqual(path.read_bytes(),secret)

    def test_capture_only_never_overwrites_original_failed_backup(self):
        state={'repo':str(self.repo),'reviewed':helper.REVIEWED,'phase':'backup-started'}
        for name,data in [('state.json',json.dumps(state).encode()),('checkout.tgz',b'original archive'),('update-helper.py',b'original helper')]:
            helper.private_bytes(self.backup/name,data)
        before={p.name:p.read_bytes() for p in self.backup.iterdir()}
        with patch.object(helper,'capture_frontend',return_value={'verified':True,'capture_dir':'private-child'}) as capture:
            helper.preserve_frontend(self.repo,self.backup,expected_image='sha256:reported-original')
            capture.assert_called_once_with(self.repo,self.backup,quiescent_mounts=False,expected_image='sha256:reported-original')
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.backup.iterdir()})

    def test_reverify_uses_only_capture_and_writes_private_evidence(self):
        with patch.object(helper,'restore_frontend_capture',return_value={'verified':True}) as restore:
            helper.verify_frontend_recovery(self.repo,self.backup)
            restore.assert_called_once_with(self.repo,self.backup)
        files=list(self.backup.glob('reverified-*.private.json'))
        self.assertEqual(len(files),1);self.assertEqual(files[0].stat().st_mode&0o777,0o600)

    def test_literal_compose_escaping_and_tamper_gate(self):
        value={'environment':{'SECRET':'literal-$abc-${UNSET}=quote"\\\\'}}
        escaped=helper.compose_literal(value)
        self.assertEqual(escaped['environment']['SECRET'],'literal-$$abc-$${UNSET}=quote"\\\\')
        private=self.backup/'capture';private.mkdir(mode=0o700)
        helper.private_bytes(private/'rootfs.private.tar',b'changed')
        helper.private_bytes(private/'manifest.private.json',json.dumps({'files':{'rootfs.private.tar':'wrong'}}).encode())
        with patch.object(helper,'private_docker') as command:
            with self.assertRaisesRegex(RuntimeError,'integrity'):helper.restore_frontend_capture(self.repo,private)
            command.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
