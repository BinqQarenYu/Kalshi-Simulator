from pathlib import Path

target_file = Path("src/kalshi_sim/batch_supervisor.py")
content = target_file.read_text(encoding="utf-8")

old_block = """        # 8. Mark Evaluated Trades as Processed & Persist to State File
        for t in recent_trades:
            self._processed_trade_ids.add(self._get_trade_id(t))
        self._save_processed_trade_ids()

        # 9. Execution Gate Verdict & Next Quota Reset"""

new_block = """        # 8. Mark Evaluated Trades as Processed & Persist to State File
        for t in recent_trades:
            self._processed_trade_ids.add(self._get_trade_id(t))
        self._save_processed_trade_ids()

        # 8.1 Execute Anti-Bloat Assessment Hygiene Duty (Clean AWS & Free Memory, Retain Brains)
        try:
            from kalshi_sim.utils.system_hygiene import run_assessment_hygiene_duty
            hygiene_stats = run_assessment_hygiene_duty()
            logger.info("🧹 [ASSESSMENT HYGIENE] Autonomous anti-bloat duty completed: %s", hygiene_stats)
        except Exception as hyg_err:
            logger.warning("[ASSESSMENT HYGIENE] Failed to run hygiene duty: %s", hyg_err)

        # 9. Execution Gate Verdict & Next Quota Reset"""

# Normalize \r\n to match
if old_block in content:
    content = content.replace(old_block, new_block, 1)
    target_file.write_text(content, encoding="utf-8")
    print("SUCCESS: Patched batch_supervisor.py with \n")
elif old_block.replace("\n", "\r\n") in content:
    content = content.replace(old_block.replace("\n", "\r\n"), new_block.replace("\n", "\r\n"), 1)
    target_file.write_text(content, encoding="utf-8")
    print("SUCCESS: Patched batch_supervisor.py with \r\n")
else:
    print("ERROR: Target block not found in batch_supervisor.py")
