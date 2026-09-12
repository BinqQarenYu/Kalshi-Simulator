# Institutional Bot Iteration Chronicle & Architectural Archive

**Curated by**: Quoquo (Desk Librarian & Archivist)  
**Repository**: `Kalshi-Simulator`  
**Master Archive Path**: `data/archives/BOT_ITERATIONS_MASTER_CHRONICLE.md`  
**Registry JSON**: `data/archives/bot_iterations_registry.json`  
**Timestamp**: 2026-09-12 08:29:00 UTC  

---

## 1. Architectural Evolution of Bot 1 (3-Step Domination Bot)

Bot 1 (`ThreeStepDominationBot`) is the sole algorithm authorized to route live orders on Lane 1 under the **Micro-Bankroll 1-Contract Armor**. Over its development lifecycle, it has evolved through **5 distinct iterations**:

```
[ v1.0: Static Normal CDF ] ➔ Mistook opening noise (+-$35) for breakout (90.4% of losses)
           │
           ▼
[ v2.0: Multi-Asset Moats ] ➔ Dynamic volatility scaling (BTC, ETH, SOL, DOGE, GOLD, HYPER)
           │
           ▼
[ v3.0: Profit Harvesting ] ➔ 92¢/95¢ Take-Profit, Trailing Ratchet, Dynamic Reversal Curve
           │
           ▼
[ v4.0: Discount Sniper ]   ➔ 48¢-52¢ sweetspot maker limits, 1-contract armor, $0 fee
           │
           ▼
[ v5.0: Anti-Breakout Triad ] ➔ 90s Opening Quarantine + Brain 1 ONNX Microstructure Veto (74.7% WR)
```

---

### Iteration Comparative Matrix

| Iteration | Version Tag | Core Innovation | Strengths | Failure Mode / Flaw Identified | Empirical Win Rate | Net PnL |
| :--- | :--- | :--- | :--- | :--- | :---: | :---: |
| **v1.0** | `v1.0-static-normal-cdf` | $z = \frac{S_t - K}{\sigma\sqrt{\tau}}$, $\Phi(z)$ | Sub-millisecond math, continuous CDF | Opening noise trap at $T > 13.5\text{m}$ (66/73 losses) | 58.5% | +$5.68 |
| **v2.0** | `v2.0-multi-asset-dynamic-moats` | Continuous dynamic proximity moats | Self-calibrating across assets | News blackout slippage on Gold | 63.0% | +$40.68 |
| **v3.0** | `v3.0-profit-harvesting-suite` | 92¢ TP, Trailing Ratchet, Reversal Curve | Salvaged +28.5% winning runs | Only handled exits, didn't block bad entries | 64.4% | +$45.20 |
| **v4.0** | `v4.0-discount-sniper-maker-armor` | 48¢–52¢ maker limits, 1-contract armor | $0.00 maker fees, capital armor ($17.49 preserved) | Maker limits left resting when spot moves fast | 64.4% | +$45.20 |
| **v5.0** | `v5.0-anti-breakout-triad` | 90s Quarantine + Brain 1 ONNX Veto | Blocks 80% false breakouts, cuts churn 64% | Slightly fewer trades, but institutional edge | **74.7%** | **+$39.52** |

---

### Deep-Dive: What Was Good & Bad in Each Iteration

#### Iteration 1: Static Parametric CDF Breakout (`v1.0`)
- **What Was Good**: Ultra-fast execution, zero neural dependencies, clean mathematical foundation for pricing digital binary options.
- **The Fatal Flaw**: Mistook opening 60-second Brownian noise ($\pm \$35$) for structural breakouts ($T_{\text{rem}} > 13.5\text{m}$). At $T=13.5\text{m}$, $\sigma\sqrt{T} \approx \$51$, so a $\$35$ move produced $P(\text{NO}) = 81\%$. It rushed to enter within 60 seconds of cycle open, and 2 minutes later spot bounced $+\$40$, causing 66 out of 73 total Playbook 1 losses!

#### Iteration 2: Multi-Asset Basket & Volatility Moats (`v2.0`)
- **What Was Good**: Replaced rigid dollar thresholds with continuous self-calibrating moats:
  $$\text{moat} = \text{clamp}(1.15 \times \text{min\_diff}, z_{\text{asset}} \cdot \sigma_{\text{live}} \cdot \sqrt{\tau}, 2.15 \times \text{min\_diff})$$
  This allowed seamless switching between Bitcoin, Ethereum, Solana, Doge, Gold, and Hyperliquid without manual reconfiguration.
- **The Fatal Flaw**: High-volatility news events (e.g. US economic data releases) caused Gold and Bitcoin to violently whip through the wider moats.

#### Iteration 3: Full Capital Defense & Profit Harvesting (`v3.0`)
- **What Was Good**:
  - **Take-Profit Ceiling (92¢–95¢)**: Harvested profit before late-cycle binary gamma cliffs.
  - **Trailing Ratchet**: Locked in gains with an 8¢–10¢ trailing buffer below the high-water mark bid.
  - **Dynamic Reversal Curve**: Decayed required exit conviction from 85% down to 50% as $\tau \to 0$, ensuring the bot doesn't stubbornly hold a reversing contract into expiration.
- **The Fatal Flaw**: It was purely an *exit* mechanism. It rescued bad trades after they occurred, but did not prevent the bad entries from being initiated.

#### Iteration 4: Discount Sniper & Micro-Bankroll Sizing Armor (`v4.0`)
- **What Was Good**:
  - Enforced maker resting limit entries at 48¢–52¢, guaranteeing $0.00 CFTC exchange fees.
  - Locked sizing to **strictly 1 contract** ($0.51 max risk per trade for bankrolls $<\$75$).
  - Successfully defended the desk during overnight adverse volatility: balance preserved at **$17.4948**.
- **The Fatal Flaw**: Did not address the timing of the entry; the bot was still placing 51¢ maker orders in the first 90 seconds of the cycle.

#### Iteration 5: The Anti-False Breakout Triad (`v5.0` — CURRENT LIVE)
- **What Was Good**:
  1. **Opening Cycle Discovery Quarantine Gate**: Enforces a strict 90-second blackout ceiling ($T_{\text{rem}} \le 810\text{s}$ for 15M; $T_{\text{rem}} \le 270\text{s}$ for 5M). Prohibits Playbook 1 from firing during opening noise.
  2. **Brain 1 (QuoLas ONNX) Microstructure Veto**: Ingests 28-dimensional orderflow tensor (OFI Levels 1/5/15, CVD, VPIN PBC, Bid/Ask Absorption). Blocks any breakout where Brain 1 signals `WAIT` or opposes the trade direction.
  - **Empirical Backtest Proof**: Eliminates **66 false breakout losses**, raises win rate from **64.4% to 74.7%**, and vetoed 80.0% of historical losses in tick-by-tick orderbook replay!

---

## 2. Status of Peer Bots (Bot 2 & Bot 3)

### Bot 2: Kalshi Microstructure Brain (`KalshiBrainBot`)
- **Lane**: Lane 3 (Simulation & Research).
- **Core Specialization**: Exploits internal Kalshi CLOB order book skew, retail flow toxicity, and passive limit book positioning.
- **Status**: Incubating. Zero capital risk.

### Bot 3: Standalone Macro HMM Bot (`StandaloneMacroEngine`)
- **Lane**: Lane 2 (Shadow Incubator on Port 8003).
- **Core Specialization**: 4-State Gaussian Hidden Markov Model (HMM) tracking Bull Trend, Bear Trend, Chop, and High Volatility regimes across 5-minute rolling candles.
- **Overnight Performance**: Detected macro range-bound chop and held fire 100% of the time, preserving **$250.00 paper equity** with zero bad trades.

---

## 3. How to Use This Archive in Future Iterations

When formulating new strategy upgrades or diagnosing performance:
1. **Never Reinvent Failed Patterns**: Review the failure modes of previous iterations (e.g., never remove the 90s opening quarantine or allow entries at $T > 13.5\text{m}$).
2. **Consult Parameter Baselines**: Read `data/archives/bot_iterations_registry.json` for verified sweetspots and threshold dials.
3. **Continuous Archiving**: Every new strategy milestone must be logged in this chronicle by Quoquo before deployment.
