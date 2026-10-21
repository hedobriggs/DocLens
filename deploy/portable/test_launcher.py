"""Launcher failure, persistence and project-isolation regressions."""
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_packaging import module


class Launcher(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.here = self.root / 'deploy/portable'
        self.here.mkdir(parents=True)
        self.launcher = module('launcher')
        self.calls = []
        for target, value in [('ROOT', self.root), ('HERE', self.here)]:
            p = patch.object(self.launcher, target, value); p.start(); self.addCleanup(p.stop)
        p = patch.dict(os.environ, {'GEMINI_API_KEY': ''}); p.start(); self.addCleanup(p.stop)

    def runtime(self):
        folder = self.here / '.runtime'; folder.mkdir(mode=0o700)
        for name, text in [('compose.env', 'COMPOSE_PROJECT_NAME=private-test\nHTTP_PORT=3001\n'),
                           ('frontend.env', 'private-frontend'), ('backend.env', 'private-backend')]:
            path = folder / name; path.write_text(text); path.chmod(0o600)

    def docker(self, command, **kwargs):
        self.calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout='2.40.3\n')

    def invoke(self, *args):
        with patch.object(sys, 'argv', ['launcher.py', *args]), patch.object(self.launcher.subprocess, 'run', side_effect=self.docker), contextlib.redirect_stdout(io.StringIO()):
            self.launcher.main()

    def test_unconfigured_stop_never_calls_docker(self):
        self.invoke('stop')
        self.assertEqual(self.calls, [])

    def test_missing_key_never_builds_or_creates_runtime(self):
        with self.assertRaisesRegex(SystemExit, 'Set GEMINI_API_KEY'):
            self.invoke('start')
        self.assertFalse((self.here / '.runtime').exists())
        self.assertFalse(any('build.py' in str(c) or 'up' in c for c, _ in self.calls))

    def test_private_key_file_is_literal_not_shell_code(self):
        path = self.root / '.env'; path.write_text('GEMINI_API_KEY="$(do-not-execute)$literal"\n'); path.chmod(0o600)
        self.assertEqual(self.launcher.provider_key(), '$(do-not-execute)$literal')
        path.chmod(0o644)
        with self.assertRaises(SystemExit): self.launcher.provider_key()

    def test_example_key_is_not_accepted_as_real_configuration(self):
        path = self.root / '.env'; path.write_text('GEMINI_API_KEY=replace-with-your-gemini-api-key\n'); path.chmod(0o600)
        with self.assertRaises(SystemExit): self.launcher.provider_key()

    def test_symlink_runtime_is_not_adopted(self):
        other = self.root / 'other'; other.mkdir()
        (self.here / '.runtime').symlink_to(other, target_is_directory=True)
        with self.assertRaises(SystemExit): self.invoke('start')
        self.assertEqual(self.calls, [])

    def test_restart_never_prompts_or_reconfigures(self):
        self.runtime()
        before = {p.name: p.read_bytes() for p in (self.here / '.runtime').iterdir()}
        with patch.object(self.launcher, 'provider_key', side_effect=AssertionError('must not read key')):
            self.invoke('start')
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.here / '.runtime').iterdir()})
        self.assertEqual(self.calls[-1][0], [str(self.here / 'doclens'), 'up', '-d', '--no-build', '--wait', '--wait-timeout', '180'])

    def test_saved_port_cannot_be_silently_changed(self):
        self.runtime()
        with self.assertRaisesRegex(SystemExit, 'saved port'): self.invoke('start', '--port', '3002')
        self.assertFalse(any('up' in c for c, _ in self.calls))

    def test_stop_uses_only_scoped_wrapper_and_preserves_files(self):
        self.runtime(); self.invoke('stop')
        self.assertEqual(self.calls[-1][0], [str(self.here / 'doclens'), 'stop'])
        self.assertTrue((self.here / '.runtime/backend.env').exists())

    def test_compose_failure_propagates_without_cleanup(self):
        self.runtime()
        original = self.docker
        def failure(command, **kwargs):
            result = original(command, **kwargs)
            if 'up' in command: raise subprocess.CalledProcessError(17, command)
            return result
        self.docker = failure
        with self.assertRaises(subprocess.CalledProcessError) as raised: self.invoke('start')
        self.assertEqual(raised.exception.returncode, 17)
        self.assertFalse(any('down' in c or 'rm' in c for c, _ in self.calls))

    def test_build_failure_prevents_credentials_and_compose(self):
        self.runtime()
        original = self.docker
        def failure(command, **kwargs):
            original(command, **kwargs)
            if 'inspect' in command: return subprocess.CompletedProcess(command, 1)
            if command[-1].endswith('build.py'): raise subprocess.CalledProcessError(19, command)
            return subprocess.CompletedProcess(command, 0, stdout='2.40.3\n')
        self.docker = failure
        with self.assertRaises(subprocess.CalledProcessError): self.invoke('start')
        self.assertFalse(any('up' in c for c, _ in self.calls))

    def test_missing_old_images_are_not_rebuilt_from_new_source(self):
        self.runtime()
        config = self.here / '.runtime/compose.env'
        with config.open('a') as stream:
            stream.write('BACKEND_IMAGE=old-backend:old\nFRONTEND_IMAGE=old-frontend:old\n')
        original = self.docker
        def missing(command, **kwargs):
            result = original(command, **kwargs)
            return subprocess.CompletedProcess(command, 1) if 'inspect' in command else result
        self.docker = missing
        with self.assertRaisesRegex(SystemExit, 'Restore those exact images'): self.invoke('start')
        self.assertFalse(any('build.py' in str(c) or 'up' in c for c, _ in self.calls))


if __name__ == '__main__':
    unittest.main(verbosity=2)
