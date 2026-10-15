# src/kalshi_sim/ml/eth_bot1v4_engine.py
"""Ethereum‑specific Bot 1 V4 Domination Engine.

This module provides a thin wrapper around the generic :class:`Bot1V4DominationEngine`
implementation, configuring it for the ETH underlying asset. All core logic –
model fusion, regime routing, EV calculation, safety vetoes – lives in the
parent class. The wrapper merely supplies the appropriate ``CryptoAsset`` value
and allows downstream code to import a dedicated ETH engine without having to
specify the asset each time.

The implementation respects the **Zero‑Float Financial Math** law by using
``decimal.Decimal`` for all monetary parameters.
"""

from __future__ import annotations

from decimal import Decimal

from kalshi_sim.ml.bot1_v4_engine import Bot1V4DominationEngine
from kalshi_sim.schemas import CryptoAsset


class EthBot1V4Engine(Bot1V4DominationEngine):
    """Ethereum‑specific configuration of :class:`Bot1V4DominationEngine`.

    The constructor mirrors the signature of the base class but defaults the
    ``asset`` argument to :class:`~kalshi_sim.schemas.CryptoAsset.ETH`.  All other
    parameters retain their default values, which are automatically tuned to the
    ETH asset via the central ``AssetConfig`` table in ``schemas.py``.
    """

    def __init__(
        self,
        max_turnover_per_event: int = 1,
        min_ev_hurdle_dollars: Decimal = Decimal("0.02"),
        discount_limit_price: Decimal = Decimal("0.52"),
        min_edge_pct: float = 0.015,
        vpin_toxic_threshold: float = 0.35,
        vpin_safe_threshold: float = 0.28,
        default_btc_1m_volatility: float = 14.0,
        take_profit_price_threshold: Decimal = Decimal("0.92"),
        enable_take_profit_ceiling: bool = True,
        require_reversal_for_tp_ceiling: bool = True,
        enable_reverse_take_profit_roi: bool = True,
        reverse_indicator_threshold: float = 0.85,
        min_take_profit_roi: float = 0.40,
        maker_entry_timeout_seconds: float = 45.0,
        late_cycle_roi: float = 0.15,
        fee_per_contract: Decimal = Decimal("0.01"),
        min_spot_diff: float | None = None,
        max_entry_price: Decimal = Decimal("0.55"),
        min_confidence: float = 0.81,
        enable_trailing_ratchet: bool = True,
        trailing_ratchet_buffer: Decimal = Decimal("0.08"),
        spot_delta_front_run_threshold: float = 28.0,
        enable_dynamic_spot_velocity: bool = True,
        velocity_z_score_threshold: float = 2.50,
        reentry_cooldown_seconds: float = 15.0,
        enable_doubt_harvest: bool = True,
        doubt_threshold: float = 0.80,
        upside_capture_ratio_threshold: float = 0.50,
        asymmetric_peak_bid: Decimal = Decimal("0.75"),
        onnx_engine: object | None = None,
        fusion_weight_micro: float = 0.40,
        opening_quarantine_seconds: float = 90.0,
        max_clob_spread_cents: float = 0.05,
        moneyness_moat_multiplier: float = 1.36,
        # ETH‑specific warrior parameters – retain BTC defaults where appropriate
        chop_discount_limit_price: Decimal = Decimal("0.38"),
        chop_max_entry_price: Decimal = Decimal("0.42"),
        chop_min_time_s: float = 150.0,
        chop_max_time_s: float = 450.0,
        chop_range_threshold: float = 48.0,
        chop_vol_threshold: float = 12.0,
        hysteresis_cooldown_seconds: float = 45.0,
        experience_buffer=None,
        enable_warrior_2_chop: bool = False,
    ) -> None:
        super().__init__(
            max_turnover_per_event=max_turnover_per_event,
            min_ev_hurdle_dollars=min_ev_hurdle_dollars,
            discount_limit_price=discount_limit_price,
            min_edge_pct=min_edge_pct,
            vpin_toxic_threshold=vpin_toxic_threshold,
            vpin_safe_threshold=vpin_safe_threshold,
            default_btc_1m_volatility=default_btc_1m_volatility,
            take_profit_price_threshold=take_profit_price_threshold,
            enable_take_profit_ceiling=enable_take_profit_ceiling,
            require_reversal_for_tp_ceiling=require_reversal_for_tp_ceiling,
            enable_reverse_take_profit_roi=enable_reverse_take_profit_roi,
            reverse_indicator_threshold=reverse_indicator_threshold,
            min_take_profit_roi=min_take_profit_roi,
            maker_entry_timeout_seconds=maker_entry_timeout_seconds,
            late_cycle_roi=late_cycle_roi,
            fee_per_contract=fee_per_contract,
            min_spot_diff=min_spot_diff,
            max_entry_price=max_entry_price,
            min_confidence=min_confidence,
            enable_trailing_ratchet=enable_trailing_ratchet,
            trailing_ratchet_buffer=trailing_ratchet_buffer,
            spot_delta_front_run_threshold=spot_delta_front_run_threshold,
            enable_dynamic_spot_velocity=enable_dynamic_spot_velocity,
            velocity_z_score_threshold=velocity_z_score_threshold,
            reentry_cooldown_seconds=reentry_cooldown_seconds,
            enable_doubt_harvest=enable_doubt_harvest,
            doubt_threshold=doubt_threshold,
            upside_capture_ratio_threshold=upside_capture_ratio_threshold,
            asymmetric_peak_bid=asymmetric_peak_bid,
            onnx_engine=onnx_engine,
            fusion_weight_micro=fusion_weight_micro,
            opening_quarantine_seconds=opening_quarantine_seconds,
            max_clob_spread_cents=max_clob_spread_cents,
            moneyness_moat_multiplier=moneyness_moat_multiplier,
            asset=CryptoAsset.ETH,
            chop_discount_limit_price=chop_discount_limit_price,
            chop_max_entry_price=chop_max_entry_price,
            chop_min_time_s=chop_min_time_s,
            chop_max_time_s=chop_max_time_s,
            chop_range_threshold=chop_range_threshold,
            chop_vol_threshold=chop_vol_threshold,
            hysteresis_cooldown_seconds=hysteresis_cooldown_seconds,
            experience_buffer=experience_buffer,
            enable_warrior_2_chop=enable_warrior_2_chop,
        )

        # No additional ETH‑specific logic is required at this layer – the
        # underlying ``Bot1V4DominationEngine`` already consults ``AssetConfig``
        # for values such as ``min_spot_diff`` and ``typical_1m_volatility``.
        logger.info("EthBot1V4Engine initialised for asset %s", CryptoAsset.ETH.value)
