# 🚀 Kalshi BTC Trading Simulator — Deployment & Operations Guide

This guide describes how to run, deploy, host, and monitor the **Kalshi BTC Quantitative Trading Simulator** on Windows, Linux, or in background service environments.

---

## 📋 System Requirements

- **Operating System**: Windows 10/11 / Windows Server / Linux (Ubuntu 22.04+)
- **Python**: 3.10, 3.11, 3.12, 3.13, 3.14+
- **Node.js**: v18+ (for compiling the React frontend with Vite)
- **Network**: Internet connection for live Kalshi WebSocket feed (optional; built-in mock simulator operates fully offline).

---

## ⚡ 1-Click Windows Launch

For immediate local execution on Windows:

1. **Double-click** `launch_simulator.bat` in the root directory.
2. The launcher will automatically:
   - Validate Python & `PYTHONPATH=src`.
   - Check if `models/nano_microscope_overhauled.onnx` is present.
   - Verify/build the React frontend in `frontend/dist/`.
   - Start the FastAPI + WebSocket server on `http://localhost:8000`.
   - Open your default browser to `http://localhost:8000`.

Alternatively, use PowerShell:
```powershell
.\launch_simulator.ps1
```

---

## 🛡️ Running as a 24/7 Unattended Windows Service

To ensure the trading simulation, AI inference, and Google Drive tick backups run continuously across system reboots:

### Installation
Run PowerShell as **Administrator**:
```powershell
cd "F:\012D_TRADE\Kalshi Simulator\scripts"
.\install_windows_service.ps1 -Install
```
This registers a native Windows Scheduled Task (`KalshiSimulatorService`) configured to:
- Run automatically on Windows system boot under `NT AUTHORITY\SYSTEM`.
- Auto-restart up to 5 times if terminated or crashed.
- Execute with no execution time limits.

### Uninstallation
```powershell
.\install_windows_service.ps1 -Uninstall
```

---

## 🌐 REST API Endpoints Reference

The backend exposes a full OpenAPI / Swagger UI at `http://localhost:8000/docs`.

### Market Data & State
| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Service health, active feed mode, and connected WebSocket client count. |
| `GET` | `/api/state` | Complete real-time state snapshot (market, order book, chart, AI, portfolio). |
| `GET` | `/api/history/ohlcv` | Rolling multi-timeframe candlestick bars (`?symbol=BTC&interval=1m&limit=100`). |

### Order Execution & Portfolio
| Method | Path | Description |
| :--- | :--- | :--- |
| `POST` | `/api/orders` | Submit market orders or resting limit orders. |
| `GET` | `/api/orders/open` | List all active resting limit orders. |
| `DELETE` | `/api/orders/{order_id}` | Cancel an active resting limit order. |
| `POST` | `/api/positions/close` | 1-Click liquidate and close an open contract position at current market price. |
| `POST` | `/api/reset` | Reset portfolio capital and clear trade history. |
| `POST` | `/api/circuit-breaker/reset` | Manually reset tripped max drawdown circuit breaker and resume trading. |

### Analytics & Data Export
| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/export/trades` | Export trade execution log (`?format=csv` or `?format=jsonl`). |
| `GET` | `/api/export/settlements` | Export contract expiry settlements (`?format=csv` or `?format=jsonl`). |
| `GET` | `/api/export/pnl` | Export portfolio P&L metrics and drawdown statistics (`?format=csv` or `?format=json`). |
| `GET` | `/api/export/ticks` | Download raw binary tick recording JSONL file. |

### Google Drive Synchronization
| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/api/gdrive/status` | Rclone remote connectivity, daemon status, and last backup timestamp. |
| `POST` | `/api/gdrive/sync` | Trigger an immediate non-blocking cloud backup. |

---

## 🧪 Running Automated Tests

Run the full Python test suite (44 unit & latency benchmark tests):
```powershell
$env:PYTHONPATH="src"
python -m pytest -v
```

Run Playwright End-to-End browser integration tests:
```powershell
cd frontend
npm run test:e2e
```
