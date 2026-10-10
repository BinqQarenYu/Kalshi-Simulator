import urllib.request
import json
import time

time.sleep(5) # Wait for server boot

try:
    req = urllib.request.Request(
        'http://localhost:8000/api/bot/strategy/select',
        data=json.dumps({"strategy_id": "3_step_domination_bot"}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    res = urllib.request.urlopen(req)
    print("Select Bot 1:", res.read().decode('utf-8'))
except Exception as e:
    print("Error selecting bot:", e)

try:
    req = urllib.request.Request(
        'http://localhost:8000/api/settings/mode',
        data=json.dumps({"mode": "live"}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    res = urllib.request.urlopen(req)
    print("Set Mode Live:", res.read().decode('utf-8'))
except Exception as e:
    print("Error setting mode:", e)

