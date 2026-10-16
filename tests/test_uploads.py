"""HTTP upload regression checks; model inference and hosted generation are isolated."""
import importlib
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

import fitz
from fastapi.testclient import TestClient


class UploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
        modules = {}
        for name, functions in {
            'embeddings': ['create_embedding', 'create_embeddings'],
            'vector_store': ['replace_document', 'hybrid_search'],
            'generation': ['generate_answer'],
        }.items():
            module = ModuleType(name)
            for function in functions:
                setattr(module, function, Mock(return_value=[]))
            modules[name] = module
        cls.modules_patch = patch.dict(sys.modules, modules)
        cls.modules_patch.start()
        cls.env_patch = patch.dict(os.environ, {'DOCLENS_SESSION_SECRET': 'test-only-authentication-key'})
        cls.env_patch.start()
        cls.app_module = importlib.import_module('main')
        cls.client = TestClient(cls.app_module.app)
        cls.headers = {'X-DocLens-Internal-Key': 'test-only-authentication-key'}

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.env_patch.stop()
        cls.modules_patch.stop()

    def test_25_mib_pdf_is_indexed(self):
        with fitz.open() as doc:
            page = doc.new_page()
            page.insert_text((72, 72), 'DocLens large PDF regression sample.')
            pdf = doc.tobytes()
        # Valid PDF with trailing whitespace: tests transfer size without expensive inference.
        pdf += b' ' * (25 * 1024 * 1024 - len(pdf))
        response = self.client.post('/documents/process', headers=self.headers,
                                    files={'file': ('large.pdf', pdf, 'application/pdf')})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['indexed'])
        self.assertEqual(response.json()['total_chunks'], 1)
        self.app_module.replace_document.assert_called()

    def test_health_responds_while_embedding_is_busy(self):
        started, release = threading.Event(), threading.Event()
        def slow_embedding(texts):
            started.set()
            release.wait(5)
            return []
        with fitz.open() as doc:
            doc.new_page().insert_text((72, 72), 'A document with text.')
            pdf = doc.tobytes()
        with TestClient(self.app_module.app) as client, patch.object(
            self.app_module, 'create_embeddings', side_effect=slow_embedding
        ):
            with ThreadPoolExecutor() as pool:
                upload = pool.submit(client.post, '/documents/process', headers=self.headers,
                                     files={'file': ('busy.pdf', pdf, 'application/pdf')})
                try:
                    self.assertTrue(started.wait(2))
                    health = pool.submit(client.get, '/')
                    self.assertEqual(health.result(timeout=2).status_code, 200)
                    metrics = pool.submit(client.get, '/metrics')
                    self.assertEqual(metrics.result(timeout=2).status_code, 200)
                finally:
                    release.set()
                self.assertEqual(upload.result(timeout=3).status_code, 200)

    def test_oversized_pdf_is_rejected(self):
        response = self.client.post('/documents/process', headers=self.headers,
                                    files={'file': ('large.pdf', b' ' * (50 * 1024 * 1024 + 1), 'application/pdf')})
        self.assertEqual(response.status_code, 413)

    def test_invalid_pdf_is_rejected(self):
        response = self.client.post('/documents/process', headers=self.headers,
                                    files={'file': ('bad.pdf', b'not a pdf', 'application/pdf')})
        self.assertEqual(response.status_code, 400)

    def test_upload_requires_authentication(self):
        response = self.client.post('/documents/process', files={'file': ('test.pdf', b'test', 'application/pdf')})
        self.assertEqual(response.status_code, 401)

    def test_metrics_are_exposed(self):
        with TestClient(self.app_module.app) as client:
            client.get('/')
            response = client.get('/metrics')
            self.assertEqual(response.status_code, 200)
            self.assertIn('http_requests_total', response.text)
            self.assertIn('http_request_duration_seconds_bucket', response.text)


if __name__ == '__main__':
    unittest.main()
