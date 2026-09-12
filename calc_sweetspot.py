import math
from scipy.stats import norm

vol = 14.0
print("=== THE SWEET SPOT MATRIX (Target Prob: 60% - 70%) ===")
print("Time Left | Req Diff for 60% | Req Diff for 70% | Target Market Ask")
for t in [14, 10, 7.5, 5, 3, 1]:
    noise = vol * math.sqrt(t)
    diff_60 = norm.ppf(0.60) * noise
    diff_70 = norm.ppf(0.70) * noise
    print(f"{t:04.1f}m     | ${diff_60:5.2f}           | ${diff_70:5.2f}           | $0.60 - $0.70")
