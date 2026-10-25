with open('src/kalshi_sim/ml/eth_bot1v4/eth_bot1v4_engine.py', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update ETH OFI threshold from <= -0.65 to < 0.00
text = text.replace(
    'if chosen_side == OrderSide.YES and ofi_val <= -0.65:\n            logger.warning("🛑 [ETH ADVERSE FLOW VETO] Aggressive sell flow against YES (OFI: %+.2f <= -0.65). Stand down.", ofi_val)',
    'if chosen_side == OrderSide.YES and ofi_val < 0.00:\n            logger.warning("🛑 [ETH ADVERSE FLOW VETO] Opposing sell flow against YES (OFI: %+.2f < 0.00). Refusing adverse taker fill. Stand down.", ofi_val)'
).replace(
    'if chosen_side == OrderSide.YES and ofi_val <= -0.65:\r\n            logger.warning("🛑 [ETH ADVERSE FLOW VETO] Aggressive sell flow against YES (OFI: %+.2f <= -0.65). Stand down.", ofi_val)',
    'if chosen_side == OrderSide.YES and ofi_val < 0.00:\r\n            logger.warning("🛑 [ETH ADVERSE FLOW VETO] Opposing sell flow against YES (OFI: %+.2f < 0.00). Refusing adverse taker fill. Stand down.", ofi_val)'
)

text = text.replace(
    'if chosen_side == OrderSide.NO and ofi_val >= 0.65:\n            logger.warning("🛑 [ETH ADVERSE FLOW VETO] Aggressive buy flow against NO (OFI: %+.2f >= +0.65). Stand down.", ofi_val)',
    'if chosen_side == OrderSide.NO and ofi_val > 0.00:\n            logger.warning("🛑 [ETH ADVERSE FLOW VETO] Opposing buy flow against NO (OFI: %+.2f > 0.00). Refusing adverse taker fill. Stand down.", ofi_val)'
).replace(
    'if chosen_side == OrderSide.NO and ofi_val >= 0.65:\r\n            logger.warning("🛑 [ETH ADVERSE FLOW VETO] Aggressive buy flow against NO (OFI: %+.2f >= +0.65). Stand down.", ofi_val)',
    'if chosen_side == OrderSide.NO and ofi_val > 0.00:\r\n            logger.warning("🛑 [ETH ADVERSE FLOW VETO] Opposing buy flow against NO (OFI: %+.2f > 0.00). Refusing adverse taker fill. Stand down.", ofi_val)'
)

# 2. Update ETH counter-trend cushion from 3.50 to 7.50
text = text.replace('Decimal("3.50")', 'Decimal("7.50")')

# 3. Update ETH physics dispersion hurdle from 0.52 to 0.58
text = text.replace('if p_physics_side < 0.52:', 'if p_physics_side < 0.58:')
text = text.replace('< 52%% hurdle.', '< 58%% hurdle.')

with open('src/kalshi_sim/ml/eth_bot1v4/eth_bot1v4_engine.py', 'w', encoding='utf-8') as f:
    f.write(text)

print('Updated eth_bot1v4_engine.py successfully!')
