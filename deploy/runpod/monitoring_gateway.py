"""Public monitoring listeners; all authority remains in the DocLens frontend.

Only a fixed loopback frontend is reachable. Raw Grafana/Prometheus are never
proxied directly, and this process never reads configuration or session secrets.
"""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import signal
import threading
from urllib.parse import urlsplit

HOP = {'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
       'te', 'trailer', 'transfer-encoding', 'upgrade'}
LOGIN = b'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DocLens monitoring sign in</title>
<style>body{font:18px system-ui;background:#101827;color:#fff;max-width:440px;margin:10vh auto;padding:24px}label,input,button{display:block;margin:16px 0}input,button{box-sizing:border-box;width:100%;padding:12px;font:inherit}a{color:#93c5fd}:focus-visible{outline:3px solid #93c5fd;outline-offset:3px}</style>
<h1>DocLens monitoring</h1><p>Sign in with your DocLens administrator credentials. This monitoring address has its own login session.</p>
<form><label>Email<input name="email" type="email" autocomplete="username" required></label>
<label>Password<input name="password" type="password" autocomplete="current-password" required></label>
<button>Sign in</button><p role="alert" id="error"></p></form>
<script src="/login.js"></script></html>'''
SCRIPT = b'''document.querySelector('form').addEventListener('submit',async event=>{
event.preventDefault();const form=event.target,button=form.querySelector('button');
button.disabled=true;document.querySelector('#error').textContent='';
try{const response=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({email:form.email.value.trim(),password:form.password.value})});
if(response.ok){location.replace('/');return;}
document.querySelector('#error').textContent=response.status===401?'Invalid email or password.':'Unable to sign in. Please try again.';
}catch{document.querySelector('#error').textContent='Connection failed. Please try again.';}finally{button.disabled=false;}});'''


class Gateway(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 16

    def __init__(self, address, service, upstream_port=3000):
        self.prefix = '/monitoring' if service == 'grafana' else '/prometheus'
        self.landing = self.prefix + ('/d/doclens' if service == 'grafana' else '/query')
        self.upstream_port = upstream_port
        self.slots = threading.BoundedSemaphore(16)
        super().__init__(address, Handler)

    def process_request(self, request, address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


class Handler(BaseHTTPRequestHandler):
    # Never log request paths, credentials, cookies or exception messages.
    def log_message(self, *_args):
        pass

    def setup(self):
        super().setup()
        self.connection.settimeout(20)

    def reply(self, status, body=b'', content_type='text/plain', location=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; connect-src 'self'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
        if location:
            self.send_header('Location', location)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def proxy(self):
        path = urlsplit(self.path).path
        if self.path.startswith('//') or urlsplit(self.path).scheme:
            return self.reply(400)
        if path == '/':
            return self.reply(303, location=self.server.landing)
        if path in ('/login', '/login.js') and self.command in ('GET', 'HEAD'):
            return self.reply(200, SCRIPT if path.endswith('.js') else LOGIN,
                              'application/javascript' if path.endswith('.js') else 'text/html; charset=utf-8')
        if not (path.startswith(self.server.prefix + '/') or
                path in ('/api/auth/login', '/api/auth/logout')):
            return self.reply(404)
        # Reject ambiguous framing; never buffer unbounded/chunked uploads.
        lengths = self.headers.get_all('Content-Length', [])
        if self.headers.get('Transfer-Encoding') or len(lengths) > 1:
            return self.reply(400)
        try:
            length = int(lengths[0]) if lengths else 0
        except ValueError:
            return self.reply(400)
        if length < 0 or length > 2 * 1024 * 1024:
            return self.reply(413)
        upstream = http.client.HTTPConnection('127.0.0.1', self.server.upstream_port, timeout=15)
        sent = False
        try:
            body = self.rfile.read(length) if length else None
            if body is not None and len(body) != length:
                return self.reply(400)
            blocked = HOP | {'x-doclens-grafana-user', 'x-doclens-internal-key', 'authorization'}
            blocked |= {v.strip().lower() for v in self.headers.get('Connection', '').split(',')}
            headers = {k: v for k, v in self.headers.items() if k.lower() not in blocked}
            upstream.request(self.command, self.path, body=body, headers=headers)
            response = upstream.getresponse()
            self.send_response(response.status)
            sent = True
            for key, value in response.getheaders():
                if key.lower() in HOP | {'content-length'}:
                    continue
                if key.lower() == 'location':
                    # Frontend anonymous redirects stay on this listener and
                    # show its login form, never an internal hostname or loop.
                    parsed = urlsplit(value)
                    value = '/login' if parsed.path == '/' else parsed.path + ('?' + parsed.query if parsed.query else '')
                self.send_header(key, value)
            self.send_header('Connection', 'close')
            self.end_headers()
            self.close_connection = True
            if self.command != 'HEAD':
                while chunk := response.read(64 * 1024):
                    self.wfile.write(chunk)
        except (OSError, http.client.HTTPException):
            if not sent:
                self.reply(502, b'Monitoring is temporarily unavailable.')
        finally:
            upstream.close()

    do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = proxy


def main():
    servers = [Gateway(('0.0.0.0', 3001), 'grafana'), Gateway(('0.0.0.0', 9090), 'prometheus')]
    def stop(*_args):
        for server in servers:
            threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    threads = [threading.Thread(target=s.serve_forever) for s in servers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    for server in servers:
        server.server_close()


if __name__ == '__main__':
    main()
