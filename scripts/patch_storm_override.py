with open('src/kalshi_sim/ml/session_timing_guard.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = """        is_storm = "STORM" in regime_upper or "VOLCANO" in regime_upper
        is_massive_breakout = diff_val >= Decimal("10.00") or diff_val >= Decimal("85.00")
        if is_storm and is_massive_breakout:"""

new_block = """        is_storm = "STORM" in regime_upper or "VOLCANO" in regime_upper
        is_massive_breakout = diff_val >= Decimal("3.00") or diff_val >= Decimal("35.00")
        if is_storm and is_massive_breakout:"""

if old_block in content:
    content = content.replace(old_block, new_block, 1)
    with open('src/kalshi_sim/ml/session_timing_guard.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: Updated session_timing_guard.py storm breakout threshold to $35 BTC / $3 ETH")
else:
    print("FAILED: old_block not found in session_timing_guard.py")
