from pathlib import Path

fpath = Path("src/kalshi_sim/routers/strategies.py")
text = fpath.read_text(encoding="utf-8")

old_code = '''    if state.guardrails_agent:
        state.guardrails_agent.reset_circuit_breaker(cur_bal)'''

new_code = '''    if state.guardrails_agent:
        state.guardrails_agent.reset_circuit_breaker(cur_bal)

    # Reset Bot 1 V4 and ETH Bot 1 V4 wave classifiers out of BLEED into STORM
    for bot_attr in ["bot1_v4_engine", "eth_bot1_v4_engine"]:
        bot_inst = getattr(state, bot_attr, None)
        if bot_inst and hasattr(bot_inst, "wave_classifier"):
            bot_inst.wave_classifier.reset("Circuit breaker reset")
            if hasattr(bot_inst, "healing_protocol"):
                bot_inst.healing_protocol.is_active = False
                bot_inst.healing_protocol.consecutive_wins = 0'''

if old_code in text:
    text = text.replace(old_code, new_code, 1)
    fpath.write_text(text, encoding="utf-8")
    print("SUCCESS: Patched reset_circuit_breaker in strategies.py")
else:
    print("Target not found in strategies.py")
