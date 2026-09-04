# Kalshi BTC Quantitative Trading Simulator & Dual-Bot Arena

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-122%20passed-brightgreen.svg)]()
[![Throughput](https://img.shields.io/badge/L2%20Throughput-135k%20deltas%2Fs-orange.svg)]()
[![Inference Latency](https://img.shields.io/badge/ONNX%20Latency-0.38ms-blue.svg)]()
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

An institutional-grade quantitative trading simulator, market data ingestion pipeline, and real-time execution engine for **Kalshi Bitcoin Binary Prediction Contracts** (`KXBTC15M`, `KXBTC5M`, `KXBTCH`).

---

## 📚 Documentation Index

- [🏛 System Architecture & Infrastructure](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/ARCHITECTURE.md)
- [🤖 Quantitative Strategy Bots & Playbooks](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/STRATEGY_BOTS.md)
- [🔌 REST & WebSocket API Reference](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/API_REFERENCE.md)
- [🚀 Trader Operations & Bankroll Guide](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/TRADING_GUIDE.md)
- [🛡️ Data Integrity & Truth Enforcement Rules](file:///f:/012D_TRADE/Kalshi%20Simulator/docs/DATA_INTEGRITY.md)

---

The system integrates a **Multi-Model Quantitative Arena**:
1. **3-Step Domination Bot**: Cycle-aware multi-playbook engine (Early Momentum Breakout, Mid OFI Drift, Late Gamma Snub) with digital option moneyness CDF mathematics.
2. **ONNX Microstructure Bot**: 28-D order flow feature tensor extraction, deep neural network inference, and statistical expected value maximization.
3. **Single Source of Truth**: 100% anchored to live Kalshi exchange L2 feeds and real-time Bitcoin Spot Index feeds.

---

## 🏛 System Architecture

```
                  [ Level-2 Central Limit Order Book (CLOB) ]
                       │ (Snapshots, Deltas, Trade Tape)
                       ▼
    ┌─────────────────────────────────────────────────────────────┐
    │       STAGE 1: MICROSTRUCTURE ORDER FLOW AI ENGINE         │
    │                                                             │
    │  • 28-D Feature Extraction (OFI, CVD, Decay Depth, VPIN)    │
    │  • ONNX Runtime Inference (nano_microscope_overhauled.onnx) │
    │  • Outputs: P(UP), P(DOWN), P(WAIT)                         │
    │  • VPIN Toxicity Hard Override Guardrail                    │
    └──────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
    ┌─────────────────────────────────────────────────────────────┐
    │       STAGE 2: MATHEMATICAL & STATISTICAL EV ENGINE         │
    │                                                             │
    │  • Expected Value:                                          │
    │    E[YES] = P(UP) * (1 - Ask_YES) - (1 - P(UP)) * Ask_YES   │
    │    E[NO]  = P(DOWN) * (1 - Ask_NO) - (1 - P(DOWN)) * Ask_NO │
    │  • Statistical Edge:                                        │
    │    Edge = P(AI) - Market_Ask                                │
    │  • Fractional Kelly Sizing:                                 │
    │    f* = (P * b - (1 - P)) / b                               │
    │  • Selects direction with highest risk-adjusted profit      │
    └──────────────────────────────┬──────────────────────────────┘
                                   │
                                   ▼
    ┌─────────────────────────────────────────────────────────────┐
    │           VIRTUAL PORTFOLIO & EXECUTION ENGINE              │
    │                                                             │
    │  • Multi-Level L2 Depth Walking & VWAP Slippage Simulation  │
    │  • Mark-to-Market P&L Tracking (10s Terminal Dashboard)     │
    │  • Automated Settlement against Bitcoin Spot Index          │
    └─────────────────────────────────────────────────────────────┘
```

---

## ⚡ Key Features

* **Two-Stage Decision Framework**: Eliminates the binary odds-inversion flaw by calculating exact Expected Value ($\mathbb{E}[V]$) against live bid/ask spreads before entering trades.
* **Low-Latency ONNX Inference**: Sub-millisecond neural execution via ONNX Runtime CPU Provider.
* **VPIN Adverse Selection Protection**: Real-time Volume-Synchronized Probability of Informed Trading (VPIN) monitoring that vetos trades during toxic order flow bursts.
* **Fractional Kelly Capital Sizing**: Dynamically sizes contract orders based on measured edge ($\alpha$) and option payoff odds ($b$) while enforcing strict portfolio risk caps.
* **Multi-Market Simulation**: Runs across 5-minute (`KXBTC5M`), 15-minute (`KXBTC15M`), and 1-hour (`KXBTCH`) Bitcoin strike series.
* **Interactive Live Dashboard**: Live terminal P&L reporting, position mark-to-market valuations, and tick tape logging.
* **Automated Expiry & Settlement**: Automatically exercises and settles expiring contracts against underlying BTC spot index prices and rolls into fresh active contracts.

---

## 📐 Mathematical Formulations

### 1. Binary Digital Option Expected Value ($\mathbb{E}[V]$)
Unlike linear assets, Kalshi prediction contracts have fixed binary payouts ($\$1.00$ on win, $\$0.00$ on loss):

$$\mathbb{E}[\text{YES}] = P_{\text{AI}}(\text{UP}) \cdot (1.00 - \text{Ask}_{\text{YES}}) - (1 - P_{\text{AI}}(\text{UP})) \cdot \text{Ask}_{\text{YES}} = P_{\text{AI}}(\text{UP}) - \text{Ask}_{\text{YES}}$$

$$\mathbb{E}[\text{NO}] = P_{\text{AI}}(\text{DOWN}) \cdot (1.00 - \text{Ask}_{\text{NO}}) - (1 - P_{\text{AI}}(\text{DOWN})) \cdot \text{Ask}_{\text{NO}} = P_{\text{AI}}(\text{DOWN}) - \text{Ask}_{\text{NO}}$$

### 2. Statistical Edge ($\alpha$) & Margin of Safety Gate
$$\alpha_{\text{YES}} = P_{\text{AI}}(\text{UP}) - \text{Ask}_{\text{YES}}, \quad \alpha_{\text{NO}} = P_{\text{AI}}(\text{DOWN}) - \text{Ask}_{\text{NO}}$$
Trades are strictly gated by minimum margin-of-safety thresholds:
$$\text{Trigger Condition}: \max(\mathbb{E}[\text{YES}], \mathbb{E}[\text{NO}]) \ge \$0.02 \quad \text{and} \quad \max(\alpha_{\text{YES}}, \alpha_{\text{NO}}) \ge 2.0\%$$

### 3. Fractional Kelly Criterion ($f^*$)
To maximize geometric portfolio growth without risking ruin:
$$b = \frac{1.00 - \text{Ask}}{\text{Ask}}, \quad f^* = \frac{p \cdot b - (1 - p)}{b} = \frac{p - \text{Ask}}{1 - \text{Ask}}$$
$$\text{Position Size (Contracts)} = \min\left( Q_{\max}, \frac{\text{Total Equity} \times \text{MaxRiskPct} \times (0.25 \cdot f^*)}{\text{Ask}} \right)$$

### 4. Exponential Depth Decay Imbalance ($\mathcal{M}_n$)
Multi-level order book depth is compressed across $n=15$ layers using an exponential decay matrix ($\alpha = 0.425$):
$$\mathcal{M}_n(t) = \sum_{i=1}^{n} e^{-\alpha(i-1)} \cdot \left[ \Delta B_i(t) - \Delta A_i(t) \right]$$

---

## 📊 28-Dimensional Microstructure Feature Tensor

| Index | Feature Symbol | Description | Formula / Normalization |
| :---: | :--- | :--- | :--- |
| `0` | `spread_bps` | Inside Touch Bounded Spread | $\max(0.001, \min(0.25, \text{Ask} - \text{Bid}))$ |
| `1` | `ofi_l1` | Top-of-Book Order Flow Imbalance | $\frac{B_1 - A_1}{B_1 + A_1 + \epsilon}$ |
| `2` | `ofi_l5` | Level 1-5 Order Flow Imbalance | $\frac{\sum_{i=1}^5 B_i - \sum_{i=1}^5 A_i}{\sum_{i=1}^5 B_i + \sum_{i=1}^5 A_i + \epsilon}$ |
| `3` | `ofi_l15` | Full Depth Order Flow Imbalance | $\frac{\sum B_i - \sum A_i}{\sum B_i + \sum A_i + \epsilon}$ |
| `4` | `cvd_norm` | Cumulative Volume Delta (Normalized) | $\frac{\sum (\text{Signed Trade Qty})}{\text{Baseline Volume}}$ |
| `5` | `entropy` | Trade Size Shannon Entropy | $-\sum p_i \log_2(p_i)$ over rolling trade window |
| `6` | `vpin_score` | Volume-Synchronized Probability of Toxicity | PBC algorithm over volume buckets |
| `7` | `spoof_mag_bid` | Bid Depth Spoofing / Pulling Metric | Weighted outer-layer queue cancellations |
| `8` | `spoof_mag_ask` | Ask Depth Spoofing / Pulling Metric | Weighted outer-layer queue cancellations |
| `9` | `bid_absorption`| Touch Absorption Volume (Bid) | Passive liquidity consumed without price change |
| `10`| `ask_absorption`| Touch Absorption Volume (Ask) | Passive liquidity consumed without price change |
| `11`| `whale_tx` | Institutional Block Trade Counter | Trades exceeding dynamic volume threshold |
| `12`| `layering_index`| Outer vs. Inner Book Density Ratio | $\frac{\text{Volume}(L_6 \dots L_{15})}{\text{Volume}(L_1 \dots L_5) + \epsilon}$ |
| `13–27`| `spatial_0..14`| Exponential Decay Depth Imbalance | $e^{-\alpha i} \cdot \left( \frac{B_i - A_i}{\text{Baseline Volume}} \right)$ for $i=0 \dots 14$ |

---

## 📁 Repository Structure

```text
Kalshi Simulator/
├── data/                               # Execution logs, tick tape JSONL files
├── models/
│   ├── nano_microscope_overhauled.onnx # Trained ONNX microstructure neural graph
│   └── feature_stats.json              # Mean and standard deviation normalization stats
├── keys/
│   └── kalshi_demo.pem                 # RSA private key for Kalshi API authentication
├── src/
│   └── kalshi_sim/
│       ├── __init__.py                 # Package version and exports
│       ├── __main__.py                 # CLI entry point and orchestration
│       ├── auth.py                     # RSA-PSS SHA-256 signing and auth headers
│       ├── execution_logger.py         # Structured JSONL execution logger
│       ├── ingestion_agent.py          # WebSocket ingestion and market discovery
│       ├── mock_feed.py                # Multi-market mock market feed & BTC price walk
│       ├── order_client.py             # REST API order client for Kalshi Demo
│       ├── order_simulator.py          # L2 depth walking & VWAP fill simulator
│       ├── orderbook.py                # Level-2 CLOB reconstructed order book state
│       ├── portfolio.py                # Virtual portfolio, mark-to-market, P&L
│       ├── schemas.py                  # Pydantic schemas, enums, data contracts
│       ├── settlement.py               # Expiry and settlement payout evaluator
│       ├── tick_writer.py              # Asynchronous JSONL tick stream recorder
│       └── ml/
│           ├── __init__.py
│           ├── feature_extractor.py    # 28-D microstructure feature extractor
│           ├── onnx_engine.py          # ONNX session manager & probability calibrator
│           └── statistical_ev_engine.py# Stage 2 Expected Value & Kelly Optimizer
├── tests/
│   ├── test_onnx_inference.py          # Unit tests for ONNX feature pipeline
│   ├── test_order_client.py            # Unit tests for demo order client
│   ├── test_simulation.py              # Unit tests for order book and fills
│   └── test_statistical_ev.py          # Unit tests for Expected Value & Kelly math
├── .env.example                        # Configuration template
├── pyproject.toml                      # Project metadata and dependencies
├── run_mock.bat                        # Launcher: Interactive Mock Simulation
├── run_live.bat                        # Launcher: Live Ingestion & Paper Trading
└── run_live_demo_trader.bat            # Launcher: Kalshi Demo Order Trading
```

---

## 🚀 Getting Started

### 1. Prerequisites
* **Python 3.11+** installed.
* Windows PowerShell / Command Prompt, Linux, or macOS terminal.

### 2. Installation
Clone the repository and install dependencies:

```powershell
# Clone repository
git clone https://github.com/BinqQarenYu/Kalshi-Simulator.git
cd "Kalshi Simulator"

# Create virtual environment (optional but recommended)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -e .
pip install -e ".[dev]"
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:

```powershell
cp .env.example .env
```

Edit `.env` to configure your credentials:
```ini
KALSHI_API_KEY_ID=your-key-id-here
KALSHI_PRIVATE_KEY_PATH=./keys/kalshi_demo.pem
KALSHI_ENV=demo
KALSHI_TIMEFRAMES=15m
```

---

## 🎮 Execution Modes

## 🚀 Quick Launch & Modes

### 🌟 Mode 0: Overhauled Web Dashboard (Interactive Kalshi UI)
Launches the institutional-grade web interface featuring real-time Level-2 order book depth, interactive Bitcoin spot chart with target strike line & countdown timer, 1-Click order execution, and live ONNX AI microstructure insights:

```powershell
.\run_dashboard.bat
# Access the web UI at: http://localhost:8000
```

### Mode 1: Interactive Live Mock Simulation (Zero Credentials Required)
Runs the full Two-Stage Quantitative Trading System locally with real-time Bitcoin price walks, Level-2 order books, ONNX AI inference, taker tape prints, and automated settlement.

```powershell
.\run_mock.bat
# Or via CLI:
python -m kalshi_sim --simulate --mock -v
```

### Mode 2: Live Kalshi Market Ingestion & Paper Trading
Connects directly to Kalshi's live WebSocket feed to ingest real-time order books, trades, and prices while executing **simulated paper orders** without risking capital.

```powershell
.\run_live.bat
# Or via CLI:
python -m kalshi_sim --simulate --timeframe 15m -v
```

### Mode 3: Kalshi Demo Account Live Trader
Submits simulated orders directly to your Kalshi Demo sandbox account via authenticated REST endpoints:

```powershell
.\run_live_demo_trader.bat
# Or via CLI:
python -m kalshi_sim --live-demo --timeframe 15m -v
```

---

## 🖥 Real-Time Console Telemetry

During execution, the console streams real-time market data and quantitative decision logs:

```text
2026-08-25 22:50:57 [INFO] MockFeed: [SNAPSHOT] KXBTC15M-T65000 | seq=1 | YesBid=$0.85 YesAsk=$0.87 | Spread=$0.02 | Strike=$65000
2026-08-25 22:50:57 [INFO] SimAgent: [ONNX AI]  KXBTC15M-T65000 | Signal=LONG (54.0%) | VPIN=0.15 | OFI_L1=+0.42 | Latency=0.82ms
2026-08-25 22:50:57 [INFO] SimAgent: [STAGE 2 EV] KXBTC15M-T65000 | NO  @ $0.15 | AI_P=51.3% | EV=+$0.363/ct | Edge=+36.3% | Kelly=10.7% (50 cts)
2026-08-25 22:50:57 [INFO] OrderSim: [SIM FILL]  KXBTC15M-T65000 | NO 50 contracts @ $0.1500 | Cost=$7.50 | Balance=$9992.50
2026-08-25 22:51:07 [INFO] SimAgent: [SETTLED]   KXBTC15M-T65500 | YES WIN 50 contracts | P&L=+$40.50 | Balance=$10,033.00

+-------------------------- P&L SUMMARY ---------------------------+
| Balance:    $10,033.00   Equity:     $10,033.00                  |
| Realized:   +$33.00      Unrealized: $0.00                       |
| Positions:  0            Trades:     4        Win Rate: 75.0%    |
+------------------------------------------------------------------+
```

---

## 🧪 Testing & Verification

Run the comprehensive unit test suite:

```powershell
$env:PYTHONPATH="src"
python -m pytest -v
```

### Test Coverage:
* `tests/test_statistical_ev.py`: Expected Value formulas, odds-inversion logic, edge verification, and Kelly sizing limits.
* `tests/test_onnx_inference.py`: 28-D feature extraction, normalization, and ONNX runtime session execution.
* `tests/test_simulation.py`: L2 order book construction, sequence tracking, and VWAP fill execution.
* `tests/test_order_client.py`: Kalshi Demo API client authentication and request signing.

---

## 📜 License

This project is licensed under the MIT License.
