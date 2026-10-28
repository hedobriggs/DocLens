"""Security compatibility regressions for the pinned ASGI framework."""
import unittest

from starlette.applications import Starlette
from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient


class FrameworkDependencies(unittest.TestCase):
    def scope(self, path='/', host=b'localhost'):
        return {'type': 'http', 'method': 'GET', 'scheme': 'http',
                'path': path, 'raw_path': path.encode(), 'root_path': '',
                'query_string': b'', 'server': ('localhost', 80),
                'headers': [(b'host', host)]}

    def test_host_cannot_prepend_path_to_reconstructed_url(self):
        try:
            url = Request(self.scope('/documents/process', b'localhost/ask')).url
        except ValueError:
            return  # Explicit malformed-authority rejection is safe.
        self.assertEqual(url.path, '/documents/process')

    def test_nonabsolute_path_cannot_replace_url_authority(self):
        try:
            url = Request(self.scope('@attacker.invalid')).url
        except ValueError:
            return
        self.assertEqual(url.hostname, 'localhost')

    def test_nonstandard_method_cannot_dispatch_internal_helper(self):
        calls = []

        class Endpoint(HTTPEndpoint):
            async def get(self, request):
                return JSONResponse({'ok': True})

            async def internal(self, request):
                calls.append('must not run')
                return JSONResponse({'internal': True})

        with TestClient(Starlette(routes=[Route('/synthetic', Endpoint)])) as client:
            self.assertEqual(client.get('/synthetic').status_code, 200)
            self.assertEqual(client.request('INTERNAL', '/synthetic').status_code, 405)
            self.assertEqual(calls, [])

    def test_urlencoded_forms_enforce_field_count_and_size(self):
        async def bounded_form(request):
            async with request.form(max_fields=1, max_part_size=8) as form:
                return JSONResponse(dict(form))

        with TestClient(Starlette(routes=[Route('/synthetic', bounded_form, methods=['POST'])])) as client:
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            self.assertEqual(client.post('/synthetic', content='a=ok', headers=headers).status_code, 200)
            for body in ['a=ok&b=extra', 'a=' + 'x' * 16]:
                with self.subTest(body=body):
                    self.assertEqual(client.post('/synthetic', content=body, headers=headers).status_code, 400)
            self.assertEqual(client.post('/synthetic', content='a=retry', headers=headers).status_code, 200)


if __name__ == '__main__':
    unittest.main()
