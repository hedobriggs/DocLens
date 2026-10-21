#!/usr/bin/env python3
"""Create private runtime files; credentials never become image build inputs."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--port', type=int, default=3000, help='loopback frontend port; 0 chooses an ephemeral test port')
parser.add_argument('--project', default='doclens-portable-' + secrets.token_hex(4))
parser.add_argument('--backend-image', default='doclens-portable-backend:3a07c4d')
parser.add_argument('--frontend-image', default='doclens-portable-frontend:3a07c4d')
parser.add_argument('--synthetic-test', action='store_true', help='dummy provider key; synthetic smoke only, no real generation')
parser.add_argument('--domain', help='public DNS hostname for optional HTTPS deployment')
parser.add_argument('--key-from-environment', action='store_true', help='read GEMINI_API_KEY privately without prompting for it')


def main():
    args = parser.parse_args()
    if not 0 <= args.port <= 65535 or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,62}', args.project):
        parser.error('Invalid port or project name')
    if args.domain and (len(args.domain) > 253 or not re.fullmatch(r'(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}', args.domain)):
        parser.error('Supply a DNS hostname only, without scheme, port or path')
    if (ROOT / '.runtime').exists():
        raise SystemExit('Refusing to overwrite .runtime; preserve the existing deployment first.')
    existing = subprocess.check_output(['docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=' + args.project], text=True)
    volumes = subprocess.check_output(['docker', 'volume', 'ls', '-q', '--filter', 'label=com.docker.compose.project=' + args.project], text=True)
    all_volumes = set(subprocess.check_output(['docker', 'volume', 'ls', '--format', '{{.Name}}'], text=True).splitlines())
    reserved = {args.project + '_' + name for name in ['index', 'snapshots', 'tls-data', 'tls-config']}
    if existing.strip() or volumes.strip() or all_volumes & reserved:
        raise SystemExit('Refusing an existing project or its data volumes; choose a fresh project name.')
    os.umask(0o077)
    if args.synthetic_test:
        email, password, key = 'trial@synthetic.invalid', secrets.token_urlsafe(24), 'synthetic-not-a-provider-key'
    else:
        email = input('Administrator email: ').strip()
        password = getpass.getpass('Administrator password (12+ characters): ')
        if password != getpass.getpass('Confirm password: '):
            raise SystemExit('Passwords differ; nothing saved.')
        key = os.environ.get('GEMINI_API_KEY', '').strip() if args.key_from_environment else getpass.getpass('Gemini API key: ').strip()
    if '@' not in email or len(password) < 12 or len(password.encode()) > 72 or not key:
        raise SystemExit('Email/key required; password must have 12+ characters and at most 72 UTF-8 bytes.')
    for value in (email, key, args.frontend_image, args.backend_image):
        if any(c in value for c in '\r\n\0'):
            raise SystemExit('Newline or NUL in configuration; nothing saved.')
    # Password is sent on stdin, never in process arguments, logs or the image.
    program = "let p='';process.stdin.setEncoding('utf8');process.stdin.on('data',d=>p+=d);process.stdin.on('end',()=>process.stdout.write(require('bcryptjs').hashSync(p,12)));"
    result = subprocess.run(['docker', 'run', '--rm', '-i', '--network', 'none', '--entrypoint', 'node', args.frontend_image, '-e', program], input=password, text=True, capture_output=True)
    if result.returncode or not re.fullmatch(r'\$2[aby]\$12\$.{53}', result.stdout):
        raise SystemExit('Password hashing failed. Build/load the frontend image first; nothing saved.')
    session = secrets.token_urlsafe(48)
    with tempfile.TemporaryDirectory(prefix='.runtime-new-', dir=ROOT) as temporary:
        folder = Path(temporary)
        (folder / 'backend.env').write_text('DOCLENS_SESSION_SECRET=' + session + '\nGEMINI_API_KEY=' + key + '\n')
        (folder / 'frontend.env').write_text('DOCLENS_SESSION_SECRET=' + session + '\nDOCLENS_ADMIN_EMAIL=' + email + '\nDOCLENS_ADMIN_PASSWORD_HASH=' + result.stdout + '\n')
        (folder / 'compose.env').write_text('COMPOSE_PROJECT_NAME=' + args.project + '\nHTTP_PORT=' + str(args.port) + '\nBACKEND_IMAGE=' + args.backend_image + '\nFRONTEND_IMAGE=' + args.frontend_image + '\n' + ('DOMAIN=' + args.domain + '\n' if args.domain else ''))
        if args.synthetic_test:
            (folder / 'test-login.json').write_text(json.dumps({'email': email, 'password': password}))
        for file in folder.iterdir():
            file.chmod(0o600)
        # Recheck instead of replacing a deployment created during prompting/build.
        destination = ROOT / '.runtime'
        destination.mkdir(mode=0o700)
        for file in folder.iterdir():
            file.rename(destination / file.name)
    print('Private runtime configuration created. No credential values printed.')
    if args.synthetic_test:
        print('SYNTHETIC TEST MODE: Gemini answers will not work with this dummy key.')


if __name__ == '__main__':
    main()
