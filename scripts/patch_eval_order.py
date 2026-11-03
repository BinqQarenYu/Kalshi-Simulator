from pathlib import Path

fpath = Path("src/kalshi_sim/ml/dynamic_regime_strategy.py")
text = fpath.read_text(encoding="utf-8")

# We want wave physics and update_regime_state to run before the timing guard check
old_block = """        # Session Timing Guard Gate (DEF-09: Empirical Golden Sessions Only)
        if self.enable_timing_guard:
            timing_guard = get_session_timing_guard()
            timing_verdict = timing_guard.evaluate_timing(
                ref_time=eval_ref_time,
                macro_regime=self._current_regime,
                spot_diff=spot_diff,
            )
            if not timing_verdict.allowed:
                return self._build_wait_decision(
                    self._current_regime,
                    spot_diff,
                    time_to_expiry_s,
                    volatility_1m,
                    spread,
                    timing_verdict.reason,
                )

        # Late-Cycle 4-Minute Expiration Blackout Gate (User Directive / Anti-Gamma Bleed)
        if time_to_expiry_s <= 240.0:
            return self._build_wait_decision(
                self.REGIME_SILAS,
                spot_diff,
                time_to_expiry_s,
                volatility_1m,
                spread,
                f"Late-Cycle 4-Minute Quarantine (T={time_to_expiry_s:.0f}s <= 240s): Trading halted near expiration to prevent gamma & pin bleed.",
            )

        # 4. Geometric Wave Physics
        wave_physics = compute_wave_physics(
            open_price=float(strike_price),
            high_price=float(max(spot_price, strike_price)),
            low_price=float(min(spot_price, strike_price)),
            current_price=float(spot_price),
            tsunami_threshold=self.tsunami_threshold,
            wick_meatgrinder_threshold=self.wick_meatgrinder_threshold,
            false_breakout_rng_threshold=self.false_breakout_rng_threshold,
            directional_body_threshold=self.directional_body_threshold,
            asset=self.asset,
        )

        # 4. State Machine Update
        regime = self.update_regime_state(
            volatility_1m=volatility_1m,
            spread=spread,
            vpin=effective_vpin,
            time_to_expiry_s=time_to_expiry_s,
            is_double_wick=wave_physics.is_double_wick_meatgrinder,
            now_ts=ts,
        )"""

new_block = """        # Late-Cycle 4-Minute Expiration Blackout Gate (User Directive / Anti-Gamma Bleed)
        if time_to_expiry_s <= 240.0:
            return self._build_wait_decision(
                self.REGIME_SILAS,
                spot_diff,
                time_to_expiry_s,
                volatility_1m,
                spread,
                f"Late-Cycle 4-Minute Quarantine (T={time_to_expiry_s:.0f}s <= 240s): Trading halted near expiration to prevent gamma & pin bleed.",
            )

        # 4. Geometric Wave Physics
        wave_physics = compute_wave_physics(
            open_price=float(strike_price),
            high_price=float(max(spot_price, strike_price)),
            low_price=float(min(spot_price, strike_price)),
            current_price=float(spot_price),
            tsunami_threshold=self.tsunami_threshold,
            wick_meatgrinder_threshold=self.wick_meatgrinder_threshold,
            false_breakout_rng_threshold=self.false_breakout_rng_threshold,
            directional_body_threshold=self.directional_body_threshold,
            asset=self.asset,
        )

        # 4. State Machine Update
        regime = self.update_regime_state(
            volatility_1m=volatility_1m,
            spread=spread,
            vpin=effective_vpin,
            time_to_expiry_s=time_to_expiry_s,
            is_double_wick=wave_physics.is_double_wick_meatgrinder,
            now_ts=ts,
        )

        # Session Timing Guard Gate (DEF-09: Empirical Golden Sessions Only & Dynamic Storm Override)
        if self.enable_timing_guard:
            timing_guard = get_session_timing_guard()
            timing_verdict = timing_guard.evaluate_timing(
                ref_time=eval_ref_time,
                macro_regime=regime,
                spot_diff=spot_diff,
            )
            if not timing_verdict.allowed:
                return self._build_wait_decision(
                    regime,
                    spot_diff,
                    time_to_expiry_s,
                    volatility_1m,
                    spread,
                    timing_verdict.reason,
                )"""

if old_block in text:
    text = text.replace(old_block, new_block, 1)
    fpath.write_text(text, encoding="utf-8")
    print("SUCCESS: Patched evaluate order in dynamic_regime_strategy.py")
else:
    print("WARNING: Old block not found in dynamic_regime_strategy.py")
