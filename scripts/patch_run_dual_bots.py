with open("src/kalshi_sim/ml/eth_bot1v4/run_dual_live_bots.py", "r", encoding="utf-8") as f:
    text = f.read()

target = '''    # Run both engines and settlement reconciler concurrently.
    async def _async_main():
        tasks = [
            _run_engine(eth_engine, "ETH_Bot", args.eth_interval, guardrails),
            _run_engine(secondary_engine, f"{args.secondary_asset.upper()}_Bot", args.secondary_interval, guardrails),
            _reconcile_settlements_loop(client, guardrails, eth_engine, secondary_engine, interval=15.0),
            _periodic_telemetry_loop(guardrails, interval=30.0),
        ]
        await asyncio.gather(*tasks)'''

assert target in text, "target not found"

replacement = '''    # Run both engines and settlement reconciler concurrently.
    async def _async_main():
        try:
            await client.ensure_crypto_collateral()
        except Exception as exc:
            logging.getLogger("DualFleet").warning("Initial collateral rebalance warning: %s", exc)

        tasks = [
            _run_engine(eth_engine, "ETH_Bot", args.eth_interval, guardrails),
            _run_engine(secondary_engine, f"{args.secondary_asset.upper()}_Bot", args.secondary_interval, guardrails),
            _reconcile_settlements_loop(client, guardrails, eth_engine, secondary_engine, interval=30.0),
            _periodic_telemetry_loop(guardrails, interval=30.0),
        ]
        await asyncio.gather(*tasks)'''

text = text.replace(target, replacement, 1)

with open("src/kalshi_sim/ml/eth_bot1v4/run_dual_live_bots.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Successfully updated run_dual_live_bots.py")
