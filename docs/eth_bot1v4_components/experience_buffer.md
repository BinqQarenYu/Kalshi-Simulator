# `ContinuousExperienceBuffer` (ETH)

**Location:** `src/kalshi_sim/ml/continuous_experience.py`

The ETH version re‑uses the same implementation as the BTC bot but receives asset‑specific configuration via `get_asset_config(CryptoAsset.ETH)`. It stores recent market observations (spot price, volatility, VPIN, etc.) and provides:

- **Quadrant mistake pruning** against the empirical loss matrix.
- **Online Platt‑Sigmoid calibration** of the ONNX confidence.
- **Dynamic scaling of the `min_spot_diff` guard** using live ETH volatility (see `lead_deer_quant_brain`).

All monetary calculations inside the buffer use `decimal.Decimal` in compliance with the Zero‑Float rule.
