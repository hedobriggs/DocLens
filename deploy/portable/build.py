#!/usr/bin/env python3
"""Build from a hash-checked, source-only context; never copy local data/secrets."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main(no_cache=False):
    manifest = json.loads((HERE / 'application-manifest.json').read_text())
    trust = os.environ.get('BUILD_CA_BUNDLE')
    if trust and not Path(trust).is_file():
        raise SystemExit('BUILD_CA_BUNDLE must point to an existing authorized PEM CA bundle.')
    with tempfile.TemporaryDirectory(prefix='doclens-build-') as temporary:
        context = Path(temporary)
        for name, expected in manifest['sha256'].items():
            source = ROOT / name
            if source.is_symlink() or not source.is_file():
                raise SystemExit('Source differs from approved application: ' + name)
            content = source.read_bytes()
            if hashlib.sha256(content).hexdigest() != expected:
                raise SystemExit('Source differs from approved application: ' + name)
            target = context / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            # Preserve source modes so Docker can reuse a valid dependency layer;
            # backend COPY sets its runtime readability explicitly.
            target.chmod(source.stat().st_mode & 0o777)
        dockerfiles = context / 'deploy/portable'
        dockerfiles.mkdir(parents=True)
        for service in ['backend', 'frontend']:
            dockerfile = dockerfiles / ('Dockerfile.' + service)
            shutil.copyfile(HERE / dockerfile.name, dockerfile)
            tag = os.environ.get(service.upper() + '_IMAGE', 'doclens-portable-' + service + ':doclens-release')
            command = ['docker', 'build', '--platform', 'linux/amd64', '-f', str(dockerfile), '-t', tag]
            if no_cache:
                command.append('--no-cache')
            if trust:
                command += ['--secret', 'id=build_ca,src=' + str(Path(trust).resolve())]
            subprocess.run(command + [str(context / service)], check=True)
    print('Both images built from manifest-verified sources; application base ' + manifest['application_commit'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-cache', action='store_true', help='Run fresh dependency installation/build layers for both images.')
    main(no_cache=parser.parse_args().no_cache)
