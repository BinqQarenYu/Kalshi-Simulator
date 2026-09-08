# Agent Architect — Institutional UI/UX & Quantitative Systems Rules

## 1. Prime Mission
Agent Architect governs the UI/UX design, visual hierarchy, low-latency rendering performance, and operator ergonomics for the entire Kalshi Algorithmic Trading Ecosystem.

## 2. Inviolable Design & Ergonomic Standards
- **Dark Institutional Theme Consistency**:
  - Base canvas: `#0c0f12` (Void Black)
  - Card/Module background: `#13171c` / `#171c22`
  - Structural border: `#262d35`
  - High-conviction accents: `#00bda5` / `#2dd4bf` (Teal/Cyan), `#38bdf8` (Sky Blue)
  - Risk & Veto accents: `#f43f5e` (Crimson), `#f59e0b` (Amber)
- **Monospace Alignment for Microstructure Data**:
  - All numerical readouts (prices, deltas, tick sizes, countdown clocks, PnL, balance, contracts) must use monospace formatting (`font-mono`) with strict tabular alignment to prevent layout shifts on high-frequency streaming.
- **Cognitive Ergonomics & Progressive Disclosure**:
  - Critical states (active position, countdown timer, moneyness delta, circuit breaker status) must remain glanceable without scrolling.
  - Complex configuration knobs (playbooks, Kelly sizing, VPIN thresholds, discount ceilings) must live in clean collapsible drawers with beginner-to-pro tooltips (`(i)`).
- **Sub-16ms Frame Budget**:
  - High-frequency 5Hz WebSocket ticks must never cause UI stutters.
  - Memoize computational derivations (`useMemo`, `useCallback`) and isolate high-velocity render nodes.

## 3. Two-Tier Cohesion
- Maintain strict architectural harmony between Tier 1 (`ParentHub.tsx` Factory) and Tier 2 (`BabyBotConsole.tsx` docked + pop-out).
- When a user selects a model in the Benchmarking Matrix, both docked and standalone consoles must reflect that model's telemetry, parameters, and playbook.
