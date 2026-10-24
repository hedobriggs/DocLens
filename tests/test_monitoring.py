"""Monitoring deployment boundaries; live behavior is exercised in test_runpod.py."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Monitoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(subprocess.check_output([
            'docker','compose','--env-file','/dev/null','-f',str(ROOT/'compose.yaml'),
            '-f',str(ROOT/'compose.monitoring.yaml'),'config','--format','json'],text=True))

    def test_only_frontend_published(self):
        services = self.config['services']
        for service in ['backend','qdrant','prometheus','grafana']:
            self.assertFalse(services[service].get('ports'))
        self.assertTrue(all(p['host_ip']=='127.0.0.1' for p in services['frontend']['ports']))
        self.assertTrue(self.config['networks']['monitoring']['internal'])
        self.assertEqual(services['frontend']['environment']['DOCLENS_MONITORING'],'1')

    def test_bounded_persistent_metrics_and_pinned_dependencies(self):
        services = self.config['services']
        for name in ['prometheus','grafana']:
            self.assertIn('@sha256:', services[name]['image'])
            self.assertLessEqual(int(services[name]['mem_limit']),512*1024**2)
            self.assertTrue(any(v['type']=='volume' for v in services[name]['volumes']))
            self.assertFalse(any('docker.sock' in v.get('source','') for v in services[name]['volumes']))
        command = services['prometheus']['command']
        self.assertIn('--storage.tsdb.retention.time=2d',command)
        self.assertIn('--storage.tsdb.retention.size=256MB',command)

    def test_grafana_requires_trusted_application_proxy(self):
        env = self.config['services']['grafana']['environment']
        self.assertEqual(env['GF_AUTH_ANONYMOUS_ENABLED'],'false')
        self.assertEqual(env['GF_AUTH_BASIC_ENABLED'],'false')
        self.assertEqual(env['GF_AUTH_PROXY_ENABLED'],'true')
        self.assertEqual(env['GF_AUTH_PROXY_HEADER_NAME'],'X-DocLens-Grafana-User')
        self.assertNotIn('GF_SECURITY_ADMIN_PASSWORD',env)
        self.assertEqual(env['GF_PLUGINS_PREINSTALL_DISABLED'],'true')
        self.assertEqual(env['GF_LIVE_MAX_CONNECTIONS'],'0')

    def test_dashboard_is_provisioned_and_labels_are_honest(self):
        dashboard = json.loads((ROOT/'deploy/monitoring/dashboards/doclens.json').read_text())
        self.assertEqual(dashboard['uid'],'doclens')
        self.assertEqual(len(dashboard['panels']),12)
        self.assertTrue(all(p['datasource']['uid']=='doclens-prometheus' for p in dashboard['panels']))
        memory = next(p for p in dashboard['panels'] if p['title']=='Backend process memory')
        self.assertIn('not whole-Pod',memory['description'])
        self.assertTrue(all('document_name' not in p['targets'][0]['expr'] for p in dashboard['panels']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
