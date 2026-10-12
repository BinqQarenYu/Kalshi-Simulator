"""Chop Protection and Toxicity Veto Module for Domination Fleet."""

from typing import Optional, Tuple


def evaluate_chop_toxicity_veto(
    stage: str,
    vpin: float,
    target_prob: float,
    discount_price_val: float,
    target_ask: float,
    max_entry_price: float,
) -> Tuple[bool, Optional[str]]:
    """Evaluates whether VPIN toxicity or chop regime caps veto the proposed order.
    Returns (should_veto, rationale_string).
    """
    if stage == "twap_sniper":
        return False, None

    if vpin > 0.35:
        return True, f"VPIN Toxicity Veto (Hard Kill): Orderbook VPIN {vpin:.2f} > 0.35 toxic flow threshold. Suppressing entry."

    is_chop_regime = (vpin > 0.28) or (target_prob < 0.75)
    chop_max_cap = 0.48 if is_chop_regime else max_entry_price
    effective_order_price = (
        discount_price_val
        if (target_ask > discount_price_val and stage != "initial_10s_maker_park")
        else target_ask
    )
    if effective_order_price > chop_max_cap:
        regime_name = "Chop Regime ($0.48)" if is_chop_regime else f"Max Cap (${max_entry_price:.2f})"
        return (
            True,
            f"Price Cap Veto ({regime_name}): Proposed entry ${effective_order_price:.2f} "
            f"> ${chop_max_cap:.2f} allowable limit. Refusing adverse fill in "
            f"{'choppy/low-conviction' if is_chop_regime else 'standard'} market.",
        )

    return False, None
