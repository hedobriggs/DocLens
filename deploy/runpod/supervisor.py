"""Single-container RunPod entrypoint; no Docker daemon or runtime installation."""
from contextlib import contextmanager
import fcntl
import json
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import signal
import stat
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


@contextmanager
def private_initial(values, initial):
    # Called only while holding the installation lock. Never follow a link or
    # treat leftover input as authority: current secrets must match saved config.
    try:
        stale = initial.lstat()
    except FileNotFoundError:
        stale = None
    if stale is not None:
        if (not stat.S_ISREG(stale.st_mode) or stale.st_uid != os.geteuid()
                or stale.st_nlink != 1 or stat.S_IMODE(stale.st_mode) & 0o077):
            raise ValueError('Refuse unsafe leftover private input')
        initial.unlink()
    fd = os.open(initial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    identity = os.fstat(fd)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write('\n'.join(key + "='" + value + "'" for key, value in values.items()))
        yield initial
    finally:
        try:
            current = initial.lstat()
        except FileNotFoundError:
            current = None
        # Never remove a different file/link if the path was replaced.
        if current is not None and (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
            initial.unlink()


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
        with private_initial(values, initial):
            subprocess.run(['node', '-e', "require('./bootstrap.cjs').initialize('/config','/workspace/doclens/index','/run/doclens-initial.env')"],
                           cwd='/opt/frontend', check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        values.clear()
    os.chmod(DATA / 'config', 0o755)
    # Only these internal aliases are added; no DNS changes outside this Pod.
    with open('/etc/hosts', 'a') as hosts:
        hosts.write('\n127.0.0.1 backend qdrant prometheus grafana\n')
    children = []
    critical_children = []
    stopping = False

    def stop(signum=None, frame=None):
        nonlocal stopping
        stopping = True
        for child in reversed(children):
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    def start(command, cwd, uid, extra=None, critical=True):
        env = os.environ.copy()
        # Provider credentials never enter Qdrant/frontend; password never enters
        # any long-lived child. Each app reads only its own UID-protected config.
        for key in (*SECRETS, 'DOCLENS_SESSION_SECRET', 'DOCLENS_ADMIN_PASSWORD_HASH'):
            env.pop(key, None)
        env.update({'NO_PROXY': 'localhost,127.0.0.1,backend,qdrant,prometheus,grafana',
                    'no_proxy': 'localhost,127.0.0.1,backend,qdrant,prometheus,grafana'})
        env.update(extra or {})
        child = subprocess.Popen(command, cwd=cwd, env=env, user=uid, group=uid,
                                 extra_groups=[], start_new_session=True)
        children.append(child)
        if critical: critical_children.append(child)
        return child

    def wait_ready(url, observed=None):
        deadline = time.monotonic() + 180
        while not health(url):
            if stopping or any(p.poll() is not None for p in critical_children) or (observed is not None and observed.poll() is not None) or time.monotonic() > deadline:
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
        grafana_key = hmac.new(backend['DOCLENS_SESSION_SECRET'].encode(), b'doclens-grafana-encryption-v1', hashlib.sha256).hexdigest()
        backend.clear()
        wait_ready('http://127.0.0.1:8000/')
        PHASE = 'frontend readiness'
        start(['node', 'bootstrap.cjs', 'frontend'], '/opt/frontend', 1000)
        wait_ready('http://127.0.0.1:3000/')
        if os.environ.get('DOCLENS_MONITORING') == '1':
            monitor_start = len(children)
            try:
                PHASE = 'monitoring readiness'
                private_directory(DATA / 'prometheus', 10003)
                private_directory(DATA / 'grafana', 10004)
                prometheus = start(['/opt/prometheus/prometheus', '--config.file=/opt/monitoring/prometheus.yml',
                       '--storage.tsdb.path=' + str(DATA / 'prometheus'),
                       '--storage.tsdb.retention.time=2d', '--storage.tsdb.retention.size=256MB',
                       '--storage.tsdb.wal-compression', '--query.max-concurrency=4',
                       '--query.max-samples=500000', '--query.timeout=10s',
                       '--web.listen-address=127.0.0.1:9090'], '/opt/monitoring', 10003,
                      {'GOMEMLIMIT': '192MiB'}, critical=False)
                wait_ready('http://127.0.0.1:9090/-/ready', prometheus)
                grafana = start(['/opt/grafana/bin/grafana', 'server', '--homepath=/opt/grafana',
                       '--config=/opt/grafana/conf/defaults.ini'], '/opt/grafana', 10004, {
                    'GF_SERVER_HTTP_ADDR': '127.0.0.1', 'GF_SERVER_HTTP_PORT': '3001',
                    'GF_SERVER_ROOT_URL': '/monitoring/', 'GF_SERVER_SERVE_FROM_SUB_PATH': 'true',
                    'GF_PATHS_DATA': str(DATA / 'grafana'),
                    'GF_PATHS_LOGS': str(DATA / 'grafana/logs'), 'GF_LOG_MODE': 'console',
                    'GF_PATHS_PLUGINS': str(DATA / 'grafana/plugins'),
                    'GF_PATHS_BUNDLED_PLUGINS': '/opt/grafana/data/plugins-bundled',
                    'GF_AUTH_DISABLE_SIGNOUT_MENU': 'true', 'GF_LIVE_MAX_CONNECTIONS': '0',
                    'GF_PATHS_PROVISIONING': '/opt/monitoring/provisioning',
                    'GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH': '/opt/monitoring/dashboards/doclens.json',
                    'GF_SECURITY_ADMIN_PASSWORD': secrets.token_urlsafe(48),
                    'GF_SECURITY_SECRET_KEY': grafana_key,
                    'GF_AUTH_PROXY_ENABLED': 'true', 'GF_AUTH_PROXY_HEADER_NAME': 'X-DocLens-Grafana-User',
                    'GF_AUTH_PROXY_WHITELIST': '127.0.0.1', 'GF_AUTH_PROXY_ENABLE_LOGIN_TOKEN': 'false',
                    'GF_AUTH_BASIC_ENABLED': 'false', 'GF_AUTH_DISABLE_LOGIN_FORM': 'true',
                    'GF_AUTH_ANONYMOUS_ENABLED': 'false', 'GF_USERS_ALLOW_SIGN_UP': 'false',
                    'GF_ANALYTICS_REPORTING_ENABLED': 'false', 'GF_ANALYTICS_CHECK_FOR_UPDATES': 'false',
                    'GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES': 'false', 'GF_PLUGINS_PREINSTALL_DISABLED': 'true',
                    'GOMEMLIMIT': '256MiB'}, critical=False)
                wait_ready('http://127.0.0.1:3001/monitoring/api/health', grafana)
            except Exception as error:
                for child in children[monitor_start:]:
                    if child.poll() is None: os.killpg(child.pid, signal.SIGTERM)
                print('DocLens monitoring unavailable (' + type(error).__name__ + '); application remains available', flush=True)
        PHASE = 'component supervision'
        print('DocLens ready: frontend 3000; API and Qdrant loopback only', flush=True)
        reported_monitors = set()
        while not stopping:
            for child in children:
                if child not in critical_children and child.poll() is not None and child.pid not in reported_monitors:
                    reported_monitors.add(child.pid)
                    print('DocLens monitoring component exited; application remains available', flush=True)
            if any(child.poll() is not None for child in critical_children):
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
        targets = ['3000/', '8000/', '6333/readyz']
        if os.environ.get('DOCLENS_MONITORING') == '1':
            targets += ['9090/-/ready', '3001/monitoring/api/health']
        sys.exit(0 if all(health('http://127.0.0.1:' + suffix) for suffix in targets) else 1)
    try:
        main()
    except Exception as error:
        print('DocLens Pod ' + PHASE + ' failed (' + type(error).__name__ +
              '); check secret bindings, attached volume and component readiness. No automatic reset.', file=sys.stderr)
        sys.exit(1)
