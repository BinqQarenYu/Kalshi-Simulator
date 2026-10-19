# Kalshi Neural & Robotics Command Deck Overhaul

A complete visual and workflow overhaul of the Kalshi Quantitative Simulator frontend that unites a TradeZella-caliber performance analytics suite, a live animated Robot Bot & Neural Synapse Arena, and an interactive ML & Bot Asset Forge for creating, training, certifying, and deploying BTC and ETH trading bots.

### User Review & Critical Decisions

> [!IMPORTANT]
> All core architectural and design choices below reflect your confirmed preferences from our design alignment and will govern the build upon approval.

- **Confirmed Decision 1 — Navigation Structure**: **Unified Command Deck with 4 Primary Workspaces** (*Performance Analytics*, *Neural & Robot Arena*, *ML & Bot Forge*, and *Terminal Operations*), providing clean single-click switching while maintaining persistent live WebSocket telemetry.
- **Confirmed Decision 2 — Visual Style for Bots & Neural Engine**: **Interactive SVG/Canvas Robots & Live Neural Synapse Graph**, where each trading bot is rendered as an articulated kinematic robot unit whose posture, core pulse, and synapse firing animations respond in real time to market ticks, orderflow imbalance, HMM regime shifts, and trade execution states.
- **Confirmed Decision 3 — ML & Bot Forge Scope**: Full end-to-end creation and training studio including:
  1. **Custom Bot Builder** with strategy templates, EV/discount floors, and risk dials.
  2. **Asset-Specific ONNX Trainer & Exporter** (14-D Microstructure & 32-D Gold models for BTC and ETH).
  3. **HMM 3-State Macro Regime Trainer & Visualizer** (`STABLE_RANGE`, `VOL_EXPANSION`, `RISK_OFF` transition matrices per asset).
  4. **Ensemble & Custom ML Feature Weight Lab** (calibrating OFI, VPIN, Spot Lead-Lag, Moneyness CDF, and Neural weights).
  5. **One-Click Paper Incubator to Live SHA-256 Seal Deployment Pipeline**.
- **Confirmed Decision 4 — Legacy Terminal Tools**: **Retained in Dedicated Sub-Tabs** within the *Terminal Operations* workspace (*L2 CLOB & Order Entry*, *Trade Journal & 15M Ledger*, *7-Councilor AI Deliberation*, and *Guardrails & Compliance*).

---

### 1. Overview & Core Concept

- **What It Does**: Transforms the trading interface into a high-precision quantitative command center that bridges institutional post-trade analytics (inspired by TradeZella's KPI gauges, 6-axis performance radar, cumulative P&L area curve, and daily net P&L bars) with a live visual AI laboratory where users watch neural networks fire across input-to-output layers, inspect animated robot bot units on the execution floor, and forge new ML assets and bots for live Kalshi crypto markets (`BTC` and `ETH`).
- **Target Audience / Persona**: Quantitative crypto derivatives traders and ML engineers operating 15-minute, hourly, and daily Kalshi binary contracts under strict `Decimal` financial math and micro-bankroll guardrails.
- **Key Value**: Eliminates disjointed configuration modals by turning model training (ONNX, HMM, Ensemble weights), bot creation, paper incubation, SHA-256 Seal certification, and live execution monitoring into a cohesive, visually transparent workflow.

---

### 2. User Experience & Visual Design

- **Key User Flows**:
  1. **Performance Analytics Deck (TradeZella-Inspired)**:
     - Top filter toolbar for switching Asset (`All`, `BTC`, `ETH`), Execution Mode (`Paper`, `Live`, `Combined`), Timeframe (`15M`, `1H`, `Daily`), and Bot Filter, plus a primary **Resync & Audit** action.
     - **5-Card Top KPI Strip**:
       1. *Net P&L* (large tabular dollar readout with trade count).
       2. *Trade Win %* paired with a semi-circular SVG arc gauge and win/breakeven/loss counters.
       3. *Profit Factor* paired with a proportional emerald/coral ring gauge.
       4. *Cycle Win %* paired with a semi-circular SVG arc gauge.
       5. *Avg Win / Loss Trade* paired with a horizontal proportional comparison bar (`+$Win` vs `-$Loss`).
     - **3-Column Core Charts Row**:
       1. *Composite Edge Score (6-Axis Radar / Spider Chart)*: Plots `Win %`, `Profit Factor`, `Avg Win/Loss`, `Recovery Factor`, `Max Drawdown Control`, and `Consistency` on a polygonal coordinate grid with a bottom 0–100 gradient score bar.
       2. *Cumulative Net P&L Curve*: Smooth SVG/Canvas area chart with emerald gradient fill above `$0` and crimson fill below `$0`, complete with crosshair hover tooltips.
       3. *Net Cycle / Daily P&L Histogram*: Vertical bar chart rendering positive emerald bars and negative coral bars across recent cycles/days.
  2. **Neural & Robot Bot Arena**:
     - **Live Neural Synapse Diagram (Left/Center Stage)**: Interactive multi-layer neural graph (*Input Feature Tensor [OFI, VPIN, Spot Lead, Strike Distance, Time Decay, HMM State]* $\rightarrow$ *Hidden Dense & Attention Layers* $\rightarrow$ *Output Probability Nodes [$P(\text{Up})$, $P(\text{Down})$, $P(\text{Wait})$]*) with real-time animated signal pulses scaled by actual WebSocket feature weights and inference probabilities.
     - **Animated Robot Bot Bay (Right/Bottom Stage)**: Each active and incubated bot (*Bot 1 V4 BTC*, *ETH Bot 1 V4*, *Dual ONNX Arbitrage*, *Macro Trend Dominion*, *Market Maker Bot 6*, plus user-created custom bots) is rendered as an articulated SVG robot unit with distinct visual states:
       - *Scanning / Idle*: Radar visor sweep and steady telemetry hum.
       - *Evaluating Gate*: Synapse tether linking the robot to the neural diagram with live preflight gate readouts.
       - *Executing / In-Position*: Energized reactor core, active target lock on strike price, and real-time P&L tether.
       - *Guarded / Cooldown*: Protective shield overlay showing exact gate or circuit-breaker status.
     - Clicking any robot unit opens its live telemetry inspector, qualification ticket stream, and instant arm/disarm or test-trade controls.
  3. **ML & Bot Asset Forge**:
     - **Tab A — Custom Bot Creator**: Name a new bot, assign target asset (`BTC` or `ETH`) and timeframe (`15m`, `1h`), bind an ONNX brain asset and HMM regime asset, configure entry EV floor, discount ceiling, Doubt-Harvester ROI trigger, and proximity moat, and register it directly into the fleet.
     - **Tab B — ONNX Neural Asset Studio (BTC & ETH)**: Select asset (`BTC` or `ETH`) and architecture (`14-D Microstructure MLP` or `32-D Gold Champion`), inspect experience buffer sample counts, trigger live training/retraining or pause/resume background continuous training, watch live loss/accuracy curves, and export verified `.onnx` model assets.
     - **Tab C — HMM 3-State Regime Studio (BTC & ETH)**: Train and calibrate the QuoLas Gaussian HMM per asset (`STABLE_RANGE`, `VOL_EXPANSION`, `RISK_OFF`), inspect the $3 \times 3$ state transition matrix SVG diagram, and test regime classification on live spot candles.
     - **Tab D — Ensemble & Feature Weight Lab**: Interactive sliders to calibrate feature weights (OFI, VPIN Toxicity Shield, Spot Lead-Lag Velocity, Moneyness CDF, HMM Regime Multiplier, ONNX Confidence) and run an instant empirical backtest pass against cached stream data.
     - **Tab E — Incubator to Live Deployment Pipeline**: Visual 3-stage promotion pipeline (*Stage 1: Paper Incubator Trial* $\rightarrow$ *Stage 2: 5-Pillar Pre-Deployment Audit* $\rightarrow$ *Stage 3: SHA-256 Seal of Excellence & Live Activation*).
  4. **Terminal Operations (Integrated Legacy Tools)**:
     - Clean sub-navigation preserving full access to:
       - *L2 CLOB & Manual Order Entry* (Price Hero, Target Strike Chart, L2 Ladder, Trade Tape, and Order Ticket).
       - *Trade Journal & 15M Win/Loss Forensic Ledger* (with CSV export and qualification ticket inspection).
       - *7-Councilor AI Deliberation Chamber* (LangGraph multi-agent debate and KEV Oracle).
       - *Guardrails, CFTC Compliance & System Integrity Station*.

- **Visual Identity & Theme**:
  - *Aesthetic Direction*: Precision Quantitative Dark Observatory — blending TradeZella's ultra-clean dark analytics surfaces with calibrated aerospace/robotics telemetry.
  - *Color Palette & Mood (60-30-10 Discipline)*:
    - **60% Dominant Canvas**: Deep obsidian slate (`#0B0D13`) for zero eye strain and high chart contrast.
    - **30% Structural Surfaces**: Matte graphite panels (`#121621`) with crisp `1px` hairline borders (`#1E2536`) and single-elevation depth (no nested card-in-card clutter).
    - **10% Semantic & Telemetry Accents**: Emerald (`#10B981`) for positive P&L, wins, and active nominal states; Coral Crimson (`#F43F5E`) for losses, drawdowns, and vetoes; Electric Indigo (`#6366F1`) and Laser Cyan (`#06B6D4`) for neural synapse pulses, radar polygons, and primary actions; Telemetry Amber (`#F59E0B`) for warnings and incubation states.
  - *Typography & Hierarchy (2+1 Font Rule)*:
    - *Display & Navigation*: `Plus Jakarta Sans` (SemiBold/Bold 600–700) for crisp headers and workspace titles.
    - *Body & Controls*: `DM Sans` (Regular/Medium 400–500) for clean readability across forms and labels.
    - *Data, Prices, P&L & Telemetry*: `JetBrains Mono` with strict `tabular-nums` (`font-variant-numeric: tabular-nums`) so live ticking prices, countdowns, and P&L columns never jitter.
  - *Component Styling & Layout*:
    - Full `1440px+` desktop workspace layout with a sleek top navigation bar following the 3-zone contract (Brand wordmark on left, 4 primary workspace links in center, active asset/mode quick-action bar on right).
    - Zero static pill clutter: metadata (timestamps, ticker symbols, cycle IDs) rendered as clean inline monospace text separated by `·` delimiters.

- **Interactive Feedback & Motion**:
  - Compositor-friendly SVG/Canvas animations (`transform`, `opacity`, `stroke-dashoffset`) for neural synapse particles and robot bot joint/visor animations, with a toggle to pause animations (`prefers-reduced-motion` friendly).
  - Immediate `<150ms` visual feedback on all bot arming, model training triggers, preset saves, and order placements.

---

### 3. Key Product Decisions & Trade-Offs

- **Decision 1: Unified 4-Workspace Architecture vs. Multi-Modal Popups**
  - *Chosen Approach*: Consolidate the primary experience into 4 top-level workspaces (*Analytics*, *Neural & Robot Arena*, *ML & Bot Forge*, *Terminal Operations*) while keeping the standalone `?view=baby-bot` pop-out console intact.
  - *Why*: Eliminates modal fatigue and gives the TradeZella-style analytics, the animated robot/neural arena, and the ML training forge full viewport breathing room.
  - *Alternatives Considered*: Keeping everything inside collapsible drawers on the old CLOB screen, which overcrowded the viewport.
- **Decision 2: Real Backend Wiring for ML Asset Training & Custom Bots**
  - *Chosen Approach*: Wire the *ML & Bot Forge* directly to real FastAPI endpoints driving `ContinuousModelTrainer`, `GoldContinuousTrainer`, `HMMBrain`, `PresetManager`, `BotDeploymentAuditor`, and a persistent custom bot/asset registry in `data/`, strictly preserving `Decimal` financial math on the backend and `decimal.js` on the frontend.
  - *Why*: Honours the Zero Hallucination and Zero Float Financial Math directives (`AGENTS.md`) so every trained model, weight adjustment, and deployed bot is empirical and persisted.
  - *Alternatives Considered*: Purely visual frontend mock animations, which would violate the simulator's core operational directives.

---

### 4. Technical Architecture & Data Strategy *(Technical Reference)*

- **Architecture & Component Diagram**:

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                         TOP COMMAND BAR (3-Zone Contract)                         │
│  [Kalshi Neural Deck]   [Analytics | Neural Arena | ML Forge | Terminal]  [Action]│
└───────────────┬──────────────────────┬───────────────────────┬────────────────────┘
                │                      │                       │
                ▼                      ▼                       ▼
┌───────────────────────────┐ ┌────────────────────────┐ ┌──────────────────────────┐
│ 1. ANALYTICS WORKSPACE    │ │ 2. NEURAL & ROBOT ARENA│ │ 3. ML & BOT ASSET FORGE  │
│ ┌───────────────────────┐ │ │ ┌────────────────────┐ │ │ ┌──────────────────────┐ │
│ │ 5-KPI Gauge Strip     │ │ │ │ Live Neural Graph  │ │ │ │ Custom Bot Builder   │ │
│ │ (Arc & Ring SVG)      │ │ │ │ (28D/32D Synapses) │ │ │ │ (BTC/ETH + Dials)    │ │
│ └───────────────────────┘ │ │ └─────────┬──────────┘ │ │ ├──────────────────────┤ │
│ ┌───────────────────────┐ │ │           │            │ │ │ ONNX & HMM Trainers  │ │
│ │ 6-Axis Edge Radar     │ │ │           ▼            │ │ │ (Asset Fit & Export) │ │
│ │ + Cumulative Area P&L │ │ │ ┌────────────────────┐ │ │ ├──────────────────────┤ │
│ │ + Daily Net P&L Bars  │ │ │ │ Animated Robot Bay │ │ │ │ Ensemble Weight Lab  │ │
│ └───────────────────────┘ │ │ │ (SVG Kinematic Bots│ │ │ │ & Seal Deployment    │ │
│                           │ │ │  + Gate Telemetry) │ │ │ └──────────────────────┘ │
└─────────────┬─────────────┘ └───────────┬────────────┘ └────────────┬─────────────┘
              │                           │                           │
              └───────────────────────────┼───────────────────────────┘
                                          ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│ 4. TERMINAL OPERATIONS WORKSPACE (Sub-Tabs)                                       │
│  [L2 CLOB & Order Entry]  [Trade Journal & 15M Ledger]  [AI Council]  [Guardrails]│
└─────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │
                          WebSocket (/ws) + REST (/api/*)
                                          ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                  FASTAPI UNIFIED ENGINE (Port 3000 • Decimal Math)                │
│  • Analytics & Equity Service      • ONNX 14D/32D Trainer & Exporter (BTC / ETH)  │
│  • QuoLas 3-State HMM Brain        • Custom Bot & ML Asset Registry (data/*.json) │
│  • 5-Pillar Pre-Deployment Auditor • SHA-256 Seal of Excellence & Live Router     │
└───────────────────────────────────────────────────────────────────────────────────┘
```

- **Data Model & State**:
  - **Real-Time WebSocket Stream (`/ws`)**: Delivers 4Hz coalesced snapshots containing `market` (BTC/ETH spot, strike, countdown, best bid/ask), `ai_signals` ($P(\text{Up})$, $P(\text{Down})$, $P(\text{Wait})$, VPIN, EV, Kelly fraction, rationale), `portfolio` & `live_portfolio`, `continuous_training`, `hmm_macro_regime`, `preflight_gates`, and `seal_registry`.
  - **ML & Bot Forge Registry (`/api/forge/*` & `/api/ml/*`)**:
    - Stores custom bot definitions (ID, name, asset `BTC`/`ETH`, timeframe, bound ONNX asset, bound HMM asset, ensemble feature weights, EV floor, discount price, certification status) in `data/custom_bots_registry.json`.
    - Tracks asset-specific ONNX model artifacts (`models/btc_microstructure.onnx`, `models/eth_microstructure.onnx`, `models/gold_32d.onnx`) and HMM regime models (`models/hmm_btc.pkl`, `models/hmm_eth.pkl`) with training metrics (epochs, loss history, validation accuracy, transition matrix, timestamp).
- **Interactive Component & State Mapping**:
  - **Analytics Filter & KPI Engine**: Changing the Asset (`BTC`/`ETH`/`All`), Mode (`Paper`/`Live`), or Date/Cycle window re-computes the 5 KPI cards, 6-axis Edge Score radar vertices, Cumulative Net P&L area points, and Cycle/Daily P&L bars using `decimal.js` arithmetic.
  - **Interactive Robot Bot Units**: Selecting any robot in the Arena highlights its active neural pathways in the Synapse Graph, displays its live 6-gate qualification checklist, and exposes one-click **Arm / Disarm**, **Test Trade**, **Switch Active Bot**, and **Inspect Forensics** actions.
  - **ML & Bot Forge Handlers**:
    - *Train ONNX Asset*: Triggers `POST /api/forge/onnx/train` for the selected asset (`BTC` or `ETH`) and architecture (`14D` or `32D`), streaming epoch progress and updating the exported model registry.
    - *Calibrate HMM Asset*: Triggers `POST /api/forge/hmm/train` for `BTC` or `ETH`, returning the updated $3 \times 3$ transition matrix and active regime probabilities.
    - *Save Ensemble Weights & Backtest*: Triggers `POST /api/forge/ensemble/evaluate`, returning empirical win rate, profit factor, and expected value across historical cycles.
    - *Create & Deploy Bot*: Saves the custom bot via `POST /api/forge/bots/create`, runs the 5-pillar certification gate via `POST /api/bots/audit`, issues/verifies the SHA-256 Seal, and activates the bot in the live/paper engine via `POST /api/bots/spawn`.
