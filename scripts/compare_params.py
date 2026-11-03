import json

with open('data/bot_parameters_bnb.json') as f:
    bnb = json.load(f)['bnb_bot1_v4']
with open('data/bot_parameters_eth.json') as f:
    eth = json.load(f)['eth_bot1_v4']
with open('data/bot_parameters_domination.json') as f:
    btc = json.load(f)

print("--- PARAMETER COMPARISON ---")
print(f"min_spot_diff: BNB={bnb.get('min_spot_diff')}, ETH={eth.get('min_spot_diff')}, BTC={btc.get('min_spot_diff')}")
print(f"min_confidence: BNB={bnb.get('min_confidence')}, ETH={eth.get('min_confidence')}, BTC={btc.get('min_confidence')}")
print(f"min_edge_pct: BNB={bnb.get('min_edge_pct')}, ETH={eth.get('min_edge_pct')}, BTC={btc.get('min_edge_pct')}")
print(f"discount_limit_price: BNB={bnb.get('discount_limit_price')}, ETH={eth.get('discount_limit_price')}, BTC={btc.get('discount_limit_price')}")
print(f"max_entry_price: BNB={bnb.get('max_entry_price')}, ETH={eth.get('max_entry_price')}, BTC={btc.get('momentum_max_price')}")
print(f"min_viable_ask_floor: BNB={bnb.get('min_viable_ask_floor')}, ETH={eth.get('min_viable_ask_floor')}, BTC={btc.get('min_viable_ask_floor')}")
print(f"vpin_toxic_threshold: BNB={bnb.get('vpin_toxic_threshold')}, ETH={eth.get('vpin_toxic_threshold')}, BTC={btc.get('vpin_toxic_threshold')}")
print(f"adverse_slippage_stress_cents: BNB={bnb.get('adverse_slippage_stress_cents')}, ETH={eth.get('adverse_slippage_stress_cents')}")
print(f"enable_warrior_2_chop: BNB={bnb.get('enable_warrior_2_chop')}, ETH={eth.get('enable_warrior_2_chop')}")
print(f"silas_pinning_blackout_seconds: BNB={bnb.get('silas_pinning_blackout_seconds')}, ETH={eth.get('silas_pinning_blackout_seconds')}")
