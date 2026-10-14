# `ContinuousExperienceBuffer` (ETH Domination Variant)

**Location:** [`src/kalshi_sim/ml/experience_buffer.py`](file:///f:/012D_TRADE/Kalshi%20Simulator/src/kalshi_sim/ml/experience_buffer.py)  
**Dedicated History Storage:** [`data/eth_win_loss_reports.json`](file:///f:/012D_TRADE/Kalshi%20Simulator/data/eth_win_loss_reports.json)  
**Associated Database:** [`data/kalshi_history_eth.db`](file:///f:/012D_TRADE/Kalshi%20Simulator/data/kalshi_history_eth.db)  

## Architectural Role
The ETH variant of `ContinuousExperienceBuffer` provides continuous online learning, causal loss attribution, and probability calibration specifically calibrated for Ethereum's market microstructure.

## Key Capabilities & ETH Adaptations
1. **Asset-Scaled Dynamic Thresholds:**
   - **Tight Spot Diff Threshold:** $\$2.00$ (prevents false `STRIKE_PROXIMITY_TRAP` attribution on normal ETH movements vs BTC's $\$25.00$).
   - **Mid Spot Diff Threshold:** $\$5.00$ (vs BTC's $\$50.00$).
   - **Momentum Inversion Threshold:** $\$6.00$ (vs BTC's $\$40.00$).
   - **Gamma Pin Threshold:** $\$1.50$ (vs BTC's $\$20.00$).
2. **3D Mistake Matrix Pruning:**
   - Evaluates historical loss clusters across `(Regime, Spot Diff Bucket, VPIN Bucket)`.
   - Vetoes trade recommendations if the corresponding quadrant records $\ge 3$ historical losses and $< 25\%$ win rate.
3. **Online Platt Sigmoid Recalibration:**
   - Dynamically sharpens model confidence slope ($\alpha$) and Brier calibration score after every settled cycle:
     $$\hat{P}_{\text{calibrated}} = \frac{1}{1 + \exp(-\alpha \cdot z)}$$
4. **Causal Mistake Classification:**
   - Integrated with Schema V5 `trade_failure_autopsies` to categorize losses into 7 standardized mistake codes (`ERR_TWAP_PIN_VICTIM`, `ERR_COUNTER_TREND`, `ERR_DOUBLE_WICK_TRAP`, `ERR_DOOMED_HOLD_TO_ZERO`, `STRIKE_PROXIMITY_TRAP`, `ADVERSE_SELECTION_SWEEP`, `ERR_DISPERSION_EXCURSION`).
5. **Zero Float Financial Math Compliance:**
   - All PnL, probability calculations, fees, and bankroll tracking strictly use `decimal.Decimal`.
