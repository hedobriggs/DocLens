"""Build locally with the cloud's existing verified proxy/CA; does not deploy."""
import os
from pathlib import Path
import socket
import subprocess
from urllib.parse import urlsplit

root=Path(__file__).resolve().parents[2]
env={**os.environ,'BUILDX_CONFIG':str(root.parent/'.cache/buildx')}
args=['docker','build','--network','host','--secret','id=build_ca,src=/etc/ssl/certs/ca-certificates.crt']
seen=set()
for name in ('HTTPS_PROXY','HTTP_PROXY'):
    host=urlsplit(os.environ.get(name,'')).hostname
    if host and host not in seen:
        args+=['--add-host',host+':'+socket.gethostbyname(host)]
        seen.add(host)
args+=['--build-arg','HTTPS_PROXY','--build-arg','HTTP_PROXY','--build-arg','NO_PROXY',
       '-f',str(root/'backend/Dockerfile.platform'),'-t','doclens-milestone1-review',str(root/'backend')]
raise SystemExit(subprocess.call(args,env=env))
