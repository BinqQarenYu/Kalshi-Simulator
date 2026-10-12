"""aws_headless_daemon.py — Production 24/7 Headless Server for Bot 1 V4 (Quolas) on AWS EC2.

Runs the complete Kalshi Quantitative Engine headless on AWS:
- Subscribes to live Kalshi WebSocket & Binance BTC spot feeds.
- Executes Bot 1 V4 with quolas.onnx inference in real time.
- Operates the HMM regime detector.
- Supervizes 6-trade evaluation batches.
- Dispatches forensic email reports directly to benjohncarino@gmail.com upon completion.
- Binds FastAPI / WebCLOB to 0.0.0.0:8000 for remote health/telemetry checks.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

import uvicorn
from logging.handlers import RotatingFileHandler
from kalshi_sim.server import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [AWS-HEADLESS] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(
            _ROOT / "quolas_24_7.log",
            maxBytes=15 * 1024 * 1024,  # 15 MB max per log file
            backupCount=2,               # keep max 2 archives (max 45 MB total)
            encoding="utf-8",
        )
    ]
)
logger = logging.getLogger("aws_headless_daemon")

if __name__ == "__main__":
    logger.info("================================================================")
    logger.info("  KALSHI BOT 1 V4 (QUOLAS) HEADLESS TRADING DAEMON ON AWS EC2   ")
    logger.info("  Mode: LIVE PRODUCTION | Inference: quolas.onnx | Asset: BTC   ")
    logger.info("  Email Alerts Target: benjohncarino@gmail.com                   ")
    logger.info("================================================================")

    # Launch server without opening browser windows (pure headless)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=False,  # Disable chatty HTTP access logs to preserve disk space
    )
