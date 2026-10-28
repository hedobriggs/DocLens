"""Exercise public gateway framing, fixed routing and credential boundaries."""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
from pathlib import Path
import threading
import unittest

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
