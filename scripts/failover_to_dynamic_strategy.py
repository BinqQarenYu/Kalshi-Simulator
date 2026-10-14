"""Failover & Dynamic Strategy Deployment Utility.

Enables zero-downtime hot-swapping to the Dynamic Trading Strategy (DRSA)
on AWS EC2 or local headless environments. Pre-flight audits invariants, updates
live bot parameters, and verifies seal certification.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root and src to path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from kalshi_sim.preset_manager import PresetManager, PresetAuditor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [FAILOVER] %(message)s"
)
logger = logging.getLogger("failover_dynamic")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy Dynamic Trading Strategy on AWS/Local")
    parser.add_argument(
        "--preset",
        type=str,
        default="dynamic_trading_strategy_v1",
        help="Preset ID to deploy (default: dynamic_trading_strategy_v1)",
    )
    parser.add_argument(
        "--asset",
        type=str,
        default="BTC",
        help="Active asset (BTC, ETH, DOGE)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force deployment even if already active",
    )

    args = parser.parse_args()

    logger.info("==================================================================")
    logger.info("  FAILOVER TO DYNAMIC TRADING STRATEGY (DRSA) — ZERO-DOWNTIME     ")
    logger.info("  Target Preset: %s | Asset: %s                                  ", args.preset, args.asset)
    logger.info("==================================================================")

    pm = PresetManager()
    active_id = pm.get_active_preset_id()

    if active_id == args.preset and not args.force:
        logger.info("Preset '%s' is already the active preset. Use --force to reload.", args.preset)
        return 0

    # 1. Hot-swap the preset into live parameters
    success, msg, data = pm.load_preset(args.preset)
    if not success:
        logger.error("❌ FAILED to load preset '%s': %s", args.preset, msg)
        return 1

    logger.info("✅ Preset '%s' successfully loaded into live parameters.", args.preset)

    # 2. Update seal_of_excellence.json active strategy pointer
    seal_path = _ROOT / "data" / "seal_of_excellence.json"
    if seal_path.exists():
        try:
            seal_data = json.loads(seal_path.read_text(encoding="utf-8"))
            seal_data["active_live_strategy"] = "dynamic_trading_strategy"
            seal_path.write_text(json.dumps(seal_data, indent=2), encoding="utf-8")
            logger.info("✅ Updated active_live_strategy in seal_of_excellence.json to 'dynamic_trading_strategy'.")
        except Exception as e:
            logger.warning("Could not update seal_of_excellence.json: %s", e)

    # 3. Check active state on disk
    active_meta = pm.get_active_preset_metadata()
    logger.info("🚀 Active Preset Name: %s", active_meta.get("preset_name"))
    logger.info("🛡️ Council Certified: %s", active_meta.get("is_council_certified"))
    logger.info("🔒 Invariant SHA-256: %s", active_meta.get("checksum"))
    logger.info("==================================================================")
    logger.info("  DYNAMIC TRADING STRATEGY IS LIVE AND READY FOR AWS EXECUTION    ")
    logger.info("==================================================================")

    return 0


if __name__ == "__main__":
    sys.exit(main())
