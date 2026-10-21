"""Read only the backend's private settings, then replace this process with API."""
import json
import os
from pathlib import Path
import sys

try:
    values = json.loads(Path('/config/backend/settings.json').read_text())
    for key in ['DOCLENS_SESSION_SECRET', 'GEMINI_API_KEY']:
        value = values[key]
        if not isinstance(value, str) or not value:
            raise ValueError('Incomplete backend configuration')
        os.environ[key] = value
except Exception as error:
    print('DocLens backend configuration failed (' + type(error).__name__ + '); preserve settings and volumes', file=sys.stderr)
    sys.exit(1)
os.execvp('python', ['python', '-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8000', '--workers', '1'])
