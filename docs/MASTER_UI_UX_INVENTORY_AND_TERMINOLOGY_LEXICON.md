# MASTER UI/UX INVENTORY & TERMINOLOGY LEXICON
## The Universal Multi-Exchange Quantitative Terminal & Capital Pool

> **Document Version**: `1.0.0-PROD`  
> **Last Updated**: `September 13, 2026`  
> **Target Audience**: Human Quantitative Trader & AI Engineering Agents (Koko, Agent Architect, Agent Codeflow, Agent Guardrails)  
> **Purpose**: Eliminates architectural ambiguity, standardizes institutional terminology, provides a complete inventory of all UI/UX pages/modals/drawers, and defines the click-through routing protocol for the entire platform.

---

# TABLE OF CONTENTS
1. [Executive Taxonomy: The "Never Say Just 'Bot'" Standard](#1-executive-taxonomy-the-never-say-just-bot-standard)
2. [The 4-Tier System Anatomy](#2-the-4-tier-system-anatomy)
3. [Full UI/UX Page & View Inventory (The 7 Primary Domains)](#3-full-uiux-page--view-inventory-the-7-primary-domains)
4. [The Master Click-Through & Interaction Protocol](#4-the-master-click-through--interaction-protocol)
5. [The Multi-Brain Neural Matrix (Brain 1, 2, 3)](#5-the-multi-brain-neural-matrix-brain-1-2-3)
6. [The 6-Exchange Venue Adapter Matrix](#6-the-6-exchange-venue-adapter-matrix)
7. [Communication & Refactoring Protocols (Future-Proofing Rules)](#7-communication--refactoring-protocols-future-proofing-rules)

---

# 1. EXECUTIVE TAXONOMY: THE "NEVER SAY JUST 'BOT'" STANDARD

As the platform scales across 6 exchanges, 4 trading strategies, and 3 neural ONNX brains, using the generic word **"bot"** creates dangerous ambiguity. 

Whenever requesting a modification or discussing system behavior, use the strict standardized terms below:

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 CANONICAL TERMINOLOGY MATRIX                                         │
├───────────────────┬───────────────────────────────────┬──────────────────────────────────────────────┤
│ CATEGORY          │ CANONICAL NAME                    │ PRECISE MEANING / SCOPE                      │
├───────────────────┼───────────────────────────────────┼──────────────────────────────────────────────┤
│ Strategy Bot 1    │ `ThreeStepDominationBot` (Bot 1)  │ Sole live-authorized strategy (Port 8001).   │
│ Strategy Bot 2    │ `MacroONNXBot` (Bot 2 / Dom 2)    │ Dual-brain shadow incubator bot (Port 8002). │
│ Strategy Bot 3    │ `MacroTrendDominionBot` (Bot 3)   │ Trend following shadow bot (Port 8003).      │
│ Strategy Bot 4    │ `GoldInversionBot` (Bot 4)        │ 32-D spacetime multi-venue engine.           │
├───────────────────┼───────────────────────────────────┼──────────────────────────────────────────────┤
│ Neural Brain 1    │ `SpotMacroAnchor` (Brain 1)       │ `nano_microscope_overhauled.onnx` (28-D).    │
│ Neural Brain 2    │ `CLOBMicroSniper` (Brain 2)       │ `kalshi_onnx.onnx` (28-D binary CLOB).       │
│ Neural Brain 3    │ `GoldSpacetimeEngine` (Brain 3)   │ `gold.onnx` (32-D tri-venue spacetime).      │
├───────────────────┼───────────────────────────────────┼──────────────────────────────────────────────┤
│ UI Cockpit        │ `ParentHub`                       │ Full institutional desktop browser terminal. │
│ Docked Rail       │ `BabyBotConsole`                  │ Right-side docked control rail in ParentHub. │
│ Floating HUD      │ `Win32BabyBotHUD`                 │ 515x245px native topmost OS window.          │
├───────────────────┼───────────────────────────────────┼──────────────────────────────────────────────┤
│ Server Core       │ `MotherServer`                    │ Port 8000 FastAPI simulation/telemetry hub.  │
│ Live Daemon       │ `StandaloneBotEngine`             │ Port 8001 exclusive live process lock holder.│
├───────────────────┼───────────────────────────────────┼──────────────────────────────────────────────┤
│ Execution Lane 1  │ `Lane 1 (LIVE)`                   │ 100% real capital on live exchange.          │
│ Execution Lane 2  │ `Lane 2 (SHADOW)`                 │ Virtual execution on live WebSocket ticks.   │
│ Execution Lane 3  │ `Lane 3 (SIMULATION)`             │ Synthetic order book walk & backtesting.     │
└───────────────────┴───────────────────┴──────────────────────────────────────────────┘
```

---

# 2. THE 4-TIER SYSTEM ANATOMY

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    TIER 1: PARENT HUB                                            │
│   Full institutional command deck containing all 7 Primary Domains and contextual sub-navs.      │
├─────────────────────────────────┬────────────────────────────────────────────────────────────────┤
│   TIER 2: DOCKED BABY BOT RAIL   │   TIER 3: NATIVE WIN32 FLOATING HUD                            │
│   Collapsible right rail in     │   515 x 245 px topmost OS desktop widget                       │
│   ParentHub with fast failsafes.│   (Zero-distraction live execution glance).                    │
├─────────────────────────────────┴────────────────────────────────────────────────────────────────┤
│                                    TIER 4: BACKEND POWERTRAIN                                    │
│   Port 8000 (Mother Server) + Port 8001 (Live Standalone) + Port 8002/8003 (Shadow Micro-Daemons) │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

# 3. FULL UI/UX PAGE & VIEW INVENTORY (THE 7 PRIMARY DOMAINS)

The terminal is organized into **7 Primary Domains** accessible via the left navigation rail:

```
Navigation Rail: [ Omni Terminal | CLOB Terminal | Engine Room | Bots | Analytics | Journal | Settings ]
```

---

### DOMAIN 1: 🌐 OMNI TERMINAL (`UniversalTerminalView.tsx`)
*The multi-exchange capital pool, global arbitrage radar, and cross-venue smart router.*

- **Header Strip: Global Liquidity Status Bar**
  - Live latency and balance across 6 exchanges: `Kalshi (CFTC)`, `Polymarket (Web3)`, `Binance`, `Bybit`, `HTX`, `Pionex`.
  - Consolidated capital pool counter (`$128,450.00`) and anti-wash trading shield status.
- **Section 1: Cross-Exchange Mispricing & Arbitrage Radar**
  - Side-by-side comparison of YES/NO contract prices across Kalshi vs Polymarket.
  - Interactive **"Snipe Spread ⚡"** 1-click execution dispatch button.
- **Section 2: Consolidated Capital Pool & Liquidity Visualizer**
  - Dynamic currency balance breakdown (USD, USDC, USDT).
  - Visual allocation percentage bars.
- **Section 3: Multi-Brain ONNX Neural Fleet Deck**
  - Live cards for Brain 1 (`nano_microscope`), Brain 2 (`kalshi_onnx`), and Brain 3 (`gold.onnx`).
  - Real-time softmax probability gauges and sub-2ms CPU inference latencies.
- **Section 4: Omni-Router Smart Execution Order Slip**
  - Multi-asset switcher (`BTC`, `ETH`, `GOLD`, `SOL`).
  - Routing modes: `BEST_VENUE`, `CROSS_VENUE_ARB`, `MULTI_VENUE_SPLIT`.
  - Micro-Bankroll armor lock (1 contract cap).

---

### DOMAIN 2: 📈 CLOB TERMINAL (`ClobTerminalView.tsx`)
*Institutional Central Limit Order Book trading cockpit and depth visualization.*

- **Sub-Tab 1: Institutional Cockpit (`terminal`)**
  - Multi-panel workspace combining L2 CLOB Depth Ladder, Live Trade Tape, and 1-click execution tickets.
- **Sub-Tab 2: Liquidity Heatmap DOM (`heatmap`)**
  - 3D rolling depth-of-market visualization showing resting liquidity walls and book thickness.
- **Sub-Tab 3: 15M Event Order Book (`event_book`)**
  - High-resolution view of the active Kalshi binary strike order book (YES/NO bids/asks).
- **Sub-Tab 4: Underlying L2 Spot Book (`spot_book`)**
  - Live Binance 20-depth spot order book with real-time Cumulative Volume Delta (CVD).
- **Sub-Tab 5: Pine Script Strategy Editor (`pine_editor`)**
  - In-browser IDE for coding, compiling, and testing custom algorithmic scripts and indicators.

---

### DOMAIN 3: ⚙️ ENGINE ROOM (`EngineRoomMatrix.tsx` & `ONNXSettingsPanel.tsx`)
*The 3-cylinder powertrain telemetry matrix and ONNX neural architecture inspection lab.*

- **Sub-Tab 1: Master Visual Matrix (`matrix`)**
  - Synchronized real-time HUD displaying all 3 cylinders firing concurrently.
- **Sub-Tab 2: Cylinder 1: Spot Orderflow (`cylinder1`)**
  - Binance depth20 tick stream, VPIN toxicity meter, and macro drift tracker.
- **Sub-Tab 3: Cylinder 2: Kalshi CLOB (`cylinder2`)**
  - Kalshi binary contract imbalance, adverse selection front-runner ($\Delta^*$), and micro-momentum.
- **Sub-Tab 4: Cylinder 3: HMM Macro Regime (`cylinder3`)**
  - 3-state Hidden Markov Model classifier (Bull Trend, Mean-Reverting Chop, High Volatility Panic) and Silas TWAP Gravity.
- **Sub-Tab 5: Bot Wiring Harness (`wiring`)**
  - Visual node-graph illustrating how raw market ticks transform through feature extractors into strategy decisions.

---

### DOMAIN 4: 🤖 BOTS & MATRIX (`ParentHub.tsx > bots`)
*Bot fleet benchmarking, shadow incubation, and 4-pillar live promotion gates.*

- **Sub-Tab 1: Benchmarking Matrix (`matrix`)**
  - Side-by-side empirical performance table comparing Bot 1 (Live), Bot 2 (Shadow), and Bot 3 (Shadow).
  - Live win-rate, profit factor, settled cycles, and Seal of Excellence status.
- **Sub-Tab 2: Active Live Fleet (`fleet`)**
  - Dedicated telemetry for the sole authorized live strategy (`ThreeStepDominationBot`).
- **Sub-Tab 3: Shadow Incubator Lab (`incubator`)**
  - Incubation progress tracker (e.g. `24/30` verified cycles required before promotion eligibility).
- **Sub-Tab 4: Promotion Gate Audit (`promotion`)**
  - Automated 4-pillar pre-flight validator:
    1. *Invariant Compliance* (100% pass)
    2. *Micro-Bankroll Sizing Armor* (1 contract cap)
    3. *Guardrail Wiring* (VPIN + Moats + Cooldowns)
    4. *Strict Decimal Precision* (Zero floats)

---

### DOMAIN 5: 📊 ANALYTICS (`ParentHub.tsx > analytics`)
*60 FPS live trajectory charting, microstructure radar, and tape forensics.*

- **Sub-Tab 1: 60fps Live Workbench (`workbench`)**
  - **Price Hero**: Target Strike ($K$), CME CF Spot ($S_t$), Distance to Strike ($S_t - K$), and 15M countdown.
  - **TargetChart**: 60 FPS spline trajectory chart rendering settlement boundary and dynamic volatility moat.
  - **Lower Deck Tabs**: L2 CLOB Ladder, Live Trade Tape, Active Positions, Bot Reports Deck.
- **Sub-Tab 2: Institutional Analytics (`historical`)**
  - Sharpe Ratio, Sortino Ratio, Maximum Drawdown, Cumulative PnL curve, Win/Loss distributions.
- **Sub-Tab 3: L2 CLOB Ladder (`clob`)**
  - Full-screen depth ladder with spread highlighted.
- **Sub-Tab 4: Live Trade Tape (`tape`)**
  - Real-time time-and-sales stream with buyer/seller aggressor tagging.
- **Sub-Tab 5: Order Flow & VPIN Radar (`vpin`)**
  - Real-time toxicity gauges and volume distribution curves.

---

### DOMAIN 6: 📖 JOURNAL (`ParentHub.tsx > journal`)
*Real execution ledger, settlement history, and deep forensic post-mortem cards.*

- **Sub-Tab 1: Today's Trades (`trades`)**
  - Filterable table of all fills executed today across Live (Lane 1) and Shadow (Lane 2).
- **Sub-Tab 2: Historical Settlements (`settlements`)**
  - Complete history of contract expirations, official settlement TWAPs, and final payout outcomes.
- **Sub-Tab 3: Win/Loss Reports (`reports`)**
  - Deep-dive diagnostic post-mortems for every trade with full AI rationales and EV calculations.

---

### DOMAIN 7: 🛠️ SETTINGS & PRESET VAULT (`ParentHub.tsx > settings`)
*Cryptographic API keys, preset vaults, bankroll armor, and global kill-switches.*

- **Sub-Nav Sections**:
  - `account`: Account balance and exchange profile status.
  - `keys`: Cryptographic RSA private keys (`.pem`) and API credentials.
  - `limits`: Micro-bankroll limits, daily loss caps, and circuit breakers.
  - `notifications`: Discord webhook and Telegram alert integration.
  - `routing`: Smart order routing rules and venue preferences.
  - `defaults`: Strategy parameter presets and default sizes.
  - `data`: Historical tick database, dataset builders, and cache hygiene.
  - `theme`: Terminal color themes (Institutional Dark, Matrix Green, Cyberpunk Cyan).
  - `killswitch`: Global emergency liquidation and order cancellation trigger.

---

# 4. THE MASTER CLICK-THROUGH & INTERACTION PROTOCOL

Below is the definitive reference for what happens when any interactive element is clicked:

```
┌──────────────────────────────────────┬────────────────────────┬────────────────────────────────────────────────────────┐
│ CLICKED ELEMENT                      │ UI/UX ACTION           │ RESULTING DESTINATION & ACTION                         │
├──────────────────────────────────────┼────────────────────────┼────────────────────────────────────────────────────────┤
│ Exchange Node (e.g. `Binance`)       │ Slide-in Flyout Sheet  │ Opens Binance 20-Depth Book & CVD Telemetry Drawer     │
│ Exchange Node (e.g. `Polymarket`)    │ Slide-in Flyout Sheet  │ Opens Web3 CTF AMM Arbitrage & Collateral Sheet        │
│ Exchange Node (e.g. `Kalshi`)        │ Slide-in Flyout Sheet  │ Opens Kalshi CFTC L2 CLOB & CME CF Settlement Sheet    │
├──────────────────────────────────────┼────────────────────────┼────────────────────────────────────────────────────────┤
│ Brain 1 (`nano_microscope`) Card     │ Spec Modal Popover     │ Opens 28-D Spot Macro Tensor & Weight Inspector        │
│ Brain 2 (`kalshi_onnx`) Card         │ Spec Modal Popover     │ Opens 28-D CLOB Micro-Imbalance Softmax Inspector      │
│ Brain 3 (`gold.onnx`) Card           │ Spec Modal Popover     │ Opens 32-D Universal Tri-Venue Spacetime Engine Sheet  │
├──────────────────────────────────────┼────────────────────────┼────────────────────────────────────────────────────────┤
│ "Preset Vault" Button (Header)       │ Modal Popover          │ Opens `PresetVaultModal.tsx` for 1-click JSON vaults   │
│ "Snipe Spread ⚡" Button (Omni)      │ Async Order Dispatch   │ Simulates instant cross-exchange arbitrage fill        │
│ Trade Row (Journal Table)            │ Diagnostic Modal       │ Opens Forensic Post-Mortem Card with AI Rationale      │
│ "Pop-out Baby Bot" Button            │ Window Spawner         │ Launches native Win32 515x245px floating desktop widget│
│ "Emergency FLATTEN / HALT" Button    │ Synchronous Failsafe   │ 100% market liquidation + instant order cancel flood   │
└──────────────────────────────────────┴────────────────────────┴────────────────────────────────────────────────────────┘
```

---

# 5. THE MULTI-BRAIN NEURAL MATRIX (BRAIN 1, 2, 3)

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   THE 3 NEURAL BRAINS OF THE FLEET                                   │
├──────────────────────────┬──────────────┬──────────────┬─────────────────────────────────────────────┤
│ BRAIN IDENTIFIER         │ MODEL FILE   │ INPUT SHAPE  │ PRIMARY QUANT OBJECTIVE                     │
├──────────────────────────┼──────────────┼──────────────┼─────────────────────────────────────────────┤
│ Brain 1: Spot Macro      │ `nano.onnx`  │ `(1, 28)`    │ Binance spot drift, CVD trend, VPIN toxicity│
│ Brain 2: CLOB Sniper     │ `kalshi.onnx`│ `(1, 28)`    │ Kalshi contract book imbalance & micro-scalp│
│ Brain 3: Gold Spacetime  │ `gold.onnx`  │ `(1, 32)`    │ Tri-Venue cross-arbitrage & basis parity    │
└──────────────────────────┴──────────────┴──────────────┴─────────────────────────────────────────────┘
```

### Brain 3 (`gold.onnx`) 32-Dimensional Feature Vector Breakdown:
- **Indices `[0 : 20]` (20-D)**: Binance Level-2 Spot Depth (10 bids, 10 asks normalized to midpoint).
- **Indices `[20 : 24]` (4-D)**: Microstructure Dynamics (5m CVD, rolling VPIN, 60s Spot Volatility, Micro-Price Diff).
- **Indices `[24 : 28]` (4-D)**: Kalshi CLOB Micro-Features (Best YES bid, best NO bid, spread, depth imbalance).
- **Indices `[28 : 32]` (4-D)**: Cross-Venue Spacetime Basis (Polymarket spread, basis spread, countdown decay $T/900$, CF TWAP divergence).

---

# 6. THE 6-EXCHANGE VENUE ADAPTER MATRIX

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                   THE 6-EXCHANGE VENUE MATRIX                                        │
├─────────────┬────────────────┬────────────────────────────┬──────────────────────────────────────────┤
│ VENUE       │ REGULATORY / TYPE│ ADAPTER MODULE           │ SUPPORTED INSTRUMENTS / ASSETS           │
├─────────────┼────────────────┼────────────────────────────┼──────────────────────────────────────────┤
│ Kalshi      │ CFTC Regulated │ `kalshi_adapter.py`        │ `KXBTC15M`, `KXETH15M`, `KXSOL15M`, DOGE │
│ Polymarket  │ Web3 (Polygon) │ `polymarket_adapter.py`    │ CTF Binary Option Smart Contracts (USDC) │
│ Binance     │ Global Derivs  │ `binance_adapter.py`       │ BTC/USDT Spot, Quarterly & Perp Futures  │
│ Bybit       │ Global Derivs  │ `bybit_adapter.py` (Draft) │ Linear Perpetuals & Basis Futures        │
│ HTX         │ Global Spot    │ `htx_adapter.py` (Draft)   │ High-liquidity Global Crypto Spot        │
│ Pionex      │ Grid Liquidity │ `pionex_adapter.py` (Draft)│ Automated Rebalancing & Grid Arbitrage   │
└─────────────┴────────────────┴────────────────────────────┴──────────────────────────────────────────┘
```

---

# 7. COMMUNICATION & REFACTORING PROTOCOLS (FUTURE-PROOFING RULES)

To guarantee that human quantitative traders and AI coding agents always remain 100% synchronized, all future requests and design specs must adhere to these **5 Communication Commandments**:

1. **Use the 3-Part Address for Bot Changes**:
   *Format*: `[Execution Lane] -> [Bot ID] -> [Target Component]`  
   *Example*: *"In Lane 1, update Bot 1 (3-Step Dominion) Dynamic Volatility Moat floor to $42.00."*

2. **Distinguish Between Models and Bots**:
   - A **Model / Brain** is a pure mathematical ONNX tensor file (e.g. `gold.onnx`, Brain 3).
   - A **Bot / Strategy** is an autonomous trading class that executes risk rules and sends orders (e.g. `ThreeStepDominationBot`).

3. **Specify the UI Surface Explicitly**:
   - Specify whether a UI change applies to the **Parent Hub**, the **Docked Baby Bot Rail**, or the **Native Win32 HUD**.

4. **Zero Float Financial Rule in All Specs**:
   - All balance changes, fee schedules, and price calculations must be specified in `Decimal` string formats (e.g. `Decimal("0.48")`, not `0.48`).

5. **Mandatory 4-Pillar Certification Before Live Promotion**:
   - No strategy may be moved from Lane 2 (Shadow) to Lane 1 (Live) without 30 verified incubation cycles and a 100% PASS score on `BotDeploymentAuditor`.

---

*This document is the official architectural ground-truth specification for the Kalshi Quantitative Simulator & Universal Multi-Exchange Terminal.*
