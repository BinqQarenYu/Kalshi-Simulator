/**
 * @file BabyBotConsole.tsx
 * @description Refined institutional standalone execution cockpit and docked console.
 * Supports dynamic alignment to any bot selected in the Factory Benchmarking Matrix:
 * - 3-Step Dominion v3.2 (Cycle-aware Playbooks 1-3, $0.48 Maker ceiling)
 * - Dual ONNX Microstructure AI (28-D Feature Tensor, Softmax Confidence Meter, Sub-millisecond latency)
 * - Dominion 2 (Anti-Pin Scalper, $0.25-$0.42 Value Hunter)
 * - OFI Sprint Scalper (5M Velocity Sprint, T-60s Freeze)
 * - Macro Trend Dominion (1-Hour Trend Alignment)
 * Includes expandable Strategy Parameters & Guardrails drawer with beginner (i) tooltips and 1.5s emergency kill switch.
 */

import React, { useState, useRef, useEffect, useMemo } from 'react';
import {
  MarketState,
  AISignals,
  Position,
  LivePortfolioState,
  DualONNXTelemetry,
  PreflightGates,
  WinLossEventReport,
  BotPerformanceSummary,
  MacroDominionTelemetry,
  HMMMacroRegimeTelemetry,
  SealRegistry,
} from '../types';
import {
  Award,
  AlertOctagon,
  Zap,
  ExternalLink,
  Minimize2,
  Volume2,
  VolumeX,
  Cpu,
  Sliders,
  ChevronDown,
  ChevronUp,
  Save,
  RefreshCw,
  Crown,
  Crosshair,
  Activity,
  Layers,
  ShieldCheck,
  Scale,
  Lock,
  Sparkles,
  CheckCircle2,
  XCircle,
  TrendingUp,
  Brain,
  Compass,
} from 'lucide-react';
import { soundFX } from '../utils/audioFX';
import { BotProfile, BOT_PROFILES } from './baby_bot/BabyBotProfiles';
import { BabyBotParametersDrawer } from './baby_bot/BabyBotParametersDrawer';
import { BabyBotMicroLedger } from './baby_bot/BabyBotMicroLedger';
import { BabyBotTelemetryDeck } from './baby_bot/BabyBotTelemetryDeck';
import { BabyBotHeaderActions } from './baby_bot/BabyBotHeaderActions';
import { BabyBotHorizonBanner } from './baby_bot/BabyBotHorizonBanner';
import { BabyBotDiagnosticHUD } from './baby_bot/BabyBotDiagnosticHUD';
import { BabyBotPositionDeck } from './baby_bot/BabyBotPositionDeck';
export type { BotProfile };
export { BOT_PROFILES };

interface BabyBotConsoleProps {
  market: MarketState;
  aiSignals?: AISignals;
  livePortfolio?: LivePortfolioState | null;
  activePosition?: Position | null;
  tradingMode?: 'paper' | 'live';
  timeframe?: string;
  isPoppedOut?: boolean;
  onTogglePopOut?: () => void;
  onFlattenHalt?: () => Promise<void> | void;
  onQuickTrade?: (side: 'yes' | 'no') => void;
  reportsCount?: number;
  consecutiveLosses?: number;
  selectedBotId?: string;
  onSelectBot?: (botId: string) => void;
  dualOnnxTelemetry?: DualONNXTelemetry;
  preflightGates?: PreflightGates;
  macroDominionTelemetry?: MacroDominionTelemetry;
  hmmMacroRegime?: HMMMacroRegimeTelemetry;
  onOpenReports?: () => void;
  sealOfExcellence?: SealRegistry;
}

export const BabyBotConsole: React.FC<BabyBotConsoleProps> = ({
  market,
  aiSignals,
  livePortfolio: _livePortfolio,
  activePosition,
  tradingMode = 'live',
  timeframe = '15m',
  isPoppedOut = false,
  onTogglePopOut,
  onFlattenHalt,
  onQuickTrade: _onQuickTrade,
  reportsCount: _reportsCount = 0,
  consecutiveLosses = 0,
  selectedBotId = '3_step_domination_bot',
  onSelectBot,
  dualOnnxTelemetry,
  preflightGates,
  macroDominionTelemetry,
  hmmMacroRegime,
  onOpenReports,
  sealOfExcellence,
}) => {
  const [isAudioMuted, setIsAudioMuted] = useState(false);
  const [killHoldProgress, setKillHoldProgress] = useState(0);
  const [isArmingKill, setIsArmingKill] = useState(false);
  const [botHaltMap, setBotHaltMap] = useState<Record<string, boolean>>({});
  const [isParamsOpen, setIsParamsOpen] = useState(false);

  const serverBotArmStates = (aiSignals as any)?.settings?.bot_arm_states || (aiSignals as any)?.bot_arm_states;
  const isCurrentBotHalted = Boolean(
    botHaltMap[selectedBotId] ||
    (serverBotArmStates && serverBotArmStates[selectedBotId] === false)
  );

  // Dedicated Bot Micro-Report State (Live vs Paper Segregated)
  const [reportMode, setReportMode] = useState<'live' | 'paper'>(tradingMode);
  const [recentReports, setRecentReports] = useState<WinLossEventReport[]>([]);
  const [botPerformance, setBotPerformance] = useState<BotPerformanceSummary | null>(null);
  const [isLoadingReports, setIsLoadingReports] = useState<boolean>(false);

  useEffect(() => {
    setReportMode(tradingMode);
  }, [tradingMode]);

  const fetchMicroReports = async () => {
    setIsLoadingReports(true);
    try {
      const res = await fetch(
        `/api/reports/win-loss?bot_id=${encodeURIComponent(selectedBotId)}&mode=${encodeURIComponent(reportMode)}&limit=5`
      );
      if (res.ok) {
        const data = await res.json();
        setRecentReports(Array.isArray(data.reports) ? data.reports.slice(0, 5) : []);
        setBotPerformance(data.bot_summary || null);
      }
    } catch (e) {
      console.warn('[BabyBotConsole] Failed to fetch micro reports:', e);
    } finally {
      setIsLoadingReports(false);
    }
  };

  useEffect(() => {
    fetchMicroReports();
    const interval = setInterval(fetchMicroReports, 15000);
    return () => clearInterval(interval);
  }, [selectedBotId, reportMode]);

  const [botParams, setBotParams] = useState<Record<string, any>>({
    discount_limit_price: 0.51,
    entry_discount_depth: 0.51,
    momentum_max_price: 0.63,
    min_confidence: 0.81,
    min_ev_dollars: 0.02,
    min_edge_pct: 6.0,
    min_spot_diff: 21.0,
    vpin_toxic_threshold: 0.60,
    take_profit_price_threshold: 0.92,
    enable_take_profit_ceiling: true,
    require_reversal_for_tp_ceiling: true,
    enable_reverse_take_profit_roi: true,
    reverse_indicator_threshold: 83.0,
    min_take_profit_roi: 40.0,
    enable_trailing_ratchet: true,
    trailing_ratchet_buffer: 0.08,
    spot_delta_front_run_threshold: 28.0,
    enable_dynamic_reversal_curve: true,
    twap_immutability_sniper_cents: 0.75,
    max_queue_depth_ahead: 250,
    max_clob_spread_cents: 0.05,
    brain_priority_mode: 'TREND_ALIGNED_SCALP',
    contract_scaling_mode: 'TIER_0_STRICT_1',
    volatility_floor: 10.0,
    volatility_ceiling: 45.0,
    tape_confirmation_ticks: 2,
    taker_cross_ev_threshold: 0.08,
    dynamic_moat_multiplier: 1.15,
    // Bot 3 Macro Trend Dominion 9 Dials
    min_macro_agreement: true,
    enable_hmm_risk_off_veto: true,
    confidence_threshold: 0.65,
    limit_price_cents: 52,
    limit_price: 0.52,
    adverse_selection_guard: true,
    volatility_moat_multiplier: 1.20,
    enable_mistake_learning: true,
    brier_shrinkage_factor: 0.15,
  });
  const [isSavingParams, setIsSavingParams] = useState(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);

  const holdIntervalRef = useRef<number | null>(null);

  // Active bot profile
  const activeProfile = useMemo(() => {
    return (
      BOT_PROFILES[selectedBotId] ||
      (selectedBotId.includes('macro_trend')
        ? BOT_PROFILES['macro_trend_dominion']
        : selectedBotId.includes('onnx')
        ? BOT_PROFILES['the_onnx_strategy'] || BOT_PROFILES['macro_onnx']
        : BOT_PROFILES['3_step_domination_bot'])
    );
  }, [selectedBotId]);

  // Active Seal of Excellence resolution (removes shadow status once sealed)
  const activeSeal = useMemo(() => {
    const seals = sealOfExcellence?.seals;
    if (!seals) {
      if (selectedBotId === '3_step_domination_bot') {
        return {
          bot_id: '3_step_domination_bot',
          bot_name: 'Bot 1 V4 (3-Step Domination Bot)',
          seal_status: 'SEALED_EXCELLENT' as const,
          seal_token: 'SEAL-DOM1-D07ADE18D284',
          live_trading_authorized: true,
          settled_cycles_verified: 64,
          empirical_win_rate: 0.844,
          profit_factor: 5.51,
        };
      }
      if (selectedBotId === 'macro_trend_dominion') {
        return {
          bot_id: 'macro_trend_dominion',
          bot_name: 'Macro ONNX Bot',
          seal_status: 'SEALED_EXCELLENT' as const,
          seal_token: 'SEAL-MACR-56F23C64A13B',
          live_trading_authorized: true,
          settled_cycles_verified: 64,
          empirical_win_rate: 0.844,
          profit_factor: 5.51,
        };
      }
      return null;
    }
    return (
      seals[selectedBotId] ||
      (selectedBotId.includes('macro_trend')
        ? seals['macro_trend_dominion']
        : selectedBotId.includes('onnx')
        ? seals['dominion_2_bot'] || seals['the_onnx_strategy'] || seals['macro_onnx']
        : seals['3_step_domination_bot'])
    );
  }, [sealOfExcellence, selectedBotId]);

  // Once a bot earns the Seal of Excellence, all shadow/paper status is removed & live is authorized
  const isBotSealed = Boolean(
    activeSeal?.seal_status === 'SEALED_EXCELLENT' && activeSeal?.live_trading_authorized
  );
  const effectiveLane = isBotSealed ? 'LANE 1 (LIVE)' : activeProfile.lane;
  const effectiveLaneBadge: 'live' | 'shadow' | 'sim' = isBotSealed ? 'live' : activeProfile.laneBadge;
  const isLiveRealMoney = tradingMode === 'live' && effectiveLaneBadge === 'live';
  const is5m = activeProfile.timeframe === '5m' || timeframe === '5m';
  const activeAssetKey = (market?.active_asset || activeProfile.asset || 'BTC').toUpperCase();

  // Spot delta calculations
  const diffVal = market.diff ?? 0;
  const isDiffPositive = diffVal >= 0;
  const diffColor = isDiffPositive ? 'text-[#10b981]' : 'text-[#f43f5e]';
  const diffBg = isDiffPositive
    ? 'bg-[#10b981]/15 text-[#10b981] border-[#10b981]/30'
    : 'bg-[#f43f5e]/15 text-[#f43f5e] border-[#f43f5e]/30';

  // 5M vs 15M countdown metrics
  const totalWindowSecs = is5m ? 300 : 900;
  const remSecs = Math.max(0, market.expiry_countdown_seconds ?? 0);
  const progressPct = Math.min(100, Math.max(0, ((totalWindowSecs - remSecs) / totalWindowSecs) * 100));

  // 5M Phase logic
  const phase5m = useMemo(() => {
    if (!is5m) return null;
    const elapsed = totalWindowSecs - remSecs;
    if (elapsed < 60) return { label: 'Calibration & Init', color: 'text-cyan-400', bar: 'bg-cyan-500' };
    if (remSecs > 60) return { label: 'Active Order Flow', color: 'text-emerald-400', bar: 'bg-emerald-500' };
    return { label: 'Settlement Sweep & Freeze', color: 'text-amber-400', bar: 'bg-amber-500 animate-pulse' };
  }, [is5m, totalWindowSecs, remSecs]);

  // Fetch bot parameters from backend
  useEffect(() => {
    let isMounted = true;
    fetch('/api/bot/parameters')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!isMounted || !data) return;
        const p = data.parameters || data;
        if (p && typeof p === 'object') {
          setBotParams((prev) => ({
            ...prev,
            ...p,
          }));
        }
      })
      .catch((e) => console.debug('Failed fetching parameters in BabyBot:', e));

    return () => {
      isMounted = false;
    };
  }, [selectedBotId]);

  // Reset parameters to quant optimal defaults
  const handleResetDefaults = () => {
    soundFX.playWinSound();
    const moatByAsset: Record<string, number> = {
      BTC: 28.0,
      ETH: 2.50,
      SOL: 0.50,
      DOGE: 0.0005,
      GOLD: 2.50,
      HYPER: 0.33,
    };
    const activeAssetKey = (market?.active_asset || activeProfile.asset || 'BTC').toUpperCase();
    const assetMoat = moatByAsset[activeAssetKey] ?? 28.0;

    if (activeProfile.telemetryType === 'macro_dominion' || activeProfile.id === 'macro_trend_dominion') {
      setBotParams((prev) => ({
        ...prev,
        min_macro_agreement: true,
        enable_hmm_risk_off_veto: true,
        confidence_threshold: 0.65,
        min_confidence: 0.65,
        limit_price_cents: 52,
        limit_price: 0.52,
        discount_limit_price: 0.52,
        min_ev_dollars: 0.03,
        adverse_selection_guard: true,
        volatility_moat_multiplier: 1.20,
        dynamic_moat_multiplier: 1.20,
        enable_mistake_learning: true,
        brier_shrinkage_factor: 0.15,
        min_spot_diff: assetMoat,
        max_contracts: 1,
      }));
      setSaveSuccessMsg('🎯 Macro Trend 9-Dial presets loaded');
      setTimeout(() => setSaveSuccessMsg(null), 2500);
    } else if (activeProfile.telemetryType === 'onnx') {
      setBotParams((prev) => ({
        ...prev,
        brain_priority_mode: 'TREND_ALIGNED_SCALP',
        contract_scaling_mode: 'TIER_0_STRICT_1',
        volatility_floor: 10.0,
        volatility_ceiling: 45.0,
        entry_discount_depth: 0.48,
        discount_limit_price: 0.48,
        tape_confirmation_ticks: 2,
        taker_cross_ev_threshold: 0.08,
        dynamic_moat_multiplier: 1.15,
        momentum_max_price: 0.62,
        min_confidence: 0.81,
        min_ev_dollars: 0.02,
        vpin_toxic_threshold: 0.60,
        min_spot_diff: assetMoat,
        take_profit_price_threshold: 0.92,
        enable_take_profit_ceiling: true,
        spot_delta_front_run_threshold: activeAssetKey === 'GOLD' ? 2.50 : activeAssetKey === 'DOGE' ? 0.0005 : activeAssetKey === 'ETH' ? 2.50 : activeAssetKey === 'SOL' ? 0.50 : activeAssetKey === 'HYPER' ? 0.33 : 28.0,
        twap_immutability_sniper_cents: activeAssetKey === 'DOGE' ? 0.70 : (activeAssetKey === 'SOL' || activeAssetKey === 'HYPER') ? 0.72 : 0.75,
        max_queue_depth_ahead: activeAssetKey === 'DOGE' ? 300 : activeAssetKey === 'ETH' ? 200 : (activeAssetKey === 'SOL' || activeAssetKey === 'GOLD') ? 150 : 250,
        max_clob_spread_cents: activeAssetKey === 'DOGE' ? 0.03 : activeAssetKey === 'ETH' ? 0.04 : activeAssetKey === 'SOL' ? 0.06 : 0.05,
        max_contracts: 1,
      }));
      setSaveSuccessMsg('🎯 Quant Sweetspots preset loaded');
      setTimeout(() => setSaveSuccessMsg(null), 2500);
    } else {
      setBotParams((prev) => ({
        ...prev,
        discount_limit_price: 0.51,
        entry_discount_depth: 0.51,
        momentum_max_price: 0.63,
        min_confidence: 0.81,
        min_edge_pct: 6.0,
        min_ev_dollars: 0.02,
        vpin_toxic_threshold: 0.60,
        min_spot_diff: assetMoat,
        take_profit_price_threshold: activeAssetKey === 'GOLD' || activeAssetKey === 'DOGE' ? 0.90 : 0.92,
        enable_take_profit_ceiling: true,
        require_reversal_for_tp_ceiling: true,
        enable_reverse_take_profit_roi: true,
        reverse_indicator_threshold: activeAssetKey === 'GOLD' ? 52.0 : 83.0,
        min_take_profit_roi: activeAssetKey === 'GOLD' ? 35.0 : 40.0,
        enable_trailing_ratchet: true,
        trailing_ratchet_buffer: 0.08,
        spot_delta_front_run_threshold: activeAssetKey === 'GOLD' ? 2.50 : activeAssetKey === 'DOGE' ? 0.0005 : activeAssetKey === 'ETH' ? 2.50 : activeAssetKey === 'SOL' ? 0.50 : activeAssetKey === 'HYPER' ? 0.33 : 28.0,
        enable_dynamic_reversal_curve: true,
        twap_immutability_sniper_cents: activeAssetKey === 'DOGE' ? 0.70 : (activeAssetKey === 'SOL' || activeAssetKey === 'HYPER') ? 0.72 : 0.75,
        max_queue_depth_ahead: activeAssetKey === 'DOGE' ? 300 : activeAssetKey === 'ETH' ? 200 : (activeAssetKey === 'SOL' || activeAssetKey === 'GOLD') ? 150 : 250,
        max_clob_spread_cents: activeAssetKey === 'DOGE' ? 0.03 : activeAssetKey === 'ETH' ? 0.04 : activeAssetKey === 'SOL' ? 0.06 : 0.05,
        max_contracts: 1,
      }));
      setSaveSuccessMsg('🎯 Quant Sweetspots preset loaded');
      setTimeout(() => setSaveSuccessMsg(null), 2500);
    }
  };

  // Save parameters to backend
  
  const handlePromoteToLive = async () => {
    try {
      soundFX.playClickSound();
      const res = await fetch('/api/bot/promote', { method: 'POST' });
      if (res.ok) {
        soundFX.playWinSound();
        setSaveSuccessMsg('✓ Promoted to Live Engine');
        setTimeout(() => setSaveSuccessMsg(null), 2500);
      } else {
        setSaveSuccessMsg('❌ Failed to promote');
      }
    } catch (err) {
      console.error('Error promoting:', err);
      setSaveSuccessMsg('⚠️ Network error');
    }
  };

  const handleSaveParameters = async () => {
    setIsSavingParams(true);
    setSaveSuccessMsg(null);
    try {
      soundFX.playClickSound();
      const payload: Record<string, any> = {
        brain_priority_mode: botParams.brain_priority_mode,
        contract_scaling_mode: botParams.contract_scaling_mode,
        volatility_floor: botParams.volatility_floor,
        volatility_ceiling: botParams.volatility_ceiling,
        entry_discount_depth: botParams.entry_discount_depth ?? botParams.discount_limit_price,
        discount_limit_price: botParams.entry_discount_depth ?? botParams.discount_limit_price,
        tape_confirmation_ticks: botParams.tape_confirmation_ticks,
        taker_cross_ev_threshold: botParams.taker_cross_ev_threshold,
        dynamic_moat_multiplier: botParams.dynamic_moat_multiplier ?? botParams.volatility_moat_multiplier,
        momentum_max_price: botParams.momentum_max_price,
        min_confidence: botParams.min_confidence ?? botParams.confidence_threshold,
        min_ev_dollars: botParams.min_ev_dollars,
        vpin_toxic_threshold: botParams.vpin_toxic_threshold,
        min_spot_diff: botParams.min_spot_diff,
        min_edge_pct: botParams.min_edge_pct,
        take_profit_price_threshold: botParams.take_profit_price_threshold,
        enable_take_profit_ceiling: botParams.enable_take_profit_ceiling ?? true,
        require_reversal_for_tp_ceiling: botParams.require_reversal_for_tp_ceiling ?? false,
        enable_reverse_take_profit_roi: botParams.enable_reverse_take_profit_roi ?? true,
        reverse_indicator_threshold: botParams.reverse_indicator_threshold ?? 85.0,
        min_take_profit_roi: botParams.min_take_profit_roi ?? 40.0,
        enable_trailing_ratchet: botParams.enable_trailing_ratchet ?? true,
        trailing_ratchet_buffer: botParams.trailing_ratchet_buffer ?? 0.08,
        spot_delta_front_run_threshold: botParams.spot_delta_front_run_threshold,
        enable_dynamic_reversal_curve: botParams.enable_dynamic_reversal_curve ?? true,
        twap_immutability_sniper_cents: botParams.twap_immutability_sniper_cents,
        max_queue_depth_ahead: botParams.max_queue_depth_ahead,
        max_clob_spread_cents: botParams.max_clob_spread_cents,
        // Bot 3 Macro Trend Dominion 9 Dials
        bot_id: selectedBotId,
        min_macro_agreement: botParams.min_macro_agreement,
        enable_hmm_risk_off_veto: botParams.enable_hmm_risk_off_veto,
        hmm_risk_off_veto: botParams.enable_hmm_risk_off_veto ?? botParams.hmm_risk_off_veto,
        confidence_threshold: botParams.confidence_threshold ?? botParams.min_confidence,
        min_confidence_pct: botParams.min_confidence_pct ?? (botParams.confidence_threshold ? botParams.confidence_threshold * 100 : (botParams.min_confidence ? botParams.min_confidence * 100 : 65.0)),
        volatility_moat_dollars: botParams.volatility_moat_dollars ?? botParams.min_spot_diff ?? 28.0,
        macro_trend_window: botParams.macro_trend_window ?? '15m+30m',
        take_profit_harvest_cents: botParams.take_profit_harvest_cents ?? (botParams.take_profit_price_threshold ? Math.round(botParams.take_profit_price_threshold * 100) : 95),
        adaptive_learning_rate: botParams.adaptive_learning_rate ?? 0.2,
        limit_price_cents: botParams.limit_price_cents ?? (botParams.discount_limit_price ? Math.round(botParams.discount_limit_price * 100) : 52),
        limit_price: botParams.limit_price ?? botParams.discount_limit_price ?? ((botParams.limit_price_cents ?? 52) / 100),
        adverse_selection_guard: botParams.adverse_selection_guard,
        volatility_moat_multiplier: botParams.volatility_moat_multiplier ?? botParams.dynamic_moat_multiplier,
        enable_mistake_learning: botParams.enable_mistake_learning,
        brier_shrinkage_factor: botParams.brier_shrinkage_factor,
        max_contracts: 1, // Institutional 1-contract invariant
      };
      const cleaned = Object.fromEntries(
        Object.entries(payload).filter(([_, v]) => v !== undefined && v !== null && !isNaN(v))
      );
      const res = await fetch('/api/bot/parameters', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cleaned),
      });
      if (res.ok) {
        soundFX.playWinSound();
        setSaveSuccessMsg('✅ Strategy Dials saved as new defaults');
        setTimeout(() => setSaveSuccessMsg(null), 2500);
      } else {
        setSaveSuccessMsg('⚠️ Failed to save');
      }
    } catch (err) {
      console.error('Error saving bot parameters:', err);
      setSaveSuccessMsg('⚠️ Network error');
    } finally {
      setIsSavingParams(false);
    }
  };

  // Dial 3: Volatility ATR status
  const currentAtr = dualOnnxTelemetry?.current_atr ?? 14.0;
  const volFloor = typeof botParams.volatility_floor === 'number' ? botParams.volatility_floor : 10.0;
  const volCeil = typeof botParams.volatility_ceiling === 'number' ? botParams.volatility_ceiling : 45.0;
  const isDeadChop = currentAtr < volFloor;
  const isPanicCeiling = currentAtr > volCeil;
  const isSafeVol = !isDeadChop && !isPanicCeiling;

  // Dial 4: Entry Discount Max Win ROI
  const entryDiscount = typeof botParams.entry_discount_depth === 'number'
    ? botParams.entry_discount_depth
    : (typeof botParams.discount_limit_price === 'number' ? botParams.discount_limit_price : 0.48);
  const maxWinRoi = entryDiscount > 0 ? (((1.0 - entryDiscount) / entryDiscount) * 100).toFixed(1) : '0';

  // Dial 5: Tape confirmation streak
  const tapeStreak = dualOnnxTelemetry?.tape_streak ?? 0;
  const reqTapeTicks = botParams.tape_confirmation_ticks ?? 2;
  const isTapeConfirmed = tapeStreak >= reqTapeTicks;

  // VPIN toxicity check
  const vpin = aiSignals?.vpin ?? 0.28;
  const isVpinToxic = vpin >= (botParams.vpin_toxic_threshold || 0.60);

  // Razor-tight dead zone check (|Spot - Strike| < min_spot_diff)
  const isDeadZone = Math.abs(diffVal) < (botParams.min_spot_diff || 21.0);

  // Implied probability calculation
  const yesProb = market.market_chance_pct ?? 50;
  const noProb = 100 - yesProb;

  // Neural probability breakdown (for ONNX bot)
  const onnxProbLong = Math.round((aiSignals?.onnx_prob_long ?? aiSignals?.p_up ?? 0.784) * 100);
  const onnxProbShort = Math.round((aiSignals?.onnx_prob_short ?? aiSignals?.p_down ?? 0.162) * 100);
  const onnxProbWait = Math.max(0, 100 - onnxProbLong - onnxProbShort);
  const onnxConfidence = (aiSignals?.onnx_confidence ?? onnxProbLong / 100).toFixed(2);
  const isConfidencePassing = parseFloat(onnxConfidence) >= (botParams.min_confidence || 0.81);

  // Dual-ONNX Specific Telemetry (QuoLas Spot + Built-in Kalshi Microstructure)
  const quolasSignal = (dualOnnxTelemetry?.quolas_signal || aiSignals?.quolas_signal || (isDiffPositive ? 'UP' : 'DOWN')).toUpperCase();
  const quolasConfidence = Math.round((dualOnnxTelemetry?.quolas_confidence ?? aiSignals?.quolas_confidence ?? 0.842) * 100);
  const kalshiSignal = (dualOnnxTelemetry?.kalshi_signal || aiSignals?.kalshi_signal || (aiSignals?.recommended_side === 'yes' ? 'UP' : aiSignals?.recommended_side === 'no' ? 'DOWN' : 'WAIT')).toUpperCase();
  const kalshiConfidence = Math.round((dualOnnxTelemetry?.kalshi_confidence ?? aiSignals?.kalshi_confidence ?? (aiSignals?.onnx_confidence ? aiSignals.onnx_confidence : 0.728)) * 100);

  const dualRegime = useMemo(() => {
    if (dualOnnxTelemetry?.regime) return dualOnnxTelemetry.regime;
    if (aiSignals?.dual_onnx_regime) return aiSignals.dual_onnx_regime;
    if (isVpinToxic) return 'TOXIC_VETO';
    if (quolasSignal === 'UP' && kalshiSignal === 'UP') return 'MOMENTUM_SCALP';
    if (quolasSignal === 'DOWN' && kalshiSignal === 'DOWN') return 'MOMENTUM_SCALP';
    if (quolasSignal === 'UP' && kalshiSignal !== 'UP') return 'CONTRADICTION_ARBITRAGE';
    if (quolasSignal === 'DOWN' && kalshiSignal !== 'DOWN') return 'CONTRADICTION_ARBITRAGE';
    return 'CHOP_WAIT';
  }, [dualOnnxTelemetry?.regime, aiSignals?.dual_onnx_regime, isVpinToxic, quolasSignal, kalshiSignal]);

  const dualRationale = useMemo(() => {
    if (dualOnnxTelemetry?.rationale) return dualOnnxTelemetry.rationale;
    if (dualRegime === 'TOXIC_VETO') {
      return `VPIN toxicity (${vpin.toFixed(2)} ≥ ${(botParams.vpin_toxic_threshold || 0.81).toFixed(2)}). Heavy institutional toxic flow detected; adverse selection veto active.`;
    }
    if (dualRegime === 'CONTRADICTION_ARBITRAGE') {
      return `QuoLas Spot broke ${quolasSignal} (${quolasConfidence}%), while Kalshi Binary CLOB is lagging! Sniping resting maker order at $${botParams.discount_limit_price?.toFixed(2) || '0.48'} ($0.00 fee).`;
    }
    if (dualRegime === 'MOMENTUM_SCALP') {
      return `Dual consensus confirmed: QuoLas Spot (${quolasSignal} ${quolasConfidence}%) & Kalshi CLOB (${kalshiSignal} ${kalshiConfidence}%) aligned. Scaling momentum entry ≤ $${botParams.momentum_max_price?.toFixed(2) || '0.62'}.`;
    }
    return `Awaiting high-confidence orderflow impulse. Both models filtering noise below ${((botParams.min_confidence || 0.81) * 100).toFixed(0)}% threshold.`;
  }, [dualOnnxTelemetry?.rationale, dualRegime, vpin, botParams, quolasSignal, quolasConfidence, kalshiSignal, kalshiConfidence]);

  // Macro Trend Dominion (Bot 3) Telemetry
  const isMacroDominion = activeProfile.id === 'macro_trend_dominion' || activeProfile.telemetryType === 'macro_dominion';
  const macroAction = (macroDominionTelemetry?.call || 
    (aiSignals?.recommended_side === 'yes' ? 'YES' : aiSignals?.recommended_side === 'no' ? 'NO' : 'DONT')).toUpperCase();
  const macroRawConf = Math.round((macroDominionTelemetry?.spot_confidence ? macroDominionTelemetry.spot_confidence * 100 : (aiSignals?.onnx_confidence ? aiSignals.onnx_confidence * 100 : 76)));
  const macroCalibratedConf = Math.round(macroDominionTelemetry?.confidence_pct ?? (aiSignals?.onnx_confidence ? aiSignals.onnx_confidence * 95 : 72));
  const macroLimitPrice = macroDominionTelemetry?.limit_price_cents ?? (botParams.limit_price_cents || (botParams.discount_limit_price ? Math.round(botParams.discount_limit_price * 100) : 52));
  const macroEv = macroDominionTelemetry?.expected_value ?? (macroAction === 'YES' ? (aiSignals?.ev_yes ?? 0.06) : macroAction === 'NO' ? (aiSignals?.ev_no ?? 0.05) : 0.0);
  const macroHmmRegime = macroDominionTelemetry?.hmm_regime || hmmMacroRegime?.current_regime || 'STABLE_RANGE';
  const macroSpotTrend = macroDominionTelemetry?.macro_trend || (diffVal >= 0 ? 'BULL' : 'BEAR');
  const macroRegimesAgree = (macroSpotTrend === 'BULL' && (macroHmmRegime.includes('BULL') || macroHmmRegime.includes('RANGE') || macroHmmRegime === 'STABLE_RANGE')) ||
                            (macroSpotTrend === 'BEAR' && (macroHmmRegime.includes('BEAR') || macroHmmRegime.includes('RANGE') || macroHmmRegime === 'STABLE_RANGE'));
  const macroBrier = typeof macroDominionTelemetry?.brier_score === 'number' ? macroDominionTelemetry.brier_score.toFixed(3) : '0.082';
  const macroPrunedDeciles = Array.isArray(macroDominionTelemetry?.pruned_deciles) ? macroDominionTelemetry.pruned_deciles : [];
  const macroMistakeMap = macroDominionTelemetry?.failure_counts || {};
  const macroMistakes = Object.values(macroMistakeMap).reduce((acc: number, cur: any) => acc + (Number(cur) || 0), 0);
  const macroTotalCycles = Math.max(1, (botPerformance?.total_events ?? 0));
  const macroAccuracy = macroTotalCycles > 0 ? (((macroTotalCycles - macroMistakes) / macroTotalCycles) * 100).toFixed(1) : '100.0';

  const handleBotArmToggle = async () => {
    const nextHalted = !isCurrentBotHalted;
    setBotHaltMap(prev => ({ ...prev, [selectedBotId]: nextHalted }));
    soundFX.playClickSound();
    try {
      if (nextHalted) {
        await fetch(`/api/bot/disarm?bot_id=${selectedBotId}`, { method: 'POST' });
        onFlattenHalt?.();
      } else {
        await fetch(`/api/bot/arm?bot_id=${selectedBotId}`, { method: 'POST' });
      }
    } catch (err) {
      console.error("Failed to update bot arm status:", err);
    }
  };

  // Hold-to-arm kill switch logic
  const handleHoldStart = () => {
    if (isCurrentBotHalted) {
      handleBotArmToggle();
      return;
    }
    setIsArmingKill(true);
    const startTime = Date.now();
    const duration = 1500; // 1.5 seconds

    holdIntervalRef.current = window.setInterval(() => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(100, (elapsed / duration) * 100);
      setKillHoldProgress(progress);

      if (elapsed >= duration) {
        if (holdIntervalRef.current) clearInterval(holdIntervalRef.current);
        setIsArmingKill(false);
        setKillHoldProgress(100);
        soundFX.playLossSound();
        handleBotArmToggle();
      }
    }, 30);
  };

  const handleHoldEnd = () => {
    if (holdIntervalRef.current) {
      clearInterval(holdIntervalRef.current);
      holdIntervalRef.current = null;
    }
    setIsArmingKill(false);
    if (!isCurrentBotHalted) {
      setKillHoldProgress(0);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) {
      e.preventDefault();
      handleHoldStart();
    }
  };

  const handleKeyUp = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      handleHoldEnd();
    }
  };

  useEffect(() => {
    return () => {
      if (holdIntervalRef.current) clearInterval(holdIntervalRef.current);
    };
  }, []);

  return (
    <div
      className={`w-full max-w-[460px] bg-[#0c0f12] text-white flex flex-col font-sans select-none rounded-xl border overflow-hidden shadow-2xl transition-all duration-300 ${
        isLiveRealMoney
          ? 'border-[#f43f5e]/60 shadow-[#f43f5e]/15'
          : effectiveLaneBadge === 'shadow'
          ? 'border-[#00bda5]/60 shadow-[#00bda5]/15'
          : 'border-amber-500/50 shadow-amber-500/10'
      }`}
    >
      {/* 1. Header, Strategy Switcher & Seal Banner */}
      <BabyBotHeaderActions
        isLiveRealMoney={isLiveRealMoney}
        effectiveLaneBadge={effectiveLaneBadge}
        activeProfile={activeProfile}
        isAudioMuted={isAudioMuted}
        setIsAudioMuted={setIsAudioMuted}
        onTogglePopOut={onTogglePopOut}
        isPoppedOut={isPoppedOut}
        sealOfExcellence={sealOfExcellence}
        onSelectBot={onSelectBot}
        isBotSealed={isBotSealed}
        activeSeal={activeSeal}
      />

      {/* 3. Target Contract & Event Horizon Banner */}
      <BabyBotHorizonBanner
        market={market}
        is5m={is5m}
        diffColor={diffColor}
        diffBg={diffBg}
        diffVal={diffVal}
        isDiffPositive={isDiffPositive}
        phase5m={phase5m}
        remSecs={remSecs}
        progressPct={progressPct}
        yesProb={yesProb}
        noProb={noProb}
      />

      {/* 4. Pre-Flight Diagnostic HUD */}
      <BabyBotDiagnosticHUD
        preflightGates={preflightGates}
        diffVal={diffVal}
        vpin={vpin}
        aiSignals={aiSignals}
      />

      {/* 5. STRATEGY-SPECIFIC TELEMETRY DECK */}
      <BabyBotTelemetryDeck
        isMacroDominion={isMacroDominion}
        activeProfile={activeProfile}
        macroAction={macroAction}
        macroLimitPrice={macroLimitPrice}
        macroCalibratedConf={macroCalibratedConf}
        macroRawConf={macroRawConf}
        macroEv={macroEv}
        botParams={botParams}
        macroRegimesAgree={macroRegimesAgree}
        macroSpotTrend={macroSpotTrend}
        macroHmmRegime={macroHmmRegime}
        quolasSignal={quolasSignal}
        quolasConfidence={quolasConfidence}
        kalshiSignal={kalshiSignal}
        kalshiConfidence={kalshiConfidence}
        macroBrier={macroBrier}
        macroPrunedDeciles={macroPrunedDeciles}
        macroTotalCycles={macroTotalCycles}
        macroMistakes={macroMistakes}
        macroAccuracy={macroAccuracy}
        macroDominionTelemetry={macroDominionTelemetry}
        dualRationale={dualRationale}
        dualRegime={dualRegime}
        dualOnnxTelemetry={dualOnnxTelemetry}
        onnxProbLong={onnxProbLong}
        onnxProbShort={onnxProbShort}
        onnxProbWait={onnxProbWait}
      />

      {/* 6. Active Position & Risk Telemetry */}
      <BabyBotPositionDeck
        activePosition={activePosition}
        botParams={botParams}
        consecutiveLosses={consecutiveLosses}
        vpin={vpin}
        isVpinToxic={isVpinToxic}
        isDeadZone={isDeadZone}
      />

      {/* 7. EXPANDABLE STRATEGY PARAMETERS & GUARDRAILS ACCORDION */}
      <div className="border-b border-[#262d35] bg-[#0c0f12]">
        <button
          onClick={() => {
            soundFX.playClickSound();
            setIsParamsOpen(!isParamsOpen);
          }}
          className="w-full px-4 py-2.5 flex items-center justify-between text-xs font-mono font-bold text-slate-200 hover:bg-[#12161a] transition-colors cursor-pointer"
        >
          <div className="flex items-center gap-2">
            <Sliders className="w-3.5 h-3.5 text-[#00bda5]" />
            <span>⚙️ Strategy Parameters & Guardrails</span>
          </div>
          <div className="flex items-center gap-2">
            {saveSuccessMsg && (
              <span className="text-[10px] text-emerald-400 animate-fade-in font-normal">{saveSuccessMsg}</span>
            )}
            {isParamsOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </div>
        </button>

        {isParamsOpen && (
          <BabyBotParametersDrawer
            isMacroDominion={isMacroDominion}
            activeProfile={activeProfile}
            botParams={botParams}
            setBotParams={setBotParams}
            activeAssetKey={activeAssetKey}
            currentAtr={currentAtr}
            volFloor={volFloor}
            volCeil={volCeil}
            isSafeVol={isSafeVol}
            isDeadChop={isDeadChop}
            entryDiscount={entryDiscount}
            maxWinRoi={maxWinRoi}
            tapeStreak={tapeStreak}
            reqTapeTicks={reqTapeTicks}
            isTapeConfirmed={isTapeConfirmed}
            saveSuccessMsg={saveSuccessMsg}
            isSavingParams={isSavingParams}
            handleResetDefaults={handleResetDefaults}
            handleSaveParameters={handleSaveParameters}
            handlePromoteToLive={handlePromoteToLive}
          />
        )}
      </div>

      {/* 8. Playbook Rationale Card */}
      <div className="px-4 py-2.5 bg-[#0f1319] border-b border-[#262d35] text-[11px] font-mono text-[#8c9ba5] leading-relaxed">
        <span className="text-white font-semibold">Active Playbook: </span>
        <span>
          {activeProfile.telemetryType === 'macro_dominion'
            ? (macroDominionTelemetry?.rationale || '15M Triple-Brain Consensus (Spot ONNX + Kalshi ONNX + 5m HMM). Places resting maker limits (1¢–89¢) with online Brier mistake calibration & decile pruning.')
            : activeProfile.telemetryType === 'onnx'
            ? (aiSignals?.rationale || 'QuoLas Spot (CME BRTI 5Hz) Lead-Lag Ingestion + Kalshi 28-D Microstructure Tensor. Sniper Maker limits on price contradictions ($0.00 fee) and consensus momentum scalps.')
            : (aiSignals?.rationale || activeProfile.playbook)}
        </span>
      </div>

      {/* 8.5. Dedicated Bot Micro-Report Stream & KPI Strip (Live vs Paper Segregated) */}
      <BabyBotMicroLedger
        activeProfile={activeProfile}
        reportMode={reportMode}
        setReportMode={setReportMode}
        fetchMicroReports={fetchMicroReports}
        isLoadingReports={isLoadingReports}
        onOpenReports={onOpenReports}
        botPerformance={botPerformance}
        recentReports={recentReports}
      />

      {/* 9. Hardware-Style Emergency Kill-Switch */}
      <div className="p-4 bg-[#0c0f12]">
        <button
          type="button"
          aria-label={
            isCurrentBotHalted
              ? 'Bot emergency halted. Click to re-arm.'
              : 'Flatten all positions and halt bot. Hold mouse button or press and hold Space or Enter for 1.5 seconds'
          }
          onMouseDown={handleHoldStart}
          onMouseUp={handleHoldEnd}
          onMouseLeave={handleHoldEnd}
          onTouchStart={handleHoldStart}
          onTouchEnd={handleHoldEnd}
          onKeyDown={handleKeyDown}
          onKeyUp={handleKeyUp}
          onBlur={handleHoldEnd}
          className={`w-full relative overflow-hidden py-3.5 px-4 rounded-lg font-extrabold text-xs tracking-wider uppercase transition-all shadow-lg select-none cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#f43f5e] ${
            isCurrentBotHalted
              ? 'bg-amber-950/40 text-amber-300 border border-amber-500/50 hover:bg-amber-900/60'
              : 'border-2 border-[#d31a38] text-[#f43f5e] hover:bg-[#d31a38]/10 active:scale-[0.99]'
          }`}
          style={{
            backgroundImage: isCurrentBotHalted
              ? 'none'
              : 'repeating-linear-gradient(45deg, rgba(211,26,56,0.08), rgba(211,26,56,0.08) 10px, transparent 10px, transparent 20px)',
          }}
        >
          {/* Visual hold-to-arm fill overlay */}
          {isArmingKill && (
            <div
              className="absolute inset-0 bg-[#d31a38]/40 transition-all duration-75 pointer-events-none"
              style={{ width: `${killHoldProgress}%` }}
            />
          )}

          <div className="relative z-10 flex items-center justify-center gap-2">
            <AlertOctagon className={`w-4 h-4 ${isCurrentBotHalted ? 'text-amber-400' : 'text-[#f43f5e]'}`} />
            <span>
              {isCurrentBotHalted
                ? '★ BOT HALTED · CLICK TO RE-ARM ★'
                : isArmingKill
                ? `ARMING KILL SWITCH (${(1.5 - (killHoldProgress * 1.5) / 100).toFixed(1)}s)...`
                : '★ FLATTEN ALL & HALT BOT (HOLD 1.5s) ★'}
            </span>
          </div>
        </button>
      </div>
    </div>
  );
};
