import re

with open('src/kalshi_sim/templates/pocket_cockpit.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Add CSS
css = """
    /* Tooltips */
    .info-icon {
      display: inline-flex; align-items: center; justify-content: center;
      width: 14px; height: 14px; border-radius: 50%;
      background: rgba(255,255,255,0.1); color: var(--muted);
      font-size: 0.6rem; font-weight: bold; cursor: help;
      margin-left: 4px; position: relative;
    }
    .info-icon:hover { background: var(--blue); color: #fff; }
    .info-icon .tooltip {
      visibility: hidden; width: 250px; background-color: #1e2230; color: #fff;
      text-align: left; border-radius: 6px; padding: 8px 10px;
      position: absolute; z-index: 100; bottom: 130%; left: 50%;
      transform: translateX(-50%); opacity: 0; transition: opacity 0.2s;
      font-size: 0.7rem; font-weight: normal; text-transform: none;
      box-shadow: 0 4px 12px rgba(0,0,0,0.5); border: 1px solid #334155;
    }
    .info-icon .tooltip::after {
      content: ""; position: absolute; top: 100%; left: 50%; margin-left: -5px;
      border-width: 5px; border-style: solid; border-color: #1e2230 transparent transparent transparent;
    }
    .info-icon:hover .tooltip { visibility: visible; opacity: 1; }
    .tooltip b { color: #38bdf8; display: block; margin-bottom: 2px; }
    .tooltip i { color: #94a3b8; display: block; margin-bottom: 4px; font-style: normal; }
"""
if "/* Tooltips */" not in html:
    html = html.replace("</style>", css + "\n  </style>")

# Define tooltips
tooltips = {
    "Discount Limit Price (Maker Ceiling)": "<b>The Beginner Translation:</b> <i>\"What is the absolute maximum price you are willing to pay?\"</i><br><b>How it works:</b> Places a 'lowball offer' below market value.<br><b>Why it matters:</b> Guarantees  Kalshi exchange fees and protects against sudden crashes.",
    "Max Contracts (Strict Invariant)": "<b>The Beginner Translation:</b> <i>\"Your bet size limit.\"</i><br><b>How it works:</b> Hard-coded safety lock capping you at 1 contract per trade.<br><b>Why it matters:</b> Prevents blowing up your micro-bankroll during losing streaks.",
    "Min Edge % (Statistical Alpha)": "<b>The Beginner Translation:</b> <i>\"How rigged must the game be before you play?\"</i><br><b>How it works:</b> Demands a mathematical advantage over the market price.<br><b>Why it matters:</b> A 6% edge means we only trade when we have a massive statistical advantage.",
    "Min Net EV ($/Contract)": "<b>The Beginner Translation:</b> <i>\"Minimum expected profit per trade.\"</i><br><b>How it works:</b> The average profit if you played this setup 1,000 times.<br><b>Why it matters:</b> Ignores trades that only yield pennies. Demands structural profit.",
    "Min Spot Distance (|Spot - Strike|)": "<b>The Beginner Translation:</b> <i>\"The Moat / Buffer Zone.\"</i><br><b>How it works:</b> Refuses trades when Bitcoin is hovering right on the strike line.<br><b>Why it matters:</b> Keeps you out of 50/50 coin-flip noise.",
    "VPIN Toxicity Veto": "<b>The Beginner Translation:</b> <i>\"The Shark Detector.\"</i><br><b>How it works:</b> Tracks if massive institutions are dumping/pumping Bitcoin right now.<br><b>Why it matters:</b> Instantly vetoes trades if a flash-crash is detected in the order flow.",
    "Take Profit Price Ceiling": "<b>The Beginner Translation:</b> <i>\"The Early Eject Button.\"</i><br><b>How it works:</b> Automatically sells the contract early if you are winning big.<br><b>Why it matters:</b> Cashes out guaranteed profit instead of risking everything for the final 5 pennies.",
    "Min Take Profit ROI %": "<b>The Beginner Translation:</b> <i>\"How much profit is good enough to leave early?\"</i><br><b>How it works:</b> Ensures you walk away with at least a 20% return on your investment.<br><b>Why it matters:</b> Stops the bot from panic-selling for a 1% profit."
}

for label_text, tooltip_html in tooltips.items():
    old_tag = f'<label class="param-label">{label_text}</label>'
    new_tag = f'<label class="param-label">{label_text} <div class="info-icon">i<div class="tooltip">{tooltip_html}</div></div></label>'
    html = html.replace(old_tag, new_tag)

with open('src/kalshi_sim/templates/pocket_cockpit.html', 'w', encoding='utf-8') as f:
    f.write(html)
