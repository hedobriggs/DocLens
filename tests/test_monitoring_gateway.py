"""Exercise public gateway framing, fixed routing and credential boundaries."""
import http.client
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
from pathlib import Path
import threading
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('gateway', Path(__file__).resolve().parents[1] / 'deploy/runpod/monitoring_gateway.py')
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)


class Upstream(BaseHTTPRequestHandler):
    def log_message(self, *_): pass

    def do_GET(self):
        self.server.received = (self.path, self.headers)
        if self.headers.get('Cookie') != 'session=valid':
            self.send_response(303)
            self.send_header('Location', 'http://127.0.0.1:3000/')
        else:
            self.send_response(200)
        self.end_headers()
        self.wfile.write(b'synthetic upstream')

    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', 0)))
        self.send_response(200)
        self.send_header('Set-Cookie', 'session=valid; Secure; HttpOnly; SameSite=Lax; Path=/')
        self.end_headers()


class MonitoringGateway(unittest.TestCase):
    def setUp(self):
        self.upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
        self.servers = [self.upstream]
        for service in ('grafana', 'prometheus'):
            self.servers.append(gateway.Gateway(('127.0.0.1', 0), service, self.upstream.server_port))
        for server in self.servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)

    def request(self, server, path, headers=None, method='GET'):
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
        self.addCleanup(connection.close)
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        return response.status, response.headers, response.read()

    def test_both_roots_and_anonymous_login_no_redirect_loop(self):
        for server in self.servers[1:]:
            status, headers, _ = self.request(server, '/')
            self.assertEqual(status, 303)
            self.assertEqual(headers['Location'], server.landing)
            status, headers, _ = self.request(server, server.landing)
            self.assertEqual(status, 303)
            self.assertEqual(headers['Location'], '/login')
            status, _, body = self.request(server, '/login')
            self.assertEqual(status, 200)
            self.assertIn(b'autocomplete="current-password"', body)

    def test_identity_spoofing_removed_session_and_query_preserved(self):
        server = self.servers[1]
        status, _, _ = self.request(server, '/monitoring/api/search?query=synthetic', {
            'Cookie': 'session=valid', 'X-DocLens-Grafana-User': 'admin',
            'X-DocLens-Internal-Key': 'not-authority', 'Authorization': 'Bearer spoof'})
        self.assertEqual(status, 200)
        path, headers = self.upstream.received
        self.assertEqual(path, '/monitoring/api/search?query=synthetic')
        self.assertEqual(headers['Cookie'], 'session=valid')
        for name in ('X-DocLens-Grafana-User', 'X-DocLens-Internal-Key', 'Authorization'):
            self.assertIsNone(headers.get(name))

    def test_login_keeps_secure_cookie_attributes(self):
        status, headers, _ = self.request(self.servers[2], '/api/auth/login', method='POST')
        self.assertEqual(status, 200)
        self.assertIn('Secure; HttpOnly; SameSite=Lax; Path=/', headers['Set-Cookie'])

    def test_back_link_uses_absolute_doclens_destination_without_changing_panels(self):
        template = (Path(__file__).resolve().parents[1] / 'deploy/monitoring/dashboards/doclens.json').read_text()
        before = json.loads(template)
        document = json.loads(gateway.dashboard_document(template, 'https://doclens.example.invalid'))
        link = next(link for link in document['links'] if link['title'] == 'Back to DocLens')
        self.assertEqual(link['url'], 'https://doclens.example.invalid/dashboard')
        self.assertEqual(document['panels'], before['panels'])
        self.assertEqual(document['uid'], before['uid'])
        self.assertEqual(json.loads(template)['links'][0]['url'], '/dashboard')  # Compose unchanged.

    def test_generated_config_is_readable_by_grafana_and_replaced_on_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'runtime'
            previous = gateway.os.umask(0o077)
            try:
                for origin in ('https://first.example.invalid', 'https://second.example.invalid'):
                    gateway.prepare_dashboard('{"uid":"doclens","links":[{"title":"Back to DocLens"}]}', output, origin)
                    self.assertEqual(output.stat().st_mode & 0o777, 0o755)
                    self.assertEqual((output/'dashboards').stat().st_mode & 0o777, 0o755)
                    final = output/'dashboards/doclens.json'
                    self.assertEqual(final.stat().st_mode & 0o777, 0o444)
                    self.assertEqual(json.loads(final.read_text())['links'][0]['url'], origin+'/dashboard')
                    self.assertEqual(len(list(final.parent.iterdir())), 1)
            finally:
                gateway.os.umask(previous)

    def test_public_origin_uses_provider_metadata_and_validated_override(self):
        with patch.dict(gateway.os.environ, {'RUNPOD_POD_ID':'abc123', 'DOCLENS_PUBLIC_ORIGIN':''}):
            self.assertEqual(gateway.doclens_origin(), 'https://abc123-3000.proxy.runpod.net')
            for value in ('https://documents.example.invalid/', 'http://doclens.localhost:43210'):
                with patch.dict(gateway.os.environ, {'DOCLENS_PUBLIC_ORIGIN':value}):
                    self.assertEqual(gateway.doclens_origin(), value.rstrip('/'))
            for value in ('http://external.invalid', 'https://user:password@example.invalid',
                          'https://example.invalid/path', 'https://example.invalid?token=bad',
                          'https://example.invalid/#fragment', '//evil.invalid',
                          'https://example.invalid:invalid', 'https://example.invalid:0',
                          'https://example.invalid/\n'):
                with patch.dict(gateway.os.environ, {'DOCLENS_PUBLIC_ORIGIN':value}):
                    with self.assertRaises(ValueError):
                        gateway.doclens_origin()
        with patch.dict(gateway.os.environ, {'RUNPOD_POD_ID':'invalid/pod', 'DOCLENS_PUBLIC_ORIGIN':''}):
            self.assertIsNone(gateway.doclens_origin())

    def test_missing_origin_does_not_advertise_a_broken_or_guessed_destination(self):
        document = json.loads(gateway.dashboard_document('{"links":[{"title":"Back to DocLens","url":"/dashboard"}]}', None))
        self.assertEqual(document['links'], [])

    def test_fixed_service_and_bounded_requests(self):
        for server in self.servers[1:]:
            for path in ('/api/documents/process', '/internal/settings', '/metrics', '//evil.invalid/'):
                self.assertIn(self.request(server, path)[0], (400, 404))
            self.assertEqual(self.request(server, server.landing, {'Content-Length': str(2 * 1024 * 1024 + 1)}, 'POST')[0], 413)
            self.assertEqual(self.request(server, server.landing, {'Transfer-Encoding': 'chunked'}, 'POST')[0], 400)
            other = '/prometheus/query' if server.prefix == '/monitoring' else '/monitoring/d/doclens'
            self.assertEqual(self.request(server, other)[0], 404)


if __name__ == '__main__':
    unittest.main(verbosity=2)
