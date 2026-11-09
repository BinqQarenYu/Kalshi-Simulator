from pathlib import Path

f_path = Path("src/kalshi_sim/strategy_evaluator.py")
content = f_path.read_text(encoding="utf-8")

old_block = """                engine = self.get_dynamic_regime_engine(ticker)

                # Sync learning dials from asset ContinuousExperienceBuffer (Closing Siloed Learning Loop)"""

new_block = """                engine = self.get_dynamic_regime_engine(ticker)

                # Hot-reload strategy parameters from Single Source of Truth
                try:
                    from kalshi_sim.truth_synchronizer import truth_synchronizer
                    truth_synchronizer.sync_engine(engine, asset=asset.value if hasattr(asset, "value") else str(asset))
                except Exception as sync_err:
                    logger.debug("[DYNAMIC STRATEGY SYNC ERROR] %s", sync_err)

                # Sync learning dials from asset ContinuousExperienceBuffer (Closing Siloed Learning Loop)"""

if old_block in content:
    content = content.replace(old_block, new_block, 1)
    f_path.write_text(content, encoding="utf-8")
    print("SUCCESS: strategy_evaluator.py patched with \\n")
elif old_block.replace("\n", "\r\n") in content:
    content = content.replace(old_block.replace("\n", "\r\n"), new_block.replace("\n", "\r\n"), 1)
    f_path.write_text(content, encoding="utf-8")
    print("SUCCESS: strategy_evaluator.py patched with \\r\\n")
else:
    print("ERROR: old_block not found")
