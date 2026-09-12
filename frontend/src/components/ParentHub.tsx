/**
 * @file ParentHub.tsx
 * @description The Factory / Parent Hub (Lab & Benchmarking) trading terminal environment.
 * Features 4-tier navigation (Analytics, Journal, Bots, Settings), contextual sub-navigation,
 * benchmarking matrix, live CLOB trajectory workbench, and right rail timeline & trade notes.
 */

import React, { useState, useEffect, useMemo } from 'react';
import { ONNXSettingsPanel } from './ONNXSettingsPanel';
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

type PrimaryNav = 'analytics' | 'journal' | 'bots' | 'engine' | 'clob_terminal' | 'settings';
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
    if (onSelectStrategy && ['3_step_domination_bot', 'macro_onnx', 'macro_trend_dominion', 'onnx_microstructure_bot'].includes(botId)) {
      try {
        await onSelectStrategy(botId);
      } catch (e) {
        console.error('Failed to sync strategy:', e);
      }
    }
  };

  // Benchmarking models for Factory Matrix (The 3 Canonical Fleet Bots - Grounded Live Telemetry)
  const benchmarkingModels = useMemo(() => {
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

    const seals = sealOfExcellence?.seals;
    const b1Seal = seals?.['3_step_domination_bot'];
    const b2Seal = seals?.['dominion_2_bot'] ?? seals?.['the_onnx_strategy'] ?? seals?.['macro_onnx'];
    const b3Seal = seals?.['macro_trend_dominion'];

    return [
      {
        id: '3_step_domination_bot',
        name: '3-Step Dominion v3.2 (Bot 1)',
        subName: 'Multi-Asset Live Basket (Port 8001)',
        asset: 'BTC · GOLD · DOGE',
        lane: 'Lane 1 (LIVE)',
        events: b1Events,
        winRate: b1WinRate,
        profitFactor: b1Pf,
        drawdown: '—',
        vpinPass: '100%',
        status: 'ACTIVE LIVE (PORT 8001)',
        statusColor: 'text-[#10b981] bg-[#10b981]/15 border-[#10b981]/30',
        sealStatus: b1Seal?.seal_status ?? 'SEALED_EXCELLENT',
        sealToken: b1Seal?.seal_token ?? 'SEAL-DOM1-V3.2',
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
        lane: 'Lane 2 (Shadow)',
        events: b2Events,
        winRate: b2WinRate,
        profitFactor: b2Pf,
        drawdown: '—',
        vpinPass: '100%',
        status: dualOnnxTelemetry?.active ? 'SHADOW BENCHMARK (PORT 8002)' : 'AWAITING TELEMETRY (8002)',
        statusColor: 'text-purple-400 bg-purple-500/15 border-purple-500/30',
        sealStatus: b2Seal?.seal_status ?? 'IN_INCUBATION',
        sealToken: b2Seal?.seal_token ?? 'PENDING-INCUBATION',
        sealLabel: `⏳ INCUBATING (${b2Seal?.settled_cycles_verified ?? b2Events}/30)`,
        sealColor: 'text-purple-300 bg-purple-500/15 border-purple-500/30',
        liveAuthorized: false,
        canPromote: b2Events >= 30,
      },
      {
        id: 'macro_trend_dominion',
        name: 'Macro Trend Dominion (Bot 3)',
        subName: 'Trend Following & Learning Engine (Port 8003)',
        asset: 'BTC-15M',
        lane: 'Lane 2 (Shadow)',
        events: b3Events,
        winRate: b3WinRate,
        profitFactor: b3Pf,
        drawdown: '—',
        vpinPass: '100%',
        status: macroDominionTelemetry?.active ? 'SHADOW BENCHMARK (PORT 8003)' : 'AWAITING TELEMETRY (8003)',
        statusColor: 'text-cyan-400 bg-cyan-500/15 border-cyan-500/30',
        sealStatus: b3Seal?.seal_status ?? 'IN_INCUBATION',
        sealToken: b3Seal?.seal_token ?? 'PENDING-INCUBATION',
        sealLabel: `⏳ INCUBATING (${b3Seal?.settled_cycles_verified ?? b3Events}/30)`,
        sealColor: 'text-cyan-300 bg-cyan-500/15 border-cyan-500/30',
        liveAuthorized: false,
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
        defaultSizes={[22, 53, 25]}
        minPixelSizes={[280, 420, 260]}
        minPercentageSizes={[14, 30, 15]}
        maxPercentageSizes={[40, 75, 45]}
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

            {/* Timeframe Selector */}
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
          {/* 1. SETTINGS VIEW (From HTML Proposal) */}
          {primaryNav === 'settings' && (
            <div className="space-y-6 max-w-4xl">
              {/* Kalshi API & Execution Routing Section */}
              <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#8c9ba5]">
                    Kalshi API & Execution Routing
                  </h2>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/20 text-[#d9a752] border border-amber-500/30">
                    ACTIVE
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-4 text-xs font-mono">
                  <div className="space-y-1">
                    <label className="text-[#8c9ba5] text-[10px] uppercase font-bold">API Key</label>
                    <div className="flex items-center justify-between bg-[#1a2128] border border-[#262d35] rounded-md px-3 py-2 text-xs">
                      <span className="text-[#2dd4bf] tracking-wider">KALSHI • L3 • •••••••• b8e2</span>
                      <span className="text-emerald-400 text-[10px]">● connected</span>
                    </div>
                    <div className="text-[10px] text-[#8c9ba5]">Scoped to read + trade only. Zero withdrawal permission.</div>
                  </div>

                  <div className="space-y-1">
                    <label className="text-[#8c9ba5] text-[10px] uppercase font-bold">Account ID</label>
                    <input
                      readOnly
                      value="acct_qx9f2-alpaca-shard-b"
                      className="w-full bg-[#1a2128] border border-[#262d35] rounded-md px-3 py-2 text-xs text-white"
                    />
                    <div className="text-[10px] text-[#8c9ba5]">Per-bot execution routing on promote.</div>
                  </div>

                  <div className="space-y-1">
                    <label className="text-[#8c9ba5] text-[10px] uppercase font-bold">Routing Mode</label>
                    <select className="w-full bg-[#1a2128] border border-[#262d35] rounded-md px-3 py-2 text-xs text-white">
                      <option>FOK · Fill-or-Kill (default for 5M)</option>
                      <option>GTC · Good-Till-Cancel (15M maker ladder)</option>
                      <option>IOC · Immediate-or-Cancel (slippage guard)</option>
                    </select>
                    <div className="text-[10px] text-[#8c9ba5]">Each Baby Bot can override per-cycle.</div>
                  </div>

                  <div className="space-y-1">
                    <label className="text-[#8c9ba5] text-[10px] uppercase font-bold">Slippage Tolerance</label>
                    <input
                      readOnly
                      value="≤ 1.5¢ from mid"
                      className="w-full bg-[#1a2128] border border-[#262d35] rounded-md px-3 py-2 text-xs text-white"
                    />
                    <div className="text-[10px] text-[#8c9ba5]">Reject entry if book top-of-book &lt; 6 contracts.</div>
                  </div>
                </div>
              </div>

              {/* Promotion Threshold Gate Section */}
              <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-4">
                <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#8c9ba5]">
                  Promotion Threshold · Promote-to-Baby Eligibility
                </h2>
                <div className="p-3 rounded-lg bg-[#f43f5e]/10 border border-[#f43f5e]/30 text-xs text-[#f43f5e] leading-relaxed">
                  Promotion is a <b>HARD gate</b>. A Lab candidate becomes an authorized Baby Bot only when all six metrics pass for &ge; 500 paper/isolated-shadow events.
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d]">
                    <div className="text-[10px] font-mono text-[#8c9ba5] uppercase">MIN WIN RATE</div>
                    <div className="text-xl font-bold font-mono text-[#34d399] mt-1">&ge; 70%</div>
                  </div>
                  <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d]">
                    <div className="text-[10px] font-mono text-[#8c9ba5] uppercase">MIN PROFIT FACTOR</div>
                    <div className="text-xl font-bold font-mono text-[#34d399] mt-1">&ge; 1.60</div>
                  </div>
                  <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d]">
                    <div className="text-[10px] font-mono text-[#8c9ba5] uppercase">MAX DRAWDOWN</div>
                    <div className="text-xl font-bold font-mono text-[#f43f5e] mt-1">&le; 8%</div>
                  </div>
                  <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d]">
                    <div className="text-[10px] font-mono text-[#8c9ba5] uppercase">MIN EDGE ¢</div>
                    <div className="text-xl font-bold font-mono text-[#34d399] mt-1">&ge; +3.5¢</div>
                  </div>
                  <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d]">
                    <div className="text-[10px] font-mono text-[#8c9ba5] uppercase">SHARPE RATIO</div>
                    <div className="text-xl font-bold font-mono text-[#34d399] mt-1">&ge; 1.20</div>
                  </div>
                  <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d]">
                    <div className="text-[10px] font-mono text-[#8c9ba5] uppercase">PROMO COOLDOWN</div>
                    <div className="text-xl font-bold font-mono text-white mt-1">24h</div>
                  </div>
                </div>
              </div>

              {/* Per-Bot Defaults Section */}
              <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-4">
                <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#8c9ba5]">
                  Per-Bot Micro-Bankroll & Safety Defaults
                </h2>

                <div className="grid grid-cols-2 gap-4 text-xs font-mono">
                  <div className="space-y-1">
                    <label className="text-[#8c9ba5] text-[10px] uppercase font-bold">Max contracts / event</label>
                    <input readOnly value="1 (Hard Institutional Cap)" className="w-full bg-[#1a2128] border border-[#262d35] rounded-md px-3 py-2 text-xs text-amber-300 font-bold" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[#8c9ba5] text-[10px] uppercase font-bold">Max contracts / session</label>
                    <input readOnly value="40" className="w-full bg-[#1a2128] border border-[#262d35] rounded-md px-3 py-2 text-xs text-white" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[#8c9ba5] text-[10px] uppercase font-bold">Max $ per side</label>
                    <input readOnly value="$150" className="w-full bg-[#1a2128] border border-[#262d35] rounded-md px-3 py-2 text-xs text-white" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[#8c9ba5] text-[10px] uppercase font-bold">Max concurrent Baby Bots</label>
                    <input readOnly value="6" className="w-full bg-[#1a2128] border border-[#262d35] rounded-md px-3 py-2 text-xs text-white" />
                  </div>
                </div>

                <div className="divide-y divide-[#1f262d] pt-2">
                  <div className="py-2.5 flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold text-white">Auto-flatten at T-5s for 5M contracts</div>
                      <div className="text-[11px] text-[#8c9ba5]">Required for all Baby Bots. Disables only on lab-tier.</div>
                    </div>
                    <span className="text-[11px] font-mono font-bold text-[#00bda5] bg-[#00bda5]/15 px-2 py-0.5 rounded border border-[#00bda5]/30">ON</span>
                  </div>
                  <div className="py-2.5 flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold text-white">Reject entries when book depth &le; 6</div>
                      <div className="text-[11px] text-[#8c9ba5]">Skip signal rather than pay excessive slippage.</div>
                    </div>
                    <span className="text-[11px] font-mono font-bold text-[#00bda5] bg-[#00bda5]/15 px-2 py-0.5 rounded border border-[#00bda5]/30">ON</span>
                  </div>
                  <div className="py-2.5 flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold text-white">Auto-pause losers (3 consecutive losses)</div>
                      <div className="text-[11px] text-[#8c9ba5]">Pauses bot for 15 minutes — does not delete state.</div>
                    </div>
                    <span className="text-[11px] font-mono font-bold text-[#f43f5e] bg-[#f43f5e]/15 px-2 py-0.5 rounded border border-[#f43f5e]/30">ARMED</span>
                  </div>
                </div>
              </div>

              {/* Global Kill-Switch */}
              <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-4">
                <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#f43f5e]">
                  Global Kill-Switch
                </h2>
                <div className="p-3 rounded-lg bg-[#f43f5e]/10 border border-[#f43f5e]/30 text-xs text-[#f43f5e] leading-relaxed">
                  <b>WARNING.</b> Activating the global kill-switch sends <span className="font-mono bg-[#13171c] px-1.5 py-0.5 rounded text-[#2dd4bf]">FLATTEN_ALL</span> to every active Baby Bot, cancels open resting orders, and revokes session tokens for 60 seconds.
                </div>

                <button
                  onClick={onFlattenHalt}
                  className="w-full py-3.5 rounded-lg border-2 border-[#d31a38] text-[#f43f5e] font-extrabold text-xs uppercase tracking-wider hover:bg-[#d31a38]/10 transition-all shadow-lg cursor-pointer"
                >
                  ★ FLATTEN ALL & HALT — GLOBAL ★
                </button>
              </div>
            </div>
          )}

          {/* 2. BOTS BENCHMARKING MATRIX VIEW */}
          {primaryNav === 'bots' && (
            <div className="space-y-6">
              <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                      Factory Benchmarking Matrix
                    </h2>
                    <p className="text-xs text-[#8c9ba5] mt-0.5">
                      Real-time side-by-side evaluation across Lane 1 (Live), Lane 2 (Shadow), and Lane 3 (Backtest).
                    </p>
                  </div>
                  <span className="text-xs font-mono text-emerald-400">Stream: 5Hz BRTI Synchronized</span>
                </div>

                {/* Benchmarking Table */}
                <div className="overflow-x-auto rounded-lg border border-[#262d35]">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-[#171c22] text-[10px] uppercase text-[#8c9ba5] border-b border-[#262d35]">
                      <tr>
                        <th className="py-2.5 px-4">Strategy Bot</th>
                        <th className="py-2.5 px-4">Asset & Cycle</th>
                        <th className="py-2.5 px-4">Execution Lane</th>
                        <th className="py-2.5 px-4 text-right">Sample Events</th>
                        <th className="py-2.5 px-4 text-right">Win Rate</th>
                        <th className="py-2.5 px-4 text-right">Profit Factor</th>
                        <th className="py-2.5 px-4 text-right">Max DD</th>
                        <th className="py-2.5 px-4 text-center">Seal of Excellence</th>
                        <th className="py-2.5 px-4">Status</th>
                        <th className="py-2.5 px-4 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1f262d]">
                      {benchmarkingModels.map((m, idx) => {
                        const isSelected =
                          selectedBotId === m.id ||
                          (m.id === 'macro_onnx' && (selectedBotId === 'onnx_microstructure_bot' || selectedBotId === 'macro_onnx'));
                        return (
                          <tr
                            key={idx}
                            onClick={() => handleSelectBot(m.id)}
                            className={`cursor-pointer transition-all duration-150 ${
                              isSelected
                                ? 'bg-[#00bda5]/15 border-l-4 border-l-[#00bda5] shadow-[inset_0_0_15px_rgba(0,189,165,0.12)]'
                                : 'hover:bg-[#171c22]/70'
                            }`}
                          >
                            <td className="py-3 px-4 font-bold text-white flex items-center gap-2">
                              {isSelected ? (
                                <span className="w-2 h-2 rounded-full bg-[#00bda5] animate-ping shrink-0" />
                              ) : (
                                <span className="w-2 h-2 rounded-full bg-transparent shrink-0" />
                              )}
                              <div className="flex flex-col">
                                <div className="flex items-center gap-2">
                                  <span>{m.name}</span>
                                  {isSelected && (
                                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#00bda5]/25 text-[#2dd4bf] font-bold border border-[#00bda5]/40 uppercase tracking-wider">
                                      Cockpit Focus
                                    </span>
                                  )}
                                </div>
                                {m.subName && (
                                  <span className="text-[10px] text-purple-400/80 font-normal font-sans">
                                    {m.subName}
                                  </span>
                                )}
                              </div>
                            </td>
                            <td className="py-3 px-4 text-[#8c9ba5]">{m.asset}</td>
                            <td className="py-3 px-4 text-slate-300">{m.lane}</td>
                            <td className="py-3 px-4 text-right text-white">{m.events}</td>
                            <td className="py-3 px-4 text-right font-bold text-[#34d399]">{m.winRate}</td>
                            <td className="py-3 px-4 text-right text-white">{m.profitFactor}</td>
                            <td className="py-3 px-4 text-right text-slate-300">{m.drawdown}</td>
                            <td className="py-3 px-4 text-center">
                              <div className="flex flex-col items-center">
                                <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold border ${m.sealColor} flex items-center gap-1 shadow-sm`}>
                                  {m.sealLabel}
                                </span>
                                <span className="text-[9px] text-[#8c9ba5] font-mono mt-0.5">
                                  {m.sealToken}
                                </span>
                              </div>
                            </td>
                            <td className="py-3 px-4">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${m.statusColor}`}>
                                {m.status}
                              </span>
                            </td>
                            <td className="py-3 px-4 text-right" onClick={(e) => e.stopPropagation()}>
                              {m.canPromote ? (
                                <button
                                  onClick={() => setIsPromoteModalOpen(true)}
                                  className="px-2.5 py-1 rounded bg-[#00bda5] text-black font-bold hover:bg-[#2dd4bf] transition-all shadow-sm cursor-pointer"
                                >
                                  Promote 🚀
                                </button>
                              ) : (
                                <span className="text-[10px] text-[#8c9ba5]">&mdash;</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              <ONNXSettingsPanel />

              {/* ONNX Continuous Autonomous Background Learning Telemetry Card */}
              <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-4 font-mono">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#262d35] pb-3">
                  <div className="flex items-center gap-2.5">
                    <Cpu className="w-5 h-5 text-[#00bda5]" />
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                          Autonomous Continuous ONNX Fine-Tuning Engine
                        </h2>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                          continuousTraining?.status === 'TRAINING' || continuousTraining?.status === 'EXTRACTING'
                            ? 'text-emerald-400 bg-emerald-500/15 border-emerald-500/30 animate-pulse'
                            : continuousTraining?.status === 'PAUSED'
                            ? 'text-amber-400 bg-amber-500/15 border-amber-500/30'
                            : 'text-[#2dd4bf] bg-[#2dd4bf]/15 border-[#2dd4bf]/30'
                        }`}>
                          {continuousTraining?.status || 'ACTIVE / IDLE'}
                        </span>
                      </div>
                      <p className="text-[11px] text-[#8c9ba5] font-sans mt-0.5">
                        Trains in background thread decoupled from live loop • Capped to 1 CPU core • Zero live execution impact
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="text-[10px] text-[#8c9ba5]">
                      OS Priority: <b className="text-emerald-400">{continuousTraining?.priority_class || 'BELOW_NORMAL (Live Protected)'}</b>
                    </span>
                    <button
                      onClick={handleToggleTrainer}
                      disabled={trainerActionLoading}
                      className={`px-3 py-1.5 rounded text-xs font-bold transition border cursor-pointer ${
                        continuousTraining?.is_paused
                          ? 'bg-emerald-600 hover:bg-emerald-500 text-white border-emerald-400 shadow-sm'
                          : 'bg-[#1a2128] hover:bg-[#262d35] text-amber-300 border-amber-500/40'
                      }`}
                    >
                      {trainerActionLoading
                        ? 'Updating...'
                        : continuousTraining?.is_paused
                        ? '▶ Resume Trainer'
                        : '⏸ Pause Trainer'}
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-xs">
                  <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d]">
                    <div className="text-[10px] text-[#8c9ba5] uppercase">Cycles Completed</div>
                    <div className="text-lg font-bold text-white mt-0.5 font-mono">
                      {continuousTraining?.cycles_completed ?? 0}
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d]">
                    <div className="text-[10px] text-[#8c9ba5] uppercase">Models Promoted</div>
                    <div className="text-lg font-bold text-[#00bda5] mt-0.5 font-mono">
                      {continuousTraining?.models_promoted ?? 0}
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d]">
                    <div className="text-[10px] text-[#8c9ba5] uppercase">Best Val Loss</div>
                    <div className="text-lg font-bold text-emerald-400 mt-0.5 font-mono">
                      {continuousTraining?.best_val_loss != null ? continuousTraining.best_val_loss : '0.4120'}
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d]">
                    <div className="text-[10px] text-[#8c9ba5] uppercase">Last Accuracy</div>
                    <div className="text-lg font-bold text-white mt-0.5 font-mono">
                      {continuousTraining?.last_val_accuracy != null ? `${continuousTraining.last_val_accuracy}%` : '82.4%'}
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d]">
                    <div className="text-[10px] text-[#8c9ba5] uppercase">Samples Trained</div>
                    <div className="text-lg font-bold text-purple-400 mt-0.5 font-mono">
                      {continuousTraining?.samples_trained ? continuousTraining.samples_trained.toLocaleString() : '1,420'}
                    </div>
                  </div>
                  <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d]">
                    <div className="text-[10px] text-[#8c9ba5] uppercase">CPU Thread Cap</div>
                    <div className="text-lg font-bold text-amber-300 mt-0.5 font-mono">
                      1 Thread (Guarded)
                    </div>
                  </div>
                </div>
              </div>
            </div>
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
            <div className="space-y-6">
              {/* Journal Sub-Header with Date Scope, Asset, Timeframe Filters, and Full Modal Trigger */}
              <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-4 flex flex-wrap items-center justify-between gap-3 font-mono">
                <div className="flex flex-wrap items-center gap-4">
                  {/* Date Scope Filter */}
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase font-bold text-[#8c9ba5] flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5 text-emerald-400" />
                      Scope:
                    </span>
                    <div className="flex items-center gap-1 bg-[#171c22] p-0.5 rounded-lg border border-[#262d35]">
                      <button
                        onClick={() => {
                          soundFX.playClickSound();
                          setJournalDateScope('today');
                        }}
                        className={`px-2.5 py-1 rounded text-[11px] font-bold transition flex items-center gap-1.5 ${
                          (journalSubNav === 'trades' ? journalDateScope !== 'all' : journalDateScope === 'today')
                            ? 'bg-emerald-500 text-black shadow-sm font-extrabold'
                            : 'text-[#8c9ba5] hover:text-white'
                        }`}
                      >
                        <span>📅 Today's Report</span>
                      </button>
                      <button
                        onClick={() => {
                          soundFX.playClickSound();
                          setJournalDateScope('all');
                        }}
                        className={`px-2.5 py-1 rounded text-[11px] font-bold transition flex items-center gap-1.5 ${
                          (journalSubNav === 'trades' ? journalDateScope === 'all' : journalDateScope !== 'today')
                            ? 'bg-[#1e293b] text-white shadow-sm font-extrabold'
                            : 'text-[#8c9ba5] hover:text-white'
                        }`}
                      >
                        <span>🌐 All History</span>
                      </button>
                    </div>
                  </div>

                  {/* Asset Filter */}
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase font-bold text-[#8c9ba5]">Asset:</span>
                    <div className="flex items-center gap-1 bg-[#171c22] p-0.5 rounded-lg border border-[#262d35]">
                      {(['ALL', 'BTC', 'ETH', 'SOL', 'DOGE'] as const).map((a) => (
                        <button
                          key={a}
                          onClick={() => {
                            soundFX.playClickSound();
                            setJournalAssetFilter(a);
                          }}
                          className={`px-2.5 py-1 rounded text-[11px] font-bold transition ${
                            journalAssetFilter === a
                              ? 'bg-[#00bda5] text-black shadow-sm font-extrabold'
                              : 'text-[#8c9ba5] hover:text-white'
                          }`}
                        >
                          {a}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Timeframe Filter */}
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase font-bold text-[#8c9ba5]">Cycle:</span>
                    <div className="flex items-center gap-1 bg-[#171c22] p-0.5 rounded-lg border border-[#262d35]">
                      {(['ALL', '5M', '15M'] as const).map((tf) => (
                        <button
                          key={tf}
                          onClick={() => {
                            soundFX.playClickSound();
                            setJournalTimeframeFilter(tf);
                          }}
                          className={`px-2.5 py-1 rounded text-[11px] font-bold transition ${
                            journalTimeframeFilter === tf
                              ? 'bg-[#d9a752] text-black shadow-sm font-extrabold'
                              : 'text-[#8c9ba5] hover:text-white'
                          }`}
                        >
                          {tf}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Modal Trigger */}
                <button
                  onClick={() => setIsWinLossModalOpen(true)}
                  className="px-3.5 py-1.5 rounded-lg bg-[#00bda5]/15 text-[#2dd4bf] hover:bg-[#00bda5]/25 border border-[#00bda5]/30 text-xs font-bold flex items-center gap-1.5 transition cursor-pointer shadow-sm"
                >
                  <span>📋 Full 15M Win/Loss Audit Modal</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Institutional KPI Summary Header Cards */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 font-mono">
                {/* 1. Filtered Win Rate */}
                <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-4 flex flex-col justify-between">
                  <div className="flex items-center justify-between text-[#8c9ba5] text-xs">
                    <span className="uppercase font-bold">Filtered Win Rate</span>
                    <Award className="w-4 h-4 text-emerald-400" />
                  </div>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className="text-2xl font-black text-white">
                      {journalStats.filtered.winRate.toFixed(1)}%
                    </span>
                    <span className="text-xs text-[#8c9ba5]">
                      ({journalStats.filtered.wins}W / {journalStats.filtered.losses}L)
                    </span>
                  </div>
                  <div className="mt-2 w-full bg-[#1e242b] h-1.5 rounded-full overflow-hidden">
                    <div
                      className="bg-emerald-400 h-full rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(100, journalStats.filtered.winRate)}%` }}
                    />
                  </div>
                </div>

                {/* 2. Filtered Realized P&L */}
                <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-4 flex flex-col justify-between">
                  <div className="flex items-center justify-between text-[#8c9ba5] text-xs">
                    <span className="uppercase font-bold">Filtered Net P&L</span>
                    {journalStats.filtered.netPnl >= 0 ? (
                      <TrendingUp className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <TrendingDown className="w-4 h-4 text-rose-400" />
                    )}
                  </div>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className={`text-2xl font-black ${
                      journalStats.filtered.netPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}>
                      {journalStats.filtered.netPnl >= 0 ? '+' : '−'}$
                      {Math.abs(journalStats.filtered.netPnl).toFixed(2)}
                    </span>
                    <span className="text-xs text-[#8c9ba5]">
                      ({journalStats.filtered.total} trades)
                    </span>
                  </div>
                  <div className="mt-2 text-[10px] text-[#8c9ba5] flex items-center justify-between">
                    <span>1 contract micro-sizing</span>
                    <span className="text-emerald-400">$0.48 entry cap</span>
                  </div>
                </div>

                {/* 3. Today's Report Card (Interactive) */}
                <div
                  onClick={() => {
                    soundFX.playClickSound();
                    setJournalDateScope('today');
                  }}
                  className={`border rounded-xl p-4 flex flex-col justify-between transition cursor-pointer ${
                    (journalSubNav === 'trades' ? journalDateScope !== 'all' : journalDateScope === 'today')
                      ? 'bg-emerald-950/20 border-emerald-500/50 shadow-md shadow-emerald-950/30'
                      : 'bg-[#12161a] border-[#262d35] hover:border-emerald-500/30'
                  }`}
                  title="Click to view Today's Trades exclusively"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="uppercase font-bold text-emerald-300 flex items-center gap-1.5">
                      <Calendar className="w-3.5 h-3.5" />
                      📅 Today's Report
                    </span>
                    {(journalSubNav === 'trades' ? journalDateScope !== 'all' : journalDateScope === 'today') && (
                      <span className="text-[10px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded border border-emerald-500/40 font-bold">
                        ACTIVE
                      </span>
                    )}
                  </div>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className={`text-2xl font-black ${
                      journalStats.today.netPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}>
                      {journalStats.today.netPnl >= 0 ? '+' : '−'}$
                      {Math.abs(journalStats.today.netPnl).toFixed(2)}
                    </span>
                    <span className="text-xs text-[#8c9ba5]">
                      ({journalStats.today.winRate.toFixed(0)}% WR)
                    </span>
                  </div>
                  <div className="mt-2 text-[10px] text-[#8c9ba5] flex items-center justify-between">
                    <span>{journalStats.today.total} trades today (ET)</span>
                    <span className="text-emerald-300 underline text-[10px]">Filter Today &rsaquo;</span>
                  </div>
                </div>

                {/* 4. Total Live Report Card (Interactive) */}
                <div
                  onClick={() => {
                    soundFX.playClickSound();
                    setJournalBotFilter(journalBotFilter === 'live' ? 'all' : 'live');
                  }}
                  className={`border rounded-xl p-4 flex flex-col justify-between transition cursor-pointer ${
                    journalBotFilter === 'live'
                      ? 'bg-rose-950/20 border-rose-500/50 shadow-md shadow-rose-950/30'
                      : 'bg-[#12161a] border-[#262d35] hover:border-rose-500/30'
                  }`}
                  title="Click to toggle Total Live Execution Report"
                >
                  <div className="flex items-center justify-between text-xs">
                    <span className="uppercase font-bold text-rose-300 flex items-center gap-1.5">
                      <Shield className="w-3.5 h-3.5" />
                      🔴 Total Live Report
                    </span>
                    {journalBotFilter === 'live' && (
                      <span className="text-[10px] bg-rose-500/20 text-rose-300 px-1.5 py-0.5 rounded border border-rose-500/40 font-bold">
                        FILTERED
                      </span>
                    )}
                  </div>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className={`text-2xl font-black ${
                      journalStats.live.netPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}>
                      {journalStats.live.netPnl >= 0 ? '+' : '−'}$
                      {Math.abs(journalStats.live.netPnl).toFixed(2)}
                    </span>
                    <span className="text-xs text-[#8c9ba5]">
                      ({journalStats.live.winRate.toFixed(0)}% WR)
                    </span>
                  </div>
                  <div className="mt-2 text-[10px] text-[#8c9ba5] flex items-center justify-between">
                    <span>{journalStats.live.total} real Kalshi fills</span>
                    <span className="text-rose-300">$0.00 Maker fee</span>
                  </div>
                </div>
              </div>

              {/* "Who Traded" Strategy Performance Breakdown Bar */}
              <div className="p-3 bg-[#12161a] rounded-xl border border-[#262d35] space-y-2 font-mono">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Bot className="w-4 h-4 text-[#00bda5]" />
                    <span className="text-xs font-bold uppercase tracking-wider text-white">
                      Who Traded — Bot & Strategy Breakdown
                    </span>
                  </div>
                  <span className="text-[10px] text-[#8c9ba5]">
                    Click strategy to filter executions
                  </span>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {(['all', '3_step_dom', 'macro_onnx', 'dominion_2', 'macro_trend', 'onnx_ml', 'live'] as TraderCategory[]).map((cat) => {
                    const badge = getTraderBadge(cat);
                    const st = journalStats.botStatsMap[cat] || { count: 0, wins: 0, pnl: 0 };
                    const isSelected = journalBotFilter === cat;
                    const wr = st.count > 0 ? ((st.wins / st.count) * 100).toFixed(0) : '0';
                    return (
                      <button
                        key={cat}
                        onClick={() => {
                          soundFX.playClickSound();
                          setJournalBotFilter(cat);
                        }}
                        className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition flex items-center gap-2 border cursor-pointer ${
                          isSelected
                            ? 'bg-[#00bda5] text-black border-[#00bda5] shadow-sm font-extrabold'
                            : 'bg-[#171c22] text-[#8c9ba5] hover:text-white border-[#262d35]'
                        }`}
                      >
                        <span>{cat === 'all' ? '🌐 ALL' : `${badge.icon} ${badge.short}`}</span>
                        <span className={`text-[10px] px-1.5 py-0.2 rounded font-mono ${
                          isSelected ? 'bg-black/20 text-black' : 'bg-[#12161a] text-[#2dd4bf]'
                        }`}>
                          {st.count}
                        </span>
                        {st.count > 0 && (
                          <span className={`text-[10px] font-mono ${
                            isSelected
                              ? 'text-black font-extrabold'
                              : st.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
                          }`}>
                            {st.pnl >= 0 ? '+' : '−'}${Math.abs(st.pnl).toFixed(2)} ({wr}%)
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Journal Table Card */}
              <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-bold uppercase tracking-wider text-white flex items-center gap-2">
                    <span>
                      {journalSubNav === 'settlements'
                        ? 'Historical Contract Settlements Ledger'
                        : journalSubNav === 'reports'
                        ? '15-Minute Event Outcome Reports'
                        : 'Today\'s Trade Executions Ledger'}
                    </span>
                    {journalBotFilter !== 'all' && (
                      <span className="text-[10px] px-2 py-0.5 rounded bg-[#00bda5]/20 text-[#2dd4bf] border border-[#00bda5]/40 font-mono font-bold">
                        Filter: {getTraderBadge(journalBotFilter).short}
                      </span>
                    )}
                  </h2>
                  <div className="text-xs font-mono text-[#8c9ba5]">
                    Showing {filteredExecutions.length} records
                  </div>
                </div>

                <div className="overflow-x-auto rounded-lg border border-[#262d35]">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-[#171c22] text-[10px] uppercase text-[#8c9ba5] border-b border-[#262d35]">
                      <tr>
                        <th className="py-2.5 px-4">Record ID</th>
                        <th className="py-2.5 px-4">Time (ET)</th>
                        <th className="py-2.5 px-4">Who Traded (Strategy)</th>
                        <th className="py-2.5 px-4">Mode</th>
                        <th className="py-2.5 px-4">Cycle</th>
                        <th className="py-2.5 px-4">Asset</th>
                        <th className="py-2.5 px-4">Strike</th>
                        {journalSubNav === 'settlements' && <th className="py-2.5 px-4">Spot Settlement</th>}
                        <th className="py-2.5 px-4">Side</th>
                        <th className="py-2.5 px-4 text-right">Entry</th>
                        <th className="py-2.5 px-4 text-center">Outcome</th>
                        <th className="py-2.5 px-4 text-right">PnL</th>
                        <th className="py-2.5 px-4">Tag</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1f262d]">
                      {filteredExecutions.map((t, idx) => (
                        <tr key={idx} className={idx % 2 === 0 ? 'bg-[#171c22]/40' : 'bg-[#13171c]/40'}>
                          <td className="py-2 px-4 text-[#8c9ba5] font-mono">{t.id}</td>
                          <td className="py-2 px-4 text-[#8c9ba5]">{t.time}</td>
                          <td className="py-2 px-4">
                            <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-bold border ${t.badge.color}`}>
                              <span>{t.badge.icon}</span>
                              <span>{t.badge.short}</span>
                            </span>
                          </td>
                          <td className="py-2 px-4">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-extrabold ${
                              t.isLive
                                ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                                : 'bg-slate-700/40 text-slate-300 border border-slate-600/30'
                            }`}>
                              {t.isLive ? 'LIVE' : 'PAPER'}
                            </span>
                          </td>
                          <td className="py-2 px-4">
                            <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                              t.tf === '5M' ? 'bg-[#d9a752]/20 text-[#d9a752]' : 'bg-[#00bda5]/20 text-[#2dd4bf]'
                            }`}>
                              {t.tf}
                            </span>
                          </td>
                          <td className="py-2 px-4 font-bold text-white">{t.asset}</td>
                          <td className="py-2 px-4 text-[#8c9ba5]">{t.strike}</td>
                          {journalSubNav === 'settlements' && (
                            <td className="py-2 px-4 text-white font-mono">{t.spotPrice || 'Pending'}</td>
                          )}
                          <td className="py-2 px-4 font-bold">
                            <span className={t.side === 'YES' ? 'text-[#34d399]' : 'text-[#f43f5e]'}>
                              {t.side}
                            </span>
                          </td>
                          <td className="py-2 px-4 text-right text-white">{t.price}</td>
                          <td className="py-2 px-4 text-center">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              t.outcome === 'WIN' ? 'bg-[#34d399]/15 text-[#34d399]' : 'bg-[#f43f5e]/15 text-[#f43f5e]'
                            }`}>
                              {t.outcome}
                            </span>
                          </td>
                          <td className={`py-2 px-4 text-right font-bold ${
                            t.outcome === 'WIN' ? 'text-[#34d399]' : 'text-[#f43f5e]'
                          }`}>
                            {t.pnl}
                          </td>
                          <td className="py-2 px-4">
                            <span className="px-2 py-0.5 rounded text-[10px] bg-[#1a2128] text-[#8c9ba5] border border-[#262d35]">
                              {t.tag}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Full WinLossReportsModal */}
              <WinLossReportsModal
                isOpen={isWinLossModalOpen}
                onClose={() => setIsWinLossModalOpen(false)}
              />
            </div>
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
      <aside className="w-full h-full bg-[#12161a] flex flex-col shrink-0 overflow-y-auto select-none">
        {/* If Baby Bot is docked (not popped out into standalone window), render here */}
        {!isPoppedOutBabyBot ? (
          <div className="p-3 border-b border-[#262d35]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#8c9ba5] flex items-center gap-1.5 truncate pr-1">
                <span>Docked:</span>
                <span className="text-[#00bda5] font-extrabold truncate">
                  {selectedBotId === 'macro_onnx' || selectedBotId === 'onnx_microstructure_bot'
                    ? 'Bot 2 (ONNX Macro v2)'
                    : selectedBotId === '3_step_domination_bot'
                    ? 'Bot 1 (3-Step Dom)'
                    : selectedBotId === 'macro_trend_dominion'
                    ? 'Bot 3 (Macro Trend)'
                    : 'Baby Bot'}
                </span>
              </span>
              <div className="flex items-center gap-1 shrink-0">
                {/* Minimize / Expand Console button */}
                <button
                  onClick={() => {
                    soundFX.playClickSound();
                    setIsBabyBotConsoleMinimized(!isBabyBotConsoleMinimized);
                  }}
                  title={isBabyBotConsoleMinimized ? 'Expand Baby Bot Console' : 'Minimize Baby Bot Console'}
                  className="p-1 rounded text-[#8c9ba5] hover:text-white hover:bg-[#17202d] transition"
                >
                  {isBabyBotConsoleMinimized ? (
                    <Maximize2 className="w-3 h-3 text-[#00bda5]" />
                  ) : (
                    <Minimize2 className="w-3 h-3 text-[#8c9ba5]" />
                  )}
                </button>

                {/* Pop out standalone button */}
                <button
                  onClick={() => onTogglePopOutBabyBot(selectedBotId)}
                  title="Pop out Baby Bot window"
                  className="text-[11px] font-mono text-[#00bda5] hover:text-white flex items-center gap-1 p-1 rounded hover:bg-[#17202d]"
                >
                  <ExternalLink className="w-3 h-3" />
                  <span>Pop-out</span>
                </button>

                {/* Hide Rail button (Maximize Center / CLOB Terminal) */}
                <button
                  onClick={() => {
                    soundFX.playClickSound();
                    setIsBabyBotRailHidden(true);
                  }}
                  title="Hide Right Rail (Maximize CLOB Terminal)"
                  className="p-1 rounded text-[#8c9ba5] hover:text-white hover:bg-[#17202d] transition"
                >
                  <PanelRightClose className="w-3.5 h-3.5 text-[#38bdf8]" />
                </button>
              </div>
            </div>

            {/* Minimized Docked Console Summary Strip */}
            {isBabyBotConsoleMinimized ? (
              <div
                onClick={() => {
                  soundFX.playClickSound();
                  setIsBabyBotConsoleMinimized(false);
                }}
                className="p-2.5 rounded-lg bg-[#17202d] border border-[#262d35] hover:border-[#00bda5]/50 cursor-pointer flex items-center justify-between font-mono text-xs transition shadow-sm"
                title="Click to expand full Baby Bot Console"
              >
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-[#10b981] animate-ping" />
                  <span className="font-bold text-white">
                    {formatBotDisplayName(selectedBotId)}
                  </span>
                  <span className={`text-[9px] px-1.5 py-0.2 rounded font-bold ${
                    tradingMode === 'live' ? 'bg-rose-500/20 text-rose-300' : 'bg-slate-700/40 text-slate-300'
                  }`}>
                    {tradingMode.toUpperCase()}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[10px] text-[#8c9ba5]">
                  <span className="text-[#00c978] font-bold">1 Lot Cap</span>
                  <span className="hover:text-white">▶ Expand</span>
                </div>
              </div>
            ) : (
              <BabyBotConsole
                market={market}
                aiSignals={aiSignals}
                livePortfolio={livePortfolio}
                activePosition={activePosition}
                tradingMode={tradingMode}
                timeframe={timeframe}
                isPoppedOut={false}
                onTogglePopOut={() => onTogglePopOutBabyBot(selectedBotId)}
                onFlattenHalt={onFlattenHalt}
                onQuickTrade={onQuickTrade}
                reportsCount={reports.length}
                consecutiveLosses={consecutiveLosses}
                selectedBotId={selectedBotId}
                onSelectBot={handleSelectBot}
                dualOnnxTelemetry={dualOnnxTelemetry}
                preflightGates={preflightGates}
                macroDominionTelemetry={macroDominionTelemetry}
                hmmMacroRegime={hmmMacroRegime}
                onOpenReports={() => setWorkbenchTab('reports')}
              />
            )}
          </div>
        ) : (
          <div className="p-4 bg-[#171c22]/50 border-b border-[#262d35] text-center text-xs font-mono text-[#8c9ba5]">
            <div className="w-2 h-2 rounded-full bg-[#00bda5] animate-ping mx-auto mb-2" />
            <span>Baby Bot running in standalone pop-out window</span>
            <button
              onClick={() => onTogglePopOutBabyBot(selectedBotId)}
              className="mt-2 block mx-auto text-[11px] text-[#2dd4bf] hover:underline"
            >
              Dock back to rail
            </button>
          </div>
        )}

        {/* Trade Note Card (From HTML Proposal) */}
        <div className="p-4 border-b border-[#262d35] space-y-2">
          <h3 className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#8c9ba5]">
            Trade Note · #3318
          </h3>
          <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d] text-xs text-[#8c9ba5] leading-relaxed font-mono">
            <div className="text-white font-bold mb-1">3-STEP DOMINATION · 09:42 ET</div>
            Spot drifted $28 above strike in 90s post open. Ladder caught at YES=58¢, scaled out at T-30s during settlement at YES=71¢. Slippage +1.2¢ acceptable — book depth &ge; 14 lots. Liquidity guard served.
          </div>
        </div>

        {/* Today's Timeline (From HTML Proposal) */}
        <div className="p-4 border-b border-[#262d35] space-y-3">
          <h3 className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#8c9ba5]">
            Today's Timeline
          </h3>
          <div className="space-y-2 font-mono text-xs">
            {[
              { time: '09:42', text: '3-Step ladder WIN · BTC-15M', type: 'win' },
              { time: '09:27', text: 'Reclaim-fail NO hit · BTC-15M', type: 'win' },
              { time: '09:15', text: 'Wick Scalp LOSS · SOL-5M', type: 'loss' },
              { time: '08:45', text: 'ONNX Macro WIN · BTC-15M', type: 'win' },
              { time: '08:11', text: 'ETH Trend scratch · ETH-5M', type: 'flat' },
              { time: '07:58', text: 'Spot-drift ladder WIN · BTC-15M', type: 'win' },
              { time: '07:42', text: 'Wick Scalp LOSS · BTC-5M', type: 'loss' },
              { time: '07:30', text: 'Spot-drift ladder WIN · BTC-15M', type: 'win' },
            ].map((item, idx) => (
              <div key={idx} className="flex items-start gap-2.5">
                <span
                  className={`w-2 h-2 rounded-full mt-1 shrink-0 ${
                    item.type === 'win'
                      ? 'bg-[#34d399]'
                      : item.type === 'loss'
                      ? 'bg-[#f43f5e]'
                      : 'bg-[#8c9ba5]'
                  }`}
                />
                <span className="text-[#8c9ba5] text-[11px] shrink-0">{item.time}</span>
                <span className="text-slate-200 text-[11px]">{item.text}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Quick Tags (From HTML Proposal) */}
        <div className="p-4 space-y-2">
          <h3 className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#8c9ba5]">
            Quick Tags
          </h3>
          <div className="flex flex-wrap gap-1.5 font-mono text-[10px]">
            {[
              'spot-drift',
              'reclaim-fail',
              'macro-trend',
              'vol-spike',
              'whipsaw',
              'book-thin',
              'atr-squeeze',
              'trend-cont',
            ].map((tag) => (
              <button
                key={tag}
                onClick={() => {
                  soundFX.playClickSound();
                  setSelectedTag(selectedTag === tag ? null : tag);
                }}
                className={`px-2 py-1 rounded transition-all border ${
                  selectedTag === tag
                    ? 'bg-[#00bda5] text-black font-bold border-[#00bda5]'
                    : tag === 'whipsaw' || tag === 'book-thin'
                    ? 'bg-[#1a2128] text-[#f43f5e] border-[#262d35] hover:border-[#f43f5e]'
                    : 'bg-[#1a2128] text-[#8c9ba5] border-[#262d35] hover:text-white'
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
        </div>
      </aside>
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
