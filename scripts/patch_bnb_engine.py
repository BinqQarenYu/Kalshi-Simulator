import sys

path = 'src/kalshi_sim/ml/bnb_bot1v4/bnb_bot1v4_engine.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

old1 = '''                        self._cached_market = MarketInfo(
                            ticker=ticker_val,
                            title=target.get("title", f"BNB 15M {ticker_val}"),
                            strike_price=strike_dec,
                            expiration_time=target.get("close_time", target.get("expiration_time")),
                            status=MarketStatus.ACTIVE,
                            yes_bid=Decimal(str(target["yes_bid"])) if target.get("yes_bid") is not None else None,
                            yes_ask=Decimal(str(target["yes_ask"])) if target.get("yes_ask") is not None else None,
                            timeframe=Timeframe.FIFTEEN_MIN,
                        )'''

new1 = '''                        self._cached_market = MarketInfo(
                            ticker=ticker_val,
                            title=target.get("title", f"BNB 15M {ticker_val}"),
                            floor_strike=strike_dec,
                            close_time=target.get("close_time", target.get("expiration_time")),
                            status=MarketStatus.ACTIVE,
                            yes_bid=Decimal(str(target["yes_bid"])) if target.get("yes_bid") is not None else None,
                            yes_ask=Decimal(str(target["yes_ask"])) if target.get("yes_ask") is not None else None,
                            timeframe=Timeframe.FIFTEEN_MIN,
                        )'''

old2 = '''        target_ticker = ticker or self.target_ticker
        market_info: Optional[MarketInfo] = None

        if not target_ticker or "-" not in target_ticker:
            market_info = await self.fetch_active_market()
            if market_info:
                target_ticker = market_info.ticker

        if not target_ticker or "-" not in target_ticker:
            logger.debug("[BNB BOT] No active KXBNB15M market discovered.")
            return None'''

new2 = '''        target_ticker = ticker or self.target_ticker
        market_info: Optional[MarketInfo] = await self.fetch_active_market()
        if market_info:
            target_ticker = market_info.ticker

        if not target_ticker or "-" not in target_ticker:
            logger.debug("[BNB BOT] No active KXBNB15M market discovered.")
            return None'''

old3 = '''        if market_info and market_info.floor_strike:
            target_strike = market_info.floor_strike
        else:
            parsed_strike = extract_strike_from_ticker(target_ticker, asset=self.asset)
            if parsed_strike is not None:
                target_strike = parsed_strike
            elif "-" in target_ticker:
                # Parse strike from ticker if formatted as KXBNB15M-YYMMMDDHHMM-STRIKE
                parts = target_ticker.split("-")
                if len(parts) >= 3:
                    try:
                        target_strike = Decimal(parts[-1])
                    except Exception:
                        pass'''

new3 = '''        if market_info and market_info.floor_strike and market_info.floor_strike > 0:
            target_strike = market_info.floor_strike
        elif market_info and hasattr(market_info, "target_strike") and market_info.target_strike > 0:
            target_strike = market_info.target_strike
        else:
            parsed_strike = extract_strike_from_ticker(target_ticker, asset=self.asset)
            if parsed_strike is not None and parsed_strike > 0:
                target_strike = parsed_strike
            elif "-" in target_ticker:
                parts = target_ticker.split("-")
                if len(parts) >= 3:
                    try:
                        cand = Decimal(parts[-1])
                        if cand > 0:
                            target_strike = cand
                    except Exception:
                        pass
        if target_strike <= 0:
            target_strike = self.get_spot_price()'''

old4 = '''        active_info = self._active_trade_forensics.get(target_ticker)
        if not active_info and self.order_client and hasattr(self.order_client, "get_live_portfolio_state"):
            try:
                st = await self.order_client.get_live_portfolio_state()'''

new4 = '''        active_info = self._active_trade_forensics.get(target_ticker)
        now_ts = time.time()
        last_port_sync = getattr(self, "_last_portfolio_sync_ts", 0.0)
        if not active_info and self.order_client and hasattr(self.order_client, "get_live_portfolio_state") and (now_ts - last_port_sync >= 30.0):
            try:
                self._last_portfolio_sync_ts = now_ts
                st = await self.order_client.get_live_portfolio_state()'''

for tag, o in [('old1', old1), ('old2', old2), ('old3', old3), ('old4', old4)]:
    if o not in text:
        print(f"Error: {tag} not found in text")
        sys.exit(1)

text = text.replace(old1, new1).replace(old2, new2).replace(old3, new3).replace(old4, new4)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Successfully updated bnb_bot1v4_engine.py")
