import urllib.request
import json

try:
    req = urllib.request.Request(
        'http://localhost:8000/api/bot/strategy/select',
        data=json.dumps({"strategy_id": "bot1_v4_domination"}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    res = urllib.request.urlopen(req)
    print("Select Bot 1 v4:", res.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code, e.read().decode('utf-8'))
except Exception as e:
    print("Error selecting bot:", e)
