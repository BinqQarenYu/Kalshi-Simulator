import urllib.request, json
data = json.dumps({"strategy_id": "market_maker"}).encode("utf-8")
req = urllib.request.Request("http://localhost:8000/api/bot/strategy/select", data=data, headers={"Content-Type": "application/json"})
print(urllib.request.urlopen(req).read())
