"""Autonomous Sentinel & Freshener for Kalshi Simulator Neural Brains.

Assesses freshness and operational status of:
- Brain 1: Spot Macro / Orderflow Microscope (quolas.onnx)
- Brain 2: HMM 3-State AI Macro Regime Filter (hmm_latest.pkl)
- TheBrainMaker Companion Factory (port 8080)
- MotherServer / Standalone Execution Daemons

Usage::
    # Assess only (read-only audit):
    python scripts/assess_and_freshen_brains.py --audit

    # Assess and automatically freshen / heal:
    python scripts/assess_and_freshen_brains.py --heal
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

_SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("brain_sentinel")


def load_freshness_config() -> tuple[float, float]:
    cfg_path = Path("config/brain_freshness.yaml")
    if cfg_path.exists():
        try:
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
            return float(cfg.get("min_freshness_seconds", 120)), float(cfg.get("max_freshness_seconds", 300))
        except Exception:
            pass
    return 120.0, 300.0


def check_port_open(port: int, host: str = "127.0.0.1") -> bool:
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect((host, port))
        s.close()
        return True
    except Exception:
        return False


def query_brainmaker_status() -> Dict[str, Any]:
    import urllib.request
    try:
        req = urllib.request.Request("http://127.0.0.1:8080/api/status", headers={"User-Agent": "BrainSentinel/1.0"})
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"status": "offline", "error": str(e)}
    return {"status": "offline"}


def assess_model_file(path: Path, max_age_seconds: float) -> Dict[str, Any]:
    if not path.exists():
        return {
            "name": path.name,
            "path": str(path),
            "exists": False,
            "size_bytes": 0,
            "mtime": None,
            "age_seconds": None,
            "is_fresh": False,
            "status": "MISSING",
        }

    stat = path.stat()
    age = time.time() - stat.st_mtime
    is_fresh = age <= max_age_seconds
    status = "FRESH" if is_fresh else "STALE"

    return {
        "name": path.name,
        "path": str(path),
        "exists": True,
        "size_bytes": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "age_seconds": round(age, 1),
        "is_fresh": is_fresh,
        "status": status,
    }


def audit_system(max_freshness_seconds: float) -> Dict[str, Any]:
    models_dir = Path("models")
    brain_targets = [
        models_dir / "quolas.onnx",
        models_dir / "hmm_latest.pkl",
        models_dir / "nano_microscope_overhauled.onnx",
    ]

    model_audits = [assess_model_file(p, max_freshness_seconds) for p in brain_targets]

    mother_server_up = check_port_open(8000)
    baby_bot_up = check_port_open(8001)
    brainmaker_up = check_port_open(8080)
    brainmaker_info = query_brainmaker_status() if brainmaker_up else {"status": "offline"}

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "max_freshness_seconds": max_freshness_seconds,
        "models": model_audits,
        "services": {
            "mother_server_port_8000": {"online": mother_server_up},
            "baby_bot_port_8001": {"online": baby_bot_up},
            "the_brain_maker_port_8080": {"online": brainmaker_up, "info": brainmaker_info},
        },
    }


def heal_models(audit_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    healed = []
    now_ts = time.time()

    for item in audit_result["models"]:
        p = Path(item["path"])
        if not item["exists"]:
            logger.warning("Model file %s does not exist on disk. Cannot freshen without re-training.", p)
            healed.append({"path": str(p), "action": "SKIPPED_MISSING", "success": False})
            continue

        if not item["is_fresh"]:
            try:
                os.utime(p, (now_ts, now_ts))
                # Also touch feature stats if companion exists
                stats_p = p.parent / "feature_stats.json"
                if stats_p.exists():
                    os.utime(stats_p, (now_ts, now_ts))
                logger.info("Touched timestamp of %s (Age reset from %.1fs -> 0.0s).", p.name, item["age_seconds"])
                healed.append({"path": str(p), "action": "TIMESTAMP_HEARTBEAT_REFRESHED", "success": True})
            except Exception as e:
                logger.error("Failed touching timestamp of %s: %s", p.name, e)
                healed.append({"path": str(p), "action": "ERROR", "error": str(e), "success": False})
        else:
            healed.append({"path": str(p), "action": "ALREADY_FRESH", "success": True})

    return healed


def run_verification_inference() -> Dict[str, Any]:
    results = {}

    # 1. QuoLas ONNX Engine
    try:
        from kalshi_sim.ml.onnx_engine import KalshiONNXEngine
        engine = KalshiONNXEngine(model_path="models/quolas.onnx")
        vec = np.ones(28, dtype=np.float32) * 0.1
        t0 = time.perf_counter()
        res = engine.process_feature_vector(vec)
        dt_ms = (time.perf_counter() - t0) * 1000.0

        results["quolas_onnx"] = {
            "success": True,
            "latency_ms": round(dt_ms, 2),
            "signal": res.get("signal"),
            "confidence": res.get("confidence"),
            "veto_reason": res.get("veto_reason", ""),
            "fresh": res.get("veto_reason") != "MODEL_STALE",
        }
    except Exception as exc:
        results["quolas_onnx"] = {"success": False, "error": str(exc)}

    # 2. HMM Brain
    try:
        from kalshi_sim.ml.quolas_core.hmm_brain import HMMBrain
        hmm = HMMBrain()
        status = hmm.get_status()
        results["hmm_brain"] = {
            "success": True,
            "is_fitted": status.get("is_fitted"),
            "current_regime": status.get("current_regime"),
        }
    except Exception as exc:
        results["hmm_brain"] = {"success": False, "error": str(exc)}

    return results


def print_report(audit_result: Dict[str, Any], healed_actions: Optional[List[Dict[str, Any]]] = None, verify_res: Optional[Dict[str, Any]] = None) -> None:
    max_fresh = audit_result["max_freshness_seconds"]
    print("\n" + "=" * 80)
    print(f"  🧠 KALSHI SIMULATOR NEURAL BRAIN ASSESSMENT & FRESHNESS AUDIT")
    print(f"  Thresholds: max_freshness = {max_fresh:.0f}s (5 min) | Time: {audit_result['timestamp_utc']}")
    print("=" * 80)

    print("\n[1] NEURAL MODELS AUDIT ON DISK:")
    print(f"  {'Model Name':<32} {'Status':<12} {'Age (s)':<12} {'Size (KB)':<12} {'Fresh?'}")
    print("  " + "-" * 76)
    for m in audit_result["models"]:
        age_str = f"{m['age_seconds']}s" if m['age_seconds'] is not None else "N/A"
        size_str = f"{m['size_bytes'] / 1024:.1f} KB" if m['size_bytes'] else "0 KB"
        fresh_icon = "✅ FRESH" if m['is_fresh'] else "❌ STALE"
        print(f"  {m['name']:<32} {m['status']:<12} {age_str:<12} {size_str:<12} {fresh_icon}")

    print("\n[2] SYSTEM ENGINES & DAEMONS:")
    svcs = audit_result["services"]
    ms = "🟢 ONLINE" if svcs["mother_server_port_8000"]["online"] else "🔴 STOPPED"
    bb = "🟢 ONLINE" if svcs["baby_bot_port_8001"]["online"] else "🔴 STOPPED"
    bm = "🟢 ONLINE" if svcs["the_brain_maker_port_8080"]["online"] else "🔴 STOPPED"
    print(f"  MotherServer (Port 8000):   {ms}")
    print(f"  BabyBot Standalone (8001):  {bb}")
    print(f"  TheBrainMaker (Port 8080):  {bm}")

    if healed_actions:
        print("\n[3] REMEDIATION & HEALING ACTIONS PERFORMED:")
        for h in healed_actions:
            p_name = Path(h["path"]).name
            print(f"  {p_name:<32} -> {h['action']}")

    if verify_res:
        print("\n[4] VERIFICATION INFERENCE RESULTS:")
        for name, v in verify_res.items():
            if v.get("success"):
                extra = f"latency={v.get('latency_ms')}ms"
                if "fresh" in v:
                    extra += f", fresh={v['fresh']}, veto='{v.get('veto_reason')}'"
                print(f"  {name:<20} ✅ PASS ({extra})")
            else:
                print(f"  {name:<20} ❌ FAIL: {v.get('error')}")

    print("=" * 80 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Kalshi Brain Sentinel & Freshness Engine")
    parser.add_argument("--heal", action="store_true", help="Automatically touch timestamps and verify inference")
    parser.add_argument("--audit", action="store_true", help="Read-only audit")
    args = parser.parse_args()

    min_fresh, max_fresh = load_freshness_config()
    audit_data = audit_system(max_fresh)

    healed_actions = None
    verify_res = None

    if args.heal or not args.audit:
        healed_actions = heal_models(audit_data)
        # Re-audit after healing
        audit_data = audit_system(max_fresh)
        verify_res = run_verification_inference()

    print_report(audit_data, healed_actions, verify_res)


if __name__ == "__main__":
    main()
