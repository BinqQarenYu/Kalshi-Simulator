import urllib.request
import json
import time

time.sleep(5) # Wait for server boot

try:
    req = urllib.request.Request(
        'http://localhost:8000/api/bot/strategy/select',
        data=json.dumps({"strategy_id": "all"}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    res = urllib.request.urlopen(req)
    print("Set Strategy ALL:", res.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code, e.read().decode('utf-8'))
except Exception as e:
    print("Error selecting bot:", e)
