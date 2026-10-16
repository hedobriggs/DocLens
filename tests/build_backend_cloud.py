"""Build with the cloud machine's existing verified proxy trust, without copying it.

Normal networks can use docker build -t doclens-review-backend ./backend directly.
"""
import os
from pathlib import Path
import socket
import subprocess
from urllib.parse import urlsplit

root = Path(__file__).resolve().parents[1]
args = ['docker', 'build', '--network', 'host', '--secret',
        'id=build_ca,src=/etc/ssl/certs/ca-certificates.crt']
seen = set()
for name in ('HTTPS_PROXY', 'HTTP_PROXY'):
    host = urlsplit(os.environ.get(name, '')).hostname
    if host and host not in seen:
        args += ['--add-host', host + ':' + socket.gethostbyname(host)]
        seen.add(host)
args += ['--build-arg', 'HTTPS_PROXY', '--build-arg', 'HTTP_PROXY', '--build-arg', 'NO_PROXY',
         '-t', 'doclens-review-backend', str(root/'backend')]
raise SystemExit(subprocess.call(args))
