"""Fetch live Kalshi balance from AWS with correct auth signature."""
import json
import os
import sys
from pathlib import Path
import requests
from dotenv import load_dotenv

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "src"))
load_dotenv(root / ".env")

try:
    from kalshi_sim.auth import PROD_REST_BASE, get_auth_headers, load_private_key
    key_id = os.getenv("KALSHI_API_KEY_ID")
    priv_path = os.getenv("KALSHI_PRIVATE_KEY_PATH")
    priv_key = load_private_key(priv_path)
    
    endpoint = "/trade-api/v2/portfolio/balance"
    headers = get_auth_headers(key_id, priv_key, "GET", endpoint)
    r = requests.get(f"{PROD_REST_BASE}/portfolio/balance", headers=headers, timeout=5)
    print("KALSHI_LIVE_BALANCE_OUTPUT:", r.text)
except Exception as e:
    print("BALANCE_FETCH_ERROR:", e)
