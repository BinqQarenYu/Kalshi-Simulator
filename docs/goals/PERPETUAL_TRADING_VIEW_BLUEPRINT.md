# 🦌 Perpetual Trading Terminal — Master Blueprint

This document outlines the architectural roadmap to transform the `perpetualtrading` branch into a fully-fledged, TradingView-style institutional terminal. The Deer Family will execute these steps autonomously, one at a time, running 24/7.

## The Vision
A Bloomberg-grade, dark-themed UI featuring a central candlestick chart, dynamic indicators, and a seamless bot-selector dropdown that connects frontend UI directly to the backend Python quantitative engines (including the 28d ONNX model).

---

## 🛠️ Phase 1: The UI Layout Grid (Deer Architect)
- **Objective:** Scaffold the CSS/React grid structure.
- **Components:**
  - **Left/Center:** Main charting container (reserved for the TradingView-style canvas).
  - **Right Panel:** Order entry slip & **Bot Selector Dropdown** (Manual vs. Nano-ONNX vs. Gold-ONNX).
  - **Bottom Panel:** Positions, Active Orders, and PnL table.
- **Agent Assigned:** `deer-architect`

## ⚙️ Phase 2: The Data Pipelines (Lead Deer)
- **Objective:** Establish the WebSocket streams for continuous data flow.
- **Components:**
  - OHLCV (Open, High, Low, Close, Volume) aggregator for the chart.
  - Active Funding Rate streamer.
  - Bot Status API (returns which bot is currently active).
- **Agent Assigned:** `lead-deer`

## 📈 Phase 3: The Indicator Engine (Deer Quant)
- **Objective:** Build the mathematical indicators that overlay on the chart.
- **Components:**
  - The Macro Shield (4H EMA).
  - The Exit Manager (ATR Trailing Stop).
  - The Cost-of-Time Suite (Funding Rate velocity).
- **Agent Assigned:** `deer-quant`

## 🎨 Phase 4: TradingView Canvas Implementation (Deer Architect)
- **Objective:** Bring the chart to life.
- **Components:**
  - Implement the HTML5 Canvas / lightweight charting module.
  - Render live candles.
  - Overlay Phase 3 indicators onto the visual chart.
- **Agent Assigned:** `deer-architect`

## 🧠 Phase 5: The Autonomous Bot Handshake (Deer Subagent)
- **Objective:** Connect the UI Bot Selector to the Python Engine.
- **Components:**
  - When the user selects "ONNX 28d" from the dropdown, the frontend sends a command to the backend to hot-swap the active trading engine.
- **Agent Assigned:** `deer-subagent`

---
*The Deer Family will execute this sequentially. As soon as one agent finishes a phase, the baton is passed to the next.*
