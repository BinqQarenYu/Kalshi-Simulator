# Copilot Instructions for Kalshi BTC Quantitative Trading Simulator

## Project Overview
Kalshi BTC Quantitative Trading Simulator is an institutional-grade algorithmic trading simulator, market data ingestion pipeline, and real-time execution engine for **Kalshi Bitcoin Binary Prediction Contracts** (`KXBTC5M`, `KXBTC15M`, `KXBTCH`).

The system integrates a **Two-Stage Quantitative Architecture**:
1. **Stage 1 (Microstructure Order Flow AI Engine)**: High-frequency Level-2 Order Flow feature extraction (28-D tensor) and ONNX neural network inference (`nano_microscope_overhauled.onnx`) for directional probability estimation $P(\text{UP}), P(\text{DOWN}), P(\text{WAIT})$ with real-time VPIN toxicity vetoes.
2. **Stage 2 (Mathematical Expected Value & Kelly Sizing)**: Fixed binary digital option payoff mathematics ($\mathbb{E}[V] = P - \text{Ask}$), fractional Kelly capital allocation ($f^*$), margin-of-safety gating ($\ge \$0.02$), and portfolio circuit breaker drawdown management.

---

## Architecture & Key Modules (`src/kalshi_sim/`)
- **`server.py`**: High-performance FastAPI server + WebSocket broadcast loop (5 updates/sec) serving the WebCLOB dashboard and REST endpoints (`/api/state`, `/api/order`, `/api/historical-candles`).
- **`orderbook.py` (`OrderBookManager`)**: Multi-timeframe L2 order book maintaining bid/ask price levels, sequence numbers (`seq`), and depth metrics.
- **`ml/microscope_onnx.py` (`KalshiONNX`)**: ONNX Runtime CPU Provider wrapper computing 28-D microstructure features (OFI, CVD, exponential depth decay imbalance $\mathcal{M}_n$, micro-price drift, VPIN) with sub-millisecond latency (<0.4ms).
- **`ml/statistical_ev_engine.py` (`StatisticalEVEngine`)**: Stage-2 Expected Value calculation, edge measurement ($\alpha$), and fractional Kelly bet sizing with continuous VPIN tapering.
- **`simulation_agent.py` (`SimulationAgent`)**: Coordinates L2 depth walking, VWAP slippage simulation, mark-to-market position tracking, automated strike expiration settlement against underlying Bitcoin spot index, and circuit breaker halts.
- **`mock_feed.py` (`MockKalshiFeed`)**: High-fidelity local simulation feed generating synthetic Bitcoin price walks, L2 delta streams, and realistic binary contract spreads.
- **`ingestion_agent.py` (`IngestionAgent`)**: Connects to live Kalshi WebSocket feed (`wss://api.elections.kalshi.com/trade-api/ws/v2`) and handles RSA-PSS key signing for live market data.
- **`auth.py`**: Cryptographic RSA-PSS signature generator for Kalshi API key authentication.
- **`rate_limiter.py`**: Token-bucket rate limiting enforcing Kalshi's 20 req/s API threshold.
- **`frontend/`**: React 18, Vite, TypeScript, Tailwind CSS, Lucide icons, and real-time WebCLOB terminal dashboard.

---

## Developer Workflows
- **Start Web Dashboard**:
  ```powershell
  .\run_dashboard.bat
  # Or:
  $env:PYTHONPATH="src"; python -m kalshi_sim.server
  # Open http://localhost:8000
  ```
- **Run Mock Simulation (Terminal CLI)**:
  ```powershell
  $env:PYTHONPATH="src"; python -m kalshi_sim --simulate --mock -v
  ```
- **Run Live Paper Trading**:
  ```powershell
  $env:PYTHONPATH="src"; python -m kalshi_sim --simulate --timeframe 15m -v
  ```
- **Run Tests (Empirical Verification)**:
  ```powershell
  $env:PYTHONPATH="src"; python -m unittest discover -s tests
  ```
- **Frontend Development & Build**:
  ```powershell
  cd frontend
  npm install
  npm run typecheck
  npm run build
  ```

---

## Project-Specific Quantitative Conventions
- **Precision Discipline**: All balances, order costs, payoffs, expected values, and PnL must strictly use `decimal.Decimal` in Python and `decimal.js` / string values in TypeScript. No native IEEE 754 float math for financial transactions.
- **Binary Digital Option Expected Value**:
  $$\mathbb{E}[\text{YES}] = P_{\text{AI}}(\text{UP}) - \text{Ask}_{\text{YES}}, \quad \mathbb{E}[\text{NO}] = P_{\text{AI}}(\text{DOWN}) - \text{Ask}_{\text{NO}}$$
- **Fractional Kelly Criterion**:
  $$b = \frac{1.00 - \text{Ask}}{\text{Ask}}, \quad f^* = \frac{p \cdot b - (1 - p)}{b} = \frac{p - \text{Ask}}{1 - \text{Ask}}$$
  $$\text{Contracts} = \min\left( Q_{\max}, \frac{\text{Equity} \times \text{MaxRiskPct} \times (0.25 \cdot f^*)}{\text{Ask}} \right)$$
- **Order Execution**: Simulated fills must walk the actual L2 depth ladder to calculate VWAP slippage.

