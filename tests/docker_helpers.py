"""Shared Docker/Qdrant readiness for isolated synthetic publication tests."""
import subprocess
import time
import requests


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True, stderr=subprocess.PIPE).strip()


def ready(url):
    deadline = time.monotonic() + 120
    session = requests.Session()
    session.trust_env = False  # Local fixture only; preserve outbound process proxy settings.
    with session:
        while time.monotonic() < deadline:
            try:
                if session.get(url, timeout=2).status_code == 200:
                    return
            except requests.RequestException:
                pass
            time.sleep(.25)
    raise RuntimeError('Synthetic Qdrant readiness failed')
