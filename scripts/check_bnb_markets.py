import requests
import datetime

now = datetime.datetime.now(datetime.timezone.utc)
resp = requests.get('https://api.elections.kalshi.com/trade-api/v2/markets', params={'series_ticker': 'KXBNB15M', 'limit': 100})
data = resp.json()
markets = data.get('markets', [])
print(f"Fetched: {len(markets)}, Now: {now.isoformat()}")
for m in markets:
    o_time = m.get('open_time')
    c_time = m.get('close_time')
    ticker = m.get('ticker')
    status = m.get('status')
    if o_time and c_time:
        o_dt = datetime.datetime.fromisoformat(o_time.replace('Z', '+00:00'))
        c_dt = datetime.datetime.fromisoformat(c_time.replace('Z', '+00:00'))
        if o_dt <= now <= c_dt:
            print(f"ACTIVE: {ticker} | status: {status} | bid: {m.get('yes_bid')} | ask: {m.get('yes_ask')} | floor: {m.get('floor_strike')}")
        elif o_dt > now and (o_dt - now).total_seconds() <= 1800:
            print(f"UPCOMING: {ticker} | status: {status} | open: {o_time}")
