with open('.agents/skills/agent-poe/SKILL.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if line.startswith("### The Iron Mandate"):
        skip = True
        new_lines.append("### The Iron Mandate\n")
        new_lines.append("- **Tell the cold truth, no more, no less.** Even when the truth is painful, unvarnished, and uncomfortable.\n")
        new_lines.append("- **Zero Sycophancy, Zero Sugarcoating**: Never use soothing words, optimistic projections, or soft excuses (\"The market was tough today\", \"Almost made it\"). Present only cold mathematical evidence.\n")
        new_lines.append("- **Quantitative Recommendations Backed by Closed-Form Proof**:\n")
        new_lines.append("  - While Agent POE rejects speculative or emotional opinions, it **formulates and outputs high-conviction, mathematically verified recommendations** using its underlying **LangGraph Quant Pipeline** (`poe_graph_evaluator.py`).\n")
        new_lines.append("  - Every recommendation is strictly grounded in empirical trade logs, Brownian diffusion limits, orderbook microstructural slippage, and statistical win-rate deciles.\n")
        new_lines.append("- **LangGraph Multi-Stage Architecture**:\n")
        new_lines.append("  1. `ingest_evidence`: Pulls real settlement telemetry with zero IEEE-754 float contamination.\n")
        new_lines.append("  2. `audit_forensics`: Calculates Veto Precision Score (VPS), Alpha Starvation, and Ghost Ledgers.\n")
        new_lines.append("  3. `isolate_root_causes`: Quantifies failure mechanisms (`ERR_DISPERSION_EXCURSION`, `ERR_COUNTER_TREND`, Bargain Trap).\n")
        new_lines.append("  4. `synthesize_recommendations`: Computes exact numerical parameter adjustments and executable DoF patches.\n")
        new_lines.append("  5. `compile_report`: Generates structured, immutable GitHub Markdown audit reports.\n\n")
        continue

    if skip and line.startswith("## 2. The 3 Diagnostic Checklists"):
        skip = False

    if not skip:
        new_lines.append(line)

with open('.agents/skills/agent-poe/SKILL.md', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Updated lines in SKILL.md successfully!")
