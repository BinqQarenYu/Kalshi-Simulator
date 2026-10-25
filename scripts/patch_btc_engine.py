with open('src/kalshi_sim/ml/btc_bot1v4/btc_bot1v4_engine.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update BTC OFI threshold from <= -0.65 to < 0.00
text = text.replace(
    'if chosen_side == OrderSide.YES and ofi_val <= -0.65:\n            logger.warning("🛑 [BTC ADVERSE FLOW VETO] Aggressive sell flow against YES (OFI: %+.2f <= -0.65). Stand down.", ofi_val)',
    'if chosen_side == OrderSide.YES and ofi_val < 0.00:\n            logger.warning("🛑 [BTC ADVERSE FLOW VETO] Opposing sell flow against YES (OFI: %+.2f < 0.00). Refusing adverse taker fill. Stand down.", ofi_val)'
).replace(
    'if chosen_side == OrderSide.YES and ofi_val <= -0.65:\r\n            logger.warning("🛑 [BTC ADVERSE FLOW VETO] Aggressive sell flow against YES (OFI: %+.2f <= -0.65). Stand down.", ofi_val)',
    'if chosen_side == OrderSide.YES and ofi_val < 0.00:\r\n            logger.warning("🛑 [BTC ADVERSE FLOW VETO] Opposing sell flow against YES (OFI: %+.2f < 0.00). Refusing adverse taker fill. Stand down.", ofi_val)'
)

text = text.replace(
    'if chosen_side == OrderSide.NO and ofi_val >= 0.65:\n            logger.warning("🛑 [BTC ADVERSE FLOW VETO] Aggressive buy flow against NO (OFI: %+.2f >= +0.65). Stand down.", ofi_val)',
    'if chosen_side == OrderSide.NO and ofi_val > 0.00:\n            logger.warning("🛑 [BTC ADVERSE FLOW VETO] Opposing buy flow against NO (OFI: %+.2f > 0.00). Refusing adverse taker fill. Stand down.", ofi_val)'
).replace(
    'if chosen_side == OrderSide.NO and ofi_val >= 0.65:\r\n            logger.warning("🛑 [BTC ADVERSE FLOW VETO] Aggressive buy flow against NO (OFI: %+.2f >= +0.65). Stand down.", ofi_val)',
    'if chosen_side == OrderSide.NO and ofi_val > 0.00:\r\n            logger.warning("🛑 [BTC ADVERSE FLOW VETO] Opposing buy flow against NO (OFI: %+.2f > 0.00). Refusing adverse taker fill. Stand down.", ofi_val)'
)

# 2. Update BTC counter-trend cushion from 50.00 to 65.00
text = text.replace(
    'if (spot_price - target_strike) < Decimal("50.00") or ofi_val < 0.20:',
    'if (spot_price - target_strike) < Decimal("65.00") or ofi_val < 0.20:'
)
text = text.replace(
    'if (target_strike - spot_price) < Decimal("50.00") or ofi_val > -0.20:',
    'if (target_strike - spot_price) < Decimal("65.00") or ofi_val > -0.20:'
)

# 3. Update BTC physics dispersion hurdle from 0.52 to 0.58
text = text.replace('if p_physics_side < 0.52:', 'if p_physics_side < 0.58:')
text = text.replace('< 52%% hurdle.', '< 58%% hurdle.')

with open('src/kalshi_sim/ml/btc_bot1v4/btc_bot1v4_engine.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Updated btc_bot1v4_engine.py successfully!')
