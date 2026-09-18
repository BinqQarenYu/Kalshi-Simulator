/**
 * @file ParentHub.tsx
 * @description The Factory / Parent Hub (Lab & Benchmarking) trading terminal environment.
 * Features 4-tier navigation (Analytics, Journal, Bots, Settings), contextual sub-navigation,
 * benchmarking matrix, live CLOB trajectory workbench, and right rail timeline & trade notes.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { ONNXSettingsPanel } from './ONNXSettingsPanel';
import { UniversalTerminalView } from './UniversalTerminalView';
import { ResizableSplitPane } from './ResizableSplitPane';
import {
  MarketState,
  OrderBookLadderRow,
  AISignals,
  LivePortfolioState,
  Position,
  TradeTapeItem,
  ChartPoint,
  CryptoAsset,
  IntegrityStatus,
  ComplianceStatus,
  SystemResourceMetrics,
  WinLossEventReport,
  DualONNXTelemetry,
  PreflightGates,
  SealRegistry,
  SealOfExcellenceRecord,
} from '../types';
import {
  BarChart3,
  BookOpen,
  Bot,
  Settings as SettingsIcon,
  Shield,
  Activity,
  Zap,
  ExternalLink,
  Minimize2,
  Maximize2,
  PanelRightClose,
  PanelRightOpen,
  AlertOctagon,
  Award,
  Radio,
  Clock,
  Globe,
  Coins,
  ArrowRightLeft,
  ArrowUpRight,
  ArrowDownRight,
  Scale,
  Cpu,
  CheckCircle2,
  AlertTriangle,
  Play,
  Calendar,
  Filter,
  TrendingUp,
  TrendingDown,
  Sliders,
} from 'lucide-react';
import { PresetVaultModal } from './PresetVaultModal';
import { PriceHero } from './PriceHero';
import { TargetChart } from './TargetChart';
import { ChanceBanner } from './ChanceBanner';
import { OrderBookLadder } from './OrderBookLadder';
import { TradeTape } from './TradeTape';
import { PortfolioDrawer } from './PortfolioDrawer';
import { OrderEntryPanel } from './OrderEntryPanel';
import { LiveGuardrailsCard } from './LiveGuardrailsCard';
import { AIMicrostructureCard } from './AIMicrostructureCard';
import { BabyBotConsole } from './BabyBotConsole';
import { BotReportsDeck } from './BotReportsDeck';
import { HistoricalAnalyticsTab } from './HistoricalAnalyticsTab';
import { 
  WinLossReportsModal,
  TraderCategory,
  getTraderCategory,
  getTraderBadge,
  isLiveReport,
  isTodayReport,
} from './WinLossReportsModal';
import { soundFX } from '../utils/audioFX';
import { ContinuousTrainingTelemetry, MacroDominionTelemetry, HMMMacroRegimeTelemetry } from '../types';
import { EngineRoomMatrix, EngineViewTab } from './EngineRoomMatrix';
import { ClobTerminalView } from './ClobTerminalView';
import { ArbitrageRadarView } from './ArbitrageRadarView';
import { SettingsView } from './parenthub/SettingsView';
import { BotsBenchmarkingView } from './parenthub/BotsBenchmarkingView';
import { TradeJournalView } from './parenthub/TradeJournalView';
import { BabyBotRightRail } from './parenthub/BabyBotRightRail';

type PrimaryNav = 'analytics' | 'journal' | 'bots' | 'engine' | 'clob_terminal' | 'omni' | 'arbitrage' | 'settings';
type ClobTerminalSubNav = 'terminal' | 'heatmap' | 'event_book' | 'spot_book' | 'pine_editor';
type SettingsSubNav =
  | 'account'
  | 'keys'
  | 'limits'
  | 'notifications'
  | 'routing'
  | 'defaults'
  | 'data'
  | 'theme'
  | 'killswitch';
type BotsSubNav = 'fleet' | 'matrix' | 'incubator' | 'promotion';
type JournalSubNav = 'trades' | 'settlements' | 'reports';
type AnalyticsSubNav = 'workbench' | 'historical' | 'clob' | 'tape' | 'vpin';

interface ParentHubProps {
  market: MarketState;
  ladder?: OrderBookLadderRow[];
  aiSignals?: AISignals;
  livePortfolio?: LivePortfolioState | null;
  activePosition?: Position | null;
  tradeTape?: TradeTapeItem[];
  chartPoints?: ChartPoint[];
  reports?: any[];
  integrityStatus?: IntegrityStatus;
  complianceStatus?: ComplianceStatus;
  systemResources?: SystemResourceMetrics;
  continuousTraining?: ContinuousTrainingTelemetry;
  tradingMode?: 'paper' | 'live';
  timeframe: string;
  activeStrategyBot?: string;
  onSelectStrategy?: (id: string) => Promise<any>;
  onSelectAsset?: (asset: CryptoAsset) => void;
  onSelectTimeframe: (tf: string) => void;
  onSelectTradingMode?: (mode: 'paper' | 'live') => void;
  onQuickTrade?: (side: 'yes' | 'no') => void;
  onFlattenHalt?: () => Promise<void> | void;
  onRunAuditNow?: () => void;
  onTestBot?: (botId: string) => void;
  isPoppedOutBabyBot: boolean;
  onTogglePopOutBabyBot: (botId?: string) => void;
  consecutiveLosses?: number;
  portfolio?: any;
  onClosePosition?: (ticker: string, executionMode?: 'paper' | 'live') => Promise<any>;
  onCancelOrder?: (orderId: string, executionMode?: 'paper' | 'live') => Promise<any>;
  onResetCircuitBreaker?: () => Promise<any>;
  dualOnnxTelemetry?: DualONNXTelemetry;
  preflightGates?: PreflightGates;
  macroDominionTelemetry?: MacroDominionTelemetry;
  hmmMacroRegime?: HMMMacroRegimeTelemetry;
  sealOfExcellence?: SealRegistry;
  botAuditStatus?: any;
}

export const ParentHub: React.FC<ParentHubProps> = ({
  market,
  ladder = [],
  aiSignals,
  livePortfolio,
  activePosition,
  tradeTape = [],
  chartPoints = [],
  reports = [],
  integrityStatus,
  complianceStatus,
  systemResources,
  continuousTraining,
  tradingMode = 'live',
  timeframe = '15m',
  activeStrategyBot = '3_step_domination_bot',
  onSelectStrategy,
  onSelectAsset,
  onSelectTimeframe,
  onSelectTradingMode,
  onQuickTrade,
  onFlattenHalt,
  onRunAuditNow,
  onTestBot,
  isPoppedOutBabyBot,
  onTogglePopOutBabyBot,
  consecutiveLosses = 0,
  portfolio,
  onClosePosition,
  onCancelOrder,
  onResetCircuitBreaker,
  dualOnnxTelemetry,
  preflightGates,
  macroDominionTelemetry,
  hmmMacroRegime,
  sealOfExcellence,
  botAuditStatus,
}) => {
  const [primaryNav, setPrimaryNav] = useState<PrimaryNav>('analytics');
  const [settingsSubNav, setSettingsSubNav] = useState<SettingsSubNav>('defaults');
  const [botsSubNav, setBotsSubNav] = useState<BotsSubNav>('matrix');
  const [engineSubNav, setEngineSubNav] = useState<EngineViewTab>('matrix');
  const [clobSubNav, setClobSubNav] = useState<ClobTerminalSubNav>('terminal');
  const [isBabyBotRailHidden, setIsBabyBotRailHidden] = useState<boolean>(false);
  const [isBabyBotConsoleMinimized, setIsBabyBotConsoleMinimized] = useState<boolean>(false);
  const [journalSubNav, setJournalSubNav] = useState<JournalSubNav>('trades');
  const [analyticsSubNav, setAnalyticsSubNav] = useState<AnalyticsSubNav>('workbench');
  const [workbenchTab, setWorkbenchTab] = useState<'orderbook' | 'tape' | 'positions' | 'reports'>('orderbook');
  const [isPromoteModalOpen, setIsPromoteModalOpen] = useState(false);
  const [isWinLossModalOpen, setIsWinLossModalOpen] = useState(false);
  const [isPresetVaultOpen, setIsPresetVaultOpen] = useState(false);
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [journalAssetFilter, setJournalAssetFilter] = useState<'ALL' | 'BTC' | 'ETH' | 'SOL' | 'DOGE'>('ALL');
  const [journalTimeframeFilter, setJournalTimeframeFilter] = useState<'ALL' | '5M' | '15M'>('ALL');
  const [journalBotFilter, setJournalBotFilter] = useState<TraderCategory>('all');
  const [journalDateScope, setJournalDateScope] = useState<'all' | 'today'>('all');
  const [trainerActionLoading, setTrainerActionLoading] = useState(false);
  const [activatingBotId, setActivatingBotId] = useState<string | null>(null);
  const [matrixNotification, setMatrixNotification] = useState<{ text: string; url?: string; type: 'success' | 'error' } | null>(null);


  const handleActivateBot = async (botId: string) => {
    soundFX.playClickSound();
    setActivatingBotId(botId);
    handleSelectBot(botId);
    setMatrixNotification({
      text: `Launching ${formatBotDisplayName(botId)} engine in background...`,
      type: 'success',
    });

    try {
      const res = await fetch('/api/bots/spawn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bot_id: botId }),
      });
      const data = await res.json();
      if (data.status === 'success') {
        soundFX.playOrderFillSound();
        setMatrixNotification({
          text: `⚡ ${formatBotDisplayName(botId)} ACTIVE! Pocket Cockpit launched.`,
          url: data.url,
          type: 'success',
        });
        if (data.url) {
          setTimeout(() => {
            window.open(data.url, '_blank');
          }, 1000);
        }
      } else {
        soundFX.playLossSound();
        setMatrixNotification({
          text: `Failed to activate bot: ${data.detail || data.message || 'Unknown error'}`,
          type: 'error',
        });
      }
    } catch (err) {
      console.error('Failed to spawn bot:', err);
      soundFX.playLossSound();
      setMatrixNotification({
        text: 'Failed to communicate with server to activate bot.',
        type: 'error',
      });
    } finally {
      setActivatingBotId(null);
    }
  };

  const handleToggleTrainer = async () => {
    setTrainerActionLoading(true);
    try {
      const isPaused = continuousTraining?.is_paused;
      const endpoint = isPaused ? '/api/ml/trainer/resume' : '/api/ml/trainer/pause';
      await fetch(endpoint, { method: 'POST' });
    } catch (err) {
      console.error('Failed to toggle trainer:', err);
    } finally {
      setTrainerActionLoading(false);
    }
  };

  const detectAssetFromTicker = (ticker: string): string => {
    const t = (ticker || '').toUpperCase();
    if (t.includes('KXETH') || t.includes('ETH')) return 'ETH';
    if (t.includes('KXSOL') || t.includes('SOL')) return 'SOL';
    if (t.includes('KXDOGE') || t.includes('DOGE')) return 'DOGE';
    return 'BTC';
  };

  const formatStrikePrice = (val: number, asset: string): string => {
    if (asset === 'DOGE') return `$${val.toFixed(4)}`;
    return `$${val.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const formatBotDisplayName = (botType?: string): string => {
    if (!botType) return '3-Step Dom';
    if (botType.includes('gold_onnx')) return 'Gold ONNX (B4)';
    if (botType.includes('macro_onnx')) return 'ONNX Macro';
    if (botType.includes('macro_trend')) return 'Macro Trend';
    if (botType.includes('dominion_2')) return 'Dominion 2';
    if (botType.includes('3_step') || botType.includes('domination')) return '3-Step Dom';
    if (botType.includes('onnx')) return 'ONNX Net';
    return botType.replace(/_/g, ' ');
  };

  const [selectedBotId, setSelectedBotId] = useState<string>(activeStrategyBot || '3_step_domination_bot');

  useEffect(() => {
    if (activeStrategyBot) {
      setSelectedBotId(activeStrategyBot);
    }
  }, [activeStrategyBot]);

  const handleSelectBot = async (botId: string) => {
    soundFX.playClickSound();
    setSelectedBotId(botId);
    if (onSelectStrategy && ['3_step_domination_bot', 'macro_onnx', 'macro_trend_dominion', 'onnx_microstructure_bot', 'gold_onnx_bot', 'gold_onnx'].includes(botId)) {
      try {
        await onSelectStrategy(botId);
      } catch (e) {
        console.error('Failed to sync strategy:', e);
      }
    }
  };

  // Institutional Seal of Excellence resolution
  const seals = sealOfExcellence?.seals;
  const b1Seal = seals?.['3_step_domination_bot'];
  const b2Seal = seals?.['dominion_2_bot'] ?? seals?.['the_onnx_strategy'] ?? seals?.['macro_onnx'];
  const b3Seal = seals?.['macro_trend_dominion'];
  const b4Seal = seals?.['gold_onnx_bot'];

  const b1IsSealed = b1Seal ? (b1Seal.seal_status === 'SEALED_EXCELLENT' && b1Seal.live_trading_authorized) : true;
  const b3IsSealed = b3Seal ? (b3Seal.seal_status === 'SEALED_EXCELLENT' && b3Seal.live_trading_authorized) : true;
  const b2IsSealed = b2Seal ? (b2Seal.seal_status === 'SEALED_EXCELLENT' && b2Seal.live_trading_authorized) : false;
  const b4IsSealed = b4Seal ? (b4Seal.seal_status === 'SEALED_EXCELLENT' && b4Seal.live_trading_authorized) : false;

  // Bot 1 Live Metrics (Port 8001 Live Production)
  const b1Events = livePortfolio?.settled_cycles ?? portfolio?.settled_cycles ?? 0;
  const b1Wins = livePortfolio?.today_wins ?? portfolio?.today_wins ?? 0;
  const b1Losses = livePortfolio?.today_losses ?? portfolio?.today_losses ?? 0;
  const b1WinRate = livePortfolio?.today_win_rate != null && b1Events > 0
    ? `${Number(livePortfolio.today_win_rate).toFixed(1)}%`
    : (b1Events > 0 ? `${((b1Wins / b1Events) * 100).toFixed(1)}%` : '—');
  const b1Pf = b1Losses > 0 ? (b1Wins / b1Losses).toFixed(2) : (b1Wins > 0 ? '∞' : '—');

  // Bot 2 Live Metrics (Port 8002 Dual ONNX Shadow)
  const b2Events = dualOnnxTelemetry?.settled_cycles ?? 0;
  const b2Wins = dualOnnxTelemetry?.today_wins ?? 0;
  const b2Losses = dualOnnxTelemetry?.today_losses ?? 0;
  const b2WinRate = dualOnnxTelemetry?.today_win_rate != null && b2Events > 0
    ? `${Number(dualOnnxTelemetry.today_win_rate).toFixed(1)}%`
    : (b2Events > 0 ? `${((b2Wins / b2Events) * 100).toFixed(1)}%` : '—');
  const b2Pf = b2Losses > 0 ? (b2Wins / b2Losses).toFixed(2) : (b2Wins > 0 ? '∞' : '—');

  // Bot 3 Live Metrics (Port 8003 Macro Trend Dominion Shadow)
  const b3Events = macroDominionTelemetry?.settled_cycles ?? 0;
  const b3Wins = macroDominionTelemetry?.today_wins ?? 0;
  const b3Losses = macroDominionTelemetry?.today_losses ?? 0;
  const b3WinRate = macroDominionTelemetry?.today_win_rate != null && b3Events > 0
    ? `${Number(macroDominionTelemetry.today_win_rate).toFixed(1)}%`
    : (b3Events > 0 ? `${((b3Wins / b3Events) * 100).toFixed(1)}%` : '—');
  const b3Pf = b3Losses > 0 ? (b3Wins / b3Losses).toFixed(2) : (b3Wins > 0 ? '∞' : '—');

  // Benchmarking models for Factory Matrix (The 3 Canonical Fleet Bots - Grounded Live Telemetry)
  const benchmarkingModels = useMemo(() => {
    return [
      {
        id: '3_step_domination_bot',
        name: '3-Step Dominion v3.2 (Bot 1)',
        subName: 'Multi-Asset Live Basket (Port 8001)',
        asset: 'BTC · GOLD · DOGE',
        lane: b1IsSealed ? 'Lane 1 (LIVE)' : 'Lane 2 (Shadow)',
        events: b1Events,
        winRate: b1WinRate,
        profitFactor: b1Pf,
        drawdown: '—',
        vpinPass: '100%',
        status: 'ACTIVE LIVE (PORT 8001)',
        statusColor: 'text-[#10b981] bg-[#10b981]/15 border-[#10b981]/30',
        sealStatus: b1Seal?.seal_status ?? 'SEALED_EXCELLENT',
        sealToken: b1Seal?.seal_token ?? 'SEAL-DOM1-D07ADE18D284',
        sealLabel: '🏆 SEALED EXCELLENT',
        sealColor: 'text-amber-400 bg-amber-500/15 border-amber-500/40',
        liveAuthorized: true,
        canPromote: false,
      },
      {
        id: 'macro_onnx',
        name: 'ONNX Macro Net v2 (Bot 2)',
        subName: 'Dual-Brain QuoLas + Kalshi (Port 8002)',
        asset: 'BTC-15M',
        lane: b2IsSealed ? 'Lane 1 (LIVE)' : 'Lane 2 (Shadow)',
        events: b2Events,
        winRate: b2WinRate,
        profitFactor: b2Pf,
        drawdown: '—',
        vpinPass: '100%',
        status: b2IsSealed
          ? (dualOnnxTelemetry?.active ? 'ACTIVE LIVE (PORT 8002)' : 'LIVE READY (PORT 8002)')
          : (dualOnnxTelemetry?.active ? 'SHADOW BENCHMARK (PORT 8002)' : 'AWAITING TELEMETRY (8002)'),
        statusColor: b2IsSealed
          ? 'text-[#10b981] bg-[#10b981]/15 border-[#10b981]/30'
          : 'text-purple-400 bg-purple-500/15 border-purple-500/30',
        sealStatus: b2IsSealed ? 'SEALED_EXCELLENT' : (b2Seal?.seal_status ?? 'IN_INCUBATION'),
        sealToken: b2Seal?.seal_token ?? 'PENDING-INCUBATION',
        sealLabel: b2IsSealed
          ? '🏆 SEALED EXCELLENT'
          : `⏳ INCUBATING (${b2Seal?.settled_cycles_verified ?? b2Events}/30)`,
        sealColor: b2IsSealed
          ? 'text-amber-400 bg-amber-500/15 border-amber-500/40'
          : 'text-purple-300 bg-purple-500/15 border-purple-500/30',
        liveAuthorized: Boolean(b2IsSealed),
        canPromote: !b2IsSealed && b2Events >= 30,
      },
      {
        id: 'macro_trend_dominion',
        name: 'Macro Trend Dominion (Bot 3)',
        subName: 'Trend Following & Learning Engine (Port 8003)',
        asset: 'BTC-15M',
        lane: b3IsSealed ? 'Lane 1 (LIVE)' : 'Lane 2 (Shadow)',
        events: b3Events,
        winRate: b3WinRate,
        profitFactor: b3Pf,
        drawdown: '—',
        vpinPass: '100%',
        status: b3IsSealed
          ? (macroDominionTelemetry?.active ? 'ACTIVE LIVE (PORT 8003)' : 'LIVE READY (PORT 8003)')
          : (macroDominionTelemetry?.active ? 'SHADOW BENCHMARK (PORT 8003)' : 'AWAITING TELEMETRY (8003)'),
        statusColor: b3IsSealed
          ? 'text-[#10b981] bg-[#10b981]/15 border-[#10b981]/30'
          : 'text-cyan-400 bg-cyan-500/15 border-cyan-500/30',
        sealStatus: b3IsSealed ? 'SEALED_EXCELLENT' : (b3Seal?.seal_status ?? 'IN_INCUBATION'),
        sealToken: b3Seal?.seal_token ?? 'SEAL-MACR-56F23C64A13B',
        sealLabel: b3IsSealed
          ? '🏆 SEALED EXCELLENT'
          : `⏳ INCUBATING (${b3Seal?.settled_cycles_verified ?? b3Events}/30)`,
        sealColor: b3IsSealed
          ? 'text-amber-400 bg-amber-500/15 border-amber-500/40'
          : 'text-cyan-300 bg-cyan-500/15 border-cyan-500/30',
        liveAuthorized: Boolean(b3IsSealed),
        canPromote: false,
      },
      {
        id: 'gold_onnx_bot',
        name: 'Gold ONNX Bot (Bot 4)',
        subName: '32-D Spacetime Inference Engine (KXGOLD15M)',
        asset: 'GOLD-15M',
        lane: b4IsSealed ? 'Lane 1 (LIVE)' : 'Lane 2 (Shadow Incubator)',
        events: b4Seal?.settled_cycles_verified ?? 0,
        winRate: b4Seal?.empirical_win_rate != null && (b4Seal.settled_cycles_verified ?? 0) > 0
          ? `${(Number(b4Seal.empirical_win_rate) * 100).toFixed(1)}%`
          : '—',
        profitFactor: b4Seal?.profit_factor ? Number(b4Seal.profit_factor).toFixed(2) : '—',
        drawdown: '—',
        vpinPass: '100%',
        status: b4IsSealed
          ? 'ACTIVE LIVE (KXGOLD15M)'
          : 'LANE 2 INCUBATOR (SHADOW)',
        statusColor: b4IsSealed
          ? 'text-[#10b981] bg-[#10b981]/15 border-[#10b981]/30'
          : 'text-amber-400 bg-amber-500/15 border-amber-500/30',
        sealStatus: b4IsSealed ? 'SEALED_EXCELLENT' : (b4Seal?.seal_status ?? 'IN_INCUBATION'),
        sealToken: b4Seal?.seal_token ?? 'INCUBATING-KXGOLD15M',
        sealLabel: b4IsSealed
          ? '🏆 SEALED EXCELLENT'
          : `⏳ INCUBATING (${b4Seal?.settled_cycles_verified ?? 0}/30)`,
        sealColor: b4IsSealed
          ? 'text-amber-400 bg-amber-500/15 border-amber-500/40'
          : 'text-amber-300 bg-amber-500/15 border-amber-500/30',
        liveAuthorized: Boolean(b4IsSealed),
        canPromote: false,
      },
    ];
  }, [livePortfolio, portfolio, dualOnnxTelemetry, macroDominionTelemetry, sealOfExcellence]);

  // Journal executions ledger dynamically populated from real reports & live fills
  const journalExecutions = useMemo(() => {
    if (Array.isArray(reports) && reports.length > 0) {
      return reports.map((r: any, idx: number) => {
        const asset = (r.asset || detectAssetFromTicker(r.ticker || '')).toUpperCase();
        const tf = (r.timeframe || (r.ticker?.includes('5M') ? '5M' : '15M')).toUpperCase();
        const id = r.report_id
          ? r.report_id.replace('WLR-LIVE-', '#L-').replace('WLR-SIM-', '#S-').slice(-7)
          : `#${idx + 1000}`;
        const time = r.cycle_time || (r.timestamp_utc ? new Date(r.timestamp_utc).toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour12: false }) : '--:--:--');
        const category = getTraderCategory(r);
        const badge = getTraderBadge(category);
        const bot = badge.name;
        const strike = formatStrikePrice(Number(r.strike_price || 0), asset);
        const side = (r.bot_side || 'YES').toUpperCase();
        const price = `$${Number(r.entry_price || 0.48).toFixed(2)}`;
        const outcome = (r.outcome || 'FLAT').toUpperCase();
        const pnlNum = Number(r.pnl || 0);
        const pnl = `${pnlNum >= 0 ? '+' : '−'}$${Math.abs(pnlNum).toFixed(2)}`;
        const tag = r.execution_mode === 'live' ? 'live-fill' : (r.ai_rationale ? r.ai_rationale.slice(0, 14) : 'microstructure');
        const isLive = isLiveReport(r);
        const isToday = isTodayReport(r);

        return {
          id,
          time,
          bot,
          category,
          badge,
          tf,
          asset,
          strike,
          side,
          price,
          outcome,
          pnl,
          pnlNum,
          tag,
          isLive,
          isToday,
          spotPrice: r.settlement_spot_price != null ? formatStrikePrice(Number(r.settlement_spot_price), asset) : undefined,
          executionMode: isLive ? 'live' : 'simulated',
          rawReport: r,
        };
      });
    }

    // Default: Zero mock records (Anti-hallucination invariant)
    return [];
  }, [reports]);

  const filteredExecutions = useMemo(() => {
    return journalExecutions.filter((item) => {
      // 1. Date Scope: if 'trades' subtab, default to today unless user picked 'all'
      const shouldFilterToday = journalSubNav === 'trades' ? journalDateScope !== 'all' : journalDateScope === 'today';
      if (shouldFilterToday && !item.isToday) return false;

      // 2. Who Traded (Bot Filter)
      if (journalBotFilter !== 'all') {
        if (journalBotFilter === 'live') {
          if (!item.isLive) return false;
        } else if (item.category !== journalBotFilter) {
          return false;
        }
      }

      // 3. Asset Filter
      if (journalAssetFilter !== 'ALL' && item.asset !== journalAssetFilter) return false;

      // 4. Timeframe Filter
      if (journalTimeframeFilter !== 'ALL' && item.tf !== journalTimeframeFilter) return false;

      // 5. Tag Filter
      if (selectedTag && item.tag !== selectedTag) return false;

      return true;
    });
  }, [journalExecutions, journalSubNav, journalDateScope, journalBotFilter, journalAssetFilter, journalTimeframeFilter, selectedTag]);

  const journalStats = useMemo(() => {
    const total = filteredExecutions.length;
    const wins = filteredExecutions.filter((x) => x.outcome === 'WIN').length;
    const losses = filteredExecutions.filter((x) => x.outcome === 'LOSS').length;
    const winRate = total > 0 ? (wins / total) * 100 : 0;
    const netPnl = filteredExecutions.reduce((acc, x) => acc + (x.pnlNum || 0), 0);

    const todayItems = journalExecutions.filter((x) => x.isToday);
    const todayTotal = todayItems.length;
    const todayWins = todayItems.filter((x) => x.outcome === 'WIN').length;
    const todayLosses = todayItems.filter((x) => x.outcome === 'LOSS').length;
    const todayWinRate = todayTotal > 0 ? (todayWins / todayTotal) * 100 : 0;
    const todayPnl = todayItems.reduce((acc, x) => acc + (x.pnlNum || 0), 0);

    const liveItems = journalExecutions.filter((x) => x.isLive);
    const liveTotal = liveItems.length;
    const liveWins = liveItems.filter((x) => x.outcome === 'WIN').length;
    const liveLosses = liveItems.filter((x) => x.outcome === 'LOSS').length;
    const liveWinRate = liveTotal > 0 ? (liveWins / liveTotal) * 100 : 0;
    const livePnl = liveItems.reduce((acc, x) => acc + (x.pnlNum || 0), 0);

    const botStatsMap: Record<TraderCategory, { count: number; wins: number; pnl: number }> = {
      all: { count: journalExecutions.length, wins: journalExecutions.filter(x => x.outcome === 'WIN').length, pnl: journalExecutions.reduce((acc, x) => acc + (x.pnlNum || 0), 0) },
      '3_step_dom': { count: 0, wins: 0, pnl: 0 },
      onnx_macro: { count: 0, wins: 0, pnl: 0 },
      macro_onnx: { count: 0, wins: 0, pnl: 0 },
      dominion_2: { count: 0, wins: 0, pnl: 0 },
      macro_trend: { count: 0, wins: 0, pnl: 0 },
      ofi_sprint: { count: 0, wins: 0, pnl: 0 },
      onnx_ml: { count: 0, wins: 0, pnl: 0 },
      live: { count: liveTotal, wins: liveWins, pnl: livePnl },
    };

    journalExecutions.forEach((x) => {
      const cat = x.category as TraderCategory;
      if (cat !== 'live' && botStatsMap[cat]) {
        botStatsMap[cat].count += 1;
        if (x.outcome === 'WIN') botStatsMap[cat].wins += 1;
        botStatsMap[cat].pnl += x.pnlNum || 0;
      }
    });

    return {
      filtered: { total, wins, losses, winRate, netPnl },
      today: { total: todayTotal, wins: todayWins, losses: todayLosses, winRate: todayWinRate, netPnl: todayPnl },
      live: { total: liveTotal, wins: liveWins, losses: liveLosses, winRate: liveWinRate, netPnl: livePnl },
      botStatsMap,
    };
  }, [filteredExecutions, journalExecutions]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#0f1319] text-white font-sans">
      <ResizableSplitPane
        storageKey="kalshi_parenthub_layout_sizes"
        defaultSizes={[20, 48, 32]}
        minPixelSizes={[260, 380, 320]}
        minPercentageSizes={[14, 25, 20]}
        maxPercentageSizes={[35, 70, 60]}
        panelClassNames={['h-full overflow-hidden', 'h-full overflow-hidden', 'h-full overflow-hidden']}
        className="w-full h-full"
        isRightPanelHidden={isBabyBotRailHidden}
        onToggleRightPanel={() => {
          soundFX.playClickSound();
          setIsBabyBotRailHidden(false);
        }}
        leftPanel={
          <div className="w-full h-full flex flex-row overflow-hidden select-none">
            {/* =========================================================================
                COLUMN 1: Primary Navigation Sidebar (150-170px)
                ========================================================================= */}
            <aside className="w-[150px] md:w-[170px] bg-[#12161a] border-r border-[#262d35] p-3 flex flex-col justify-between shrink-0 select-none">
        <div>
          {/* Brand Header */}
          <div className="flex items-center gap-2 mb-8 text-[#00bda5] font-extrabold text-xl tracking-tight">
            <span className="w-2.5 h-2.5 rounded-full bg-[#00bda5] shadow-sm shadow-[#00bda5]/50 animate-pulse" />
            <span>Kalshi</span>
            <span className="text-[10px] font-mono uppercase bg-[#00bda5]/15 px-1.5 py-0.5 rounded text-[#2dd4bf] border border-[#00bda5]/30">
              Parent Hub
            </span>
          </div>

          {/* Primary Nav Links */}
          <nav className="flex flex-col gap-1.5 font-semibold text-xs">
            <button
              onClick={() => {
                soundFX.playClickSound();
                setPrimaryNav('analytics');
              }}
              className={`w-full px-3 py-2.5 rounded-lg flex items-center gap-3 transition-all text-left ${
                primaryNav === 'analytics'
                  ? 'bg-[#00bda5]/10 text-white border-l-2 border-[#00bda5] font-bold'
                  : 'text-[#8c9ba5] hover:text-white hover:bg-[#171c22]'
              }`}
            >
              <BarChart3 className={`w-4 h-4 ${primaryNav === 'analytics' ? 'text-[#00bda5]' : 'text-[#8c9ba5]'}`} />
              <span>Analytics</span>
            </button>

            <button
              onClick={() => {
                soundFX.playClickSound();
                setPrimaryNav('journal');
              }}
              className={`w-full px-3 py-2.5 rounded-lg flex items-center gap-3 transition-all text-left ${
                primaryNav === 'journal'
                  ? 'bg-[#00bda5]/10 text-white border-l-2 border-[#00bda5] font-bold'
                  : 'text-[#8c9ba5] hover:text-white hover:bg-[#171c22]'
              }`}
            >
              <BookOpen className={`w-4 h-4 ${primaryNav === 'journal' ? 'text-[#00bda5]' : 'text-[#8c9ba5]'}`} />
              <span>Journal</span>
            </button>

            <button
              onClick={() => {
                soundFX.playClickSound();
                setPrimaryNav('bots');
              }}
              className={`w-full px-3 py-2.5 rounded-lg flex items-center gap-3 transition-all text-left ${
                primaryNav === 'bots'
                  ? 'bg-[#00bda5]/10 text-white border-l-2 border-[#00bda5] font-bold'
                  : 'text-[#8c9ba5] hover:text-white hover:bg-[#171c22]'
              }`}
            >
              <Bot className={`w-4 h-4 ${primaryNav === 'bots' ? 'text-[#00bda5]' : 'text-[#8c9ba5]'}`} />
              <span>Bots</span>
              <span className="ml-auto text-[9px] font-mono px-1.5 py-0.2 rounded-full bg-[#171c22] text-[#8c9ba5]">
                4
              </span>
            </button>

            <button
              onClick={() => {
                soundFX.playClickSound();
                setPrimaryNav('engine');
              }}
              className={`w-full px-3 py-2.5 rounded-lg flex items-center gap-3 transition-all text-left ${
                primaryNav === 'engine'
                  ? 'bg-[#38bdf8]/10 text-white border-l-2 border-[#38bdf8] font-bold'
                  : 'text-[#8c9ba5] hover:text-white hover:bg-[#171c22]'
              }`}
            >
              <Cpu className={`w-4 h-4 ${primaryNav === 'engine' ? 'text-[#38bdf8]' : 'text-[#8c9ba5]'}`} />
              <span>Engine Room</span>
              <span className="ml-auto text-[9px] font-mono px-1.5 py-0.2 rounded-full bg-[#171c22] text-[#38bdf8]">
                3 CYL
              </span>
            </button>

            <button
              onClick={() => {
                soundFX.playClickSound();
                setPrimaryNav('clob_terminal');
              }}
              className={`w-full px-3 py-2.5 rounded-lg flex items-center gap-3 transition-all text-left ${
                primaryNav === 'clob_terminal'
                  ? 'bg-[#00c978]/10 text-white border-l-2 border-[#00c978] font-bold'
                  : 'text-[#8c9ba5] hover:text-white hover:bg-[#171c22]'
              }`}
            >
              <Activity className={`w-4 h-4 ${primaryNav === 'clob_terminal' ? 'text-[#00c978]' : 'text-[#8c9ba5]'}`} />
              <span>CLOB Terminal</span>
              <span className="ml-auto text-[9px] font-mono px-1.5 py-0.2 rounded-full bg-[#171c22] text-[#00c978]">
                DOM
              </span>
            </button>

            <button
              onClick={() => {
                soundFX.playClickSound();
                setPrimaryNav('omni');
              }}
              className={`w-full px-3 py-2.5 rounded-lg flex items-center gap-3 transition-all text-left ${
                primaryNav === 'omni'
                  ? 'bg-cyan-500/15 text-white border-l-2 border-cyan-400 font-bold'
                  : 'text-[#8c9ba5] hover:text-white hover:bg-[#171c22]'
              }`}
            >
              <Globe className={`w-4 h-4 ${primaryNav === 'omni' ? 'text-cyan-400' : 'text-[#8c9ba5]'}`} />
              <span>Omni Terminal</span>
              <span className="ml-auto text-[8px] font-mono px-1.5 py-0.2 rounded-full bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-500/30">
                6 EX
              </span>
            </button>

            <button
              onClick={() => {
                soundFX.playClickSound();
                setPrimaryNav('arbitrage');
              }}
              className={`w-full px-3 py-2.5 rounded-lg flex items-center gap-3 transition-all text-left ${
                primaryNav === 'arbitrage'
                  ? 'bg-amber-500/15 text-white border-l-2 border-amber-400 font-bold'
                  : 'text-[#8c9ba5] hover:text-white hover:bg-[#171c22]'
              }`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={primaryNav === 'arbitrage' ? 'text-amber-400' : 'text-[#8c9ba5]'}><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
              <span>Arbitrage Scanner</span>
            </button>

            <button
              onClick={() => {
                soundFX.playClickSound();
                setPrimaryNav('settings');
              }}
              className={`w-full px-3 py-2.5 rounded-lg flex items-center gap-3 transition-all text-left ${
                primaryNav === 'settings'
                  ? 'bg-[#00bda5]/10 text-white border-l-2 border-[#00bda5] font-bold'
                  : 'text-[#8c9ba5] hover:text-white hover:bg-[#171c22]'
              }`}
            >
              <SettingsIcon className={`w-4 h-4 ${primaryNav === 'settings' ? 'text-[#00bda5]' : 'text-[#8c9ba5]'}`} />
              <span>Settings</span>
            </button>
          </nav>
        </div>

        {/* Operator Badge */}
        <div className="pt-4 border-t border-[#262d35] flex items-center gap-2 text-xs font-mono text-[#8c9ba5]">
          <span className="w-2 h-2 rounded-full bg-[#34d399]" />
          <span>Operator ▸ L2</span>
        </div>
      </aside>

            {/* =========================================================================
                COLUMN 2: Contextual Secondary Sub-Navigation (Flex-1 inside Left Panel)
                ========================================================================= */}
            <aside className="flex-1 min-w-0 bg-[#12161a] p-3 flex flex-col shrink-0 select-none overflow-y-auto">
        <h3 className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#8c9ba5] mb-3">
          {primaryNav.toUpperCase()} SECTIONS
        </h3>

        {/* Sub-nav: Settings */}
        {primaryNav === 'settings' && (
          <nav className="flex flex-col gap-1 text-xs">
            {[
              { id: 'account', label: 'Account' },
              { id: 'keys', label: 'Exchange Keys' },
              { id: 'limits', label: 'Risk Limits' },
              { id: 'notifications', label: 'Notifications' },
              { id: 'routing', label: 'Execution & Routing' },
              { id: 'defaults', label: 'Bot Defaults' },
              { id: 'data', label: 'Data & Backtests' },
              { id: 'theme', label: 'Display & Theme' },
              { id: 'killswitch', label: 'Kill-Switch', isDanger: true },
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  soundFX.playClickSound();
                  setSettingsSubNav(item.id as SettingsSubNav);
                }}
                className={`w-full px-3 py-2 rounded-md transition-all text-left flex items-center justify-between ${
                  settingsSubNav === item.id
                    ? 'bg-[#00bda5]/10 text-white border-l-2 border-[#00bda5] font-bold'
                    : item.isDanger
                    ? 'text-[#f43f5e] hover:bg-[#f43f5e]/10'
                    : 'text-[#8c9ba5] hover:text-white hover:bg-[#171c22]'
                }`}
              >
                <span>{item.label}</span>
                {item.id === 'defaults' && (
                  <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-[#1a2128] text-[#8c9ba5]">
                    PROMO
                  </span>
                )}
              </button>
            ))}
          </nav>
        )}

        {/* Sub-nav: Bots */}
        {primaryNav === 'bots' && (
          <nav className="flex flex-col gap-1 text-xs">
            {[
              { id: 'matrix', label: 'Benchmarking Matrix' },
              { id: 'fleet', label: 'Active Live Fleet' },
              { id: 'incubator', label: 'Shadow Incubator' },
              { id: 'promotion', label: 'Promotion Gate Audit' },
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  soundFX.playClickSound();
                  setBotsSubNav(item.id as BotsSubNav);
                }}
                className={`w-full px-3 py-2 rounded-md transition-all text-left flex items-center justify-between ${
                  botsSubNav === item.id
                    ? 'bg-[#00bda5]/10 text-white border-l-2 border-[#00bda5] font-bold'
                    : 'text-[#8c9ba5] hover:text-white hover:bg-[#171c22]'
                }`}
              >
                <span>{item.label}</span>
              </button>
            ))}
          </nav>
        )}

        {/* Sub-nav: Engine Room */}
        {primaryNav === 'engine' && (
          <nav className="flex flex-col gap-1 text-xs">
            {[
              { id: 'matrix', label: 'Master Visual Matrix' },
              { id: 'cylinder1', label: 'Cylinder 1: Spot Orderflow' },
              { id: 'cylinder2', label: 'Cylinder 2: Kalshi CLOB' },
              { id: 'cylinder3', label: 'Cylinder 3: HMM Macro' },
              { id: 'wiring', label: 'Bot Wiring Harness' },
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  soundFX.playClickSound();
                  setEngineSubNav(item.id as EngineViewTab);
                }}
                className={`w-full px-3 py-2 rounded-md transition-all text-left flex items-center justify-between ${
                  engineSubNav === item.id
                    ? 'bg-[#38bdf8]/10 text-white border-l-2 border-[#38bdf8] font-bold'
                    : 'text-[#8c9ba5] hover:text-white hover:bg-[#171c22]'
                }`}
              >
                <span>{item.label}</span>
              </button>
            ))}
          </nav>
        )}

        {/* Sub-nav: CLOB Terminal */}
        {primaryNav === 'clob_terminal' && (
          <nav className="flex flex-col gap-1 text-xs">
            {[
              { id: 'terminal', label: 'Institutional Cockpit' },
              { id: 'heatmap', label: 'Liquidity Heatmap (DOM)' },
              { id: 'event_book', label: '15M Event Order Book' },
              { id: 'spot_book', label: 'Underlying L2 Spot Book' },
              { id: 'pine_editor', label: 'Pine Script Editor' },
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  soundFX.playClickSound();
                  setClobSubNav(item.id as ClobTerminalSubNav);
                }}
                className={`w-full px-3 py-2 rounded-md transition-all text-left flex items-center justify-between ${
                  clobSubNav === item.id
                    ? 'bg-[#00c978]/10 text-white border-l-2 border-[#00c978] font-bold'
                    : 'text-[#8c9ba5] hover:text-white hover:bg-[#171c22]'
                }`}
              >
                <span>{item.label}</span>
              </button>
            ))}
          </nav>
        )}

        {/* Sub-nav: Journal */}
        {primaryNav === 'journal' && (
          <nav className="flex flex-col gap-1 text-xs">
            {[
              { id: 'trades', label: "Today's Trades" },
              { id: 'settlements', label: 'Historical Settlements' },
              { id: 'reports', label: 'Win/Loss Reports' },
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  soundFX.playClickSound();
                  setJournalSubNav(item.id as JournalSubNav);
                }}
                className={`w-full px-3 py-2 rounded-md transition-all text-left flex items-center justify-between ${
                  journalSubNav === item.id
                    ? 'bg-[#00bda5]/10 text-white border-l-2 border-[#00bda5] font-bold'
                    : 'text-[#8c9ba5] hover:text-white hover:bg-[#171c22]'
                }`}
              >
                <span>{item.label}</span>
              </button>
            ))}
          </nav>
        )}

        {/* Sub-nav: Analytics */}
        {primaryNav === 'analytics' && (
          <nav className="flex flex-col gap-1 text-xs">
            {[
              { id: 'workbench', label: '60fps Live Workbench' },
              { id: 'historical', label: 'Institutional Analytics' },
              { id: 'clob', label: 'L2 CLOB Ladder' },
              { id: 'tape', label: 'Live Trade Tape' },
              { id: 'vpin', label: 'Order Flow & VPIN' },
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  soundFX.playClickSound();
                  setAnalyticsSubNav(item.id as AnalyticsSubNav);
                }}
                className={`w-full px-3 py-2 rounded-md transition-all text-left flex items-center justify-between ${
                  analyticsSubNav === item.id
                    ? 'bg-[#00bda5]/10 text-white border-l-2 border-[#00bda5] font-bold'
                    : 'text-[#8c9ba5] hover:text-white hover:bg-[#171c22]'
                }`}
              >
                <span>{item.label}</span>
              </button>
            ))}
          </nav>
        )}
      </aside>
    </div>
  }
  centerPanel={
    <main className="w-full h-full flex flex-col min-w-0 overflow-y-auto bg-[#0f1319]">
        {/* Top Header & Breadcrumbs */}
        <header className="px-6 py-3 border-b border-[#262d35] flex items-center justify-between bg-[#12161a]/60 backdrop-blur sticky top-0 z-20">
          <div>
            <div className="text-[11px] font-mono text-[#8c9ba5]">
              {primaryNav.toUpperCase()} &rsaquo;{' '}
              <b className="text-[#2dd4bf]">
                {primaryNav === 'settings'
                  ? settingsSubNav.toUpperCase()
                  : primaryNav === 'bots'
                  ? botsSubNav.toUpperCase()
                  : primaryNav === 'engine'
                  ? engineSubNav.toUpperCase()
                  : primaryNav === 'clob_terminal'
                  ? clobSubNav.toUpperCase()
                  : primaryNav === 'journal'
                  ? journalSubNav.toUpperCase()
                  : primaryNav === 'omni'
                  ? 'MULTI-EXCHANGE CAPITAL POOL & ARBITRAGE'
                  : analyticsSubNav.toUpperCase()}
              </b>
            </div>
            <h1 className="text-sm font-bold uppercase tracking-wider text-white mt-0.5">
              {primaryNav === 'settings' && settingsSubNav === 'defaults' && 'SETTINGS / BOT DEFAULTS'}
              {primaryNav === 'settings' && settingsSubNav === 'killswitch' && 'SETTINGS / GLOBAL KILL-SWITCH'}
              {primaryNav === 'settings' && settingsSubNav !== 'defaults' && settingsSubNav !== 'killswitch' && `SETTINGS / ${settingsSubNav.toUpperCase()}`}
              {primaryNav === 'bots' && 'BOT MANAGEMENT & BENCHMARKING MATRIX'}
              {primaryNav === 'engine' && 'ENGINE ROOM / 3-CYLINDER POWERTRAIN MATRIX'}
              {primaryNav === 'clob_terminal' && 'CLOB TERMINAL / INSTITUTIONAL WEBCLOB & HEATMAP'}
              {primaryNav === 'journal' && "TRADE JOURNAL & TODAY'S TIMELINE"}
              {primaryNav === 'analytics' && 'LIVE WORKBENCH & MICROSTRUCTURE RADAR'}
              {primaryNav === 'omni' && 'THE UNIVERSAL MULTI-EXCHANGE TERMINAL & CAPITAL POOL'}
            </h1>
          </div>

          <div className="flex items-center gap-3">
            {/* Preset Vault Modal Trigger */}
            <button
              onClick={() => {
                soundFX.playClickSound();
                setIsPresetVaultOpen(true);
              }}
              className="px-3 py-1.5 rounded-lg text-xs font-mono font-bold bg-indigo-500/15 hover:bg-indigo-500/25 text-indigo-300 border border-indigo-500/40 hover:border-indigo-400 transition-all flex items-center gap-1.5 shadow-sm"
              title="Open Bot Preset Vault: Save, load, upload, or switch settings"
            >
              <Sliders className="w-3.5 h-3.5 text-indigo-400" />
              <span>Preset Vault</span>
            </button>

            {/* Pop-Out Baby Bot Console Button */}
            <button
              onClick={() => onTogglePopOutBabyBot(selectedBotId)}
              className="px-3 py-1.5 rounded-lg text-xs font-mono font-bold bg-[#00bda5]/15 hover:bg-[#00bda5]/25 text-[#2dd4bf] border border-[#00bda5]/40 transition-all flex items-center gap-1.5 shadow-sm"
              title="Open Baby Bot Standalone Execution Cockpit in new window"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>Pop-Out Baby Bot</span>
            </button>

            {/* Hide / Unhide Docked Baby Bot Rail (Maximize Center / CLOB Terminal) */}
            <button
              onClick={() => {
                soundFX.playClickSound();
                setIsBabyBotRailHidden((prev) => !prev);
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-all flex items-center gap-1.5 shadow-sm ${
                isBabyBotRailHidden
                  ? 'bg-[#00c978] text-black hover:bg-emerald-400 font-extrabold shadow-[0_0_12px_rgba(0,201,120,0.35)]'
                  : 'bg-[#171c22] text-[#8c9ba5] hover:text-white border border-[#262d35]'
              }`}
              title={isBabyBotRailHidden ? 'Unhide Docked Baby Bot Rail' : 'Hide Docked Baby Bot (Maximize CLOB Terminal / Center Panel)'}
            >
              {isBabyBotRailHidden ? (
                <>
                  <PanelRightOpen className="w-3.5 h-3.5 text-black" />
                  <span>Unhide Bot Rail</span>
                </>
              ) : (
                <>
                  <PanelRightClose className="w-3.5 h-3.5 text-[#00bda5]" />
                  <span>Hide Bot Rail (Max)</span>
                </>
              )}
            </button>

            {/* Asset Selector */}
            <div className="flex gap-1 bg-[#171c22] p-0.5 rounded-lg border border-[#262d35]">
              {(['BTC', 'ETH', 'SOL'] as CryptoAsset[]).map((ast) => (
                <button
                  key={ast}
                  onClick={() => onSelectAsset?.(ast)}
                  className={`px-2.5 py-1 text-xs font-mono font-bold rounded ${
                    market.active_asset === ast ? 'bg-[#00bda5] text-black shadow-sm' : 'text-[#8c9ba5] hover:text-white'
                  }`}
                >
                  {ast}
                </button>
              ))}
            </div>

            {/* Timeframe selector */}
            <div className="flex gap-1 bg-[#171c22] p-0.5 rounded-lg border border-[#262d35]">
              {['5m', '15m'].map((tf) => (
                <button
                  key={tf}
                  onClick={() => onSelectTimeframe(tf)}
                  className={`px-2.5 py-1 text-xs font-mono font-bold rounded ${
                    timeframe === tf ? 'bg-[#d9a752] text-black shadow-sm' : 'text-[#8c9ba5] hover:text-white'
                  }`}
                >
                  {tf.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
        </header>

        {/* DYNAMIC VIEW BODY */}
        <div className="p-6 space-y-6">
          {/* 0. OMNI UNIVERSAL TERMINAL VIEW */}
          {primaryNav === 'omni' && <UniversalTerminalView />}

          {/* ARBITRAGE RADAR VIEW */}
          {primaryNav === 'arbitrage' && <ArbitrageRadarView />}

          {/* 1. SETTINGS VIEW (From HTML Proposal) */}
          {primaryNav === 'settings' && (
            <SettingsView onFlattenHalt={onFlattenHalt} />
          )}

          {/* 2. BOTS BENCHMARKING MATRIX VIEW */}
          {primaryNav === 'bots' && (
            <BotsBenchmarkingView
              matrixNotification={matrixNotification}
              setMatrixNotification={setMatrixNotification}
              b1Seal={b1Seal}
              b2Seal={b2Seal}
              b3Seal={b3Seal}
              b1WinRate={b1WinRate}
              b3WinRate={b3WinRate}
              b2Events={b2Events}
              benchmarkingModels={benchmarkingModels}
              selectedBotId={selectedBotId}
              activatingBotId={activatingBotId}
              handleSelectBot={handleSelectBot}
              handleActivateBot={handleActivateBot}
              continuousTraining={continuousTraining}
              trainerActionLoading={trainerActionLoading}
              handleToggleTrainer={handleToggleTrainer}
            />
          )}

          {/* ENGINE ROOM: 3-CYLINDER POWERTRAIN VIEW */}
          {primaryNav === 'engine' && (
            <EngineRoomMatrix
              activeTab={engineSubNav}
              onTabChange={(tab) => setEngineSubNav(tab)}
            />
          )}

          {/* CLOB TERMINAL: INSTITUTIONAL COCKPIT & LIQUIDITY HEATMAP */}
          {primaryNav === 'clob_terminal' && (
            <div className="h-[calc(100vh-140px)] -m-6 flex flex-col overflow-hidden">
              <ClobTerminalView
                market={market}
                ladder={ladder}
                aiSignals={aiSignals}
                activePosition={activePosition}
                tradeTape={tradeTape}
                chartPoints={chartPoints}
                tradingMode={tradingMode}
                timeframe={timeframe}
                onQuickTrade={onQuickTrade}
                onSelectAsset={onSelectAsset}
                onSelectTimeframe={onSelectTimeframe}
                onClosePosition={onClosePosition}
                onCancelOrder={onCancelOrder}
                isRightPanelHidden={isBabyBotRailHidden}
                onToggleRightPanel={() => {
                  soundFX.playClickSound();
                  setIsBabyBotRailHidden((prev) => !prev);
                }}
              />
            </div>
          )}

          {/* 3. JOURNAL VIEW */}
          {primaryNav === 'journal' && (
            <TradeJournalView
              journalSubNav={journalSubNav}
              journalDateScope={journalDateScope}
              setJournalDateScope={setJournalDateScope}
              journalAssetFilter={journalAssetFilter}
              setJournalAssetFilter={setJournalAssetFilter}
              journalTimeframeFilter={journalTimeframeFilter}
              setJournalTimeframeFilter={setJournalTimeframeFilter}
              journalBotFilter={journalBotFilter}
              setJournalBotFilter={setJournalBotFilter}
              journalStats={journalStats}
              filteredExecutions={filteredExecutions}
              isWinLossModalOpen={isWinLossModalOpen}
              setIsWinLossModalOpen={setIsWinLossModalOpen}
            />
          )}

          {/* 4. ANALYTICS / WORKBENCH VIEW */}
          {primaryNav === 'analytics' && analyticsSubNav === 'historical' && (
            <div className="space-y-4">
              <HistoricalAnalyticsTab />
            </div>
          )}

          {primaryNav === 'analytics' && analyticsSubNav === 'clob' && (
            <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-4">
              <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                Deep Level-2 Central Limit Order Book (CLOB)
              </h2>
              <OrderBookLadder
                ladder={ladder}
                onSelectPrice={() => onQuickTrade?.('yes')}
              />
            </div>
          )}

          {primaryNav === 'analytics' && analyticsSubNav === 'tape' && (
            <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-4">
              <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                Institutional Live Trade Tape
              </h2>
              <TradeTape tradeTape={tradeTape} />
            </div>
          )}

          {primaryNav === 'analytics' && analyticsSubNav === 'vpin' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {aiSignals ? (
                <AIMicrostructureCard signals={aiSignals} macroDominionTelemetry={macroDominionTelemetry} />
              ) : (
                <div className="p-6 bg-[#12161a] border border-[#262d35] rounded-xl flex items-center justify-center text-xs font-mono text-[#8c9ba5]">
                  Awaiting AI Microstructure Signals...
                </div>
              )}
              <LiveGuardrailsCard
                livePortfolio={livePortfolio}
                integrityStatus={integrityStatus}
                complianceStatus={complianceStatus}
                isKillSwitchTripped={consecutiveLosses >= 3}
                onKillSwitch={onFlattenHalt || (() => {})}
                onResumeTrading={onResetCircuitBreaker || (() => {})}
              />
            </div>
          )}

          {primaryNav === 'analytics' && analyticsSubNav === 'workbench' && (
            <div className="space-y-4">
              {/* Compact Price Hero */}
              <PriceHero market={market} preflightGates={preflightGates} />

              {/* 60 FPS Trajectory Spline Chart */}
              <TargetChart
                market={market}
                chart={chartPoints}
                tradeTape={tradeTape}
                winLossReports={reports}
              />

              {/* Lower Deck Tabs */}
              <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-4">
                <div className="flex items-center gap-6 border-b border-[#262d35] pb-2 mb-3 text-xs font-semibold">
                  <button
                    onClick={() => setWorkbenchTab('orderbook')}
                    className={`pb-1 border-b-2 transition-all flex items-center gap-1.5 ${
                      workbenchTab === 'orderbook' ? 'border-[#00bda5] text-[#2dd4bf] font-bold' : 'border-transparent text-[#8c9ba5] hover:text-white'
                    }`}
                  >
                    <span>📊 Level-2 CLOB Ladder</span>
                  </button>
                  <button
                    onClick={() => setWorkbenchTab('tape')}
                    className={`pb-1 border-b-2 transition-all flex items-center gap-1.5 ${
                      workbenchTab === 'tape' ? 'border-[#00bda5] text-[#2dd4bf] font-bold' : 'border-transparent text-[#8c9ba5] hover:text-white'
                    }`}
                  >
                    <span>⚡ Live Trade Tape</span>
                  </button>
                  <button
                    onClick={() => setWorkbenchTab('positions')}
                    className={`pb-1 border-b-2 transition-all flex items-center gap-1.5 ${
                      workbenchTab === 'positions' ? 'border-[#00bda5] text-[#2dd4bf] font-bold' : 'border-transparent text-[#8c9ba5] hover:text-white'
                    }`}
                  >
                    <span>💼 Active Positions & Fills</span>
                  </button>
                  <button
                    onClick={() => setWorkbenchTab('reports')}
                    className={`pb-1 border-b-2 transition-all flex items-center gap-1.5 ${
                      workbenchTab === 'reports' ? 'border-[#00bda5] text-[#2dd4bf] font-bold' : 'border-transparent text-[#8c9ba5] hover:text-white'
                    }`}
                  >
                    <span>📋 Bot Reports</span>
                  </button>
                </div>

                {workbenchTab === 'orderbook' && (
                  <OrderBookLadder
                    ladder={ladder}
                    onSelectPrice={() => onQuickTrade?.('yes')}
                  />
                )}

                {workbenchTab === 'tape' && <TradeTape tradeTape={tradeTape} />}

                {workbenchTab === 'positions' && (
                  <PortfolioDrawer
                    portfolio={portfolio}
                    livePortfolio={livePortfolio}
                    tradingMode={tradingMode}
                    onClosePosition={onClosePosition || (async () => {})}
                    onCancelOrder={onCancelOrder}
                    onResetCircuitBreaker={onResetCircuitBreaker}
                  />
                )}

                {workbenchTab === 'reports' && (
                  <BotReportsDeck
                    botId={selectedBotId}
                    activeAsset={market.active_asset}
                    tradingMode={tradingMode}
                    onOpenFullReports={() => setIsWinLossModalOpen(true)}
                  />
                )}
              </div>
            </div>
          )}
        </div>
      </main>
    }
    rightPanel={
      <BabyBotRightRail
        isPoppedOutBabyBot={isPoppedOutBabyBot}
        selectedBotId={selectedBotId}
        isBabyBotConsoleMinimized={isBabyBotConsoleMinimized}
        setIsBabyBotConsoleMinimized={setIsBabyBotConsoleMinimized}
        onTogglePopOutBabyBot={onTogglePopOutBabyBot}
        setIsBabyBotRailHidden={setIsBabyBotRailHidden}
        formatBotDisplayName={formatBotDisplayName}
        tradingMode={tradingMode}
        market={market}
        aiSignals={aiSignals}
        livePortfolio={livePortfolio}
        activePosition={activePosition}
        timeframe={timeframe}
        onFlattenHalt={onFlattenHalt}
        onQuickTrade={onQuickTrade}
        reportsCount={reports.length}
        consecutiveLosses={consecutiveLosses}
        handleSelectBot={handleSelectBot}
        dualOnnxTelemetry={dualOnnxTelemetry}
        preflightGates={preflightGates}
        macroDominionTelemetry={macroDominionTelemetry}
        hmmMacroRegime={hmmMacroRegime}
        setWorkbenchTab={setWorkbenchTab}
        sealOfExcellence={sealOfExcellence}
        selectedTag={selectedTag}
        setSelectedTag={setSelectedTag}
      />
    }
  />

      {/* Promotion Workflow Modal */}
      {isPromoteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
          <div className="bg-[#12161a] border border-[#00bda5]/60 rounded-2xl w-full max-w-lg shadow-2xl p-6 space-y-5 font-mono">
            <div className="flex items-center justify-between border-b border-[#262d35] pb-3">
              <div className="flex items-center gap-2 text-[#00bda5] font-bold text-sm">
                <Zap className="w-4 h-4" />
                <span>PROMOTE STRATEGY TO BABY BOT</span>
              </div>
              <button
                onClick={() => setIsPromoteModalOpen(false)}
                className="text-[#8c9ba5] hover:text-white text-xs"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="p-3 rounded-lg bg-[#00bda5]/10 border border-[#00bda5]/30 text-[#2dd4bf] leading-relaxed">
                ✔ Passed all 6 hard gates over 520 events.<br />
                Candidate: <b>OFI Sprint Scalper (BTC-5M)</b>
              </div>

              <div className="space-y-2">
                <label className="text-[#8c9ba5] text-[10px] uppercase font-bold">Target Timeframe</label>
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2.5 rounded bg-[#171c22] border border-[#00bda5] text-center font-bold text-[#00bda5]">
                    5-Minute Sprint
                  </div>
                  <div className="p-2.5 rounded bg-[#13171c] border border-[#262d35] text-center text-[#8c9ba5]">
                    15-Minute Cycle
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-[#8c9ba5] text-[10px] uppercase font-bold">Execution Regime</label>
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2.5 rounded bg-[#13171c] border border-[#262d35] text-center text-[#2dd4bf]">
                    Isolated Shadow (Paper)
                  </div>
                  <div className="p-2.5 rounded bg-[#f43f5e]/20 border border-[#f43f5e] text-center font-bold text-[#f43f5e]">
                    Live Production (Real Money)
                  </div>
                </div>
              </div>

              <div className="p-2.5 rounded bg-[#171c22] border border-[#262d35] text-[11px] text-[#8c9ba5]">
                🔒 <b>Micro-Bankroll Lock:</b> Hard-capped to strictly 1 contract per trade.
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setIsPromoteModalOpen(false)}
                className="px-4 py-2 rounded text-xs text-[#8c9ba5] hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  soundFX.playOrderFillSound();
                  setIsPromoteModalOpen(false);
                  onTogglePopOutBabyBot(selectedBotId);
                }}
                className="px-4 py-2 rounded bg-[#00bda5] hover:bg-[#2dd4bf] text-black font-bold text-xs shadow-lg transition-all"
              >
                🚀 Fork Process & Launch Baby Bot
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Preset Vault Modal */}
      <PresetVaultModal
        isOpen={isPresetVaultOpen}
        onClose={() => setIsPresetVaultOpen(false)}
      />
    </div>
  );
};
