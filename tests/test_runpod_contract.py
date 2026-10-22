"""Fast packaging guards; integration lives in test_runpod.py."""
import ast
import os
from unittest.mock import patch
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pod', ROOT / 'deploy/runpod/supervisor.py')
pod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pod)


class Contract(unittest.TestCase):
    def test_template_only_frontend_and_secret_bindings(self):
        template = json.loads((ROOT / 'deploy/runpod/template.json').read_text())
        self.assertEqual(template['ports'], '3000/http')
        self.assertEqual(template['volumeMountPath'], '/workspace')
        self.assertEqual(set(template['env']), set(pod.SECRETS))
        self.assertTrue(all(value.startswith('{{ RUNPOD_SECRET_') for value in template['env'].values()))

    def test_no_runtime_dependency_installation_or_docker(self):
        source = (ROOT / 'deploy/runpod/supervisor.py').read_text()
        for forbidden in ['pip install', 'npm install', 'docker compose', 'dockerd', 'shell=True']:
            self.assertNotIn(forbidden, source)

    def test_directory_refuses_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / 'link').symlink_to(path, target_is_directory=True)
            with self.assertRaises(ValueError):
                pod.private_directory(path / 'link', 10002)

    def test_actual_child_launch_strips_unrelated_secrets(self):
        # Execute the production launch function with a captured Popen. This
        # avoids /proc/environ, restricted even for same-UID readers here.
        tree = ast.parse((ROOT / 'deploy/runpod/supervisor.py').read_text())
        launch = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'start')
        calls = []
        class Process:
            @staticmethod
            def Popen(*args, **kwargs):
                calls.append(kwargs)
                return object()
        namespace = {'os': os, 'subprocess': Process, 'children': [], 'SECRETS': pod.SECRETS}
        exec(compile(ast.Module(body=[launch], type_ignores=[]), '<production child launcher>', 'exec'), namespace)
        with patch.dict(os.environ, {k: 'synthetic-private' for k in (*pod.SECRETS, 'DOCLENS_SESSION_SECRET', 'DOCLENS_ADMIN_PASSWORD_HASH')}):
            namespace['start'](['node'], '/frontend', 1000)
            self.assertFalse(set(calls[-1]['env']) & set((*pod.SECRETS, 'DOCLENS_SESSION_SECRET', 'DOCLENS_ADMIN_PASSWORD_HASH')))
            namespace['start'](['python'], '/backend', 10001, {'GEMINI_API_KEY': 'backend-only', 'DOCLENS_SESSION_SECRET': 'shared-session'})
            self.assertEqual(calls[-1]['env']['GEMINI_API_KEY'], 'backend-only')
            self.assertNotIn('DOCLENS_ADMIN_PASSWORD', calls[-1]['env'])
        self.assertEqual(calls[0]['user'], 1000)
        self.assertEqual(calls[1]['user'], 10001)
        self.assertEqual(calls[0]['extra_groups'], [])

    def test_bind_mount_detection(self):
        self.assertTrue(pod.attached_volume('48 24 0:41 /volumes/data /workspace rw - overlay overlay rw'))
        self.assertFalse(pod.attached_volume('48 24 0:41 / / rw - overlay overlay rw'))
        self.assertFalse(pod.attached_volume('48 24 0:41 /volumes/data /workspace-other rw - overlay overlay rw'))

    def test_private_build_context(self):
        rules = (ROOT / 'deploy/runpod/.dockerignore').read_text().splitlines()
        self.assertEqual([line for line in rules if line and not line.startswith('#')],
                         ['**', '!Dockerfile', '!supervisor.py'])


if __name__ == '__main__':
    unittest.main()
