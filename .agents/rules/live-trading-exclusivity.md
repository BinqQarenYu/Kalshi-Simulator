---
trigger: always_on
glob: "**/*"
description: Strict execution mode segregation, live trading exclusivity, zero concurrent paper trading, and 100% resource dedication.
---

# Live Trading Exclusivity & Resource Allocation Rule

## 1. Zero Simulated Trades in Live Portfolio
- **Absolute Portfolio Segregation**: In Live Mode (`Lane 1`), **ALL orders, balances, margin, and fills must originate 100% from authenticated Kalshi exchange endpoints**.
- **No Blended State**: Simulated fills, mock executions, and paper trades must NEVER touch or contaminate the real Kalshi balance, real positions, or live win/loss records (`win_loss_reports.json`).
- **Lane 2 Shadow Isolation**: When testing candidate bots in Lane 2 (Shadow/Incubator Mode on live ticks), the candidate bot operates on a completely quarantined virtual ledger with zero access to live order routing, live API keys, or live margin. 

## 2. 100% Resource & Compute Dedication to Live Execution
- When Live Mode is enabled, 100% of available system resources are dedicated exclusively to live production trading:
  - **Network & WebSockets**: Prioritize live Kalshi exchange feeds (`api.elections.kalshi.com` / `external-api-ws.kalshi.com`) and underlying spot index feeds. Zero synthetic tick generation.
  - **CPU & Event Loop**: Direct all event loop capacity and async task scheduling to live L2 book parsing, sub-millisecond feature extraction, VPIN computation, and immediate order routing.
  - **Memory & Storage**: Allocate high-throughput buffers solely to live trade tape logging and real-time execution telemetry.
  - **AI & ONNX Inference**: Dedicate ONNX runtime threads exclusively to scoring live exchange market opportunities for the active live domination bot.

## 3. Real Exchange Data & Settlement Exclusivity
- **Positions & Balances**: In Live Mode, all balances, active positions, and margin allocations must reflect real authenticated Kalshi portfolio queries (`GET /trade-api/v2/portfolio/balance`, `GET /trade-api/v2/portfolio/positions`).
- **Fills & Win/Loss Records**: Win/loss reports and trade tapes in Live Mode must originate 100% from real exchange fills (`GET /trade-api/v2/portfolio/fills`) and verified market settlements (`GET /trade-api/v2/portfolio/settlements`), with zero simulated virtual trades.
- **Micro-Contract Bankroll Protection**: Live order routing must adhere to strict risk constraints (1–4 contracts per trade for micro-bankrolls, pre-trade EV threshold checks, and VPIN toxicity filters).
