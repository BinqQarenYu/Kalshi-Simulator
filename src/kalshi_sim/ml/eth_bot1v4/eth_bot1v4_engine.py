"""ETH‑specific Bot 1 V4 wrapper.

This module provides `EthBot1V4Engine`, which re‑uses the existing
`Bot1V4DominationEngine` implementation but forces the underlying
asset ticker to "ETH". It also creates a **separate** `ContinuousExperienceBuffer`
instance that persists to its own JSON file (`data/eth_win_loss_reports.json`).
All other logic (ONNX inference, HMM, statistical EV, etc.) remains unchanged.
"""

from pathlib import Path
from kalshi_sim.ml.bot1_v4_engine import Bot1V4DominationEngine
from kalshi_sim.ml.experience_buffer import ContinuousExperienceBuffer


class EthBot1V4Engine(Bot1V4DominationEngine):
    """Identical to Bot1V4DominationEngine but operates on ETH markets.

    The constructor ensures:
    * ``asset`` is set to ``"ETH"`` (or the corresponding ``CryptoAsset``).
    * A dedicated ``ContinuousExperienceBuffer`` writes to
      ``data/eth_win_loss_reports.json`` so its learning is isolated from the
      BTC bot.
    """

    def __init__(self, *args, **kwargs):
        # Force the ticker / asset to ETH.
        kwargs.setdefault("ticker", "ETH")
        kwargs.setdefault("asset", "ETH")
        # Provide a dedicated experience buffer if the caller did not supply one.
        if "experience_buffer" not in kwargs or kwargs["experience_buffer"] is None:
            # Store ETH experience separately from the default BTC buffer.
            buffer_path = Path("data/eth_win_loss_reports.json")
            kwargs["experience_buffer"] = ContinuousExperienceBuffer(
                history_file=buffer_path
            )
        super().__init__(*args, **kwargs)
