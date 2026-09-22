from decimal import Decimal
from typing import List, Optional

def calculate_ema(prices: List[Decimal], period: int = 4) -> List[Optional[Decimal]]:
    """
    Calculate the Exponential Moving Average (EMA).
    Returns a list of EMA values corresponding to the prices.
    """
    if not prices or period <= 0:
        return []
        
    emas: List[Optional[Decimal]] = []
    multiplier = Decimal('2') / Decimal(str(period + 1))
    
    current_ema: Optional[Decimal] = None
    
    for i, price in enumerate(prices):
        if i < period - 1:
            emas.append(None)
            if i == period - 2:
                # Calculate SMA for the first 'period' elements to seed the EMA
                current_ema = sum(prices[:period]) / Decimal(str(period))
        elif i == period - 1:
            if current_ema is None:
                current_ema = sum(prices[:period]) / Decimal(str(period))
            emas.append(current_ema)
        else:
            if current_ema is not None:
                current_ema = (price - current_ema) * multiplier + current_ema
                emas.append(current_ema)
            
    # If the list is shorter than the period, just fallback to simpler logic or return Nones
    if len(prices) < period:
        # Fill with Nones if less than period, which is already done
        pass
        
    return emas

def calculate_atr(highs: List[Decimal], lows: List[Decimal], closes: List[Decimal], period: int = 14) -> List[Optional[Decimal]]:
    """
    Calculate the Average True Range (ATR).
    """
    if not (len(highs) == len(lows) == len(closes)) or period <= 0 or not highs:
        return []
        
    trs: List[Decimal] = []
    for i in range(len(highs)):
        if i == 0:
            tr = highs[i] - lows[i]
        else:
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
        trs.append(tr)
        
    atrs: List[Optional[Decimal]] = []
    current_atr: Optional[Decimal] = None
    
    for i, tr in enumerate(trs):
        if i < period - 1:
            atrs.append(None)
        elif i == period - 1:
            # First ATR is SMA of TRs
            current_atr = sum(trs[:period]) / Decimal(str(period))
            atrs.append(current_atr)
        else:
            if current_atr is not None:
                # Wilder's smoothing
                current_atr = (current_atr * Decimal(str(period - 1)) + tr) / Decimal(str(period))
                atrs.append(current_atr)
            
    return atrs

def calculate_funding_velocity(funding_rates: List[Decimal]) -> List[Optional[Decimal]]:
    """
    Calculate the velocity (rate of change) of funding rates.
    """
    if not funding_rates:
        return []
        
    velocities: List[Optional[Decimal]] = [None]
    for i in range(1, len(funding_rates)):
        velocities.append(funding_rates[i] - funding_rates[i-1])
        
    return velocities
