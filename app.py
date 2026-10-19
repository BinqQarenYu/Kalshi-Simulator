"""AI Studio entrypoint for the Kalshi Quantitative Simulator & AI Engine."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
for p in (str(ROOT_DIR), str(SRC_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


def _bind_early_listener(host: str, port: int) -> socket.socket:
    """Bind and listen on (host, port) immediately so the runtime readiness probe succeeds."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(2048)
    sock.setblocking(False)
    return sock


def _ensure_frontend_built() -> None:
    """Ensure frontend/dist/index.html exists before serving static assets."""
    dist_index = ROOT_DIR / "frontend" / "dist" / "index.html"
    if dist_index.exists():
        return
    frontend_dir = ROOT_DIR / "frontend"
    if not (frontend_dir / "package.json").exists():
        return
    if not (frontend_dir / "node_modules").exists():
        subprocess.run(["npm", "install"], cwd=str(frontend_dir), check=True)
    subprocess.run(["npm", "run", "build"], cwd=str(frontend_dir), check=True)


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "3000"))

    # Default to safe mock/paper simulation mode if not configured
    os.environ.setdefault("KALSHI_MODE", "mock")
    os.environ.setdefault("KALSHI_LIVE_TRADING_ENABLED", "false")

    sock = _bind_early_listener(host, port)
    _ensure_frontend_built()

    import uvicorn
    from kalshi_sim.server import app

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    asyncio.run(server.serve(sockets=[sock]))


if __name__ == "__main__":
    main()
