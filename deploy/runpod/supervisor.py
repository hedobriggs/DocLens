"""Single-container RunPod entrypoint; no Docker daemon or runtime installation."""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

DATA = Path('/workspace/doclens')
PHASE = 'volume validation'
SECRETS = ('DOCLENS_ADMIN_EMAIL', 'DOCLENS_ADMIN_PASSWORD', 'GEMINI_API_KEY')


def health(url):
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def private_directory(path, uid):
    if path.is_symlink():
        raise ValueError('Refuse symbolic link in persistent storage')
    path.mkdir(mode=0o700, exist_ok=True)
    if path.stat().st_uid != uid and any(path.iterdir()):
        raise ValueError('Existing storage ownership mismatch; no migration performed')
    os.chown(path, uid, uid)
    os.chmod(path, 0o700)


def attached_volume(mountinfo):
    # Bind mounts can share a device with /; os.path.ismount misses those.
    return any(len(fields := line.split()) > 5 and fields[4] == '/workspace'
               for line in mountinfo.splitlines())


def main():
    global PHASE
    # A container root filesystem is not durable. Refuse to silently use it.
    if not attached_volume(Path('/proc/self/mountinfo').read_text()):
        raise ValueError('Attach a persistent volume at /workspace before starting')
    if DATA.is_symlink():
        raise ValueError('Refuse symbolic link in persistent storage')
    DATA.mkdir(mode=0o755, exist_ok=True)
    config_link = Path('/config')
    if not config_link.exists():
        config_link.symlink_to(DATA / 'config')
    if not config_link.is_symlink() or config_link.readlink() != DATA / 'config':
        raise ValueError('Unexpected configuration path')
    lock = os.fdopen(os.open(DATA / 'run.lock', os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600), 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    private_directory(DATA / 'index', 10002)
    private_directory(DATA / 'snapshots', 10002)
    private_directory(DATA / 'config', 0)
    # Existing bootstrap performs exact credential matching and refuses adoption
    # of an existing index without its matching saved identity/configuration.
    PHASE = 'private configuration'
    initial = Path('/run/doclens-initial.env')
    values = {key: os.environ.pop(key, '') for key in SECRETS}
    if any(not value or any(c in value for c in '\r\n\0') for value in values.values()):
        raise ValueError('Bind all three required private RunPod secrets')
    try:
        fd = os.open(initial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write('\n'.join(key + "='" + value + "'" for key, value in values.items()))
        subprocess.run(['node', '-e', "require('./bootstrap.cjs').initialize('/config','/workspace/doclens/index','/run/doclens-initial.env')"],
                       cwd='/opt/frontend', check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        initial.unlink(missing_ok=True)
        values.clear()
    os.chmod(DATA / 'config', 0o755)
    # Only these internal aliases are added; no DNS changes outside this Pod.
    with open('/etc/hosts', 'a') as hosts:
        hosts.write('\n127.0.0.1 backend qdrant\n')
    children = []
    stopping = False

    def stop(signum=None, frame=None):
        nonlocal stopping
        stopping = True
        for child in reversed(children):
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    def start(command, cwd, uid, extra=None):
        env = os.environ.copy()
        # Provider credentials never enter Qdrant/frontend; password never enters
        # any long-lived child. Each app reads only its own UID-protected config.
        for key in (*SECRETS, 'DOCLENS_SESSION_SECRET', 'DOCLENS_ADMIN_PASSWORD_HASH'):
            env.pop(key, None)
        env.update({'NO_PROXY': 'localhost,127.0.0.1,backend,qdrant',
                    'no_proxy': 'localhost,127.0.0.1,backend,qdrant'})
        env.update(extra or {})
        child = subprocess.Popen(command, cwd=cwd, env=env, user=uid, group=uid,
                                 extra_groups=[], start_new_session=True)
        children.append(child)

    def wait_ready(url):
        deadline = time.monotonic() + 180
        while not health(url):
            if stopping or any(p.poll() is not None for p in children) or time.monotonic() > deadline:
                raise RuntimeError('Component failed readiness')
            time.sleep(0.25)

    try:
        PHASE = 'Qdrant readiness'
        start(['/opt/qdrant/lib/ld-linux-x86-64.so.2', '--library-path', '/opt/qdrant/lib', '/opt/qdrant/qdrant'], '/opt/qdrant', 10002, {
            'QDRANT__STORAGE__STORAGE_PATH': str(DATA / 'index'),
            'QDRANT__STORAGE__SNAPSHOTS_PATH': str(DATA / 'snapshots')})
        wait_ready('http://127.0.0.1:6333/readyz')
        PHASE = 'API readiness'
        backend = json.loads((DATA / 'config/backend/settings.json').read_text())
        start(['python', '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8000', '--workers', '1'], '/app', 10001, backend)
        backend.clear()
        wait_ready('http://127.0.0.1:8000/')
        PHASE = 'frontend readiness'
        start(['node', 'bootstrap.cjs', 'frontend'], '/opt/frontend', 1000)
        wait_ready('http://127.0.0.1:3000/')
        PHASE = 'component supervision'
        print('DocLens ready: frontend 3000; API and Qdrant loopback only', flush=True)
        while not stopping:
            if any(child.poll() is not None for child in children):
                raise RuntimeError('Component exited; stopping entire Pod container')
            time.sleep(0.5)
    finally:
        stop()
        deadline = time.monotonic() + 25
        for child in children:
            try:
                child.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()


if __name__ == '__main__':
    if sys.argv[1:] == ['health']:
        sys.exit(0 if all(health('http://127.0.0.1:' + suffix) for suffix in
                         ['3000/', '8000/', '6333/readyz']) else 1)
    try:
        main()
    except Exception as error:
        print('DocLens Pod ' + PHASE + ' failed (' + type(error).__name__ +
              '); check secret bindings, attached volume and component readiness. No automatic reset.', file=sys.stderr)
        sys.exit(1)
