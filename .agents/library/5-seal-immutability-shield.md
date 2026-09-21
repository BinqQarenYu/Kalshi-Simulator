---
trigger: always_on:glob: "**/*"
description: Cryptographic Seal of Excellence Immutability Shield — protects certified bots from unauthorized modifications.
---

# 5. Cryptographic Seal of Excellence Immutability Shield

## 1. Core Principle: Sealed Code is Read-Only by Default
Any trading strategy that possesses an automated SHA-256 **Seal of Excellence** on disk (`data/seal_of_excellence.json`):
- **Currently Sealed Roster**: **Bot 1 (`3_step_domination_bot`)** and **Bot 3 (`macro_trend_dominion`)**.
- **The Invariant**: All frontend UI components, backend trading logic, risk guardrails, mathematical formulas, and parameter configurations belonging to a sealed bot are **STRICTLY PROTECTED & FROZEN**.
- **Zero Autonomous Modifications**: No AI assistant, background subagent (Lead Deer, Jules, Antigravity, or Ollama) may edit, refactor, reorganize, optimize, or reset code or parameters for a sealed bot without **explicit, affirmative user authorization in the current conversation turn**.

---

## 2. Protected File Boundaries

The following files and component slices are under **Seal Immutability Lock**:

### Backend Engine & Parameters:
- `src/kalshi_sim/ml/domination_bot.py` (Bot 1 Strategy Engine)
- `src/kalshi_sim/ml/macro_trend_dominion_bot.py` (Bot 3 Strategy Engine)
- `data/bot_parameters_domination.json` (Bot 1 Parameter Profiles)
- `data/seal_of_excellence.json` (Cryptographic Seal Ledger)

### Frontend Dedicated UI Slices:
- In `frontend/src/components/BabyBotConsole.tsx`:
  - Bot 1 Slider Cockpit & Winning Presets (`35«`, `48£`, `�1ª`, `52«`)
  - Bot 3 Triple-Brain Cockpit (Dials 1–9)
  - Bot 1 & Bot 3 default parameter state and reset handlers

---

## 3. The Revision Unlock Protocol (Explicit User Authorization Required)
An AI agent may ONLY touch or revise sealed bot code or parameters if:
1. **Explicit Request**: The user explicitly states an affirmative instruction targeting that sealed bot (e.g. *\v"revise Bot 1\"*, *\v"unlock Bot 1 to change X\"*, *\v"update winning parameters for Bot 1\"*).
2. **Minimal & Targeted Diff**: The edit must be strictly confined to what the user explicitly requested. Unsolicited refactoring or secondary file churn is prohibited.
3. **ASVL Verification**: Any authorized revision must immediately pass:
   - `python -m pytest tests/test_domination_bot.py -v` (for Bot 1)
   - `python -m pytest tests/test_macro_trend_dominion.py -v` (for Bot 3)
   - `cd frontend && npm run typecheck && npm run build`
