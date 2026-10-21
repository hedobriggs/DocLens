"""Start/stop only this checkout's portable project. Never source secret files."""
import argparse
import fcntl
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def private_text(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise SystemExit('Private configuration must be a regular file accessible only to you; run chmod 600 on ' + str(path))
    return path.read_text()


def provider_key():
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not key:
        path = ROOT / '.env'
        if path.exists() or path.is_symlink():
            entries = [line.split('=', 1)[1].strip() for line in private_text(path).splitlines()
                       if line.strip().startswith('GEMINI_API_KEY=')]
            if len(entries) != 1:
                raise SystemExit('Put exactly one GEMINI_API_KEY=your-key line in the private root .env file.')
            key = entries[0]
            if key[:1] in ('"', "'") and key[-1:] == key[:1]:
                key = key[1:-1]
    if not key or key == 'replace-with-your-gemini-api-key' or any(c in key for c in '\r\n\0'):
        raise SystemExit('Set GEMINI_API_KEY in your server secret environment or in the root .env file (chmod 600 .env), then rerun ./start. No configuration was created.')
    return key


def saved_config():
    folder = HERE / '.runtime'
    if folder.is_symlink() or not folder.is_dir() or folder.stat().st_mode & 0o077:
        raise SystemExit('Existing .runtime must be a private directory; it will not be replaced.')
    values = {}
    for name in ('compose.env', 'frontend.env', 'backend.env'):
        content = private_text(folder / name)
        if name == 'compose.env':
            values = dict(line.split('=', 1) for line in content.splitlines() if '=' in line)
    if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,62}', values.get('COMPOSE_PROJECT_NAME', '')):
        raise SystemExit('Invalid saved project; no services changed.')
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'stop'])
    parser.add_argument('--port', type=int, help='first setup only; default 3000')
    args = parser.parse_args()
    if args.port is not None and (args.action != 'start' or not 1 <= args.port <= 65535):
        parser.error('--port is a startup port between 1 and 65535')
    # The lock covers prompts, builds and Compose; a second invocation must not
    # overwrite credentials or stop a project still being initialized.
    descriptor = os.open(HERE / '.launcher.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit('Another start/stop is already running for this checkout.')
        folder = HERE / '.runtime'
        exists = folder.exists() or folder.is_symlink()
        if args.action == 'stop' and not exists:
            print('This checkout has no configured deployment. Nothing stopped.')
            return
        config = saved_config() if exists else None
        version = run(['docker', 'compose', 'version', '--short'], capture_output=True, text=True).stdout.strip()
        match = re.search(r'(\d+)\.(\d+)\.(\d+)', version)
        if not match or tuple(map(int, match.groups())) < (2, 30, 0):
            raise SystemExit('Docker Compose 2.30+ is required. Update Docker Desktop/Compose.')
        run(['docker', 'info'], stdout=subprocess.DEVNULL)
        if args.action == 'start':
            if config and args.port is not None and str(args.port) != config.get('HTTP_PORT'):
                raise SystemExit('This checkout already has a saved port; existing configuration was preserved.')
            key = None
            if not exists:
                key = provider_key()
                if not sys.stdin.isatty():
                    raise SystemExit('Run ./start in an interactive terminal for first-time login setup.')
                port = args.port or 3000
                with socket.socket() as probe:
                    try:
                        probe.bind(('127.0.0.1', port))
                    except OSError:
                        raise SystemExit('Port is unavailable. Choose another port, for example ./start --port 3001. Existing services were not changed.')
            images = [config.get(k, default) if config else default for k, default in
                      [('BACKEND_IMAGE', 'doclens-portable-backend:66db29f'), ('FRONTEND_IMAGE', 'doclens-portable-frontend:66db29f')]]
            missing = any(subprocess.run(['docker', 'image', 'inspect', image], stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL).returncode != 0 for image in images)
            if missing:
                print('Building application images. First startup can take several minutes.', flush=True)
                build_env = os.environ.copy()
                build_env.pop('GEMINI_API_KEY', None)
                build_env.update(zip(('BACKEND_IMAGE', 'FRONTEND_IMAGE'), images))
                run([sys.executable, str(HERE / 'build.py')], env=build_env)
            if not exists:
                env = os.environ.copy()
                env['GEMINI_API_KEY'] = key
                run([sys.executable, str(HERE / 'configure.py'), '--key-from-environment', '--port', str(port)], env=env)
                config = saved_config()
        command = [str(HERE / 'doclens')]
        if config.get('DOMAIN'):
            command.append('--https')
        if args.action == 'stop':
            run(command + ['stop'])
            print('DockLens stopped. Settings and document volumes were preserved.')
        else:
            run(command + ['up', '-d', '--no-build', '--wait', '--wait-timeout', '180'])
            address = 'https://' + config['DOMAIN'] if config.get('DOMAIN') else 'http://127.0.0.1:' + config.get('HTTP_PORT', '3000')
            print('DockLens is ready: ' + address)


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        print('Startup/stop step failed (exit %s). No automatic retry or data cleanup was performed.' % error.returncode, file=sys.stderr)
        sys.exit(error.returncode if error.returncode > 0 else 1)
    except (OSError, ValueError) as error:
        print('Cannot continue: ' + str(error), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print('\nCancelled. Existing settings and document volumes were preserved.', file=sys.stderr)
        sys.exit(130)
