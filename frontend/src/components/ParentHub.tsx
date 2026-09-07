/**
 * @file ParentHub.tsx
 * @description The Factory / Parent Hub (Lab & Benchmarking) trading terminal environment.
 * Features 4-tier navigation (Analytics, Journal, Bots, Settings), contextual sub-navigation,
 * benchmarking matrix, live CLOB trajectory workbench, and right rail timeline & trade notes.
 */

import React, { useState, useMemo } from 'react';
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
} from 'lucide-react';
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
import { soundFX } from '../utils/audioFX';

type PrimaryNav = 'analytics' | 'journal' | 'bots' | 'settings';
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
type AnalyticsSubNav = 'workbench' | 'clob' | 'tape' | 'vpin';

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
  onTogglePopOutBabyBot: () => void;
  consecutiveLosses?: number;
  portfolio?: any;
  onClosePosition?: (ticker: string, executionMode?: 'paper' | 'live') => Promise<any>;
  onCancelOrder?: (orderId: string, executionMode?: 'paper' | 'live') => Promise<any>;
  onResetCircuitBreaker?: () => Promise<any>;
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
}) => {
  const [primaryNav, setPrimaryNav] = useState<PrimaryNav>('analytics');
  const [settingsSubNav, setSettingsSubNav] = useState<SettingsSubNav>('defaults');
  const [botsSubNav, setBotsSubNav] = useState<BotsSubNav>('matrix');
  const [journalSubNav, setJournalSubNav] = useState<JournalSubNav>('trades');
  const [analyticsSubNav, setAnalyticsSubNav] = useState<AnalyticsSubNav>('workbench');
  const [workbenchTab, setWorkbenchTab] = useState<'orderbook' | 'tape' | 'positions'>('orderbook');
  const [isPromoteModalOpen, setIsPromoteModalOpen] = useState(false);
  const [selectedTag, setSelectedTag] = useState<string | null>(null);

  // Benchmarking models for Factory Matrix
  const benchmarkingModels = useMemo(
    () => [
      {
        name: '3-Step Dominion v3.2',
        asset: 'BTC-15M',
        lane: 'Lane 1 (LIVE)',
        events: 142,
        winRate: '78.2%',
        profitFactor: '2.14',
        drawdown: '3.4%',
        vpinPass: '98.6%',
        status: 'ACTIVE LIVE',
        statusColor: 'text-[#10b981] bg-[#10b981]/15 border-[#10b981]/30',
        canPromote: false,
      },
      {
        name: 'OFI Sprint Scalper',
        asset: 'BTC-5M',
        lane: 'Lane 2 (Shadow)',
        events: 520,
        winRate: '71.8%',
        profitFactor: '1.72',
        drawdown: '6.1%',
        vpinPass: '94.2%',
        status: 'READY TO PROMOTE',
        statusColor: 'text-[#2dd4bf] bg-[#2dd4bf]/15 border-[#2dd4bf]/30',
        canPromote: true,
      },
      {
        name: 'ONNX Macro Net v2',
        asset: 'ETH-15M',
        lane: 'Lane 2 (Shadow)',
        events: 318,
        winRate: '66.4%',
        profitFactor: '1.41',
        drawdown: '9.2%',
        vpinPass: '91.0%',
        status: 'INCUBATING (318/500)',
        statusColor: 'text-[#d9a752] bg-[#d9a752]/15 border-[#d9a752]/30',
        canPromote: false,
      },
      {
        name: 'SOL Vol-Breakout',
        asset: 'SOL-5M',
        lane: 'Lane 3 (Backtest)',
        events: 1200,
        winRate: '59.2%',
        profitFactor: '1.18',
        drawdown: '14.8%',
        vpinPass: 'N/A',
        status: 'REJECTED (DD > 8%)',
        statusColor: 'text-[#f43f5e] bg-[#f43f5e]/15 border-[#f43f5e]/30',
        canPromote: false,
      },
    ],
    []
  );

  // Journal executions mock list matching user HTML
  const journalExecutions = useMemo(() => {
    return [
      { id: '#3480', time: '07:14:55', bot: 'ONNX Macro', tf: '15M', asset: 'ETH', strike: '$3,398', side: 'NO', price: '$0.42', outcome: 'WIN', pnl: '+$18.00', tag: 'macro-trend' },
      { id: '#3466', time: '06:58:21', bot: '3-Step Dom', tf: '15M', asset: 'BTC', strike: '$90,850', side: 'YES', price: '$0.60', outcome: 'WIN', pnl: '+$20.00', tag: 'spot-drift' },
      { id: '#3448', time: '06:45:00', bot: 'SOL Mean-Rev', tf: '15M', asset: 'SOL', strike: '$235.40', side: 'YES', price: '$0.55', outcome: 'WIN', pnl: '+$20.00', tag: 'atr-squeeze' },
      { id: '#3429', time: '06:30:00', bot: '3-Step Dom', tf: '15M', asset: 'BTC', strike: '$90,710', side: 'NO', price: '$0.36', outcome: 'WIN', pnl: '+$18.00', tag: 'reclaim-fail' },
      { id: '#3411', time: '06:15:11', bot: 'ETH Trend', tf: '5M', asset: 'ETH', strike: '$3,360', side: 'YES', price: '$0.58', outcome: 'WIN', pnl: '+$28.00', tag: 'trend-cont' },
      { id: '#3400', time: '06:00:00', bot: '3-Step Dom', tf: '15M', asset: 'BTC', strike: '$90,580', side: 'YES', price: '$0.57', outcome: 'LOSS', pnl: '−$18.00', tag: 'book-thin' },
    ];
  }, []);

  const filteredExecutions = useMemo(() => {
    if (!selectedTag) return journalExecutions;
    return journalExecutions.filter((item) => item.tag === selectedTag);
  }, [journalExecutions, selectedTag]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#0f1319] text-white font-sans">
      {/* =========================================================================
          COLUMN 1: Primary Navigation Sidebar (200px)
          ========================================================================= */}
      <aside className="w-[200px] bg-[#12161a] border-r border-[#262d35] p-4 flex flex-col justify-between shrink-0 select-none">
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
          COLUMN 2: Contextual Secondary Sub-Navigation (220px)
          ========================================================================= */}
      <aside className="w-[220px] bg-[#12161a] border-r border-[#262d35] p-4 flex flex-col shrink-0 select-none overflow-y-auto">
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

      {/* =========================================================================
          COLUMN 3: Main Central Workbench View (Flex 1)
          ========================================================================= */}
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto bg-[#0f1319]">
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
              {primaryNav === 'journal' && "TRADE JOURNAL & TODAY'S TIMELINE"}
              {primaryNav === 'analytics' && 'LIVE WORKBENCH & MICROSTRUCTURE RADAR'}
            </h1>
          </div>

          <div className="flex items-center gap-3">
            {/* Pop-Out Baby Bot Console Button */}
            <button
              onClick={onTogglePopOutBabyBot}
              className="px-3 py-1.5 rounded-lg text-xs font-mono font-bold bg-[#00bda5]/15 hover:bg-[#00bda5]/25 text-[#2dd4bf] border border-[#00bda5]/40 transition-all flex items-center gap-1.5 shadow-sm"
              title="Open Baby Bot Standalone Execution Cockpit in new window"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>Pop-Out Baby Bot</span>
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
                        <th className="py-2.5 px-4">Status</th>
                        <th className="py-2.5 px-4 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1f262d]">
                      {benchmarkingModels.map((m, idx) => (
                        <tr key={idx} className="hover:bg-[#171c22]/50 transition-colors">
                          <td className="py-3 px-4 font-bold text-white">{m.name}</td>
                          <td className="py-3 px-4 text-[#8c9ba5]">{m.asset}</td>
                          <td className="py-3 px-4 text-slate-300">{m.lane}</td>
                          <td className="py-3 px-4 text-right text-white">{m.events}</td>
                          <td className="py-3 px-4 text-right font-bold text-[#34d399]">{m.winRate}</td>
                          <td className="py-3 px-4 text-right text-white">{m.profitFactor}</td>
                          <td className="py-3 px-4 text-right text-slate-300">{m.drawdown}</td>
                          <td className="py-3 px-4">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${m.statusColor}`}>
                              {m.status}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-right">
                            {m.canPromote ? (
                              <button
                                onClick={() => setIsPromoteModalOpen(true)}
                                className="px-2.5 py-1 rounded bg-[#00bda5] text-black font-bold hover:bg-[#2dd4bf] transition-all shadow-sm"
                              >
                                Promote 🚀
                              </button>
                            ) : (
                              <span className="text-[10px] text-[#8c9ba5]">&mdash;</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* 3. JOURNAL VIEW (From HTML Proposal) */}
          {primaryNav === 'journal' && (
            <div className="space-y-6">
              <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                    Trade Journal Execution Ledger
                  </h2>
                  <div className="text-xs font-mono text-[#8c9ba5]">
                    Showing {filteredExecutions.length} trades
                  </div>
                </div>

                <div className="overflow-x-auto rounded-lg border border-[#262d35]">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-[#171c22] text-[10px] uppercase text-[#8c9ba5] border-b border-[#262d35]">
                      <tr>
                        <th className="py-2.5 px-4">Trade ID</th>
                        <th className="py-2.5 px-4">Time (ET)</th>
                        <th className="py-2.5 px-4">Strategy</th>
                        <th className="py-2.5 px-4">Cycle</th>
                        <th className="py-2.5 px-4">Asset</th>
                        <th className="py-2.5 px-4">Strike</th>
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
                          <td className="py-2 px-4 text-[#8c9ba5]">{t.id}</td>
                          <td className="py-2 px-4 text-[#8c9ba5]">{t.time}</td>
                          <td className="py-2 px-4 font-semibold text-white">{t.bot}</td>
                          <td className="py-2 px-4">
                            <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                              t.tf === '5M' ? 'bg-[#d9a752]/20 text-[#d9a752]' : 'bg-[#00bda5]/20 text-[#2dd4bf]'
                            }`}>
                              {t.tf}
                            </span>
                          </td>
                          <td className="py-2 px-4 font-bold text-white">{t.asset}</td>
                          <td className="py-2 px-4 text-[#8c9ba5]">{t.strike}</td>
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
            </div>
          )}

          {/* 4. ANALYTICS / WORKBENCH VIEW */}
          {primaryNav === 'analytics' && (
            <div className="space-y-4">
              {/* Compact Price Hero */}
              <PriceHero market={market} />

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
              </div>
            </div>
          )}
        </div>
      </main>

      {/* =========================================================================
          COLUMN 4: Right Rail / Docked Baby Bot & Timeline (320px)
          ========================================================================= */}
      <aside className="w-[340px] bg-[#12161a] border-l border-[#262d35] flex flex-col shrink-0 overflow-y-auto select-none">
        {/* If Baby Bot is docked (not popped out into standalone window), render here */}
        {!isPoppedOutBabyBot ? (
          <div className="p-3 border-b border-[#262d35]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#8c9ba5]">
                Docked Baby Bot Console
              </span>
              <button
                onClick={onTogglePopOutBabyBot}
                title="Pop out Baby Bot window"
                className="text-[11px] font-mono text-[#00bda5] hover:text-white flex items-center gap-1"
              >
                <ExternalLink className="w-3 h-3" />
                <span>Pop-out</span>
              </button>
            </div>
            <BabyBotConsole
              market={market}
              aiSignals={aiSignals}
              livePortfolio={livePortfolio}
              activePosition={activePosition}
              tradingMode={tradingMode}
              timeframe={timeframe}
              isPoppedOut={false}
              onTogglePopOut={onTogglePopOutBabyBot}
              onFlattenHalt={onFlattenHalt}
              onQuickTrade={onQuickTrade}
              reportsCount={reports.length}
              consecutiveLosses={consecutiveLosses}
            />
          </div>
        ) : (
          <div className="p-4 bg-[#171c22]/50 border-b border-[#262d35] text-center text-xs font-mono text-[#8c9ba5]">
            <div className="w-2 h-2 rounded-full bg-[#00bda5] animate-ping mx-auto mb-2" />
            <span>Baby Bot running in standalone pop-out window</span>
            <button
              onClick={onTogglePopOutBabyBot}
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
                  onTogglePopOutBabyBot();
                }}
                className="px-4 py-2 rounded bg-[#00bda5] hover:bg-[#2dd4bf] text-black font-bold text-xs shadow-lg transition-all"
              >
                🚀 Fork Process & Launch Baby Bot
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
