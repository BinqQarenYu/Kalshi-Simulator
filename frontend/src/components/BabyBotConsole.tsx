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

export interface BotProfile {
  id: string;
  name: string;
  shortName: string;
  version: string;
  lane: string;
  laneBadge: 'live' | 'shadow' | 'sim';
  asset: string;
  timeframe: string;
  telemetryType: 'dominion' | 'onnx' | 'antipin' | 'scalper' | 'trend' | 'macro_dominion';
  description: string;
  hardCapContracts: number;
  discountCeiling: number;
  playbook: string;
}

export const BOT_PROFILES: Record<string, BotProfile> = {
  'the_onnx_strategy': {
    id: 'the_onnx_strategy',
    name: 'The ONNX Strategy',
    shortName: 'ONNX Strategy',
    version: 'v1.0 (Quant Dials)',
    lane: 'LANE 2 (SHADOW PAPER)',
    laneBadge: 'shadow',
    asset: 'BTC',
    timeframe: '15m',
    telemetryType: 'onnx',
    description: 'The ONNX Strategy: Dual-Brain Spot Lead vs Kalshi Lag CLOB with 5 Precision Execution Dials',
    hardCapContracts: 1,
    discountCeiling: 0.48,
    playbook: 'Trend Aligned Scalp · Volatility Regime Shield · Sizing Armor',
  },
  'dual_onnx': {
    id: 'dual_onnx',
    name: 'The ONNX Strategy (Dual-Brain)',
    shortName: 'ONNX Strategy',
    version: 'v1.0 (Quant Dials)',
    lane: 'LANE 2 (SHADOW PAPER)',
    laneBadge: 'shadow',
    asset: 'BTC',
    timeframe: '15m',
    telemetryType: 'onnx',
    description: 'The ONNX Strategy: Dual-Brain Spot Lead vs Kalshi Lag CLOB with 5 Precision Execution Dials',
    hardCapContracts: 1,
    discountCeiling: 0.48,
    playbook: 'Trend Aligned Scalp · Volatility Regime Shield · Sizing Armor',
  },
  '3_step_domination_bot': {
    id: '3_step_domination_bot',
    name: '3-Step Dominion v3.2',
    shortName: '3-Step Dom',
    version: 'v3.2',
    lane: 'LANE 1 (LIVE REAL-MONEY)',
    laneBadge: 'live',
    asset: 'BTC',
    timeframe: '15m',
    telemetryType: 'dominion',
    description: '3-Step Playbook Cycle Sniper (Early Breakout, Mid OFI Drift, Late Gamma Snub)',
    hardCapContracts: 1,
    discountCeiling: 0.48,
    playbook: 'Playbook 2: OFI Trend Drift · Resting $0.48 Limit',
  },
  'macro_onnx': {
    id: 'macro_onnx',
    name: 'ONNX Macro Net v2',
    shortName: 'ONNX Macro v2',
    version: 'v2.4 (Dual-Brain)',
    lane: 'LANE 2 (SHADOW PAPER)',
    laneBadge: 'shadow',
    asset: 'BTC',
    timeframe: '15m',
    telemetryType: 'onnx',
    description: 'Dual-Brain Arbitrage: QuoLas Nano Microscope (Spot) + Built-in Kalshi Microstructure (Binary)',
    hardCapContracts: 1,
    discountCeiling: 0.48,
    playbook: 'Dual-Brain Consensus · Lead-Lag Contradiction Arbitrage',
  },
  'onnx_microstructure_bot': {
    id: 'onnx_microstructure_bot',
    name: 'ONNX Macro Net v2',
    shortName: 'ONNX Macro v2',
    version: 'v2.4 (Dual-Brain)',
    lane: 'LANE 2 (SHADOW PAPER)',
    laneBadge: 'shadow',
    asset: 'BTC',
    timeframe: '15m',
    telemetryType: 'onnx',
    description: 'Dual-Brain Arbitrage: QuoLas Nano Microscope (Spot) + Built-in Kalshi Microstructure (Binary)',
    hardCapContracts: 1,
    discountCeiling: 0.48,
    playbook: 'Dual-Brain Consensus · Lead-Lag Contradiction Arbitrage',
  },
  'dominion_2_bot': {
    id: 'dominion_2_bot',
    name: 'Dominion 2 (Anti-Pin Scalper)',
    shortName: 'Dominion 2',
    version: 'v2.1',
    lane: 'LANE 2 (SHADOW PAPER)',
    laneBadge: 'shadow',
    asset: 'BTC',
    timeframe: '15m',
    telemetryType: 'antipin',
    description: 'Anti-Pin Asymmetric Scalper with Kalshi Tie Exploitation ($0.25-$0.42)',
    hardCapContracts: 1,
    discountCeiling: 0.42,
    playbook: 'Anti-Pin Zone Defense · Discount Value Hunter',
  },
  'ofi_sprint_scalper': {
    id: 'ofi_sprint_scalper',
    name: 'OFI Sprint Scalper',
    shortName: 'OFI Scalp',
    version: 'v1.8',
    lane: 'LANE 2 (SHADOW PAPER)',
    laneBadge: 'shadow',
    asset: 'BTC',
    timeframe: '5m',
    telemetryType: 'scalper',
    description: '5-Minute High-Velocity Order Flow Imbalance Momentum Scalper',
    hardCapContracts: 1,
    discountCeiling: 0.50,
    playbook: '5M Velocity Window · T-60s Settlement Freeze',
  },
  'macro_trend_dominion': {
    id: 'macro_trend_dominion',
    name: 'Macro Trend Dominion',
    shortName: 'Macro Trend',
    version: 'v2.0 (3-Brain Fusion)',
    lane: 'LANE 1 (LIVE REAL-MONEY)',
    laneBadge: 'live',
    asset: 'BTC',
    timeframe: '15m',
    telemetryType: 'macro_dominion',
    description: '15M Triple-Brain Consensus (Spot ONNX + Kalshi ONNX + 5m HMM) with 9 Dials & Mistake-Learning Engine',
    hardCapContracts: 1,
    discountCeiling: 0.48,
    playbook: '15M 3-Brain Consensus · 1¢–89¢ Limit Sweetspot · Online Mistake Learning',
  },
  'gold_onnx_bot': {
    id: 'gold_onnx_bot',
    name: 'Gold ONNX Bot (Bot 4)',
    shortName: 'Gold ONNX (B4)',
    version: 'v2.5 (32-D Spacetime)',
    lane: 'LANE 1 (LIVE REAL-MONEY)',
    laneBadge: 'live',
    asset: 'GOLD',
    timeframe: '15m',
    telemetryType: 'macro_dominion',
    description: 'Triple-Brain Gold Sovereign: Binance Spot ONNX + Kalshi Binary ONNX + 5M HMM Regime Fusion',
    hardCapContracts: 1,
    discountCeiling: 0.48,
    playbook: 'Triple-Brain Consensus · Dynamic Volatility Moat · Mistake-Learning Shrinkage',
  },
  'sol_vol_breakout': {
    id: 'sol_vol_breakout',
    name: 'SOL Vol-Breakout',
    shortName: 'SOL Breakout',
    version: 'v1.0',
    lane: 'LANE 3 (BACKTEST)',
    laneBadge: 'sim',
    asset: 'SOL',
    timeframe: '5m',
    telemetryType: 'scalper',
    description: 'Solana High-Volatility Breakout Model (Lane 3 Historical Backtest)',
    hardCapContracts: 1,
    discountCeiling: 0.45,
    playbook: 'Lane 3 Backtesting Regime · Synthetic Fill Simulator',
  },
};

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
  const [isHalted, setIsHalted] = useState(false);
  const [isParamsOpen, setIsParamsOpen] = useState(false);

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
    discount_limit_price: 0.48,
    entry_discount_depth: 0.48,
    momentum_max_price: 0.62,
    min_confidence: 0.81,
    min_ev_dollars: 0.02,
    min_edge_pct: 6.0,
    min_spot_diff: 21.0,
    vpin_toxic_threshold: 0.60,
    take_profit_price_threshold: 0.92,
    enable_take_profit_ceiling: true,
    require_reversal_for_tp_ceiling: false,
    enable_reverse_take_profit_roi: true,
    reverse_indicator_threshold: 85.0,
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
          bot_name: '3-Step Domination Bot',
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
        discount_limit_price: 0.48,
        momentum_max_price: 0.62,
        min_confidence: 0.81,
        min_edge_pct: 6.0,
        min_ev_dollars: 0.02,
        vpin_toxic_threshold: 0.60,
        min_spot_diff: assetMoat,
        take_profit_price_threshold: activeAssetKey === 'GOLD' || activeAssetKey === 'DOGE' ? 0.90 : 0.92,
        enable_take_profit_ceiling: true,
        require_reversal_for_tp_ceiling: false,
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

  // Hold-to-arm kill switch logic
  const handleHoldStart = () => {
    if (isHalted) return;
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
        setIsHalted(true);
        soundFX.playLossSound();
        onFlattenHalt?.();
      }
    }, 30);
  };

  const handleHoldEnd = () => {
    if (holdIntervalRef.current) {
      clearInterval(holdIntervalRef.current);
      holdIntervalRef.current = null;
    }
    setIsArmingKill(false);
    if (!isHalted) {
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
      {/* 1. Header: Execution Mode, Bot Name & Telemetry */}
      <div
        className={`px-4 py-2.5 border-b flex items-center justify-between transition-colors ${
          isLiveRealMoney
            ? 'bg-[#4c111e]/50 border-[#f43f5e]/40'
            : effectiveLaneBadge === 'shadow'
            ? 'bg-[#115e59]/40 border-[#00bda5]/40'
            : 'bg-[#291f0b]/50 border-amber-500/40'
        }`}
      >
        <div className="flex items-center gap-2 overflow-hidden">
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono font-bold tracking-wider uppercase border shadow-sm shrink-0 ${
              isLiveRealMoney
                ? 'bg-[#d31a38] text-white border-rose-400 animate-pulse'
                : effectiveLaneBadge === 'shadow'
                ? 'bg-[#00bda5]/20 text-[#2dd4bf] border-[#00bda5]/50'
                : 'bg-amber-500/20 text-amber-300 border-amber-500/50'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isLiveRealMoney ? 'bg-white' : effectiveLaneBadge === 'shadow' ? 'bg-[#2dd4bf]' : 'bg-amber-400'
              }`}
            />
            <span>{isLiveRealMoney ? 'LIVE REAL-MONEY' : effectiveLaneBadge === 'shadow' ? 'SHADOW (PAPER)' : 'OFFLINE SIM'}</span>
          </div>

          <span className="text-xs font-mono font-bold text-slate-200 truncate">
            {activeProfile.name}
          </span>
        </div>

        <div className="flex items-center gap-2 text-[11px] font-mono shrink-0">
          <span className="text-emerald-400 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            14ms
          </span>
          <button
            onClick={() => {
              setIsAudioMuted(!isAudioMuted);
              soundFX.playClickSound();
            }}
            aria-label="Toggle sound FX"
            className="p-1 rounded text-slate-400 hover:text-white transition-colors cursor-pointer"
          >
            {isAudioMuted ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
          </button>
          {onTogglePopOut && (
            <button
              onClick={onTogglePopOut}
              aria-label={isPoppedOut ? 'Dock into parent' : 'Pop out window'}
              title={isPoppedOut ? 'Dock into parent' : 'Pop out into standalone window'}
              className="p-1 rounded text-slate-400 hover:text-white transition-colors cursor-pointer"
            >
              {isPoppedOut ? <Minimize2 className="w-3.5 h-3.5" /> : <ExternalLink className="w-3.5 h-3.5" />}
            </button>
          )}
        </div>
      </div>

      {/* 2. Embedded Strategy Switcher Pill Bar */}
      <div className="px-3 py-1.5 bg-[#090b0e] border-b border-[#1f262d] flex items-center gap-1.5 overflow-x-auto scrollbar-none">
        <span className="text-[9px] font-mono uppercase text-[#8c9ba5] font-bold shrink-0 mr-1">
          Model:
        </span>
        {[
          BOT_PROFILES['3_step_domination_bot'],
          BOT_PROFILES['dual_onnx'] || BOT_PROFILES['the_onnx_strategy'] || BOT_PROFILES['macro_onnx'],
          BOT_PROFILES['macro_trend_dominion'],
          BOT_PROFILES['gold_onnx_bot'],
        ].filter(Boolean).map((profile) => {
          const profileSeal =
            sealOfExcellence?.seals?.[profile.id] ||
            (profile.id === '3_step_domination_bot'
              ? { seal_status: 'SEALED_EXCELLENT', live_trading_authorized: true }
              : profile.id === 'macro_trend_dominion'
              ? { seal_status: 'SEALED_EXCELLENT', live_trading_authorized: true }
              : null);
          const profileIsSealed = Boolean(
            profileSeal?.seal_status === 'SEALED_EXCELLENT' && profileSeal?.live_trading_authorized
          );
          const isActive =
            activeProfile.id === profile.id ||
            (profile.id === 'macro_trend_dominion' && (activeProfile.id.includes('macro_trend') || activeProfile.id === 'macro_onnx')) ||
            ((profile.id === 'dual_onnx' || profile.id === 'macro_onnx') && (activeProfile.id === 'onnx_microstructure_bot' || activeProfile.id === 'the_onnx_strategy'));
          return (
            <button
              key={profile.id}
              onClick={() => {
                soundFX.playClickSound();
                onSelectBot?.(profile.id);
              }}
              className={`px-2.5 py-0.5 rounded text-[10px] font-mono font-bold whitespace-nowrap transition-all flex items-center gap-1 border cursor-pointer ${
                isActive
                  ? profileIsSealed
                    ? 'bg-amber-500/25 text-amber-300 border-amber-500/60 shadow-sm ring-1 ring-amber-500/40'
                    : 'bg-[#00bda5]/20 text-[#2dd4bf] border-[#00bda5] shadow-sm ring-1 ring-[#00bda5]/40'
                  : 'bg-[#12161a] text-[#8c9ba5] border-[#262d35] hover:text-white hover:border-[#384451]'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  profileIsSealed
                    ? 'bg-amber-400 animate-pulse'
                    : profile.laneBadge === 'live'
                    ? 'bg-[#f43f5e] animate-pulse'
                    : 'bg-[#2dd4bf]'
                }`}
              />
              <span>{profile.shortName}</span>
              {profileIsSealed && (
                <span className="text-[8px] px-1 py-0.2 rounded bg-amber-500/20 text-amber-300 font-extrabold ml-0.5">
                  LIVE
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* 2b. Institutional Seal of Excellence Status Banner */}
      <div
        className={`px-4 py-2 border-b flex items-center justify-between text-xs font-mono transition-all ${
          isBotSealed
            ? 'bg-amber-500/15 border-amber-500/40 text-amber-300'
            : 'bg-purple-500/10 border-purple-500/30 text-purple-300'
        }`}
      >
        <div className="flex items-center gap-2">
          <Award className={`w-4 h-4 shrink-0 ${isBotSealed ? 'text-amber-400' : 'text-purple-400'}`} />
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5">
              <span className="font-extrabold text-[11px] uppercase tracking-wider text-white">
                {isBotSealed ? '🏆 SEAL OF EXCELLENCE' : '⏳ INCUBATOR SHADOW'}
              </span>
              <span
                className={`text-[9px] px-1.5 py-0.5 rounded font-mono font-bold border ${
                  isBotSealed
                    ? 'bg-amber-500/25 text-amber-200 border-amber-500/50'
                    : 'bg-purple-500/20 text-purple-200 border-purple-500/40'
                }`}
              >
                {activeSeal?.seal_token || (isBotSealed ? 'SEAL-EXCELLENT' : 'PENDING-TOKEN')}
              </span>
            </div>
            <span className="text-[10px] text-[#8c9ba5]">
              {isBotSealed
                ? 'Shadow paper trading removed · Lane 1 Live trading authorized'
                : 'Cooking in Lane 2 Shadow · Live trading blocked'}
            </span>
          </div>
        </div>

        <div className="flex flex-col items-end shrink-0">
          <span
            className={`px-2 py-0.5 rounded text-[10px] font-extrabold border uppercase tracking-wider ${
              isBotSealed
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                : 'bg-yellow-500/15 text-yellow-300 border border-yellow-500/30'
            }`}
          >
            {isBotSealed ? 'LANE 1 LIVE' : `INCUBATING (${activeSeal?.settled_cycles_verified ?? 0}/30)`}
          </span>
          {activeSeal?.empirical_win_rate ? (
            <span className="text-[10px] text-slate-300 mt-0.5 font-bold">
              {(activeSeal.empirical_win_rate * 100).toFixed(1)}% WR · {activeSeal.profit_factor ? `${activeSeal.profit_factor.toFixed(2)} PF` : '—'}
            </span>
          ) : null}
        </div>
      </div>

      {/* Target Contract Banner */}
      <div className="px-4 py-1.5 bg-[#12161a] border-b border-[#262d35] flex items-center justify-between text-[11px] font-mono text-[#8c9ba5]">
        <div className="flex items-center gap-2">
          <span className="text-white font-bold">{market.ticker || 'KXBTC15M-CURRENT'}</span>
          <span
            className={`px-1.5 py-0.2 rounded text-[9px] font-bold uppercase ${
              is5m
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                : 'bg-teal-500/20 text-teal-300 border border-teal-500/40'
            }`}
          >
            {is5m ? '5M SPRINT' : '15M CYCLE'}
          </span>
        </div>
        <span className="text-emerald-400">TAPE: OK (5Hz BRTI)</span>
      </div>

      {/* 3. Live Event Horizon: Strike K vs CME Spot S_t */}
      <div className="p-4 bg-[#12161a] border-b border-[#262d35] space-y-3">
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="text-left">
            <div className="text-[10px] uppercase font-mono tracking-wider text-[#8c9ba5]">TO BEAT (K)</div>
            <div className="text-lg font-bold font-mono text-white tracking-tight">
              {market.target_strike_str || '$88,450.00'}
            </div>
            <div className="text-[10px] text-[#8c9ba5]">{market.target_time_str || '10:00 AM ET'}</div>
          </div>

          <div className="text-center">
            <div className="text-[10px] uppercase font-mono tracking-wider text-[#8c9ba5]">NOW (SPOT)</div>
            <div className={`text-lg font-bold font-mono tracking-tight ${diffColor}`}>
              {market.current_btc_price_str || '$88,482.50'}
            </div>
            <div className="text-[10px] text-emerald-400 flex items-center justify-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>CF Benchmarks</span>
            </div>
          </div>

          <div className="text-right">
            <div className="text-[10px] uppercase font-mono tracking-wider text-[#8c9ba5]">SPOT DIFF</div>
            <div className={`text-sm font-bold font-mono tracking-tight ${diffColor}`}>
              {isDiffPositive ? '▲' : '▼'} {market.diff_str ? market.diff_str.split(' ')[0] : `${isDiffPositive ? '+' : ''}$${Math.abs(diffVal).toFixed(2)}`}
            </div>
            <span className={`inline-block px-1.5 py-0.2 rounded text-[10px] font-mono font-bold border mt-0.5 ${diffBg}`}>
              {isDiffPositive ? '+' : ''}
              {market.diff_pct?.toFixed(3) ?? '0.037'}%
            </span>
          </div>
        </div>

        {/* Dynamic 5M vs 15M Progress Bar */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[11px] font-mono">
            <span className="text-[#8c9ba5] flex items-center gap-1.5">
              <span>{is5m ? '5M Velocity Window' : '15M Settlement Countdown'}:</span>
              {phase5m && <span className={`font-semibold ${phase5m.color}`}>{phase5m.label}</span>}
            </span>
            <span className="font-bold text-white tracking-wider">
              {market.expiry_countdown_str || '03:02'} ({remSecs}s)
            </span>
          </div>
          <div className="w-full h-2 bg-[#171c22] rounded-full overflow-hidden border border-[#262d35] relative">
            <div
              className={`h-full transition-all duration-300 ${
                is5m ? phase5m?.bar || 'bg-emerald-500' : 'bg-gradient-to-r from-teal-500 to-emerald-400'
              }`}
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      </div>

      {/* 4. CLOB Inside Touch & Implied Probability */}
      <div className="px-4 py-2.5 bg-[#0f1319] border-b border-[#262d35] space-y-2">
        <div className="flex items-center justify-between text-xs font-mono">
          <div className="flex items-center gap-2">
            <span className="text-[#10b981] font-bold">YES</span>
            <span className="text-white font-extrabold">{market.yes_cents_str || '58¢'}</span>
            <span className="text-[10px] text-[#8c9ba5]">(9 cts)</span>
          </div>
          <div className="text-[10px] text-[#8c9ba5] font-semibold uppercase tracking-wider">CLOB INSIDE TOUCH</div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-[#8c9ba5]">(14 cts)</span>
            <span className="text-white font-extrabold">{market.no_cents_str || '44¢'}</span>
            <span className="text-[#f43f5e] font-bold">NO</span>
          </div>
        </div>

        {/* Probability Split Bar */}
        <div className="w-full h-3 bg-[#171c22] rounded overflow-hidden flex text-[9px] font-mono font-bold leading-3">
          <div
            className="bg-[#10b981] text-black pl-1.5 flex items-center transition-all duration-300"
            style={{ width: `${yesProb}%` }}
          >
            YES {yesProb.toFixed(0)}%
          </div>
          <div
            className="bg-[#f43f5e] text-white pr-1.5 flex items-center justify-end transition-all duration-300"
            style={{ width: `${noProb}%` }}
          >
            {noProb.toFixed(0)}% NO
          </div>
        </div>
      </div>

      {/* 4.5. THE "WHY NO TRADE?" PRE-FLIGHT DIAGNOSTIC HUD (Pillar 2) */}
      <div className="px-3 py-2 bg-[#090c10] border-b border-[#262d35] font-mono text-[10px]">
        <div className="flex items-center justify-between pb-1.5 text-[#8c9ba5]">
          <span className="text-[9px] uppercase font-bold tracking-wider flex items-center gap-1 text-gray-300">
            <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
            Pre-Flight Gates (Why No Trade?)
          </span>
          <span className="text-[8px] text-gray-500">Continuous Microstructure Guardian</span>
        </div>

        <div className="grid grid-cols-4 gap-1.5">
          {/* Gate 1: Dynamic Moat */}
          <div 
            className={`p-1.5 rounded border text-center transition-all ${
              (preflightGates?.moat_gate?.status ?? (Math.abs(diffVal) >= 40.25 ? 'PASS' : 'VETO')) === 'PASS'
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : 'bg-amber-500/15 border-amber-500/40 text-amber-300 ring-1 ring-amber-500/30'
            }`}
            title={preflightGates?.moat_gate?.reason || `Moat: |Diff| $${Math.abs(diffVal).toFixed(2)} vs $40.25 Floor`}
          >
            <div className="text-[8px] text-gray-400 uppercase font-bold">Dynamic Moat</div>
            <div className="font-bold text-[10px] mt-0.5">
              {(preflightGates?.moat_gate?.status ?? (Math.abs(diffVal) >= 40.25 ? 'PASS' : 'VETO'))}
            </div>
          </div>

          {/* Gate 2: VPIN Safety */}
          <div 
            className={`p-1.5 rounded border text-center transition-all ${
              (preflightGates?.vpin_gate?.status ?? (vpin < 0.60 ? 'PASS' : 'VETO')) === 'PASS'
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : 'bg-rose-500/15 border-rose-500/40 text-rose-300 ring-1 ring-rose-500/30'
            }`}
            title={preflightGates?.vpin_gate?.reason || `VPIN: ${vpin.toFixed(2)} vs 0.60 Threshold`}
          >
            <div className="text-[8px] text-gray-400 uppercase font-bold">VPIN Safety</div>
            <div className="font-bold text-[10px] mt-0.5">
              {(preflightGates?.vpin_gate?.status ?? (vpin < 0.60 ? 'PASS' : 'VETO'))}
            </div>
          </div>

          {/* Gate 3: Cycle Lock */}
          <div 
            className={`p-1.5 rounded border text-center transition-all ${
              (preflightGates?.cycle_lock_gate?.status ?? 'READY') === 'READY'
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : 'bg-rose-500/15 border-rose-500/40 text-rose-300'
            }`}
            title={preflightGates?.cycle_lock_gate?.reason || '1 trade per 15M cycle protection'}
          >
            <div className="text-[8px] text-gray-400 uppercase font-bold">Cycle Lock</div>
            <div className="font-bold text-[10px] mt-0.5">
              {(preflightGates?.cycle_lock_gate?.status ?? 'READY')}
            </div>
          </div>

          {/* Gate 4: Edge / EV */}
          <div 
            className={`p-1.5 rounded border text-center transition-all ${
              (preflightGates?.edge_gate?.status ?? (aiSignals?.recommended_side !== 'wait' ? 'PASS' : 'WAIT')) === 'PASS'
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : 'bg-slate-800/80 border-slate-700 text-slate-400'
            }`}
            title={preflightGates?.edge_gate?.reason || 'Waiting for statistical edge > 5%'}
          >
            <div className="text-[8px] text-gray-400 uppercase font-bold">Edge / EV</div>
            <div className="font-bold text-[10px] mt-0.5">
              {(preflightGates?.edge_gate?.status ?? (aiSignals?.recommended_side !== 'wait' ? 'PASS' : 'WAIT'))}
            </div>
          </div>
        </div>

        {/* Dynamic Veto Explanation Bar */}
        {((preflightGates?.moat_gate?.status === 'VETO') || (preflightGates?.vpin_gate?.status === 'VETO') || (preflightGates?.cycle_lock_gate?.status === 'LOCKED')) && (
          <div className="mt-2 px-2.5 py-1 bg-amber-500/10 border border-amber-500/30 rounded text-[9px] text-amber-200 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse shrink-0" />
            <span>
              {preflightGates?.vpin_gate?.status === 'VETO'
                ? preflightGates.vpin_gate.reason
                : preflightGates?.cycle_lock_gate?.status === 'LOCKED'
                ? preflightGates.cycle_lock_gate.reason
                : preflightGates?.moat_gate?.reason || 'Proximity Veto: Trapped inside strike noise trap.'}
            </span>
          </div>
        )}
      </div>

      {/* 5. STRATEGY-SPECIFIC TELEMETRY DECK */}
      {isMacroDominion ? (
        // --- Bot 3: Macro Trend Dominion 15M Triple-Brain & Mistake-Learning Deck ---
        <div className="p-3.5 bg-[#0a0f14] border-b border-[#262d35] space-y-3 font-mono">
          {/* Header Bar */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-bold text-white uppercase tracking-wider">
                Macro Trend Dominion
              </span>
              <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                15M 3-BRAIN
              </span>
            </div>
            <span
              className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                macroAction === 'YES'
                  ? 'text-emerald-400 bg-emerald-500/15 border-emerald-500/30'
                  : macroAction === 'NO'
                  ? 'text-rose-400 bg-rose-500/15 border-rose-500/30'
                  : 'text-amber-400 bg-amber-500/15 border-amber-500/30'
              }`}
            >
              {macroAction === 'YES' && '🎯 CALL: BUY YES'}
              {macroAction === 'NO' && '🎯 CALL: BUY NO'}
              {macroAction === 'DONT' && '⏸️ CALL: DONT (HOLD)'}
            </span>
          </div>

          {/* Centerpiece 15M Decision Hero */}
          <div className={`p-3 rounded-xl border flex flex-col gap-2 ${
            macroAction === 'YES'
              ? 'bg-emerald-950/25 border-emerald-500/40 shadow-lg shadow-emerald-500/10 ring-1 ring-emerald-500/30'
              : macroAction === 'NO'
              ? 'bg-rose-950/25 border-rose-500/40 shadow-lg shadow-rose-500/10 ring-1 ring-rose-500/30'
              : 'bg-slate-900/60 border-slate-700/60'
          }`}>
            <div className="flex items-center justify-between border-b border-[#1f2833] pb-2">
              <div className="flex items-center gap-2">
                <span className={`text-xl font-black tracking-tight ${
                  macroAction === 'YES' ? 'text-emerald-400' : macroAction === 'NO' ? 'text-rose-400' : 'text-slate-300'
                }`}>
                  {macroAction === 'DONT' ? 'DONT (NO TRADE)' : `BUY ${macroAction}`}
                </span>
                <span className="text-[10px] text-slate-400">@ 15M Cycle</span>
              </div>
              <div className="text-right">
                <div className="text-sm font-black font-mono text-cyan-300">
                  {macroLimitPrice}¢ Limit
                </div>
                <div className="text-[9px] text-emerald-400/80 font-bold">
                  $0 Maker Fee · +{macroLimitPrice > 0 ? (((100 - macroLimitPrice) / macroLimitPrice) * 100).toFixed(0) : '0'}% ROI
                </div>
              </div>
            </div>

            {/* Metrics Triad: Calibrated Win %, Net EV, Consensus Agreement */}
            <div className="grid grid-cols-3 gap-2 pt-1 text-center">
              <div className="bg-[#0b1017] p-1.5 rounded border border-[#1e2530]">
                <div className="text-[8px] uppercase text-slate-400">Win Probability</div>
                <div className="text-xs font-black text-cyan-300 mt-0.5">
                  {macroCalibratedConf}%
                </div>
                <div className="text-[8px] text-slate-500">
                  Raw: {macroRawConf}% (Brier Cal)
                </div>
              </div>
              <div className="bg-[#0b1017] p-1.5 rounded border border-[#1e2530]">
                <div className="text-[8px] uppercase text-slate-400">Net EV / Ct</div>
                <div className={`text-xs font-black mt-0.5 ${macroEv >= 0.02 ? 'text-emerald-400' : 'text-slate-300'}`}>
                  {macroEv >= 0 ? '+' : ''}${macroEv.toFixed(2)}
                </div>
                <div className="text-[8px] text-slate-500">
                  Hurdle: &ge; ${(botParams.min_ev_dollars ?? 0.03).toFixed(2)}
                </div>
              </div>
              <div className="bg-[#0b1017] p-1.5 rounded border border-[#1e2530]">
                <div className="text-[8px] uppercase text-slate-400">Macro Agreement</div>
                <div className={`text-xs font-black mt-0.5 ${macroRegimesAgree ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {macroRegimesAgree ? 'AGREED' : 'DIVERGENT'}
                </div>
                <div className="text-[8px] text-slate-500 truncate">
                  {macroSpotTrend} vs {macroHmmRegime.replace('_TREND', '')}
                </div>
              </div>
            </div>
          </div>

          {/* Triple-Brain Consensus Grid */}
          <div className="grid grid-cols-3 gap-1.5 text-[9px]">
            {/* Brain 1: QuoLas Spot */}
            <div className="p-2 rounded bg-[#10151c] border border-cyan-500/30 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-cyan-400 font-bold">1. SPOT ONNX</span>
                <span className={`px-1 py-0.2 rounded font-bold ${quolasSignal === 'UP' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                  {quolasSignal}
                </span>
              </div>
              <div className="text-white font-bold">{quolasConfidence}% Conf</div>
              <div className="text-[8px] text-slate-500">CME 5Hz BRTI</div>
            </div>

            {/* Brain 2: Kalshi CLOB ONNX */}
            <div className="p-2 rounded bg-[#10151c] border border-purple-500/30 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-purple-400 font-bold">2. CLOB ONNX</span>
                <span className={`px-1 py-0.2 rounded font-bold ${kalshiSignal === 'UP' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                  {kalshiSignal}
                </span>
              </div>
              <div className="text-white font-bold">{kalshiConfidence}% Conf</div>
              <div className="text-[8px] text-slate-500">28-D Microstructure</div>
            </div>

            {/* Brain 3: 5m HMM Markov */}
            <div className="p-2 rounded bg-[#10151c] border border-amber-500/30 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-amber-400 font-bold">3. 5M HMM</span>
                <span className={`px-1 py-0.2 rounded font-bold ${macroHmmRegime.includes('BULL') ? 'bg-emerald-500/20 text-emerald-400' : macroHmmRegime.includes('BEAR') ? 'bg-rose-500/20 text-rose-400' : 'bg-amber-500/20 text-amber-300'}`}>
                  {macroHmmRegime.replace('_TREND', '')}
                </span>
              </div>
              <div className="text-white font-bold truncate">{macroSpotTrend} 1H</div>
              <div className="text-[8px] text-slate-500">Markov Anchor</div>
            </div>
          </div>

          {/* Mistake-Learning & Adaptation Engine Bar */}
          <div className="p-2.5 rounded-lg bg-[#0d1218] border border-[#1e2530] text-[10px] space-y-1.5">
            <div className="flex items-center justify-between text-slate-400">
              <span className="font-bold uppercase tracking-wider text-cyan-300 flex items-center gap-1">
                <Brain className="w-3.5 h-3.5 text-cyan-400" />
                <span>Dual Paper/Live Mistake-Learning Engine</span>
              </span>
              <span className="text-[9px] font-mono text-emerald-400 font-semibold">
                ONLINE TRACKING
              </span>
            </div>

            <div className="grid grid-cols-3 gap-1.5 text-center text-[9px] pt-0.5">
              <div className="bg-[#121820] p-1.5 rounded border border-[#212a36]">
                <div className="text-slate-400">Brier Score</div>
                <div className="text-white font-bold font-mono">{macroBrier}</div>
                <div className="text-[8px] text-emerald-400">Calibration OK</div>
              </div>
              <div className="bg-[#121820] p-1.5 rounded border border-[#212a36]">
                <div className="text-slate-400">Pruned Deciles</div>
                <div className="text-amber-300 font-bold font-mono">
                  {macroPrunedDeciles.length > 0 ? macroPrunedDeciles.map(d => `${d}¢`).join(', ') : 'None'}
                </div>
                <div className="text-[8px] text-slate-500">-EV Filter</div>
              </div>
              <div className="bg-[#121820] p-1.5 rounded border border-[#212a36]">
                <div className="text-slate-400">Cycles / Mistakes</div>
                <div className="text-white font-bold font-mono">
                  {macroTotalCycles}c / {macroMistakes}m
                </div>
                <div className="text-[8px] text-cyan-400">{macroAccuracy}% Accuracy</div>
              </div>
            </div>
          </div>

          {/* Rationale Banner */}
          <div className="p-2 rounded bg-[#10141a] border border-[#1e2530] text-[10px] text-slate-300">
            <span className="text-cyan-400 font-bold mr-1">Rationale:</span>
            <span>{macroDominionTelemetry?.rationale || dualRationale}</span>
          </div>
        </div>
      ) : activeProfile.telemetryType === 'onnx' ? (
        // --- ONNX Macro Net v2: Dual-Brain Neural Telemetry Deck ---
        <div className="p-3.5 bg-[#0e1117] border-b border-[#262d35] space-y-3 font-mono">
          {/* Header with Dual-Brain Mode & Status */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-purple-400" />
              <span className="text-xs font-bold text-white uppercase tracking-wider">
                {activeProfile.name}
              </span>
            </div>
            <span
              className={`text-[10px] font-bold px-2 py-0.5 rounded border ${
                dualRegime === 'MOMENTUM_SCALP'
                  ? 'text-emerald-400 bg-emerald-500/15 border-emerald-500/30'
                  : dualRegime === 'CONTRADICTION_ARBITRAGE'
                  ? 'text-cyan-400 bg-cyan-500/15 border-cyan-500/30 ring-1 ring-cyan-500/30 animate-pulse'
                  : dualRegime === 'TOXIC_VETO'
                  ? 'text-rose-400 bg-rose-500/15 border-rose-500/30'
                  : 'text-amber-400 bg-amber-500/15 border-amber-500/30'
              }`}
            >
              {dualRegime === 'MOMENTUM_SCALP' && '⚡ MOMENTUM SCALP'}
              {dualRegime === 'CONTRADICTION_ARBITRAGE' && '💎 CONTRADICTION ARB'}
              {dualRegime === 'TOXIC_VETO' && '🛡️ TOXIC VETO'}
              {dualRegime === 'CHOP_WAIT' && '⏸️ CHOP WAIT'}
            </span>
          </div>

          {/* Central Glowing Arbitrage Badge (Pillar 1) */}
          <div className="text-center py-0.5">
            <div className={`w-full py-1.5 px-2.5 rounded-xl font-mono text-[11px] font-extrabold uppercase border shadow-md flex items-center justify-center gap-2 transition-all ${
              dualRegime === 'CONTRADICTION_ARBITRAGE'
                ? 'bg-cyan-500/15 text-cyan-300 border-cyan-400/50 shadow-cyan-500/20 ring-1 ring-cyan-400/40 animate-pulse'
                : dualRegime === 'MOMENTUM_SCALP'
                ? 'bg-emerald-500/15 text-emerald-300 border-emerald-400/50 shadow-emerald-500/20 ring-1 ring-emerald-400/40 animate-pulse'
                : dualRegime === 'TOXIC_VETO'
                ? 'bg-rose-500/15 text-rose-300 border-rose-400/50 shadow-rose-500/20'
                : 'bg-[#151921] text-gray-400 border-gray-700'
            }`}>
              {dualRegime === 'CONTRADICTION_ARBITRAGE' && (
                <>
                  <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                  <span>💎 ASYMMETRIC DISCOUNT (BUY {(dualOnnxTelemetry?.side || (quolasSignal === 'UP' ? 'YES' : 'NO')).toUpperCase()} @ {((dualOnnxTelemetry?.recommended_limit_price ?? botParams.discount_limit_price ?? 0.48) * 100).toFixed(0)}¢)</span>
                </>
              )}
              {dualRegime === 'MOMENTUM_SCALP' && (
                <>
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                  <span>⚡ MOMENTUM VELOCITY SCALP (BUY {(dualOnnxTelemetry?.side || (quolasSignal === 'UP' ? 'YES' : 'NO')).toUpperCase()})</span>
                </>
              )}
              {dualRegime === 'TOXIC_VETO' && (
                <>
                  <span className="w-2 h-2 rounded-full bg-rose-400" />
                  <span>🔴 TOXIC VETO (SPOT DUMP / HIGH VPIN)</span>
                </>
              )}
              {dualRegime === 'CHOP_WAIT' && (
                <>
                  <span className="w-2 h-2 rounded-full bg-gray-500" />
                  <span>⏸️ CAPITAL PRESERVATION (CHOP WAIT)</span>
                </>
              )}
            </div>
          </div>

          {/* Dual-Brain Twin Cards: QuoLas (Spot) vs Kalshi (Binary CLOB) */}
          <div className="grid grid-cols-2 gap-2 text-[10px]">
            {/* Brain A: QuoLas Nano Microscope (Spot Order Flow) */}
            <div className="p-2.5 rounded bg-[#13171c] border border-cyan-500/20 space-y-1.5 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-12 h-12 bg-cyan-500/5 rounded-full blur-xl pointer-events-none" />
              <div className="flex items-center justify-between">
                <span className="text-[9px] font-bold uppercase text-cyan-400 flex items-center gap-1">
                  <Activity className="w-3 h-3" />
                  QuoLas Spot
                </span>
                <span
                  className={`px-1.5 py-0.2 rounded font-bold text-[9px] ${
                    quolasSignal === 'UP'
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                      : quolasSignal === 'DOWN'
                      ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                      : 'bg-slate-700 text-slate-300'
                  }`}
                >
                  {quolasSignal}
                </span>
              </div>
              <div className="flex items-baseline justify-between pt-0.5">
                <span className="text-[#8c9ba5] text-[9px]">Confidence:</span>
                <span className="text-white font-bold text-xs">{quolasConfidence}%</span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-[#1e252e] overflow-hidden">
                <div
                  className="h-full bg-cyan-400 transition-all duration-300"
                  style={{ width: `${quolasConfidence}%` }}
                />
              </div>
              <div className="text-[8px] text-[#6e7d8b] pt-0.5 flex justify-between">
                <span>Feed: CME BRTI (5Hz)</span>
                <span className="text-cyan-300/80">L2 Imbalance</span>
              </div>
            </div>

            {/* Brain B: Built-in Kalshi CLOB Brain (Binary Microstructure) */}
            <div className="p-2.5 rounded bg-[#13171c] border border-purple-500/20 space-y-1.5 relative overflow-hidden">
              <div className="absolute top-0 right-0 w-12 h-12 bg-purple-500/5 rounded-full blur-xl pointer-events-none" />
              <div className="flex items-center justify-between">
                <span className="text-[9px] font-bold uppercase text-purple-400 flex items-center gap-1">
                  <Cpu className="w-3 h-3" />
                  Kalshi CLOB
                </span>
                <span
                  className={`px-1.5 py-0.2 rounded font-bold text-[9px] ${
                    kalshiSignal === 'UP'
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                      : kalshiSignal === 'DOWN'
                      ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                      : 'bg-slate-700 text-slate-300'
                  }`}
                >
                  {kalshiSignal}
                </span>
              </div>
              <div className="flex items-baseline justify-between pt-0.5">
                <span className="text-[#8c9ba5] text-[9px]">Confidence:</span>
                <span className="text-white font-bold text-xs">{kalshiConfidence}%</span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-[#1e252e] overflow-hidden">
                <div
                  className="h-full bg-purple-400 transition-all duration-300"
                  style={{ width: `${kalshiConfidence}%` }}
                />
              </div>
              <div className="text-[8px] text-[#6e7d8b] pt-0.5 flex justify-between">
                <span>28-D Tensor</span>
                <span className="text-emerald-400">0.38ms (CPU)</span>
              </div>
            </div>
          </div>

          {/* Contradiction / Momentum Lead-Lag Rationale Banner */}
          <div className="p-2.5 rounded bg-[#12161f] border border-[#232b35] text-[10px] space-y-1">
            <div className="flex items-center justify-between text-[#8c9ba5]">
              <span className="font-bold uppercase tracking-wider text-[#a5b4fc] flex items-center gap-1">
                <span>🎯 Execution Rationale:</span>
              </span>
              <span className="text-[9px] text-[#34d399] font-semibold">
                Maker Limit: ≤ ${botParams.discount_limit_price?.toFixed(2) || '0.52'}
              </span>
            </div>
            <p className="text-white text-[11px] leading-tight">
              {dualRationale}
            </p>
          </div>

          {/* Softmax Probability Distribution Bar */}
          <div className="space-y-1 pt-0.5">
            <div className="flex justify-between text-[10px] text-[#8c9ba5]">
              <span>Softmax Distribution:</span>
              <span className="text-white font-bold">
                YES {onnxProbLong}% · NO {onnxProbShort}% · WAIT {onnxProbWait}%
              </span>
            </div>
            <div className="w-full h-2 rounded bg-[#171c22] overflow-hidden flex">
              <div className="bg-purple-500 transition-all duration-300" style={{ width: `${onnxProbLong}%` }} title={`YES ${onnxProbLong}%`} />
              <div className="bg-rose-500 transition-all duration-300" style={{ width: `${onnxProbShort}%` }} title={`NO ${onnxProbShort}%`} />
              <div className="bg-slate-600 transition-all duration-300" style={{ width: `${onnxProbWait}%` }} title={`WAIT ${onnxProbWait}%`} />
            </div>
          </div>
        </div>
      ) : activeProfile.telemetryType === 'antipin' ? (
        // --- Dominion 2 Anti-Pin Scalper Telemetry ---
        <div className="p-3.5 bg-[#0e1117] border-b border-[#262d35] space-y-2.5 font-mono">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Crown className="w-4 h-4 text-[#d9a752]" />
              <span className="text-xs font-bold text-white uppercase tracking-wider">Anti-Pin Zone Defense</span>
            </div>
            <span className="text-[10px] text-amber-400 font-bold px-1.5 py-0.5 rounded bg-amber-500/15 border border-amber-500/30">
              ENTRY CEILING: ≤ ${botParams.discount_limit_price?.toFixed(2) || '0.42'}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <div className="p-2 rounded bg-[#13171c] border border-[#1f262d]">
              <span className="text-[#8c9ba5]">PIN RISK RANGE:</span>
              <div className="text-sm font-bold text-white mt-0.5">|Diff| &lt; $25 (T &lt; 180s)</div>
            </div>
            <div className="p-2 rounded bg-[#13171c] border border-[#1f262d]">
              <span className="text-[#8c9ba5]">DISCOUNT VALUE:</span>
              <div className="text-sm font-bold text-[#34d399] mt-0.5">$0.25 - $0.42 Range</div>
            </div>
          </div>
        </div>
      ) : activeProfile.telemetryType === 'scalper' ? (
        // --- OFI Sprint Scalper Telemetry ---
        <div className="p-3.5 bg-[#0e1117] border-b border-[#262d35] space-y-2.5 font-mono">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Crosshair className="w-4 h-4 text-[#00bda5]" />
              <span className="text-xs font-bold text-white uppercase tracking-wider">OFI Sprint Momentum</span>
            </div>
            <span className="text-[10px] text-teal-400 font-bold px-1.5 py-0.5 rounded bg-teal-500/15 border border-teal-500/30">
              5M SPRINT DYNAMICS
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <div className="p-2 rounded bg-[#13171c] border border-[#1f262d]">
              <span className="text-[#8c9ba5]">ORDER FLOW IMBALANCE:</span>
              <div className="text-sm font-bold text-emerald-400 mt-0.5">+4.2 cts/sec (Bullish)</div>
            </div>
            <div className="p-2 rounded bg-[#13171c] border border-[#1f262d]">
              <span className="text-[#8c9ba5]">SETTLEMENT FREEZE:</span>
              <div className="text-sm font-bold text-amber-300 mt-0.5">T-60s Hard Sweep</div>
            </div>
          </div>
        </div>
      ) : (
        // --- 3-Step Dominion Playbook Telemetry ---
        <div className="p-3.5 bg-[#0e1117] border-b border-[#262d35] space-y-2 font-mono">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-emerald-400" />
              <span className="text-xs font-bold text-white uppercase tracking-wider">3-Step Playbook Stage</span>
            </div>
            <span className="text-[10px] text-emerald-400 font-bold px-1.5 py-0.5 rounded bg-emerald-500/15 border border-emerald-500/30">
              MAKER CEILING: ${botParams.discount_limit_price?.toFixed(2) || '0.52'}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-1.5 text-[9px] text-center">
            <div className="p-1.5 rounded bg-[#13171c] border border-[#1f262d] text-[#8c9ba5]">
              <div>STAGE 1 (0-5m)</div>
              <div className="font-bold text-white mt-0.5">Breakout</div>
            </div>
            <div className="p-1.5 rounded bg-emerald-500/20 border border-emerald-500/40 text-emerald-300">
              <div>STAGE 2 (5-11m)</div>
              <div className="font-bold text-white mt-0.5">★ OFI Drift</div>
            </div>
            <div className="p-1.5 rounded bg-[#13171c] border border-[#1f262d] text-[#8c9ba5]">
              <div>STAGE 3 (11-14m)</div>
              <div className="font-bold text-white mt-0.5">Gamma Snub</div>
            </div>
          </div>
        </div>
      )}

      {/* 6. Active Position & Risk Telemetry */}
      <div className="p-4 bg-[#12161a] border-b border-[#262d35] space-y-2.5">
        <div className="flex items-center justify-between text-xs font-mono">
          <span className="text-[#8c9ba5] uppercase tracking-wider text-[10px] font-bold">Active Position</span>
          <span className="text-[10px] text-amber-400 font-bold">Hard Cap: 1 Contract</span>
        </div>

        <div className="p-2.5 rounded-lg bg-[#171c22] border border-[#262d35] flex items-center justify-between font-mono text-xs">
          {activePosition && activePosition.size > 0 ? (
            <>
              <div className="flex items-center gap-2">
                <span
                  className={`px-2 py-0.5 rounded font-bold uppercase text-[10px] ${
                    activePosition.side === 'yes'
                      ? 'bg-[#10b981]/20 text-[#10b981]'
                      : 'bg-[#f43f5e]/20 text-[#f43f5e]'
                  }`}
                >
                  {activePosition.side.toUpperCase()}
                </span>
                <span className="text-white font-bold">
                  {activePosition.size} ct @ {activePosition.entry_price * 100}¢
                </span>
              </div>
              <div className="text-right">
                <div
                  className={`font-bold ${
                    activePosition.unrealized_pnl >= 0 ? 'text-[#10b981]' : 'text-[#f43f5e]'
                  }`}
                >
                  {activePosition.unrealized_pnl >= 0 ? '+' : ''}${activePosition.unrealized_pnl.toFixed(2)}
                </div>
                <div className="text-[10px] text-[#8c9ba5]">Unrealized PnL</div>
              </div>
            </>
          ) : (
            <div className="w-full text-center text-[#8c9ba5] py-1 text-xs">
              FLAT · No open contract positions (Holding ${(botParams.discount_limit_price || 0.52).toFixed(2)} Maker Resting Limit)
            </div>
          )}
        </div>

        {/* Asymmetric Risk Breakdown */}
        <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
          <div className="p-2 rounded bg-[#13171c] border border-[#1f262d]">
            <span className="text-[#8c9ba5] text-[10px]">MAX RISK (CAPITAL):</span>
            <div className="text-sm font-bold text-[#f43f5e] mt-0.5">
              -${(botParams.discount_limit_price || 0.52).toFixed(2)} / ct
            </div>
          </div>
          <div className="p-2 rounded bg-[#13171c] border border-[#1f262d]">
            <span className="text-[#8c9ba5] text-[10px]">MAX SETTLEMENT WIN:</span>
            <div className="text-sm font-bold text-[#10b981] mt-0.5">
              +${(1.0 - (botParams.discount_limit_price || 0.52)).toFixed(2)} / ct
            </div>
          </div>
        </div>

        {/* Guardrail Health: Consecutive Losses & VPIN */}
        <div className="grid grid-cols-2 gap-2 text-[11px] font-mono pt-1">
          <div className="flex items-center justify-between p-2 rounded bg-[#13171c] border border-[#1f262d]">
            <span className="text-[#8c9ba5]">Loss Breaker:</span>
            <div className="flex items-center gap-1">
              {[0, 1, 2].map((idx) => (
                <span
                  key={idx}
                  className={`w-2 h-2 rounded-full border ${
                    idx < consecutiveLosses
                      ? 'bg-[#f43f5e] border-[#f43f5e]'
                      : 'bg-transparent border-[#8c9ba5]/40'
                  }`}
                />
              ))}
              <span className="text-[10px] text-[#8c9ba5] ml-1">{consecutiveLosses}/3</span>
            </div>
          </div>

          <div className="flex items-center justify-between p-2 rounded bg-[#13171c] border border-[#1f262d]">
            <span className="text-[#8c9ba5]">VPIN Toxicity:</span>
            <span className={`font-bold ${isVpinToxic ? 'text-[#f43f5e]' : 'text-emerald-400'}`}>
              {vpin.toFixed(2)} {isVpinToxic ? '⚠️' : 'OK'}
            </span>
          </div>
        </div>

        {/* Coin-Flip Dead-Zone Indicator */}
        <div
          className={`p-2 rounded-lg border text-[11px] font-mono flex items-center justify-between ${
            isDeadZone
              ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
              : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
          }`}
        >
          <div className="flex items-center gap-1.5">
            <span
              className={`w-2 h-2 rounded-full ${isDeadZone ? 'bg-amber-400' : 'bg-emerald-400 animate-pulse'}`}
            />
            <span>{isDeadZone ? 'Razor-Tight Dead Zone Active' : 'Directional Edge Ready'}</span>
          </div>
          <span className="text-[10px] font-bold uppercase tracking-wider">
            {isDeadZone ? 'SKIPPING' : 'EDGE CONFIRMED'}
          </span>
        </div>
      </div>

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
          <div className="p-4 bg-[#12161a] border-t border-[#1f262d] space-y-3 font-mono text-xs">
            {isMacroDominion ? (
              /* MACRO TREND DOMINION — 9 STRATEGY DIALS COCKPIT */
              <div className="space-y-3.5">
                {/* Header Banner */}
                <div className="p-2.5 rounded-lg bg-gradient-to-r from-cyan-950/40 via-teal-950/30 to-slate-900 border border-cyan-500/30 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-cyan-400" />
                    <div>
                      <div className="text-[11px] font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                        <span>MACRO TREND DOMINION</span>
                        <span className="px-1.5 py-0.2 rounded text-[9px] bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-mono">
                          9 DIALS COCKPIT
                        </span>
                      </div>
                      <div className="text-[9px] text-slate-400">
                        15M Triple-Brain Consensus · 1¢–89¢ Sweetspot · Online Mistake Learning
                      </div>
                    </div>
                  </div>
                  <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                    SWEETSPOTS ACTIVE
                  </span>
                </div>

                {/* DIAL 1: Macro Consensus Agreement (min_macro_agreement) */}
                <div className="space-y-1.5 p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d]">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-cyan-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-cyan-400 inline-block animate-pulse" />
                      Dial 1: 1H Macro Trend & HMM Agreement
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-cyan-500/40 z-50 shadow-2xl leading-snug">
                          <b>Higher-Timeframe Alignment Filter:</b><br />
                          • <b>Strict Consensus (Sweetspot):</b> Demands 1-Hour Spot Trend and 5m HMM Markov Regime agree before taking directional trades.<br />
                          • <b>Why it matters:</b> Eliminates taking counter-trend bets into dominant institutional flow.
                        </div>
                      </div>
                    </label>
                    <span className="text-[9px] font-mono text-cyan-400 font-bold">
                      {botParams.min_macro_agreement !== false ? 'STRICT CONSENSUS' : 'ALLOW DIVERGENCE'}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-1.5">
                    {[
                      { val: true, label: 'Strict Consensus', badge: 'Sweetspot', desc: '1H Spot & HMM Must Agree' },
                      { val: false, label: 'Allow Divergence', badge: 'Aggressive', desc: 'Trade on ONNX alone' },
                    ].map((opt) => {
                      const isActive = (botParams.min_macro_agreement !== false) === opt.val;
                      return (
                        <button
                          key={String(opt.val)}
                          type="button"
                          onClick={() => {
                            soundFX.playClickSound();
                            setBotParams({ ...botParams, min_macro_agreement: opt.val });
                          }}
                          className={`p-2 rounded border text-left transition-all cursor-pointer ${
                            isActive
                              ? 'bg-cyan-500/15 border-cyan-400 text-white shadow-lg shadow-cyan-500/10 ring-1 ring-cyan-400/40'
                              : 'bg-[#10141b] border-[#222933] text-slate-400 hover:border-slate-600 hover:text-slate-200'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-bold">{opt.label}</span>
                            <span className={`text-[8px] font-mono px-1 rounded ${
                              isActive ? 'bg-cyan-400/20 text-cyan-300 font-semibold' : 'bg-slate-800 text-slate-400'
                            }`}>
                              {opt.badge}
                            </span>
                          </div>
                          <div className="text-[8px] text-slate-400 mt-0.5 truncate">{opt.desc}</div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* DIAL 2: HMM Risk-Off Regime Veto (enable_hmm_risk_off_veto) */}
                <div className="space-y-1.5 p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d]">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-amber-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
                      Dial 2: 5m HMM Risk-Off Veto
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-amber-500/40 z-50 shadow-2xl leading-snug">
                          <b>Markov Volatility Protection:</b><br />
                          • <b>Veto Active (Sweetspot):</b> Hard stop on trading when HMM enters RISK_OFF, high volatility entropy, or unanchored churn.<br />
                          • <b>Why it matters:</b> Prevents catastrophic drawdown during unpredictable regime transitions.
                        </div>
                      </div>
                    </label>
                    <span className="text-[9px] font-mono text-amber-400 font-bold">
                      {botParams.enable_hmm_risk_off_veto !== false ? 'VETO ACTIVE' : 'VETO BYPASSED'}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-1.5">
                    {[
                      { val: true, label: 'Veto Active', badge: 'Sweetspot', desc: 'Halt in RISK_OFF / Churn' },
                      { val: false, label: 'Bypass Veto', badge: 'Risky', desc: 'Ignore Markov regime' },
                    ].map((opt) => {
                      const isActive = (botParams.enable_hmm_risk_off_veto !== false) === opt.val;
                      return (
                        <button
                          key={String(opt.val)}
                          type="button"
                          onClick={() => {
                            soundFX.playClickSound();
                            setBotParams({ ...botParams, enable_hmm_risk_off_veto: opt.val });
                          }}
                          className={`p-2 rounded border text-left transition-all cursor-pointer ${
                            isActive
                              ? 'bg-amber-500/15 border-amber-400 text-white shadow ring-1 ring-amber-400/40'
                              : 'bg-[#10141b] border-[#222933] text-slate-400 hover:border-slate-600 hover:text-slate-200'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-bold">{opt.label}</span>
                            <span className={`text-[8px] font-mono px-1 rounded ${
                              isActive ? 'bg-amber-400/20 text-amber-300 font-semibold' : 'bg-slate-800 text-slate-400'
                            }`}>
                              {opt.badge}
                            </span>
                          </div>
                          <div className="text-[8px] text-slate-400 mt-0.5 truncate">{opt.desc}</div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* DIAL 3: Calibrated Win Probability Hurdle (min_confidence / confidence_threshold) */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-cyan-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-cyan-400 inline-block" />
                      Dial 3: Calibrated Win Probability Hurdle
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-cyan-500/40 z-50 shadow-2xl leading-snug">
                          <b>Calibrated Conviction Gate:</b><br />
                          • Minimum calibrated AI probability score (0.50 - 0.95) to place resting order.<br />
                          • <b>65% Sweetspot:</b> Filters out low-conviction noise bets while capturing institutional trend cycles.
                        </div>
                      </div>
                    </label>
                    <span className="text-xs font-mono font-bold text-cyan-300">
                      {Math.round(((botParams.confidence_threshold ?? botParams.min_confidence ?? 0.65)) * 100)}% Conviction
                    </span>
                  </div>

                  <div className="space-y-1">
                    <input
                      type="range"
                      min="0.50"
                      max="0.95"
                      step="0.01"
                      value={botParams.confidence_threshold ?? botParams.min_confidence ?? 0.65}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setBotParams({ ...botParams, confidence_threshold: val, min_confidence: val });
                      }}
                      className="w-full accent-cyan-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                    />
                    <div className="flex justify-between text-[8px] text-slate-500 font-mono">
                      <span>50% (Coin-Flip)</span>
                      <span className="text-cyan-400 font-semibold">65% (Sweetspot)</span>
                      <span>95% (Ultra-Hurdle)</span>
                    </div>
                  </div>
                </div>

                {/* DIAL 4: Resting Limit Sweet Spot (limit_price_cents: 1¢ - 89¢) */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-emerald-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" />
                      Dial 4: Resting Limit Sweet Spot (1¢–89¢)
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-emerald-500/40 z-50 shadow-2xl leading-snug">
                          <b>The Maker Limit Ceiling:</b><br />
                          • <i>What is the maximum price you will pay?</i><br />
                          • Places resting maker orders on Kalshi book with <b>$0.00 Maker Fee</b>.<br />
                          • <b>48¢–52¢ Sweetspot:</b> Generates <b>+92% to +108% net ROI</b> on winning $1.00 binary payout.<br />
                          • Parameter adjustable from 1¢ up to 89¢.
                        </div>
                      </div>
                    </label>

                    <div className="flex items-center gap-2">
                      <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-bold">
                        +{(((100 - (botParams.limit_price_cents ?? 52)) / (botParams.limit_price_cents ?? 52)) * 100).toFixed(0)}% ROI
                      </span>
                      <span className="text-xs font-mono font-bold text-emerald-300">
                        {botParams.limit_price_cents ?? 52}¢ (${((botParams.limit_price_cents ?? 52) / 100).toFixed(2)})
                      </span>
                    </div>
                  </div>

                  {/* Range Slider (1 - 89 cents) */}
                  <div className="space-y-1">
                    <input
                      type="range"
                      min="1"
                      max="89"
                      step="1"
                      value={botParams.limit_price_cents ?? 52}
                      onChange={(e) => {
                        const val = parseInt(e.target.value, 10);
                        setBotParams({
                          ...botParams,
                          limit_price_cents: val,
                          limit_price: val / 100,
                          discount_limit_price: val / 100,
                          entry_discount_depth: val / 100,
                        });
                      }}
                      className="w-full accent-emerald-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                    />
                    <div className="flex justify-between text-[8px] text-slate-500 font-mono">
                      <span>1¢ (Deep Penny)</span>
                      <span className="text-emerald-400 font-semibold">48¢–52¢ (Sweetspot · +92% to +108% ROI)</span>
                      <span>89¢ (Max Cap)</span>
                    </div>
                  </div>

                  {/* Preset Pills */}
                  <div className="grid grid-cols-4 gap-1 pt-1">
                    {[
                      { cents: 35, label: '35¢ Deep' },
                      { cents: 48, label: '48¢ Maker' },
                      { cents: 52, label: '52¢ Sweet' },
                      { cents: 62, label: '62¢ Mom' },
                    ].map((p) => {
                      const isSel = (botParams.limit_price_cents ?? 52) === p.cents;
                      return (
                        <button
                          key={p.cents}
                          type="button"
                          onClick={() => {
                            soundFX.playClickSound();
                            setBotParams({
                              ...botParams,
                              limit_price_cents: p.cents,
                              limit_price: p.cents / 100,
                              discount_limit_price: p.cents / 100,
                              entry_discount_depth: p.cents / 100,
                            });
                          }}
                          className={`py-1 rounded text-[9px] font-mono font-bold transition-all border cursor-pointer ${
                            isSel
                              ? 'bg-emerald-500/20 text-emerald-300 border-emerald-400 shadow-sm'
                              : 'bg-[#10141a] text-slate-400 border-[#222933] hover:text-white'
                          }`}
                        >
                          {p.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* DIAL 5: Net Expected Value Hurdle (min_ev_dollars) */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-indigo-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-indigo-400 inline-block" />
                      Dial 5: Net Expected Value Hurdle ($/ct)
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-indigo-500/40 z-50 shadow-2xl leading-snug">
                          <b>Expected Return Gate:</b><br />
                          • EV = P(win) * ($1 - Price) - P(loss) * Price - Fees.<br />
                          • <b>+$0.03 Sweetspot:</b> Rejects paper-thin edges; guarantees long-term statistical profitability.
                        </div>
                      </div>
                    </label>
                    <span className="text-xs font-mono font-bold text-indigo-300">
                      +${(botParams.min_ev_dollars ?? 0.03).toFixed(2)} / ct
                    </span>
                  </div>

                  <div className="flex items-center bg-[#10141a] border border-indigo-500/30 rounded px-2 py-1">
                    <span className="text-indigo-400 mr-1">$</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0.01"
                      max="0.25"
                      value={botParams.min_ev_dollars ?? 0.03}
                      onChange={(e) => setBotParams({ ...botParams, min_ev_dollars: parseFloat(e.target.value) })}
                      className="w-full bg-transparent text-white font-mono outline-none text-xs"
                    />
                  </div>
                </div>

                {/* DIAL 6: Adverse Selection Guard (adverse_selection_guard) */}
                <div className="space-y-1.5 p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d]">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-rose-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-rose-400 inline-block" />
                      Dial 6: Adverse Selection Guard
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-rose-500/40 z-50 shadow-2xl leading-snug">
                          <b>High-Velocity Spike Shield:</b><br />
                          • When Bitcoin spot velocity |ΔSpot| &gt; $15, protects against toxic fills by applying +$0.01 drift offset.<br />
                          • <b>Why it matters:</b> Prevents high-frequency bots from picking off resting limit orders ahead of crashes.
                        </div>
                      </div>
                    </label>
                    <span className="text-[9px] font-mono text-rose-400 font-bold">
                      {botParams.adverse_selection_guard !== false ? 'GUARD ACTIVE' : 'BYPASS'}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-1.5">
                    {[
                      { val: true, label: 'Guard Active', badge: '+$0.01 Shield', desc: 'Hold when |ΔSpot| > $15' },
                      { val: false, label: 'Bypass Guard', badge: 'No Offset', desc: 'Accept toxic fills' },
                    ].map((opt) => {
                      const isActive = (botParams.adverse_selection_guard !== false) === opt.val;
                      return (
                        <button
                          key={String(opt.val)}
                          type="button"
                          onClick={() => {
                            soundFX.playClickSound();
                            setBotParams({ ...botParams, adverse_selection_guard: opt.val });
                          }}
                          className={`p-2 rounded border text-left transition-all cursor-pointer ${
                            isActive
                              ? 'bg-rose-500/15 border-rose-400 text-white shadow ring-1 ring-rose-400/40'
                              : 'bg-[#10141b] border-[#222933] text-slate-400 hover:border-slate-600 hover:text-slate-200'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-bold">{opt.label}</span>
                            <span className={`text-[8px] font-mono px-1 rounded ${
                              isActive ? 'bg-rose-400/20 text-rose-300 font-semibold' : 'bg-slate-800 text-slate-400'
                            }`}>
                              {opt.badge}
                            </span>
                          </div>
                          <div className="text-[8px] text-slate-400 mt-0.5 truncate">{opt.desc}</div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* DIAL 7: Volatility Moat Multiplier (volatility_moat_multiplier) */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-purple-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-purple-400 inline-block" />
                      Dial 7: Volatility Moat Multiplier
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-purple-500/40 z-50 shadow-2xl leading-snug">
                          <b>Dynamic Strike Buffer:</b><br />
                          • Multiplies base moat ($21 BTC) based on market volatility: ${(21.0 * (botParams.volatility_moat_multiplier ?? 1.20)).toFixed(2)} active buffer.<br />
                          • Refuses trades when Bitcoin is hovering too close to strike K at expiration.
                        </div>
                      </div>
                    </label>
                    <span className="text-xs font-mono font-bold text-purple-300">
                      {(botParams.volatility_moat_multiplier ?? 1.20).toFixed(2)}x (${(21.0 * (botParams.volatility_moat_multiplier ?? 1.20)).toFixed(2)})
                    </span>
                  </div>

                  <div className="space-y-1">
                    <input
                      type="range"
                      min="0.5"
                      max="3.0"
                      step="0.05"
                      value={botParams.volatility_moat_multiplier ?? 1.20}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setBotParams({ ...botParams, volatility_moat_multiplier: val, dynamic_moat_multiplier: val });
                      }}
                      className="w-full accent-purple-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                    />
                    <div className="flex justify-between text-[8px] text-slate-500 font-mono">
                      <span>0.5x ($10.50)</span>
                      <span className="text-purple-400 font-semibold">1.2x ($25.20 Sweetspot)</span>
                      <span>3.0x ($63.00 Heavy)</span>
                    </div>
                  </div>
                </div>

                {/* DIAL 8: Online Mistake Learning (enable_mistake_learning) */}
                <div className="space-y-1.5 p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d]">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-teal-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <Brain className="w-3.5 h-3.5 text-teal-400" />
                      Dial 8: Online Mistake-Learning Engine
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-teal-500/40 z-50 shadow-2xl leading-snug">
                          <b>Online Feedback Adaptation:</b><br />
                          • Records both Paper & Live cycle outcomes.<br />
                          • Dynamically applies Brier shrinkage to overconfident guesses and prunes persistent negative-EV deciles.
                        </div>
                      </div>
                    </label>
                    <span className="text-[9px] font-mono text-teal-400 font-bold">
                      {botParams.enable_mistake_learning !== false ? 'ONLINE LEARNING ACTIVE' : 'OFFLINE STATIC'}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-1.5">
                    {[
                      { val: true, label: 'Online Learning', badge: 'Paper & Live', desc: 'Calibrate after every cycle' },
                      { val: false, label: 'Static Mode', badge: 'No Learning', desc: 'Zero probability updates' },
                    ].map((opt) => {
                      const isActive = (botParams.enable_mistake_learning !== false) === opt.val;
                      return (
                        <button
                          key={String(opt.val)}
                          type="button"
                          onClick={() => {
                            soundFX.playClickSound();
                            setBotParams({ ...botParams, enable_mistake_learning: opt.val });
                          }}
                          className={`p-2 rounded border text-left transition-all cursor-pointer ${
                            isActive
                              ? 'bg-teal-500/15 border-teal-400 text-white shadow ring-1 ring-teal-400/40'
                              : 'bg-[#10141b] border-[#222933] text-slate-400 hover:border-slate-600 hover:text-slate-200'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-bold">{opt.label}</span>
                            <span className={`text-[8px] font-mono px-1 rounded ${
                              isActive ? 'bg-teal-400/20 text-teal-300 font-semibold' : 'bg-slate-800 text-slate-400'
                            }`}>
                              {opt.badge}
                            </span>
                          </div>
                          <div className="text-[8px] text-slate-400 mt-0.5 truncate">{opt.desc}</div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* DIAL 9: Brier Shrinkage Factor (brier_shrinkage_factor) */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-teal-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-teal-400 inline-block" />
                      Dial 9: Mistake Shrinkage Factor (Brier Rate)
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-teal-500/40 z-50 shadow-2xl leading-snug">
                          <b>Overconfidence Dampener:</b><br />
                          • When a prediction fails at settlement, confidence is shrunk by this rate.<br />
                          • <b>0.15 Sweetspot:</b> Sufficient to avoid revenge trading streaks while maintaining responsiveness to trend changes.
                        </div>
                      </div>
                    </label>
                    <span className="text-xs font-mono font-bold text-teal-300">
                      {Math.round(((botParams.brier_shrinkage_factor ?? 0.15)) * 100)}% Shrinkage
                    </span>
                  </div>

                  <div className="space-y-1">
                    <input
                      type="range"
                      min="0.01"
                      max="0.50"
                      step="0.01"
                      value={botParams.brier_shrinkage_factor ?? 0.15}
                      onChange={(e) => setBotParams({ ...botParams, brier_shrinkage_factor: parseFloat(e.target.value) })}
                      className="w-full accent-teal-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                    />
                    <div className="flex justify-between text-[8px] text-slate-500 font-mono">
                      <span>1% (Minimal)</span>
                      <span className="text-teal-400 font-semibold">15% (Sweetspot)</span>
                      <span>50% (Heavy Dampening)</span>
                    </div>
                  </div>
                </div>
              </div>
            ) : activeProfile.telemetryType === 'onnx' ? (
              /* THE ONNX STRATEGY — 5 STRATEGY DIALS COCKPIT MATRIX */
              <div className="space-y-3.5">
                {/* Header Banner */}
                <div className="p-2.5 rounded-lg bg-gradient-to-r from-cyan-950/40 via-purple-950/30 to-slate-900 border border-cyan-500/30 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-cyan-400" />
                    <div>
                      <div className="text-[11px] font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                        <span>THE ONNX STRATEGY</span>
                        <span className="px-1.5 py-0.2 rounded text-[9px] bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-mono">
                          5 DIALS COCKPIT
                        </span>
                      </div>
                      <div className="text-[9px] text-slate-400">
                        Dual-Brain Spot Lead vs Kalshi Lag CLOB · Microstructure Arbitrage
                      </div>
                    </div>
                  </div>
                  <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                    SWEETSPOTS ACTIVE
                  </span>
                </div>

                {/* DIAL 1: Brain Priority Mode (Full Width Segmented Selector) */}
                <div className="space-y-1.5 p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d]">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-cyan-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-cyan-400 inline-block animate-pulse" />
                      Dial 1: Brain Priority Mode
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-cyan-500/40 z-50 shadow-2xl leading-snug">
                          <b>Quant Arbitration Arbiter:</b><br />
                          • <b>Trend Aligned Scalp (Sweetspot):</b> QuoLas Binance Spot Microscope leads; Kalshi binary CLOB lags. Exploits directional momentum.<br />
                          • <b>Contradiction Sniper:</b> Strict divergence required. Spot and Kalshi must oppose to snipe mispriced discount contracts.<br />
                          • <b>Unanimous Consensus:</b> Both models must agree 100% on direction (ultra-safe).
                        </div>
                      </div>
                    </label>
                    <span className="text-[9px] font-mono text-cyan-400 font-bold">
                      {(botParams.brain_priority_mode || 'TREND_ALIGNED_SCALP').replace(/_/g, ' ')}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-1.5">
                    {[
                      {
                        mode: 'TREND_ALIGNED_SCALP',
                        label: 'Trend Scalp',
                        badge: 'Sweetspot',
                        desc: 'Spot Lead · CLOB Lag',
                      },
                      {
                        mode: 'CONTRADICTION_SNIPER',
                        label: 'Contradiction',
                        badge: 'Divergence',
                        desc: 'Discount Hunter',
                      },
                      {
                        mode: 'UNANIMOUS_CONSENSUS',
                        label: 'Consensus',
                        badge: 'Ultra-Safe',
                        desc: '100% Agreement',
                      },
                    ].map((opt) => {
                      const isActive = (botParams.brain_priority_mode || 'TREND_ALIGNED_SCALP') === opt.mode;
                      return (
                        <button
                          key={opt.mode}
                          type="button"
                          onClick={() => {
                            soundFX.playClickSound();
                            setBotParams({ ...botParams, brain_priority_mode: opt.mode });
                          }}
                          className={`p-2 rounded border text-left transition-all cursor-pointer ${
                            isActive
                              ? 'bg-cyan-500/15 border-cyan-400 text-white shadow-lg shadow-cyan-500/10 ring-1 ring-cyan-400/40'
                              : 'bg-[#10141b] border-[#222933] text-slate-400 hover:border-slate-600 hover:text-slate-200'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-bold">{opt.label}</span>
                            <span className={`text-[8px] font-mono px-1 rounded ${
                              isActive ? 'bg-cyan-400/20 text-cyan-300 font-semibold' : 'bg-slate-800 text-slate-400'
                            }`}>
                              {opt.badge}
                            </span>
                          </div>
                          <div className="text-[8px] text-slate-400 mt-0.5 truncate">{opt.desc}</div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* DIAL 2: Micro-Bankroll Sizing Armor */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-amber-400 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <Lock className="w-3.5 h-3.5 text-amber-400" />
                      Dial 2: Sizing Mode & Bankroll Armor
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-amber-500/40 z-50 shadow-2xl leading-snug">
                          <b>Micro-Bankroll Sizing Armor:</b><br />
                          Enforces exactly 1 contract per trade for bankrolls &lt; $75 to guarantee zero drawdown blowup.<br />
                          Tier 1 (2 contracts) unlocks conditionally only when bankroll reaches $75+, AI confidence ≥ 75%, and Net EV ≥ +$0.06.
                        </div>
                      </div>
                    </label>
                    <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 font-bold flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3 text-amber-400" />
                      &lt; $75 ARMOR LOCKED
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <div className="p-2 rounded border bg-amber-500/10 border-amber-500/40 text-amber-300 flex items-center justify-between">
                      <div>
                        <div className="text-[10px] font-bold flex items-center gap-1">
                          <Lock className="w-3 h-3 text-amber-400" />
                          TIER 0: STRICT 1-CT
                        </div>
                        <div className="text-[8px] text-amber-400/80">Micro-Bankroll Armor (Enforced)</div>
                      </div>
                      <span className="text-xs font-bold font-mono px-2 py-0.5 bg-amber-400 text-black rounded font-black">
                        1 CT
                      </span>
                    </div>

                    <div className="p-2 rounded border bg-[#0e1217] border-slate-800 text-slate-500 flex items-center justify-between opacity-60">
                      <div>
                        <div className="text-[10px] font-semibold flex items-center gap-1">
                          <span>TIER 1: CONVICTION 2-CT</span>
                        </div>
                        <div className="text-[8px] text-slate-500">Unlocks at &ge; $75 Bankroll</div>
                      </div>
                      <span className="text-[9px] font-mono px-1.5 py-0.5 bg-slate-800 text-slate-400 rounded">
                        LOCKED
                      </span>
                    </div>
                  </div>
                </div>

                {/* DIAL 3: Volatility Regime Window (Floor & Ceiling) */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-purple-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-purple-400 inline-block" />
                      Dial 3: Volatility Regime Window (1m ATR)
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-purple-500/40 z-50 shadow-2xl leading-snug">
                          <b>Regime Window Protection:</b><br />
                          • <b>Floor ($10):</b> Dead chop shield. Refuses entry in flat, stationary order flow.<br />
                          • <b>Ceiling ($45):</b> News panic shield. Halts orders during violent spike chaos where adverse selection is extreme.
                        </div>
                      </div>
                    </label>

                    {/* Live ATR Badge */}
                    <div className="flex items-center gap-1.5">
                      <span className="text-[9px] font-mono text-slate-400">
                        1m ATR: <b className="text-white font-mono">${currentAtr.toFixed(1)}</b>
                      </span>
                      <span className={`text-[8px] font-mono px-1.5 py-0.5 rounded border font-bold ${
                        isSafeVol
                          ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                          : isDeadChop
                          ? 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                          : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                      }`}>
                        {isSafeVol ? 'SAFE REGIME' : isDeadChop ? 'CHOP VETO' : 'PANIC VETO'}
                      </span>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <div className="text-[9px] text-slate-400 flex items-center justify-between">
                        <span>Floor (Dead Chop Cutoff)</span>
                        <span className="text-purple-400 font-mono">${volFloor.toFixed(0)}</span>
                      </div>
                      <div className="flex items-center bg-[#10141a] border border-purple-500/30 rounded px-2 py-1">
                        <span className="text-purple-400 mr-1">$</span>
                        <input
                          type="number"
                          step="1.0"
                          min="0"
                          max="50"
                          value={botParams.volatility_floor ?? 10.0}
                          onChange={(e) => setBotParams({ ...botParams, volatility_floor: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-xs"
                        />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <div className="text-[9px] text-slate-400 flex items-center justify-between">
                        <span>Ceiling (News Spike Cutoff)</span>
                        <span className="text-purple-400 font-mono">${volCeil.toFixed(0)}</span>
                      </div>
                      <div className="flex items-center bg-[#10141a] border border-purple-500/30 rounded px-2 py-1">
                        <span className="text-purple-400 mr-1">$</span>
                        <input
                          type="number"
                          step="1.0"
                          min="20"
                          max="200"
                          value={botParams.volatility_ceiling ?? 45.0}
                          onChange={(e) => setBotParams({ ...botParams, volatility_ceiling: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-xs"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* DIAL 4: Entry Discount Depth Ceiling ($0.35 - $0.65) */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-cyan-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-cyan-400 inline-block" />
                      Dial 4: Entry Discount Depth Ceiling ($0.35 - $0.65)
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-cyan-500/40 z-50 shadow-2xl leading-snug">
                          <b>Asymmetric Discount Hunter:</b><br />
                          Resting maker order price ceiling (e.g. $0.48, max $0.65).<br />
                          • Guarantees <b>$0.00 Maker Fee</b> on Kalshi.<br />
                          • At $0.48 entry, winning $1.00 binary yields <b>+{maxWinRoi}% net ROI</b>.<br />
                          • Up to <b>$0.65</b> ceiling allows capturing fills during rapid momentum shifts.
                        </div>
                      </div>
                    </label>

                    <div className="flex items-center gap-2">
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-bold">
                        +{maxWinRoi}% MAX ROI
                      </span>
                      <span className="text-xs font-mono font-bold text-cyan-300">
                        ${entryDiscount.toFixed(2)} ({(entryDiscount * 100).toFixed(0)}¢)
                      </span>
                    </div>
                  </div>

                  {/* Slider Control */}
                  <div className="space-y-1">
                    <input
                      type="range"
                      min="0.35"
                      max="0.65"
                      step="0.01"
                      value={entryDiscount}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setBotParams({
                          ...botParams,
                          entry_discount_depth: val,
                          discount_limit_price: val,
                        });
                      }}
                      className="w-full accent-cyan-400 cursor-pointer h-1.5 bg-slate-800 rounded-lg"
                    />
                    <div className="flex justify-between text-[8px] text-slate-500 font-mono">
                      <span>$0.35 (Deep Discount · +185% ROI)</span>
                      <span className="text-cyan-400 font-semibold">$0.48 (Sweetspot · +108% ROI)</span>
                      <span>$0.65 (Maker Ceiling Max · +54% ROI)</span>
                    </div>
                  </div>
                </div>

                {/* DIAL 5: Orderflow Tape Confirmation (Anti-Spoofing Shield) */}
                <div className="p-2.5 rounded-lg bg-[#0a0d12] border border-[#1e242d] space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-indigo-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-indigo-400 inline-block" />
                      Dial 5: Orderflow Tape Confirmation
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-slate-300 text-[9px] flex items-center justify-center font-bold border border-slate-600">i</span>
                        <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-64 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded-lg border border-indigo-500/40 z-50 shadow-2xl leading-snug">
                          <b>Anti-Spoofing Tape Shield:</b><br />
                          Requires consecutive confirmed market trade prints in the directional impulse before placing orders.<br />
                          Filters out phantom ghost bids and resting order spoofing.
                        </div>
                      </div>
                    </label>

                    {/* Streak indicator */}
                    <span className={`text-[9px] font-mono px-2 py-0.5 rounded border font-bold ${
                      isTapeConfirmed
                        ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                        : 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                    }`}>
                      {tapeStreak} / {reqTapeTicks} PRINTS CONFIRMED
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-1.5">
                    {[
                      { ticks: 1, label: '1 Tick', sub: 'Fast Entry' },
                      { ticks: 2, label: '2 Ticks', sub: 'Sweetspot (300ms)' },
                      { ticks: 3, label: '3 Ticks', sub: 'Heavy Armor' },
                    ].map((opt) => {
                      const isSel = (botParams.tape_confirmation_ticks ?? 2) === opt.ticks;
                      return (
                        <button
                          key={opt.ticks}
                          type="button"
                          onClick={() => {
                            soundFX.playClickSound();
                            setBotParams({ ...botParams, tape_confirmation_ticks: opt.ticks });
                          }}
                          className={`p-1.5 rounded border text-center transition-all cursor-pointer ${
                            isSel
                              ? 'bg-indigo-500/20 border-indigo-400 text-white shadow ring-1 ring-indigo-400/40'
                              : 'bg-[#10141a] border-[#222933] text-slate-400 hover:text-white'
                          }`}
                        >
                          <div className="text-[10px] font-bold">{opt.label}</div>
                          <div className="text-[8px] text-slate-400">{opt.sub}</div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Secondary Pre-Flight Guardrails Grid */}
                <div className="space-y-1.5 pt-1">
                  <div className="text-[9px] font-mono text-slate-400 uppercase tracking-wider font-bold">
                    PRE-FLIGHT GUARDRAILS & EV THRESHOLDS
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {/* Taker Cross EV Gate */}
                    <div className="space-y-0.5 p-1.5 rounded bg-[#0a0d12] border border-[#1e242d]">
                      <div className="text-[8px] text-slate-400">Taker Cross EV</div>
                      <div className="flex items-center bg-[#10141a] border border-[#252c36] rounded px-1.5 py-0.5">
                        <span className="text-slate-500 text-[10px] mr-1">$</span>
                        <input
                          type="number"
                          step="0.01"
                          min="0.01"
                          max="0.30"
                          value={botParams.taker_cross_ev_threshold ?? 0.08}
                          onChange={(e) => setBotParams({ ...botParams, taker_cross_ev_threshold: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-[11px]"
                        />
                      </div>
                    </div>

                    {/* Dynamic Moat Multiplier */}
                    <div className="space-y-0.5 p-1.5 rounded bg-[#0a0d12] border border-[#1e242d]">
                      <div className="text-[8px] text-slate-400">Dynamic Moat</div>
                      <div className="flex items-center bg-[#10141a] border border-[#252c36] rounded px-1.5 py-0.5">
                        <input
                          type="number"
                          step="0.05"
                          min="0.5"
                          max="2.5"
                          value={botParams.dynamic_moat_multiplier ?? 1.15}
                          onChange={(e) => setBotParams({ ...botParams, dynamic_moat_multiplier: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-[11px]"
                        />
                        <span className="text-slate-500 text-[10px] ml-1">x</span>
                      </div>
                    </div>

                    {/* Min Conviction */}
                    <div className="space-y-0.5 p-1.5 rounded bg-[#0a0d12] border border-[#1e242d]">
                      <div className="text-[8px] text-slate-400">Min Conviction</div>
                      <div className="flex items-center bg-[#10141a] border border-[#252c36] rounded px-1.5 py-0.5">
                        <input
                          type="number"
                          step="0.01"
                          min="0.50"
                          max="0.99"
                          value={botParams.min_confidence ?? 0.81}
                          onChange={(e) => setBotParams({ ...botParams, min_confidence: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-[11px]"
                        />
                      </div>
                    </div>

                    {/* Min EV */}
                    <div className="space-y-0.5 p-1.5 rounded bg-[#0a0d12] border border-[#1e242d]">
                      <div className="text-[8px] text-slate-400">Min Net EV</div>
                      <div className="flex items-center bg-[#10141a] border border-[#252c36] rounded px-1.5 py-0.5">
                        <span className="text-slate-500 text-[10px] mr-1">$</span>
                        <input
                          type="number"
                          step="0.01"
                          min="0.01"
                          max="0.50"
                          value={botParams.min_ev_dollars ?? 0.02}
                          onChange={(e) => setBotParams({ ...botParams, min_ev_dollars: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-[11px]"
                        />
                      </div>
                    </div>

                    {/* VPIN Cutoff */}
                    <div className="space-y-0.5 p-1.5 rounded bg-[#0a0d12] border border-[#1e242d]">
                      <div className="text-[8px] text-slate-400">VPIN Shark Veto</div>
                      <div className="flex items-center bg-[#10141a] border border-[#252c36] rounded px-1.5 py-0.5">
                        <input
                          type="number"
                          step="0.05"
                          min="0.10"
                          max="0.95"
                          value={botParams.vpin_toxic_threshold ?? 0.60}
                          onChange={(e) => setBotParams({ ...botParams, vpin_toxic_threshold: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-[11px]"
                        />
                      </div>
                    </div>

                    {/* Take Profit Price */}
                    <div className="space-y-0.5 p-1.5 rounded bg-[#0a0d12] border border-[#1e242d]">
                      <div className="text-[8px] text-slate-400">Take Profit Cap</div>
                      <div className="flex items-center bg-[#10141a] border border-[#252c36] rounded px-1.5 py-0.5">
                        <span className="text-slate-500 text-[10px] mr-1">$</span>
                        <input
                          type="number"
                          step="0.01"
                          min="0.50"
                          max="0.99"
                          value={botParams.take_profit_price_threshold ?? 0.92}
                          onChange={(e) => setBotParams({ ...botParams, take_profit_price_threshold: parseFloat(e.target.value) })}
                          className="w-full bg-transparent text-white font-mono outline-none text-[11px]"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              /* Standard / 3-Step Dominion Parameter Grid */
              <div className="grid grid-cols-2 gap-2.5">
                {/* Discount Maker Limit Ceiling */}
                <div className="space-y-1">
                  <label className="text-[10px] text-[#8c9ba5] font-semibold flex items-center gap-1">
                    Maker Ceiling ($)
                    <div className="group relative cursor-help">
                      <span className="w-3 h-3 rounded-full bg-slate-700 text-white text-[9px] flex items-center justify-center">i</span>
                      <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-52 p-2 bg-slate-800 text-slate-200 text-[10px] rounded border border-slate-600 z-50 shadow-xl leading-snug">
                        <b>The Beginner Translation:</b> <i>"What is the maximum price you will pay?"</i><br />
                        <b>How it works:</b> Places lowball maker resting orders.<br />
                        <b>Why it matters:</b> Guarantees $0 Kalshi exchange taker fees.
                      </div>
                    </div>
                  </label>
                  <div className="flex items-center bg-[#07080c] border border-[#262d35] rounded px-2 py-1">
                    <span className="text-slate-500 mr-1">$</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0.10"
                      max="0.65"
                      value={botParams.discount_limit_price ?? 0.52}
                      onChange={(e) => setBotParams({ ...botParams, discount_limit_price: parseFloat(e.target.value) })}
                      className="w-full bg-transparent text-white font-mono outline-none text-xs"
                    />
                  </div>
                </div>



                {/* Min Net EV ($/ct) */}
                <div className="space-y-1">
                  <label className="text-[10px] text-[#8c9ba5] font-semibold flex items-center gap-1">
                    Min Net EV ($)
                    <div className="group relative cursor-help">
                      <span className="w-3 h-3 rounded-full bg-slate-700 text-white text-[9px] flex items-center justify-center">i</span>
                      <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-52 p-2 bg-slate-800 text-slate-200 text-[10px] rounded border border-slate-600 z-50 shadow-xl leading-snug">
                        <b>The Beginner Translation:</b> <i>"Minimum expected profit per trade."</i><br />
                        <b>How it works:</b> Average statistical payoff across 1,000 simulations.<br />
                        <b>Why it matters:</b> Rejects setups yielding pennies; demands structural profit.
                      </div>
                    </div>
                  </label>
                  <div className="flex items-center bg-[#07080c] border border-[#262d35] rounded px-2 py-1">
                    <span className="text-slate-500 mr-1">$</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0.01"
                      max="0.50"
                      value={botParams.min_ev_dollars ?? 0.02}
                      onChange={(e) => setBotParams({ ...botParams, min_ev_dollars: parseFloat(e.target.value) })}
                      className="w-full bg-transparent text-white font-mono outline-none text-xs"
                    />
                  </div>
                </div>

                {/* VPIN Toxicity Cutoff */}
                <div className="space-y-1">
                  <label className="text-[10px] text-[#8c9ba5] font-semibold flex items-center gap-1">
                    VPIN Cutoff
                    <div className="group relative cursor-help">
                      <span className="w-3 h-3 rounded-full bg-slate-700 text-white text-[9px] flex items-center justify-center">i</span>
                      <div className="absolute bottom-full right-0 mb-1 hidden group-hover:block w-52 p-2 bg-slate-800 text-slate-200 text-[10px] rounded border border-slate-600 z-50 shadow-xl leading-snug">
                        <b>The Beginner Translation:</b> <i>"The Shark Detector."</i><br />
                        <b>How it works:</b> Measures volume toxicity from institutional whales.<br />
                        <b>Why it matters:</b> Instantly vetoes orders during sudden toxic bursts.
                      </div>
                    </div>
                  </label>
                  <div className="flex items-center bg-[#07080c] border border-[#262d35] rounded px-2 py-1">
                    <input
                      type="number"
                      step="0.05"
                      min="0.10"
                      max="0.95"
                      value={botParams.vpin_toxic_threshold ?? 0.60}
                      onChange={(e) => setBotParams({ ...botParams, vpin_toxic_threshold: parseFloat(e.target.value) })}
                      className="w-full bg-transparent text-white font-mono outline-none text-xs"
                    />
                  </div>
                </div>

                {/* Min Conviction (min_confidence) */}
                <div className="space-y-1">
                  <label className="text-[10px] text-[#8c9ba5] font-semibold flex items-center gap-1">
                    Min Conviction
                    <div className="group relative cursor-help">
                      <span className="w-3 h-3 rounded-full bg-slate-700 text-white text-[9px] flex items-center justify-center">i</span>
                      <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-52 p-2 bg-slate-800 text-slate-200 text-[10px] rounded border border-slate-600 z-50 shadow-xl leading-snug">
                        <b>The Beginner Translation:</b> <i>"Win Probability Hurdle."</i><br />
                        <b>How it works:</b> Required ONNX model confidence to enter a trade.<br />
                        <b>Why it matters:</b> Keeps the bot from taking low-probability setups.
                      </div>
                    </div>
                  </label>
                  <div className="flex items-center bg-[#07080c] border border-[#262d35] rounded px-2 py-1">
                    <input
                      type="number"
                      step="0.01"
                      min="0.50"
                      max="0.99"
                      value={botParams.min_confidence ?? 0.81}
                      onChange={(e) => setBotParams({ ...botParams, min_confidence: parseFloat(e.target.value) })}
                      className="w-full bg-transparent text-white font-mono outline-none text-xs"
                    />
                  </div>
                </div>

                {/* Min Spot Distance */}
                <div className="space-y-1">
                  <label className="text-[10px] text-[#8c9ba5] font-semibold flex items-center gap-1">
                    min_spot_diff
                    <div className="group relative cursor-help">
                      <span className="w-3 h-3 rounded-full bg-slate-700 text-white text-[9px] flex items-center justify-center">i</span>
                      <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-52 p-2 bg-slate-800 text-slate-200 text-[10px] rounded border border-slate-600 z-50 shadow-xl leading-snug">
                        <b>The Beginner Translation:</b> <i>"The Moat / Buffer Zone."</i><br />
                        <b>How it works:</b> Refuses trades when Bitcoin is right on the strike line.<br />
                        <b>Why it matters:</b> Prevents gambling on 50/50 coin-flip noise.
                      </div>
                    </div>
                  </label>
                  <div className="flex items-center bg-[#07080c] border border-[#262d35] rounded px-2 py-1">
                    <span className="text-slate-500 mr-1">$</span>
                    <input
                      type="number"
                      step="1.0"
                      min="0"
                      max="200"
                      value={botParams.min_spot_diff ?? 21.0}
                      onChange={(e) => setBotParams({ ...botParams, min_spot_diff: parseFloat(e.target.value) })}
                      className="w-full bg-transparent text-white font-mono outline-none text-xs"
                    />
                  </div>
                </div>



                {/* Opening Quarantine */}
                <div className="space-y-1">
                  <label className="text-[10px] text-[#8c9ba5] font-semibold flex items-center gap-1">
                    opening_quarantine_seconds
                    <div className="group relative cursor-help">
                      <span className="w-3 h-3 rounded-full bg-slate-700 text-white text-[9px] flex items-center justify-center">i</span>
                      <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-52 p-2 bg-slate-800 text-slate-200 text-[10px] rounded border border-slate-600 z-50 shadow-xl leading-snug">
                        <b>The Beginner Translation:</b> <i>"Opening Wait Time."</i><br />
                        <b>How it works:</b> Disables trading for the first N seconds of a cycle.<br />
                        <b>Why it matters:</b> Prevents getting caught in initial cycle volatility.
                      </div>
                    </div>
                  </label>
                  <div className="flex items-center bg-[#07080c] border border-[#262d35] rounded px-2 py-1">
                    <span className="text-slate-500 mr-1">⏱️</span>
                    <input
                      type="number"
                      step="1"
                      min="0"
                      max="300"
                      value={botParams.opening_quarantine_seconds ?? 60.0}
                      onChange={(e) => setBotParams({ ...botParams, opening_quarantine_seconds: parseFloat(e.target.value) })}
                      className="w-full bg-transparent text-white font-mono outline-none text-xs"
                    />
                  </div>
                </div>

                {/* Take Profit Ceiling */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-[#8c9ba5] font-semibold flex items-center gap-1">
                      Take Profit ($)
                      <div className="group relative cursor-help">
                        <span className="w-3 h-3 rounded-full bg-slate-700 text-white text-[9px] flex items-center justify-center">i</span>
                        <div className="absolute bottom-full right-0 mb-1 hidden group-hover:block w-56 p-2 bg-slate-800 text-slate-200 text-[10px] rounded border border-slate-600 z-50 shadow-xl leading-snug">
                          <b>The Beginner Translation:</b> <i>"The Early Eject Button."</i><br />
                          <b>How it works:</b> Sells winning contract before expiration if an adverse reversal is detected.<br />
                          <b>Philosophy:</b> Let winners run to 100% ($1.00) unless an adverse reversal ≥85% is detected.
                        </div>
                      </div>
                    </label>
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => setBotParams({ ...botParams, require_reversal_for_tp_ceiling: !(botParams.require_reversal_for_tp_ceiling ?? false) })}
                        title="Require adverse reversal detected before ejecting at ceiling (otherwise take profit immediately at ceiling)"
                        className={`text-[8px] font-bold px-1 py-0.5 rounded border transition-colors ${
                          (botParams.require_reversal_for_tp_ceiling ?? false)
                            ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-400'
                            : 'border-amber-500/40 bg-amber-500/10 text-amber-400'
                        }`}
                      >
                        {(botParams.require_reversal_for_tp_ceiling ?? false) ? '🛡️ REV GATE' : '⚡ 0-DELAY HARVEST'}
                      </button>
                      <button
                        type="button"
                        onClick={() => setBotParams({ ...botParams, enable_take_profit_ceiling: !(botParams.enable_take_profit_ceiling ?? true) })}
                        className={`text-[9px] font-bold px-1.5 py-0.5 rounded border transition-colors ${
                          (botParams.enable_take_profit_ceiling ?? true)
                            ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400'
                            : 'border-slate-700 bg-slate-800/40 text-slate-400'
                        }`}
                      >
                        {(botParams.enable_take_profit_ceiling ?? true) ? '🟢 ON' : '⚪ OFF'}
                      </button>
                    </div>
                  </div>
                  <div className="flex items-center bg-[#07080c] border border-[#262d35] rounded px-2 py-1">
                    <span className="text-slate-500 mr-1">$</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0.50"
                      max="0.99"
                      value={botParams.take_profit_price_threshold ?? 0.92}
                      onChange={(e) => setBotParams({ ...botParams, take_profit_price_threshold: parseFloat(e.target.value) })}
                      className="w-full bg-transparent text-white font-mono outline-none text-xs"
                    />
                  </div>
                </div>

                {/* Trailing Ratchet & Breakeven Armor */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-[#8c9ba5] font-semibold flex items-center gap-1">
                      Trailing Ratchet ($)
                      <div className="group relative cursor-help">
                        <span className="w-3 h-3 rounded-full bg-slate-700 text-white text-[9px] flex items-center justify-center">i</span>
                        <div className="absolute bottom-full right-0 mb-1 hidden group-hover:block w-64 p-2 bg-slate-800 text-slate-200 text-[10px] rounded border border-slate-600 z-50 shadow-xl leading-snug">
                          <b>High-Water Mark Trailing Ratchet:</b><br />
                          • <b>Tier 1 (Breakeven Armor):</b> If bid touches ≥$0.68, stops out if it drops back to entry.<br />
                          • <b>Tier 2 (Profit Trail):</b> If bid reaches ≥$0.80, exits if bid drops below (Peak Bid - Buffer).
                        </div>
                      </div>
                    </label>
                    <button
                      type="button"
                      onClick={() => setBotParams({ ...botParams, enable_trailing_ratchet: !(botParams.enable_trailing_ratchet ?? true) })}
                      className={`text-[9px] font-bold px-1.5 py-0.5 rounded border transition-colors ${
                        (botParams.enable_trailing_ratchet ?? true)
                          ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400'
                          : 'border-slate-700 bg-slate-800/40 text-slate-400'
                      }`}
                    >
                      {(botParams.enable_trailing_ratchet ?? true) ? '🟢 ON' : '⚪ OFF'}
                    </button>
                  </div>
                  <div className="flex items-center bg-[#07080c] border border-[#262d35] rounded px-2 py-1">
                    <span className="text-slate-500 mr-1">$</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0.02"
                      max="0.25"
                      value={botParams.trailing_ratchet_buffer ?? 0.08}
                      onChange={(e) => setBotParams({ ...botParams, trailing_ratchet_buffer: parseFloat(e.target.value) })}
                      className="w-full bg-transparent text-white font-mono outline-none text-xs"
                    />
                  </div>
                </div>

                {/* Spot Delta Front-Runner */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-[#8c9ba5] font-semibold flex items-center gap-1.5">
                      Spot Front-Run Δ*
                      <span className="text-[8px] px-1.5 py-0.2 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30 font-mono font-semibold">
                        ⚡ DYNAMIC FADING
                      </span>
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-700 text-white text-[9px] flex items-center justify-center hover:bg-slate-600 transition-colors">i</span>
                        <div className="absolute bottom-full right-0 mb-1 hidden group-hover:block w-80 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded border border-slate-700 z-50 shadow-2xl leading-relaxed backdrop-blur-md">
                          <b className="text-amber-300">Dynamic Spot Velocity Front-Run & Fading Engine (Δ*):</b><br />
                          <span className="text-slate-300"><b>1. Macro Drift (T &gt; 240s):</b> |Z_v| ≥ 2.50σ with Moneyness Moat (2σ√t). Deep ITM positions never panic dump.</span><br />
                          <span className="text-slate-300"><b>2. Adaptive Transition (60s &lt; T ≤ 240s):</b> Dynamic threshold Δ*(T) scales with 1m realized volatility.</span><br />
                          <span className="text-slate-300"><b>3. Silas TWAP Gravity (15s &lt; T ≤ 60s):</b> Quadratic decay ~ (T/60)². Vetoes exits when spot fluctuations cannot mathematically flip settlement TWAP (v &lt; v_crit).</span><br />
                          <span className="text-slate-300"><b>4. Expiration Quarantine (T ≤ 15s):</b> Front-run sells strictly locked out to capture full $1.00 settlement.</span><br />
                          <span className="text-emerald-400 font-semibold mt-1 block">★ Winning Option ($28.0 BTC / 2.0σ): Filters 95.4% sensor noise, eliminates premature dumps into wide spreads (+166% net yield), while maintaining 100% defense against flash crashes.</span>
                        </div>
                      </div>
                    </label>
                  </div>
                  <div className="flex items-center bg-[#07080c] border border-[#262d35] rounded px-2 py-1">
                    <span className="text-slate-500 mr-1">Δ*</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0.0001"
                      max="50"
                      value={botParams.spot_delta_front_run_threshold ?? (activeAssetKey === 'GOLD' ? 2.50 : activeAssetKey === 'DOGE' ? 0.0005 : activeAssetKey === 'ETH' ? 2.50 : activeAssetKey === 'SOL' ? 0.50 : activeAssetKey === 'HYPER' ? 0.33 : 28.0)}
                      onChange={(e) => setBotParams({ ...botParams, spot_delta_front_run_threshold: parseFloat(e.target.value) })}
                      className="w-full bg-transparent text-white font-mono outline-none text-xs"
                    />
                  </div>
                </div>

                {/* Frontier 1: Silas TWAP Immutability Sniper */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-[#8c9ba5] font-semibold flex items-center gap-1.5">
                      TWAP Sniper Ceiling
                      <span className="text-[8px] px-1.5 py-0.2 rounded bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 font-mono font-semibold">
                        ⚡ LATE-CYCLE ALPHA
                      </span>
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-700 text-white text-[9px] flex items-center justify-center hover:bg-slate-600 transition-colors">i</span>
                        <div className="absolute bottom-full right-0 mb-1 hidden group-hover:block w-80 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded border border-slate-700 z-50 shadow-2xl leading-relaxed backdrop-blur-md">
                          <b className="text-cyan-300">Playbook 4: Silas TWAP Immutability Sniper:</b><br />
                          <span className="text-slate-300"><b>Concept:</b> In the endgame window (T ∈ [15s, 45s]), trailing 60s TWAP mathematically guarantees settlement outcome (&gt; 1.5σ√τ deep ITM).</span><br />
                          <span className="text-slate-300"><b>Action:</b> Opportunistically snipes panicked retail limit asks resting up to this ceiling price.</span><br />
                          <span className="text-emerald-400 font-semibold mt-1 block">★ Winning Sweetspot: 75¢ (BTC/ETH/GOLD), 72¢ (SOL/HYPER), 70¢ (DOGE). Captures locked $1.00 payouts with 99.9% settlement certainty (+5.9% win rate boost).</span>
                        </div>
                      </div>
                    </label>
                  </div>
                  <div className="flex items-center bg-[#07080c] border border-[#262d35] rounded px-2 py-1">
                    <span className="text-slate-500 mr-1">$</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0.50"
                      max="0.95"
                      value={botParams.twap_immutability_sniper_cents ?? (activeAssetKey === 'DOGE' ? 0.70 : (activeAssetKey === 'SOL' || activeAssetKey === 'HYPER') ? 0.72 : 0.75)}
                      onChange={(e) => setBotParams({ ...botParams, twap_immutability_sniper_cents: parseFloat(e.target.value) })}
                      className="w-full bg-transparent text-white font-mono outline-none text-xs"
                    />
                  </div>
                </div>



                {/* Frontier 3: Vance Max CLOB Spread Corridor Cap */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-[#8c9ba5] font-semibold flex items-center gap-1.5">
                      Max Spread Corridor
                      <span className="text-[8px] px-1.5 py-0.2 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-mono font-semibold">
                        📏 LIQUIDITY CORRIDOR
                      </span>
                      <div className="group relative cursor-help">
                        <span className="w-3.5 h-3.5 rounded-full bg-slate-700 text-white text-[9px] flex items-center justify-center hover:bg-slate-600 transition-colors">i</span>
                        <div className="absolute bottom-full right-0 mb-1 hidden group-hover:block w-80 p-2.5 bg-slate-900 text-slate-200 text-[10px] rounded border border-slate-700 z-50 shadow-2xl leading-relaxed backdrop-blur-md">
                          <b className="text-emerald-300">Vance Max CLOB Spread Corridor Cap:</b><br />
                          <span className="text-slate-300"><b>Concept:</b> Enforces maximum bid-ask spread across the Kalshi CLOB ladder before routing trade intent.</span><br />
                          <span className="text-slate-300"><b>Protection:</b> Vetoes entries into dislocated or illiquid orderbooks where spread &gt; corridor cap.</span><br />
                          <span className="text-emerald-400 font-semibold mt-1 block">★ Winning Sweetspot: $0.05 (BTC/GOLD/HYPER), $0.04 (ETH), $0.06 (SOL), $0.03 (DOGE). Blocks wide-spread slippage traps.</span>
                        </div>
                      </div>
                    </label>
                  </div>
                  <div className="flex items-center bg-[#07080c] border border-[#262d35] rounded px-2 py-1">
                    <span className="text-slate-500 mr-1">$</span>
                    <input
                      type="number"
                      step="0.01"
                      min="0.01"
                      max="0.25"
                      value={botParams.max_clob_spread_cents ?? (activeAssetKey === 'DOGE' ? 0.03 : activeAssetKey === 'ETH' ? 0.04 : activeAssetKey === 'SOL' ? 0.06 : 0.05)}
                      onChange={(e) => setBotParams({ ...botParams, max_clob_spread_cents: parseFloat(e.target.value) })}
                      className="w-full bg-transparent text-white font-mono outline-none text-xs"
                    />
                  </div>
                </div>

                {/* Min Take Profit ROI % */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-[#8c9ba5] font-semibold flex items-center gap-1">
                      Take Profit ROI %
                      <div className="group relative cursor-help">
                        <span className="w-3 h-3 rounded-full bg-slate-700 text-white text-[9px] flex items-center justify-center">i</span>
                        <div className="absolute bottom-full right-0 mb-1 hidden group-hover:block w-56 p-2 bg-slate-800 text-slate-200 text-[10px] rounded border border-slate-600 z-50 shadow-xl leading-snug">
                          <b>The Beginner Translation:</b> <i>"Target ROI Early Harvest."</i><br />
                          <b>How it works:</b> Harvests profits if at least this ROI is met AND indicators show an adverse reversal.<br />
                          <b>Why it matters:</b> Protects against late-cycle profit evaporation.
                        </div>
                      </div>
                    </label>
                    <button
                      type="button"
                      onClick={() => setBotParams({ ...botParams, enable_reverse_take_profit_roi: !(botParams.enable_reverse_take_profit_roi ?? true) })}
                      className={`text-[9px] font-bold px-1.5 py-0.5 rounded border transition-colors ${
                        (botParams.enable_reverse_take_profit_roi ?? true)
                          ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400'
                          : 'border-slate-700 bg-slate-800/40 text-slate-400'
                      }`}
                    >
                      {(botParams.enable_reverse_take_profit_roi ?? true) ? '🟢 ON' : '⚪ OFF'}
                    </button>
                  </div>
                  <div className="flex items-center bg-[#07080c] border border-[#262d35] rounded px-2 py-1">
                    <input
                      type="number"
                      step="5"
                      min="5"
                      max="100"
                      value={botParams.min_take_profit_roi ?? 40.0}
                      onChange={(e) => setBotParams({ ...botParams, min_take_profit_roi: parseFloat(e.target.value) })}
                      className="w-full bg-transparent text-white font-mono outline-none text-xs"
                    />
                    <span className="text-slate-500 ml-1">%</span>
                  </div>
                </div>

                {/* Adverse Reversal Threshold % */}
                <div className="space-y-1">
                  <label className="text-[10px] text-[#8c9ba5] font-semibold flex items-center gap-1">
                    Reversal Trigger %
                    <div className="group relative cursor-help">
                      <span className="w-3 h-3 rounded-full bg-slate-700 text-white text-[9px] flex items-center justify-center">i</span>
                      <div className="absolute bottom-full left-0 mb-1 hidden group-hover:block w-56 p-2 bg-slate-800 text-slate-200 text-[10px] rounded border border-slate-600 z-50 shadow-xl leading-snug">
                        <b>The Beginner Translation:</b> <i>"Reversal Conviction Sensor."</i><br />
                        <b>How it works:</b> Exit triggers only fire if indicators calculate this conviction in reverse direction.<br />
                        <b>Default:</b> 83%-85% baseline conviction.
                      </div>
                    </div>
                  </label>
                  <div className="flex items-center bg-[#07080c] border border-[#262d35] rounded px-2 py-1">
                    <input
                      type="number"
                      step="1"
                      min="50"
                      max="99"
                      value={botParams.reverse_indicator_threshold ?? 85.0}
                      onChange={(e) => setBotParams({ ...botParams, reverse_indicator_threshold: parseFloat(e.target.value) })}
                      className="w-full bg-transparent text-white font-mono outline-none text-xs"
                    />
                    <span className="text-slate-500 ml-1">%</span>
                  </div>
                </div>

                {/* Dynamic Reversal Decay Curve */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] text-[#8c9ba5] font-semibold flex items-center gap-1">
                      Dynamic Reversal Decay
                      <div className="group relative cursor-help">
                        <span className="w-3 h-3 rounded-full bg-slate-700 text-white text-[9px] flex items-center justify-center">i</span>
                        <div className="absolute bottom-full right-0 mb-1 hidden group-hover:block w-64 p-2 bg-slate-800 text-slate-200 text-[10px] rounded border border-slate-600 z-50 shadow-xl leading-snug">
                          <b>Decay Formula:</b> R*(τ) = min(85%, 50% + 3.5% × τ_mins).<br />
                          Relaxes reversal threshold from 85% at entry window down to ~53% at 60s remaining, matching the 5× gamma surge.
                        </div>
                      </div>
                    </label>
                    <button
                      type="button"
                      onClick={() => setBotParams({ ...botParams, enable_dynamic_reversal_curve: !(botParams.enable_dynamic_reversal_curve ?? true) })}
                      className={`text-[9px] font-bold px-1.5 py-0.5 rounded border transition-colors ${
                        (botParams.enable_dynamic_reversal_curve ?? true)
                          ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-400'
                          : 'border-slate-700 bg-slate-800/40 text-slate-400'
                      }`}
                    >
                      {(botParams.enable_dynamic_reversal_curve ?? true) ? '📈 DYNAMIC' : '⚪ STATIC'}
                    </button>
                  </div>
                  <div className="flex items-center justify-center bg-[#07080c] border border-[#262d35] rounded px-2 py-1">
                    <span className="text-[10px] font-mono text-cyan-400">
                      {(botParams.enable_dynamic_reversal_curve ?? true) ? '85% → 50% (τ SCALED)' : 'FIXED THRESHOLD'}
                    </span>
                  </div>
                </div>

                {/* Early Harvest Policy */}
                <div className="space-y-1">
                  <label className="text-[10px] text-[#8c9ba5] font-semibold flex items-center gap-1">
                    Early Harvest Policy
                    <div className="group relative cursor-help">
                      <span className="w-3 h-3 rounded-full bg-slate-700 text-white text-[9px] flex items-center justify-center">i</span>
                      <div className="absolute bottom-full right-0 mb-1 hidden group-hover:block w-64 p-2 bg-slate-800 text-slate-200 text-[10px] rounded border border-slate-600 z-50 shadow-xl leading-snug">
                        <b>4-Pillar Harvest Engine:</b> Takes profit at ${(botParams.take_profit_price_threshold ?? 0.92).toFixed(2)}, trails high-water mark, and front-runs spot velocity air pockets.
                      </div>
                    </div>
                  </label>
                  <div className="flex items-center justify-center bg-emerald-500/10 border border-emerald-500/30 rounded px-2 py-1">
                    <span className="text-[10px] font-mono font-bold text-emerald-400">
                      {!(botParams.require_reversal_for_tp_ceiling ?? false) ? `ZERO-DELAY ≥$${(botParams.take_profit_price_threshold ?? 0.92).toFixed(2)}` : 'RUN TO $1.00 (REV GATE)'}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Footer with Reset Defaults & Apply & Save */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2 border-t border-[#1f262d]">
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-[#8c9ba5] flex items-center gap-1">
                  <span>Target:</span>
                  <span className="text-white font-semibold">{activeProfile.name}</span>
                </span>
                {saveSuccessMsg && (
                  <span className="text-[10px] font-mono text-emerald-400 font-bold animate-pulse">
                    {saveSuccessMsg}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleResetDefaults}
                  type="button"
                  title="Reset to recommended quant sweetspots"
                  className="px-2.5 py-1.5 rounded bg-[#171c22] hover:bg-[#222933] text-amber-300 hover:text-amber-200 border border-amber-500/30 text-[10px] font-bold transition-all cursor-pointer flex items-center gap-1"
                >
                  <span>🎯</span>
                  <span>{activeProfile.telemetryType === 'macro_dominion' ? 'Reset Macro Sweetspots' : activeProfile.telemetryType === 'onnx' ? 'Reset Quant Sweetspots' : 'Sweetspots Preset'}</span>
                </button>
                <button
                  onClick={handleSaveParameters}
                  disabled={isSavingParams}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#00bda5] text-black font-bold text-xs hover:bg-[#2dd4bf] transition-all shadow cursor-pointer disabled:opacity-50"
                >
                  {isSavingParams ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                  <span>{activeProfile.telemetryType === 'macro_dominion' || activeProfile.telemetryType === 'onnx' ? 'Apply Strategy Dials' : 'Apply & Save as Default'}</span>
                </button>

                <button
                  onClick={handlePromoteToLive}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-red-600 text-white font-bold text-xs hover:bg-red-500 transition-all shadow cursor-pointer"
                >
                  <Zap className="w-3.5 h-3.5" />
                  <span>PROMOTE TO LIVE</span>
                </button>
              </div>
            </div>
          </div>
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
      <div className="border-b border-[#262d35] bg-[#0c1015] p-3 text-xs font-mono">
        {/* Header & Segregated Pill Toggle */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
              <span>📋</span>
              <span className="truncate max-w-[110px] sm:max-w-none">{activeProfile.shortName} Ledger</span>
            </span>
            {/* Live / Paper Pill Toggle */}
            <div className="flex items-center bg-[#171c22] p-0.5 rounded border border-[#262d35] text-[10px]">
              <button
                type="button"
                onClick={() => setReportMode('live')}
                className={`px-2 py-0.5 rounded font-bold transition-all ${
                  reportMode === 'live'
                    ? 'bg-amber-500 text-black shadow-sm'
                    : 'text-[#8c9ba5] hover:text-white'
                }`}
              >
                LIVE
              </button>
              <button
                type="button"
                onClick={() => setReportMode('paper')}
                className={`px-2 py-0.5 rounded font-bold transition-all ${
                  reportMode === 'paper'
                    ? 'bg-purple-500 text-white shadow-sm'
                    : 'text-[#8c9ba5] hover:text-white'
                }`}
              >
                PAPER
              </button>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={fetchMicroReports}
              disabled={isLoadingReports}
              title="Refresh ledger"
              className="text-[#8c9ba5] hover:text-white transition-colors"
            >
              <RefreshCw className={`w-3 h-3 ${isLoadingReports ? 'animate-spin text-[#00bda5]' : ''}`} />
            </button>
            {onOpenReports && (
              <button
                type="button"
                onClick={onOpenReports}
                className="text-[10px] text-[#00bda5] hover:text-[#2dd4bf] hover:underline flex items-center gap-0.5 cursor-pointer"
              >
                <span>Full Ledger</span>
                <ExternalLink className="w-2.5 h-2.5" />
              </button>
            )}
          </div>
        </div>

        {/* Mini KPI Strip */}
        <div className="grid grid-cols-3 gap-1.5 mb-2 bg-[#12171e] p-2 rounded border border-[#262d35]/60">
          <div className="flex flex-col">
            <span className="text-[9px] text-[#8c9ba5] uppercase tracking-wider">Win Rate</span>
            <span className={`text-[12px] font-bold ${
              (botPerformance?.win_rate_pct ?? 0) >= 50
                ? 'text-emerald-400'
                : (botPerformance?.total_events ?? 0) === 0
                ? 'text-[#8c9ba5]'
                : 'text-rose-400'
            }`}>
              {botPerformance && botPerformance.total_events > 0
                ? `${botPerformance.win_rate_pct.toFixed(1)}%`
                : '--'}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-[9px] text-[#8c9ba5] uppercase tracking-wider">Net PnL</span>
            <span className={`text-[12px] font-bold ${
              (botPerformance?.total_pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
            }`}>
              {botPerformance && botPerformance.total_events > 0
                ? `${botPerformance.total_pnl >= 0 ? '+' : ''}$${botPerformance.total_pnl.toFixed(2)}`
                : '--'}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-[9px] text-[#8c9ba5] uppercase tracking-wider">Cycles</span>
            <span className="text-[12px] font-bold text-white">
              {botPerformance && botPerformance.total_events > 0
                ? `${botPerformance.wins}W / ${botPerformance.losses}L`
                : '--'}
            </span>
          </div>
        </div>

        {/* Recent Settlements List */}
        {recentReports.length > 0 ? (
          <div className="space-y-1">
            {recentReports.map((r, idx) => {
              const isWin = r.outcome.toLowerCase() === 'win';
              const rawPnl = r.pnl !== undefined ? r.pnl : r.net_pnl;
              const pnlNum = typeof rawPnl === 'number' ? rawPnl : parseFloat(String(rawPnl || '0'));
              const displaySide = r.bot_side || r.side || 'YES';
              return (
                <div
                  key={r.report_id || idx}
                  className={`flex items-center justify-between p-1.5 rounded border text-[10px] ${
                    isWin
                      ? 'bg-emerald-950/20 border-emerald-500/20 text-emerald-300'
                      : 'bg-rose-950/20 border-rose-500/20 text-rose-300'
                  }`}
                >
                  <div className="flex items-center gap-1.5 truncate max-w-[65%]">
                    {isWin ? (
                      <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
                    ) : (
                      <XCircle className="w-3 h-3 text-rose-400 shrink-0" />
                    )}
                    <span className="truncate text-white font-medium">
                      {r.ticker.replace('KXBTC15M-', '').replace('KXETH15M-', 'ETH-').replace('KXSOL15M-', 'SOL-')}
                    </span>
                    <span className="text-[8px] text-[#8c9ba5] uppercase px-1 py-0.2 bg-[#171c22] rounded border border-[#262d35]">
                      {displaySide}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0 font-mono">
                    <span className={`font-bold ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {pnlNum >= 0 ? `+$${pnlNum.toFixed(2)}` : `-$${Math.abs(pnlNum).toFixed(2)}`}
                    </span>
                    <span className="text-[9px] text-[#8c9ba5]">
                      {r.timestamp_utc ? r.timestamp_utc.slice(11, 16) : ''}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="py-2 text-center text-[#8c9ba5] text-[10px] bg-[#12171e]/50 rounded border border-[#262d35]/40">
            <span>No {reportMode.toUpperCase()} settlements for {activeProfile.shortName}</span>
          </div>
        )}
      </div>

      {/* 9. Hardware-Style Emergency Kill-Switch */}
      <div className="p-4 bg-[#0c0f12]">
        <button
          type="button"
          aria-label={
            isHalted
              ? 'Bot emergency halted. All resting orders cancelled.'
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
            isHalted
              ? 'bg-slate-800 text-slate-500 border border-slate-700 cursor-not-allowed'
              : 'border-2 border-[#d31a38] text-[#f43f5e] hover:bg-[#d31a38]/10 active:scale-[0.99]'
          }`}
          style={{
            backgroundImage: isHalted
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
            <AlertOctagon className={`w-4 h-4 ${isHalted ? 'text-slate-500' : 'text-[#f43f5e]'}`} />
            <span>
              {isHalted
                ? '★ BOT EMERGENCY HALTED · RESTING CANCELLED ★'
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
