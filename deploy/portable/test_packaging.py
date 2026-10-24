"""Failure-path and context-isolation checks; no Docker daemon is started."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def module(name):
    spec = importlib.util.spec_from_file_location('portable_' + name, HERE / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class Packaging(unittest.TestCase):
    def test_existing_runtime_is_never_overwritten(self):
        configure = module('configure')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / '.runtime').mkdir(); original = root / '.runtime/private.env'; original.write_text('preserve')
            with patch.object(configure, 'ROOT', root), patch.object(sys, 'argv', ['configure.py', '--synthetic-test']), patch.object(configure.subprocess, 'check_output') as docker:
                with self.assertRaises(SystemExit): configure.main()
                docker.assert_not_called()
            self.assertEqual(original.read_text(), 'preserve')

    def test_unlabelled_existing_volume_is_not_adopted(self):
        configure = module('configure')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(configure, 'ROOT', root), patch.object(sys, 'argv', ['configure.py', '--synthetic-test', '--project', 'existing']), patch.object(configure.subprocess, 'check_output', side_effect=['', '', 'existing_index\n']):
                with self.assertRaises(SystemExit): configure.main()
            self.assertFalse((root / '.runtime').exists())

    def test_automatic_compose_contexts_are_source_only_allowlists(self):
        manifest = json.loads((HERE/'application-manifest.json').read_text())
        root = HERE.parents[1]
        for service in ['backend','frontend']:
            lines = [line for line in (root/service/'.dockerignore').read_text().splitlines()
                     if line and not line.startswith('#')]
            self.assertEqual(lines[0], '**')
            self.assertTrue(all(line.startswith('!') for line in lines[1:]))
            files = {line[1:].replace('\\[','[').replace('\\]',']') for line in lines[1:] if not line.endswith('/')}
            expected = {str(Path(name).relative_to(service)) for name in manifest['sha256']
                        if name.startswith(service+'/') and not name.endswith('/.dockerignore')}
            self.assertEqual(files, expected)
            self.assertFalse(files & {'.env','.env.local','private.backup','original.pdf'})
            self.assertFalse(any('*' in name for name in files))

    def test_release_manifest_matches_real_build_inputs(self):
        # This caught the legal UI integration retaining stale dashboard hashes.
        # Run the actual builder's checks/contexts without requiring Docker.
        build = module('build')
        checked = []
        def inspect_context(command, **kwargs):
            context = Path(command[-1])
            files = [p for p in context.rglob('*') if p.is_file()]
            self.assertTrue(files)
            self.assertFalse(any(p.name.startswith('.env') or p.suffix in {'.backup','.log'} for p in files))
            if context.name == 'frontend':
                self.assertIn('legal-workspace', (context/'app/dashboard/page.tsx').read_text())
            checked.append(context.name)
        with patch.object(build.subprocess, 'run', side_effect=inspect_context), patch.dict('os.environ', {'BUILD_CA_BUNDLE':''}), contextlib.redirect_stdout(io.StringIO()):
            build.main()
        self.assertEqual(checked, ['backend','frontend'])

    def test_changed_source_stops_before_any_build(self):
        build = module('build')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); here = root / 'deploy/portable'; here.mkdir(parents=True); (root / 'backend').mkdir(); (root / 'backend/main.py').write_text('modified')
            (here / 'application-manifest.json').write_text(json.dumps({'sha256': {'backend/main.py': hashlib.sha256(b'approved').hexdigest()}}))
            with patch.object(build, 'HERE', here), patch.object(build, 'ROOT', root), patch.object(build.subprocess, 'run') as docker, patch.dict('os.environ', {'BUILD_CA_BUNDLE': ''}):
                with self.assertRaises(SystemExit): build.main()
                docker.assert_not_called()

    def test_build_context_excludes_untracked_credentials(self):
        build = module('build')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); here = root / 'deploy/portable'; here.mkdir(parents=True)
            checks = {}
            for service in ['backend', 'frontend']:
                (root / service).mkdir(); (root / service / 'approved.txt').write_text('approved'); (root / service / '.env').write_text('PRIVATE_SENTINEL')
                checks[service + '/approved.txt'] = hashlib.sha256(b'approved').hexdigest()
                (here / ('Dockerfile.' + service)).write_text('FROM scratch\n')
            (here / 'application-manifest.json').write_text(json.dumps({'application_commit': 'test', 'sha256': checks}))
            commands = []
            def docker(command, **kwargs):
                context = Path(command[-1]); self.assertEqual(sorted(p.name for p in context.iterdir()), ['approved.txt']); commands.append(command)
            with patch.object(build, 'HERE', here), patch.object(build, 'ROOT', root), patch.object(build.subprocess, 'run', side_effect=docker), patch.dict('os.environ', {'BUILD_CA_BUNDLE': ''}), contextlib.redirect_stdout(io.StringIO()):
                build.main()
            self.assertEqual(len(commands), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
