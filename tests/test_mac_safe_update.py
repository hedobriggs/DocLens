"""Exercise selective update/backup using real Git; Docker lifecycle is controlled."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('safe_update', ROOT/'recovery/mac-upload/safe_update.py')
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)


class SafeMacUpdate(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)/'DocLens'
        subprocess.run(['git', 'clone', '--shared', '--no-checkout', str(ROOT), str(self.repo)], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(self.repo), 'checkout', '--detach', update.BASE], check=True, capture_output=True)
        for name in update.ORIGINALS:
            (self.repo/name).write_bytes(update.blob(ROOT, update.MAC, name))
        (self.repo/'backend/main.py').write_bytes(update.blob(ROOT, update.INDENT, 'backend/main.py'))
        (self.repo/'.env').write_text('PRIVATE_TEST_CREDENTIAL=preserve-only\n')
        (self.repo/'backend/.env').write_text('PRIVATE_TEST_BACKEND=preserve-only\n')
        for name in ('1', 'backend/main.py.backup', 'fix_doclens_stop.py',
                     'frontend/app/dashboard/page.tsx.backup',
                     'frontend/app/dashboard/page.tsx.before-stop-fix'):
            (self.repo/name).write_bytes(b'Exact untracked local bytes\n')
        self.backup = Path(self.temp.name)/'private-backup'

    def test_prepare_preserves_local_files_credentials_and_cold_backup(self):
        untouched = {n:(self.repo/n).read_bytes() for n in (
            '.env', 'backend/.env', '1', 'backend/main.py.backup', 'fix_doclens_stop.py',
            'frontend/app/dashboard/page.tsx.backup', 'frontend/app/dashboard/page.tsx.before-stop-fix',
            'backend/generation.py', 'frontend/app/api/auth/login/route.ts')}
        original_main = (self.repo/'backend/main.py').read_bytes()
        original_run = update.run
        calls = []
        def command(args, cwd, data=None):
            if args[0] != 'docker': return original_run(args, cwd, data)
            calls.append(args)
            if args[1] == 'cp':
                target = Path(args[-1]); target.mkdir()
                (target/'synthetic-wal').write_bytes(b'Cold original Qdrant storage')
            return b''
        details = {n:{'Image':'sha256:synthetic-'+n,'State':{'Running':True}} for n in update.CONTAINERS}
        with patch.object(update, 'run', side_effect=command), patch.object(update, 'context', return_value=('existing-project','existing-volume',details)):
            update.prepare(self.repo,self.backup)
            state = update.load(self.repo,self.backup)
        self.assertEqual(state['phase'],'prepared')
        self.assertEqual(state['volume'],'existing-volume')
        self.assertEqual(update.git(self.repo,'rev-parse','HEAD').decode().strip(),update.BASE)
        for name in update.UPDATE:
            self.assertEqual((self.repo/name).read_bytes(),update.blob(ROOT,update.REVIEWED,name))
        for name, data in untouched.items(): self.assertEqual((self.repo/name).read_bytes(),data)
        with tarfile.open(self.backup/'checkout.tgz') as archive:
            self.assertEqual(archive.extractfile('DocLens/backend/main.py').read(),original_main)
            for name,data in untouched.items():self.assertEqual(archive.extractfile('DocLens/'+name).read(),data)
        self.assertEqual((self.backup/'qdrant-storage/synthetic-wal').read_bytes(),b'Cold original Qdrant storage')
        stop_apps = calls.index(['docker','stop','-t','60',*update.CONTAINERS[:2]])
        stop_store = calls.index(['docker','stop','-t','60',update.CONTAINERS[2]])
        copy_store = next(i for i,c in enumerate(calls) if c[1]=='cp')
        self.assertLess(stop_apps,stop_store);self.assertLess(stop_store,copy_store)
        self.assertEqual(self.backup.stat().st_mode & 0o777,0o700)
        with patch.object(update,'context',return_value=('existing-project','different-volume',details)):
            with self.assertRaisesRegex(RuntimeError,'volume changed'): update.load(self.repo,self.backup)
        (self.repo/'backend/main.py').write_bytes(b'Changed after preparation')
        with self.assertRaisesRegex(RuntimeError,'Reviewed source changed'):update.load(self.repo,self.backup)

    def test_mismatch_backs_up_then_stops_without_applying_or_touching_docker(self):
        path=self.repo/'backend/embeddings.py';path.write_bytes(b'More recent local work\n')
        with patch.object(update,'context') as context:
            with self.assertRaisesRegex(RuntimeError,'Starting files differ'):update.prepare(self.repo,self.backup)
            context.assert_not_called()
        self.assertEqual(path.read_bytes(),b'More recent local work\n')
        self.assertTrue((self.backup/'checkout.tgz').is_file())

    def test_external_credential_symlink_is_preserved_and_backed_up(self):
        target=Path(self.temp.name)/'external-secret.env'
        target.write_bytes(b'PRIVATE_TEST_SECRET=external-original\n')
        (self.repo/'.env').unlink()
        (self.repo/'.env').symlink_to(target)
        with patch.object(update,'context',side_effect=RuntimeError('Stop before Docker')):
            with self.assertRaisesRegex(RuntimeError,'Stop before Docker'):update.prepare(self.repo,self.backup)
        self.assertTrue((self.repo/'.env').is_symlink())
        self.assertEqual(target.read_bytes(),b'PRIVATE_TEST_SECRET=external-original\n')
        self.assertEqual((self.backup/'root-env.private').read_bytes(),target.read_bytes())
        with tarfile.open(self.backup/'checkout.tgz') as archive:
            self.assertTrue(archive.getmember('DocLens/.env').issym())

    def test_original_indentation_and_untracked_collision(self):
        (self.repo/'backend/main.py').write_bytes(update.blob(ROOT,update.MAC,'backend/main.py'))
        self.assertEqual(len(update.check_sources(self.repo)),len(update.UPDATE))
        path=self.repo/'backend/document_publication.py';path.write_bytes(b'Keep my new local module')
        with self.assertRaisesRegex(RuntimeError,'untracked collision'):update.check_sources(self.repo)
        self.assertEqual(path.read_bytes(),b'Keep my new local module')

    def test_wrong_head_never_normalizes_or_resets(self):
        subprocess.run(['git','-C',str(self.repo),'update-ref','HEAD',update.INDENT],check=True,capture_output=True)
        with self.assertRaisesRegex(RuntimeError,'HEAD is not'):update.check_sources(self.repo)

    def test_rebuild_is_explicit_and_never_recreates_data_service(self):
        self.backup.mkdir(mode=0o700)
        state={'phase':'prepared','project':'existing-project','volume':'existing-volume',
               'images':{'doclens-qdrant':'original-data-image'}}
        details={'doclens-qdrant':{'Image':'original-data-image'}}
        prefix=['docker','compose','-f',str(self.repo/'docker-compose.yml'),'-p','existing-project']
        with patch.object(update,'load',return_value=state), \
             patch.object(update,'context',return_value=('existing-project','existing-volume',details)), \
             patch.object(update,'logged') as logged, patch.object(update,'run') as command:
            update.rebuild(self.repo,self.backup)
        self.assertEqual(logged.call_args_list[0].args[0],prefix+['build','backend','frontend'])
        self.assertEqual(logged.call_args_list[1].args[0],prefix+['up','-d','--no-deps','--no-build','backend','frontend'])
        command.assert_called_once_with(['docker','start','doclens-qdrant'],self.repo)
        self.assertEqual(json.loads((self.backup/'state.json').read_text())['phase'],'rebuilt')
        with patch.object(update,'load',return_value=state), \
             patch.object(update,'logged',side_effect=RuntimeError('Build failed')), \
             patch.object(update,'run') as command:
            with self.assertRaisesRegex(RuntimeError,'Build failed'):update.rebuild(self.repo,self.backup)
            command.assert_not_called()

    def test_verify_fixture_is_dense_and_multipart_has_real_newlines(self):
        import fitz,time
        code=update.VERIFY
        with tempfile.TemporaryDirectory() as directory:
            fixture=code[code.index("name='doclens-synthetic-"):code.index('def upload(data):')]
            fixture=fixture.replace("pathlib.Path('/tmp')",'pathlib.Path(directory)')
            scope={'fitz':fitz,'time':time,'pathlib':__import__('pathlib'),'directory':directory}
            exec(fixture,scope)
            self.assertGreater(scope['chars'],200000)
            with fitz.open(scope['path']) as document:self.assertEqual(len(document),40)
        compile(code,'verify-child','exec')


if __name__=='__main__':unittest.main(verbosity=2)
