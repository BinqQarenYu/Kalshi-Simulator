# Script to update affected documentation files with POE & Council upgrades

files_to_update = [
    'docs/02_TRADING_SYSTEM/BOT1_V4_SPECIFICATION.md',
    'docs/02_TRADING_SYSTEM/ETH_DOMINATION_SPECIFICATION.md',
    'docs/03_AGENTS/AGENT_REGISTRY.md'
]

# 1. Update BOT1_V4_SPECIFICATION.md
with open('docs/02_TRADING_SYSTEM/BOT1_V4_SPECIFICATION.md', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    '        F5["Asset Isolation Gate: Reject non-BTC symbols"]\n    end',
    '        F5["Asset Isolation Gate: Reject non-BTC symbols"]\n        F6["Adverse Selection OFI Shield: Veto if OFI < 0.00 opposing"]\n        F7["Macro-Trend Cushion: Diff >= $65.00 if counter-trend"]\n        F8["Physics Dispersion Gate: P(Physics) >= 58.0%"]\n    end'
).replace(
    '        F5["Asset Isolation Gate: Reject non-BTC symbols"]\r\n    end',
    '        F5["Asset Isolation Gate: Reject non-BTC symbols"]\r\n        F6["Adverse Selection OFI Shield: Veto if OFI < 0.00 opposing"]\r\n        F7["Macro-Trend Cushion: Diff >= $65.00 if counter-trend"]\r\n        F8["Physics Dispersion Gate: P(Physics) >= 58.0%"]\r\n    end'
)
with open('docs/02_TRADING_SYSTEM/BOT1_V4_SPECIFICATION.md', 'w', encoding='utf-8') as f:
    f.write(text)

# 2. Update ETH_DOMINATION_SPECIFICATION.md
with open('docs/02_TRADING_SYSTEM/ETH_DOMINATION_SPECIFICATION.md', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    '        Iso["Asset Isolation: Reject any non-ETH contract"]\n    end',
    '        Iso["Asset Isolation: Reject any non-ETH contract"]\n        OFI_Shield["Adverse Selection OFI Shield: Veto if OFI < 0.00 opposing"]\n        Trend_Cushion["Macro-Trend Cushion: Diff >= $7.50 if counter-trend"]\n        Physics_Gate["Physics Dispersion Gate: P(Physics) >= 58.0%"]\n    end'
).replace(
    '        Iso["Asset Isolation: Reject any non-ETH contract"]\r\n    end',
    '        Iso["Asset Isolation: Reject any non-ETH contract"]\r\n        OFI_Shield["Adverse Selection OFI Shield: Veto if OFI < 0.00 opposing"]\r\n        Trend_Cushion["Macro-Trend Cushion: Diff >= $7.50 if counter-trend"]\r\n        Physics_Gate["Physics Dispersion Gate: P(Physics) >= 58.0%"]\r\n    end'
)
with open('docs/02_TRADING_SYSTEM/ETH_DOMINATION_SPECIFICATION.md', 'w', encoding='utf-8') as f:
    f.write(text)

# 3. Update AGENT_REGISTRY.md (Agent POE entry)
with open('docs/03_AGENTS/AGENT_REGISTRY.md', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace(
    '### 2.12 Agent POE (Post-Occupancy Evaluator)\n- **Primary Source:** [`.agents/skills/agent-poe/SKILL.md`](file:///.agents/skills/agent-poe/SKILL.md)\n- **Why do I exist?** To serve as the cold, unvarnished empirical truth auditor of the codebase and system operations.',
    '### 2.12 Agent POE (Post-Occupancy Evaluator & LangGraph Quant Engine)\n- **Primary Source:** [`.agents/skills/agent-poe/SKILL.md`](file:///.agents/skills/agent-poe/SKILL.md), [`src/kalshi_sim/ml/poe_graph_evaluator.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/poe_graph_evaluator.py)\n- **Why do I exist?** To serve as the cold empirical truth auditor and quantitative reasoning engine, executing a 5-stage LangGraph workflow to isolate failure mechanisms and compute closed-form parameter calibrations.'
).replace(
    '### 2.12 Agent POE (Post-Occupancy Evaluator)\r\n- **Primary Source:** [`.agents/skills/agent-poe/SKILL.md`](file:///.agents/skills/agent-poe/SKILL.md)\r\n- **Why do I exist?** To serve as the cold, unvarnished empirical truth auditor of the codebase and system operations.',
    '### 2.12 Agent POE (Post-Occupancy Evaluator & LangGraph Quant Engine)\r\n- **Primary Source:** [`.agents/skills/agent-poe/SKILL.md`](file:///.agents/skills/agent-poe/SKILL.md), [`src/kalshi_sim/ml/poe_graph_evaluator.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/poe_graph_evaluator.py)\r\n- **Why do I exist?** To serve as the cold empirical truth auditor and quantitative reasoning engine, executing a 5-stage LangGraph workflow to isolate failure mechanisms and compute closed-form parameter calibrations.'
)
with open('docs/03_AGENTS/AGENT_REGISTRY.md', 'w', encoding='utf-8') as f:
    f.write(text)

print("Documentation files successfully updated!")
