"""Synthetic TLS, HTTP/2 and worker regressions; no external requests or data."""
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ssl
import tempfile
import threading
import unittest

import certifi
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from h2.config import H2Configuration
from h2.connection import H2Connection
from h2.events import RequestReceived
import httpx
import requests


def noisy_worker():
    # Regression: undrained process-pool stderr used to deadlock a valid job.
    import sys
    sys.stderr.write('synthetic worker diagnostic\n' * 20000)
    sys.stderr.flush()
    return 'complete'


class NetworkDependencies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
        now = datetime.now(timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(minutes=1))
                .not_valid_after(now + timedelta(hours=1))
                .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), False)
                .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
                .sign(key, hashes.SHA256()))
        cls.ca = Path(cls.temp.name) / 'synthetic-ca.pem'
        private = Path(cls.temp.name) / 'synthetic-key.pem'
        cls.ca.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        private.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                           serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        private.chmod(0o600)

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = b'synthetic TLS success'
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cls.ca, private)
        cls.server.socket = ctx.wrap_socket(cls.server.socket, server_side=True)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def test_certifi_excludes_compromised_root(self):
        subjects = {cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
                    for cert in x509.load_pem_x509_certificates(Path(certifi.where()).read_bytes())
                    if cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)}
        self.assertNotIn('emSign ECC Root CA - G3', subjects)
        self.assertGreater(len(subjects), 50)

    def test_requests_default_rejects_untrusted_and_explicit_ca_checks_hostname(self):
        with requests.Session() as client:
            client.trust_env = False  # Local synthetic server only; no external traffic.
            with self.assertRaises(requests.exceptions.SSLError):
                client.get(f'https://localhost:{self.port}', timeout=3)
            response = client.get(f'https://localhost:{self.port}', verify=str(self.ca), timeout=3)
            self.assertEqual(response.content, b'synthetic TLS success')
            with self.assertRaises(requests.exceptions.SSLError):
                client.get(f'https://127.0.0.1:{self.port}', verify=str(self.ca), timeout=3)

    def test_httpx_default_rejects_untrusted_and_explicit_ca_checks_hostname(self):
        with httpx.Client(trust_env=False, timeout=3) as client:
            with self.assertRaises(httpx.ConnectError):
                client.get(f'https://localhost:{self.port}')
        ctx = ssl.create_default_context(cafile=str(self.ca))
        with httpx.Client(verify=ctx, trust_env=False, timeout=3) as client:
            self.assertEqual(client.get(f'https://localhost:{self.port}').status_code, 200)
            with self.assertRaises(httpx.ConnectError):
                client.get(f'https://127.0.0.1:{self.port}')

    def test_http2_header_compression_roundtrip(self):
        client = H2Connection(config=H2Configuration(client_side=True, header_encoding='utf-8'))
        server = H2Connection(config=H2Configuration(client_side=False, header_encoding='utf-8'))
        client.initiate_connection()
        server.receive_data(client.data_to_send())
        headers = [(':method', 'GET'), (':scheme', 'https'),
                   (':authority', 'synthetic.invalid'), (':path', '/health')]
        client.send_headers(1, headers, end_stream=True)
        events = server.receive_data(client.data_to_send())
        self.assertEqual(next(e.headers for e in events if isinstance(e, RequestReceived)), headers)

    def test_anyio_noisy_worker_completes_within_deadline(self):
        # Run from -c so AnyIO does not replay unittest.__main__ as a script
        # (its relative imports require a package and fail in worker startup).
        script = '''
import sys
sys.path.insert(0, sys.argv[1])
import anyio
from anyio import to_process
from test_dependency_network import noisy_worker
async def run():
    with anyio.fail_after(5):
        assert await to_process.run_sync(noisy_worker, cancellable=True) == 'complete'
anyio.run(run)
'''
        result = subprocess.run([sys.executable, '-c', script, str(Path(__file__).parent)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
