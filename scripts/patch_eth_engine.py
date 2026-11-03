with open("src/kalshi_sim/ml/eth_bot1v4/eth_bot1v4_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

target = '''        active_info = self._active_trade_forensics.get(target_ticker)
        if not active_info and self.order_client and hasattr(self.order_client, "get_live_portfolio_state"):
            try:
                st = await self.order_client.get_live_portfolio_state()'''

assert target in text, "target not found"

replacement = '''        active_info = self._active_trade_forensics.get(target_ticker)
        now_ts = time.time()
        last_port_sync = getattr(self, "_last_portfolio_sync_ts", 0.0)
        if not active_info and self.order_client and hasattr(self.order_client, "get_live_portfolio_state") and (now_ts - last_port_sync >= 30.0):
            try:
                self._last_portfolio_sync_ts = now_ts
                st = await self.order_client.get_live_portfolio_state()'''

text = text.replace(target, replacement, 1)

with open("src/kalshi_sim/ml/eth_bot1v4/eth_bot1v4_engine.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Successfully throttled get_live_portfolio_state in eth_bot1v4_engine.py")
