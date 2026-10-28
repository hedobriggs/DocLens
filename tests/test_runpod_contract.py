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
    def test_template_only_authenticated_services_and_secret_bindings(self):
        template = json.loads((ROOT / 'deploy/runpod/template.json').read_text())
        self.assertEqual(template['ports'], '3000/http,3001/http,9090/http')
        self.assertEqual(template['volumeMountPath'], '/workspace')
        self.assertEqual(set(template['env']) - {'DOCLENS_MONITORING'}, set(pod.SECRETS))
        self.assertTrue(all(value.startswith('{{ RUNPOD_SECRET_') for key,value in template['env'].items() if key != 'DOCLENS_MONITORING'))

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
        namespace = {'os': os, 'subprocess': Process, 'children': [], 'critical_children': [], 'SECRETS': pod.SECRETS}
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
        namespace['start'](['grafana'], '/grafana', 10004, critical=False)
        self.assertEqual(len(namespace['children']),3)
        self.assertEqual(len(namespace['critical_children']),2)

    def test_stale_private_input_replaced_and_cleaned(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'initial.env'
            path.write_text('wrong stale credentials')
            path.chmod(0o600)
            with pod.private_initial({'KEY': 'current-value'}, path):
                self.assertEqual(path.read_text(), "KEY='current-value'")
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertFalse(path.exists())

    def test_unsafe_stale_paths_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / 'valid-settings'
            original.write_text('preserve configuration')
            link = root / 'initial.env'
            link.symlink_to(original)
            with self.assertRaises(ValueError), pod.private_initial({'KEY': 'current'}, link):
                pass
            self.assertTrue(link.is_symlink())
            self.assertEqual(original.read_text(), 'preserve configuration')
            link.unlink()
            os.link(original, link)
            with self.assertRaises(ValueError), pod.private_initial({'KEY': 'current'}, link):
                pass
            self.assertEqual(original.read_text(), 'preserve configuration')
            link.unlink()
            link.write_text('not private')
            link.chmod(0o644)
            with self.assertRaises(ValueError), pod.private_initial({'KEY': 'current'}, link):
                pass
            self.assertEqual(link.read_text(), 'not private')
            link.chmod(0o600)
            with patch.object(pod.os, 'geteuid', return_value=link.stat().st_uid + 1):
                with self.assertRaises(ValueError), pod.private_initial({'KEY': 'current'}, link):
                    pass
            self.assertEqual(link.read_text(), 'not private')

    def test_failed_setup_cleans_only_its_input(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'initial.env'
            with self.assertRaises(RuntimeError):
                with pod.private_initial({'KEY': 'current'}, path):
                    raise RuntimeError('synthetic setup failure')
            self.assertFalse(path.exists())
            with pod.private_initial({'KEY': 'current'}, path):
                path.unlink()
                path.symlink_to(Path(temp) / 'other')
            self.assertTrue(path.is_symlink())

    def test_bind_mount_detection(self):
        self.assertTrue(pod.attached_volume('48 24 0:41 /volumes/data /workspace rw - overlay overlay rw'))
        self.assertFalse(pod.attached_volume('48 24 0:41 / / rw - overlay overlay rw'))
        self.assertFalse(pod.attached_volume('48 24 0:41 /volumes/data /workspace-other rw - overlay overlay rw'))

    def test_private_build_context(self):
        rules = (ROOT / 'deploy/runpod/Dockerfile.dockerignore').read_text().splitlines()
        self.assertEqual(rules[0], '**')
        files = {line[1:] for line in rules[1:] if not line.endswith('/')}
        self.assertEqual(files, {
            'deploy/runpod/supervisor.py', 'deploy/runpod/monitoring_gateway.py', 'deploy/monitoring/prometheus.yml',
            'deploy/monitoring/dashboards/doclens.json',
            'deploy/monitoring/provisioning/datasources/prometheus.yml',
            'deploy/monitoring/provisioning/dashboards/doclens.yml'})



if __name__ == '__main__':
    unittest.main()
