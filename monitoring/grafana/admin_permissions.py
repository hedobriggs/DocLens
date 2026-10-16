"""Remove default Viewer/Editor access from the provisioned monitoring folder.

Run before exposing Grafana beyond loopback. Uses independent Grafana credentials.
"""
import base64
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

url = os.environ.get('GRAFANA_URL', 'http://grafana:3000').rstrip('/')
auth = base64.b64encode(('admin:' + os.environ['GRAFANA_ADMIN_PASSWORD']).encode()).decode()
for attempt in range(90):
    try:
        with urlopen(Request(url + '/api/folders/doclens-admin', headers={'Authorization': 'Basic ' + auth}), timeout=5):
            pass
        request = Request(url + '/api/folders/doclens-admin/permissions', method='POST',
                          headers={'Authorization': 'Basic ' + auth, 'Content-Type': 'application/json'},
                          data=json.dumps({'items': [{'role': 'Admin', 'permission': 4}]}).encode())
        with urlopen(request, timeout=5) as response:
            assert response.status == 200
        print('DocLens Grafana folder permissions: Admin only')
        break
    except (HTTPError, URLError, TimeoutError):
        if attempt == 89:
            raise RuntimeError('Grafana admin permissions were not configured; do not expose Grafana') from None
        time.sleep(1)
