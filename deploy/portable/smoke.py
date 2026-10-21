#!/usr/bin/env python3
"""Synthetic-only functional test of an already configured, isolated deployment."""
import argparse
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--restart', action='store_true', help='restart only this configured project and check stored identities')
parser.add_argument('--live-answers', action='store_true', help='send synthetic context to configured Gemini; requires a real key')
args = parser.parse_args()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
EMPLOYERS = ['Aster Research', 'Birch Analytics', 'Cobalt Systems', 'Delta Robotics', 'Elm Computing']


def dc(*command):
    return subprocess.check_output([str(ROOT / 'doclens'), *command], text=True).strip()


def pdf(pages):
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'', b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    kids = []
    for number, text in enumerate(pages):
        page_id = len(objects) + 1
        kids.append(str(page_id) + ' 0 R')
        escaped = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        stream = ('BT /F1 12 Tf 30 740 Td (' + escaped + ') Tj ET').encode('ascii')
        objects.extend([('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents ' + str(page_id + 1) + ' 0 R >>').encode(), b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream'])
    objects[1] = ('<< /Type /Pages /Count ' + str(len(kids)) + ' /Kids [' + ' '.join(kids) + '] >>').encode()
    body, offsets = b'%PDF-1.4\n', [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(body)); body += str(number).encode() + b' 0 obj\n' + obj + b'\nendobj\n'
    start = len(body)
    body += ('xref\n0 ' + str(len(offsets)) + '\n0000000000 65535 f \n').encode()
    body += b''.join(('%010d 00000 n \n' % offset).encode() for offset in offsets[1:])
    return body + ('trailer << /Size ' + str(len(offsets)) + ' /Root 1 0 R >>\nstartxref\n' + str(start) + '\n%%EOF\n').encode()


def request(path, data=None, cookie=None, content_type='application/json'):
    address = dc('port', 'frontend', '3000').splitlines()[0].rsplit(':', 1)[1]
    headers = {'Content-Type': content_type}
    if cookie:
        headers['Cookie'] = cookie
    req = urllib.request.Request('http://127.0.0.1:' + address + path, data=data, headers=headers)
    try:
        response = opener.open(req, timeout=150)
    except urllib.error.HTTPError as error:
        response = error
    body = response.read()
    return response.status, response.headers, json.loads(body) if body else {}


def upload(data, cookie=None):
    boundary = 'doclens-portable-synthetic-boundary'
    body = ('--' + boundary + '\r\nContent-Disposition: form-data; name="file"; filename="portable-synthetic.pdf"\r\nContent-Type: application/pdf\r\n\r\n').encode() + data + ('\r\n--' + boundary + '--\r\n').encode()
    return request('/api/documents/process', body, cookie, 'multipart/form-data; boundary=' + boundary)


def records():
    code = "import json,requests; s=requests.Session(); s.trust_env=False; out={};\nfor c in ['document_chunks','doclens_document_publications']:\n r=s.post('http://qdrant:6333/collections/'+c+'/points/scroll',json={'limit':1000,'with_payload':True},timeout=10); r.raise_for_status(); out[c]=sorted(r.json()['result']['points'],key=lambda p:str(p['id']))\nprint(json.dumps(out))"
    return json.loads(dc('exec', '-T', 'backend', 'python', '-c', code))


login_file = ROOT / '.runtime/test-login.json'
if login_file.exists():
    login = json.loads(login_file.read_text())
    if args.live_answers:
        raise SystemExit('Synthetic configuration has a dummy key; configure a fresh live-evaluation project instead.')
else:
    import getpass
    login = {'email': input('Administrator email: ').strip(), 'password': getpass.getpass('Administrator password: ')}
status, _, _ = upload(pdf(['Synthetic anonymous denial test']))
assert status == 401, 'Anonymous upload must be denied'
status, headers, body = request('/api/auth/login', json.dumps(login).encode())
assert status == 200, 'Login failed'
cookie = headers['Set-Cookie'].split(';', 1)[0]
status, _, body = upload(pdf(['Employer: ' + name for name in EMPLOYERS]), cookie)
assert status == 200 and body.get('indexed') is True and body.get('total_chunks') == 5, 'Synthetic five-page ingestion failed'
before = records()
pointer = next(p['payload']['revision'] for p in before['doclens_document_publications'] if p['payload']['document_name'] == 'portable-synthetic.pdf')
active = [p for p in before['document_chunks'] if p['payload'].get('_doclens_revision') == pointer]
assert len(active) == 5 and {p['payload']['page_number'] for p in active} == {1, 2, 3, 4, 5}
for bad, expected in [(b'not a PDF', 400), (pdf(['Synthetic page'] * 301), 413)]:
    status, _, _ = upload(bad, cookie)
    assert status == expected, 'Invalid replacement status changed'
    assert records() == before, 'Failed replacement changed stored records'
results = {'anonymous_upload': 401, 'login': 200, 'real_model_ingestion_chunks': 5, 'invalid_replacement_preserved': True, 'page_limit_preserved': True, 'restart': 'not run', 'live_answers': 'not run'}
if args.live_answers:
    status, _, body = request('/api/ask', json.dumps({'question': 'List all employers in this CV', 'document_name': 'portable-synthetic.pdf'}).encode(), cookie)
    assert status == 200 and all(n in body.get('answer', '') for n in EMPLOYERS), 'Live answer incomplete'
    assert {c['page_number'] for c in body.get('citations', [])} == {1, 2, 3, 4, 5}, 'Live citations incomplete'
    results['live_answers'] = 'all five synthetic employers and page citations passed'
if args.restart:
    dc('restart')
    dc('up', '-d', '--wait', '--wait-timeout', '180')
    assert records() == before, 'Restart changed data or publication metadata'
    results['restart'] = 'all points, payloads and publication records preserved'
print(json.dumps(results, indent=2))
