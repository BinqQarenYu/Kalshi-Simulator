"""Zero-Float Financial Math Operations.

Strictly enforces decimal.Decimal math for all monetary, probability,
and contract fee calculations in accordance with Law 1 (AGENTS.md).
"""

from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from typing import Union


def to_decimal(val: Union[Decimal, str, int]) -> Decimal:
    """Safely convert numerical input to Decimal without floating-point artifacts."""
    if isinstance(val, Decimal):
        return val
    if isinstance(val, (str, int)):
        return Decimal(str(val))
    raise TypeError(f"Disallowed IEEE-754 floating-point type: {type(val)}. Use Decimal, str, or int.")


def calculate_kalshi_taker_fee(contracts: Union[Decimal, int], price_prob: Union[Decimal, str]) -> Decimal:
    """Calculate Kalshi taker fee using the quadratic schedule rounded UP to the nearest cent:
    
    Fee = ceil(0.07 * C * P * (1 - P))
    
    Args:
        contracts: Number of contracts (Decimal or int).
        price_prob: Contract price in probability terms (0.01 to 0.99).
        
    Returns:
        Fee in USD as Decimal.
    """
    c = to_decimal(contracts)
    p = to_decimal(price_prob)
    
    multiplier = Decimal("0.07")
    one = Decimal("1.00")
    
    # Quadratic formula: 0.07 * C * P * (1 - P)
    raw_fee = multiplier * c * p * (one - p)
    
    # Round CEILING to nearest cent ($0.01)
    fee_cents = (raw_fee * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_CEILING)
    return fee_cents / Decimal("100")


def calculate_binary_net_ev(
    p_win: Union[Decimal, str],
    cost_price: Union[Decimal, str],
    taker_fee: Union[Decimal, str] = Decimal("0")
) -> Decimal:
    """Calculate net Expected Value of a binary contract payoff:
    
    EV = P_win * ($1.00 - cost) - (1 - P_win) * cost - fee
    
    Args:
        p_win: True model probability of winning (0.00 to 1.00).
        cost_price: Price paid per contract (0.01 to 0.99).
        taker_fee: Total taker fee per contract.
        
    Returns:
        Net EV in USD per contract.
    """
    p = to_decimal(p_win)
    cost = to_decimal(cost_price)
    fee = to_decimal(taker_fee)
    one = Decimal("1.00")
    
    win_payout = (one - cost)
    loss_amount = cost
    
    gross_ev = (p * win_payout) - ((one - p) * loss_amount)
    net_ev = gross_ev - fee
    return net_ev.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def decimal_to_cents(usd_amount: Union[Decimal, str]) -> int:
    """Convert USD Decimal amount to integer cents."""
    d = to_decimal(usd_amount)
    return int((d * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def cents_to_decimal(cents: int) -> Decimal:
    """Convert integer cents to USD Decimal with 2 decimal places."""
    return (Decimal(cents) / Decimal("100")).quantize(Decimal("0.01"))
