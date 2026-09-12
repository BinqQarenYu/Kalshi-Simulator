import math
import sys

def black_scholes_binary_call(S, K, T, sigma):
    if T <= 0: return 1.0 if S > K else 0.0
    d2 = (math.log(S / K)) / (sigma * math.sqrt(T))
    return 0.5 * (1.0 + math.erf(d2 / math.sqrt(2.0)))

S = 0.1000
vol_annual = 0.60  # 60% annualized
sigma_1m = vol_annual / math.sqrt(365 * 24 * 60)
print(f"1m volatility approx: {S * sigma_1m:.6f}")

diffs = [0.0001, 0.0002, 0.0003, 0.0004, 0.0005, 0.0008, 0.0010]
T_15m = 15.0 / (365*24*60)
T_7m = 7.5 / (365*24*60)

print("At Mid-Cycle (7.5 mins left):")
for diff in diffs:
    prob = black_scholes_binary_call(S + diff, S, T_7m, vol_annual)
    print(f"Diff: {diff:.4f} -> Prob: {prob*100:.1f}%")
