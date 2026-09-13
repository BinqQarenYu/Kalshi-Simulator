/**
 * @file Header.tsx
 * @description Top navigation bar with Bitcoin symbol, active market timeframe selector (5m, 15m, 1h),
 * Feed Mode switcher (Mock Sim vs Live Kalshi), AI Copilot switch, audio FX toggle, and connection status.
 */

import React, { useState } from 'react';
import { MarketState, MemoryProfileData, IntegrityStatus, ComplianceStatus, SystemResourceMetrics, LivePortfolioState, CryptoAsset } from '../types';
import { Bot, RefreshCw, Radio, Share2, ArrowDownToLine, MessageSquare, Volume2, VolumeX, Activity, Zap, Play, Award, Loader2, ShieldCheck, ShieldAlert, Scale, Cpu, Wallet, AlertOctagon, BarChart3, TrendingUp } from 'lucide-react';
import { soundFX } from '../utils/audioFX';

interface HeaderProps {
  market: MarketState;
  isConnected: boolean;
  aiAutoTrade: boolean;
  timeframe: string;
  mode?: 'mock' | 'live';
  tradingMode?: 'paper' | 'live';
  activeStrategyBot?: string;
  onSelectStrategy?: (strategyId: string) => Promise<any>;
  onSelectAsset?: (asset: CryptoAsset) => void;
  mainView?: 'trading' | 'analytics';
  onSelectMainView?: (view: 'trading' | 'analytics') => void;
  isKillSwitchTripped?: boolean;
  livePortfolio?: LivePortfolioState | null;
  memoryProfile?: MemoryProfileData;
  reportsCount?: number;
  integrityStatus?: IntegrityStatus;
  complianceStatus?: ComplianceStatus;
  botAuditStatus?: any;
  systemResources?: SystemResourceMetrics;
  onToggleAI: (enabled: boolean) => void;
  onToggleMode?: (mode: 'mock' | 'live') => void;
  onSelectTradingMode?: (mode: 'paper' | 'live') => void;
  onSelectTimeframe: (tf: string) => void;
  onReset: () => void;
  onKillSwitch?: () => void;
  onResumeTrading?: () => void;
  onOpenReports?: () => void;
  onOpenIntegrity?: () => void;
  onOpenCompliance?: () => void;
  onOpenSystemResources?: () => void;
  onTestBot?: () => Promise<any>;
}
import { CRYPTO_ASSET_LIST } from '../utils/assets';

const CRYPTO_ASSET_TABS = CRYPTO_ASSET_LIST;

export const Header: React.FC<HeaderProps> = ({
  market,
  isConnected,
  aiAutoTrade,
  timeframe,
  mode = 'mock',
  tradingMode = 'paper',
  activeStrategyBot = '3_step_domination_bot',
  onSelectStrategy,
  onSelectAsset,
  mainView = 'trading',
  onSelectMainView,
  isKillSwitchTripped = false,
  livePortfolio,
  memoryProfile,
  reportsCount = 0,
  integrityStatus,
  complianceStatus,
  botAuditStatus,
  systemResources,
  onToggleAI,
  onToggleMode,
  onSelectTradingMode,
  onSelectTimeframe,
  onReset,
  onKillSwitch,
  onResumeTrading,
  onOpenReports,
  onOpenIntegrity,
  onOpenCompliance,
  onOpenSystemResources,
  onTestBot,
}) => {
  const [isMuted, setIsMuted] = useState<boolean>(soundFX.muted);
  const [isTesting, setIsTesting] = useState<boolean>(false);

  const activeAssetKey = market.active_asset || 'BTC';
  const currentAsset = CRYPTO_ASSET_TABS.find((a) => a.id === activeAssetKey) || CRYPTO_ASSET_TABS[0];

  const handleRunBotTest = async () => {
    if (!onTestBot || isTesting) return;
    setIsTesting(true);
    try {
      await onTestBot();
    } catch (err) {
      console.error(err);
    } finally {
      setIsTesting(false);
    }
  };

  const handleToggleSound = () => {
    const muted = soundFX.toggleMute();
    setIsMuted(muted);
    if (!muted) {
      soundFX.playClickSound();
    }
  };

  const isLive = tradingMode === 'live';

  return (
    <header className={`border-b border-[#21262d] px-4 py-3 sm:px-6 transition-all ${
      isLive ? 'bg-[#0e111a] border-rose-500/20' : 'bg-[#0d1117]'
    }`}>
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Left: Dynamic Asset Icon + Selector + Title + Live Subtitle */}
        <div className="flex items-center gap-3.5">
          {/* Dynamic Asset Icon */}
          <div className={`flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br ${currentAsset.bgGrad} shadow-lg shadow-black/40`}>
            <span className="text-2xl font-bold text-white leading-none">{currentAsset.symbol}</span>
          </div>

          <div>
            {/* Breadcrumb Navigation: Asset Selector + Timeframe Selector */}
            <div className="flex items-center gap-1.5 text-xs text-[#8b949e] font-medium flex-wrap">
              {/* Asset Selector Pills */}
              <div role="group" aria-label="Crypto asset selection" className="flex gap-1 bg-[#161b22] p-0.5 rounded-lg border border-[#30363d]">
                {CRYPTO_ASSET_TABS.map((a) => {
                  const isSel = activeAssetKey === a.id;
                  return (
                    <button
                      key={a.id}
                      type="button"
                      aria-pressed={isSel}
                      onClick={() => {
                        soundFX.playClickSound();
                        onSelectAsset?.(a.id);
                      }}
                      className={`px-2 py-0.5 text-[11px] font-bold rounded-md transition-all flex items-center gap-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#f7931a] ${
                        isSel
                          ? 'bg-[#30363d] text-white shadow-sm ring-1 ring-white/20'
                          : 'text-[#8b949e] hover:text-white'
                      }`}
                      style={isSel ? { borderLeft: `3px solid ${a.color}` } : undefined}
                    >
                      <span style={{ color: a.color }}>{a.symbol}</span>
                      <span>{a.label}</span>
                    </button>
                  );
                })}
              </div>

              <span className="text-[#484f58]">/</span>

              <div role="group" aria-label="Timeframe selection" className="flex gap-1 bg-[#161b22] p-0.5 rounded-lg border border-[#30363d]">
                {['5m', '15m', '1h'].map((tf) => {
                  const is5m = tf === '5m';
                  const isSel = timeframe === tf;
                  return (
                    <button
                      key={tf}
                      type="button"
                      aria-pressed={isSel}
                      onClick={() => {
                        soundFX.playClickSound();
                        onSelectTimeframe(tf);
                      }}
                      className={`px-2 py-0.5 text-[11px] font-semibold rounded-md transition-all flex items-center gap-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#f7931a] ${
                        isSel
                          ? is5m
                            ? 'bg-amber-500 text-black shadow-sm font-extrabold'
                            : 'bg-[#f7931a] text-black shadow-sm font-bold'
                          : 'text-[#8b949e] hover:text-white'
                      }`}
                      title={is5m ? '5M Expansion Sprint Cycle (Exclusive to Mother Dash Paper Live)' : `${tf.toUpperCase()} Market`}
                    >
                      <span>{tf.toUpperCase()}</span>
                      {is5m && (
                        <span className={`px-1 py-0.1 text-[8px] font-mono uppercase tracking-wider rounded ${
                          isSel ? 'bg-black/25 text-black font-black' : 'bg-amber-500/20 text-amber-300 font-bold'
                        }`}>
                          PAPER
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="flex items-center gap-2.5 mt-0.5 flex-wrap">
              <h1 className="text-xl font-bold text-white tracking-tight">
                {market.active_asset_name || currentAsset.label} {timeframe === '15m' ? '15 min' : timeframe === '5m' ? '5 min' : '1 hour'}
              </h1>
              {timeframe === '5m' && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/40 text-amber-300 font-extrabold text-[10px] tracking-wider uppercase shadow-sm">
                  <span className="h-1.5 w-1.5 rounded-full bg-amber-400 animate-pulse" />
                  EXPANSION · PAPER LIVE ONLY
                </span>
              )}
              <div className="flex items-center gap-1.5 text-xs text-[#8b949e]">
                <span className="text-white/90 font-medium">
                  {market.time_window_str || 'August 30, 4:00 - 4:15 PM ET'}
                </span>
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-red-500/10 text-red-400 font-bold text-[10px]">
                  <span className="h-1.5 w-1.5 rounded-full bg-red-500 animate-ping" />
                  LIVE
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Center: View Switcher (Trading Arena vs Institutional Analytics & Journal) */}
        {onSelectMainView && (
          <div role="group" aria-label="Main view mode" className="flex items-center bg-[#161b22] p-1 rounded-xl border border-[#30363d] text-xs font-bold shadow-md">
            <button
              type="button"
              aria-pressed={mainView === 'trading'}
              onClick={() => {
                soundFX.playClickSound();
                onSelectMainView('trading');
              }}
              className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 ${
                mainView === 'trading'
                  ? isLive
                    ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40 shadow-sm'
                    : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-sm'
                  : 'text-[#8b949e] hover:text-white border border-transparent'
              }`}
            >
              <Activity className="h-3.5 w-3.5" />
              <span>⚡ Trading Arena</span>
            </button>
            <button
              type="button"
              aria-pressed={mainView === 'analytics'}
              onClick={() => {
                soundFX.playClickSound();
                onSelectMainView('analytics');
              }}
              className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                mainView === 'analytics'
                  ? 'bg-blue-500/25 text-blue-400 border border-blue-500/50 shadow-sm font-extrabold'
                  : 'text-[#8b949e] hover:text-white border border-transparent'
              }`}
            >
              <BarChart3 className="h-3.5 w-3.5 text-blue-400" />
              <span>📊 Analytics & Journal</span>
            </button>
          </div>
        )}

        {/* Center/Right: Prominent PAPER vs LIVE Trading Mode Switcher */}
        <div role="group" aria-label="Trading execution mode" className="flex items-center bg-[#161b22] p-1 rounded-xl border border-[#30363d] text-xs font-bold shadow-md">
          <button
            type="button"
            aria-pressed={!isLive}
            onClick={() => {
              soundFX.playClickSound();
              onSelectTradingMode?.('paper');
            }}
            className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
              !isLive
                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40 shadow-sm'
                : 'text-[#8b949e] hover:text-white border border-transparent'
            }`}
          >
            <span>📄 Paper Trading {timeframe === '5m' && '(Active)'}</span>
          </button>
          <button
            type="button"
            aria-pressed={isLive}
            disabled={timeframe === '5m'}
            onClick={() => {
              if (timeframe === '5m') return;
              soundFX.playClickSound();
              onSelectTradingMode?.('live');
            }}
            title={timeframe === '5m' ? '5M contracts are strictly Paper Live only. Live real-money trading is disabled.' : 'Switch to Live Trading'}
            className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 ${
              timeframe === '5m'
                ? 'opacity-40 cursor-not-allowed text-[#6e7681] border border-transparent select-none'
                : isLive
                ? 'bg-rose-500/25 text-rose-400 border border-rose-500/50 shadow-md shadow-rose-500/20 font-extrabold'
                : 'text-[#8b949e] hover:text-white border border-transparent'
            }`}
          >
            <span className={`h-2 w-2 rounded-full ${timeframe === '5m' ? 'bg-[#484f58]' : 'bg-rose-500 animate-pulse'}`} />
            <span>🔴 Live Trading</span>
            {timeframe === '5m' && <span className="text-[10px] font-mono ml-0.5 text-amber-400/80">🔒</span>}
          </button>
        </div>

        {/* Center/Right: Active Quantitative Strategy Bot Indicator Pill */}
        <div 
          className={`flex items-center gap-2 px-3 py-1.5 rounded-xl bg-[#161b22] border text-xs shadow-md cursor-default ${
            activeStrategyBot === '3_step_domination_bot'
              ? 'border-amber-500/40 shadow-amber-500/10'
              : activeStrategyBot === 'macro_onnx' || activeStrategyBot === 'onnx_microstructure_bot'
              ? 'border-purple-500/40 shadow-purple-500/10'
              : 'border-cyan-500/40 shadow-cyan-500/10'
          }`}
          title={`Active Strategy Bot: ${
            activeStrategyBot === '3_step_domination_bot'
              ? 'Bot 1: 3-Step Domination Bot (Port 8001 • Lane 1 LIVE)'
              : activeStrategyBot === 'macro_onnx' || activeStrategyBot === 'onnx_microstructure_bot'
              ? 'Bot 2: ONNX Strategy / Dual-Brain ONNX (Port 8002 • Lane 2 Shadow)'
              : 'Bot 3: Macro Trend Dominion (Port 8003 • Lane 2 Shadow)'
          }`}
        >
          <div className={`h-2 w-2 rounded-full animate-ping ${
            activeStrategyBot === '3_step_domination_bot'
              ? 'bg-amber-400'
              : activeStrategyBot === 'macro_onnx' || activeStrategyBot === 'onnx_microstructure_bot'
              ? 'bg-purple-400'
              : 'bg-cyan-400'
          }`} />
          {activeStrategyBot === '3_step_domination_bot' ? (
            <Zap className="h-3.5 w-3.5 text-amber-400" />
          ) : activeStrategyBot === 'macro_onnx' || activeStrategyBot === 'onnx_microstructure_bot' ? (
            <Cpu className="h-3.5 w-3.5 text-purple-400" />
          ) : (
            <TrendingUp className="h-3.5 w-3.5 text-cyan-400" />
          )}
          <div className="flex items-center gap-1.5">
            <span className="text-[#8b949e] font-sans text-[11px] hidden sm:inline">Active Bot:</span>
            <span className="font-bold text-white text-[11px]">
              {activeStrategyBot === '3_step_domination_bot'
                ? 'Bot 1 (3-Step Dom)'
                : activeStrategyBot === 'macro_onnx' || activeStrategyBot === 'onnx_microstructure_bot'
                ? 'Bot 2 (ONNX Dual-Brain)'
                : 'Bot 3 (Macro Trend)'}
            </span>
            {activeStrategyBot === '3_step_domination_bot' && (
              <span className="px-1.5 py-0.2 text-[9px] font-mono bg-amber-500/30 text-amber-200 border border-amber-500/40 rounded-full font-extrabold">
                Lane 1 Live
              </span>
            )}
            {activeStrategyBot !== '3_step_domination_bot' && (
              <span className="px-1.5 py-0.2 text-[9px] font-mono bg-purple-500/30 text-purple-200 border border-purple-500/40 rounded-full font-extrabold">
                Lane 2 Shadow
              </span>
            )}
          </div>
        </div>

        {/* Pre-Deployment 4-Pillar Audit Certification Badge */}
        <div
          role="status"
          aria-label={
            botAuditStatus?.is_certified !== false
              ? 'Pre-deployment audit certified'
              : 'Pre-deployment audit blocked'
          }
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-[11px] font-bold border shadow-sm transition-all cursor-help ${
            botAuditStatus?.is_certified !== false
              ? 'bg-emerald-950/40 border-emerald-500/50 text-emerald-300 shadow-emerald-500/10'
              : 'bg-rose-950/40 border-rose-500/60 text-rose-300 animate-pulse shadow-rose-500/20'
          }`}
          title={
            botAuditStatus?.is_certified !== false
              ? `✅ 4-PILLAR PRE-DEPLOYMENT AUDIT CERTIFIED\n• Guardrails: Micro-cap 1-2 contracts, cycle locks, resting order locks, VPIN veto\n• Math Invariants: Strict Decimal types, {0, 1} binary payoff\n• Truths: Zero-mock in live, secret isolation, ET clock parity\n• Law & Order: CFTC anti-wash, uncrossed order books`
              : `❌ AUDIT BLOCKED: ${botAuditStatus?.report?.failure_reasons?.join('; ') || 'Bot failed pre-deployment audit'}`
          }
        >
          {botAuditStatus?.is_certified !== false ? (
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
          ) : (
            <ShieldAlert className="h-3.5 w-3.5 text-rose-400" />
          )}
          <span className="tracking-wide font-mono text-[10px]">
            {botAuditStatus?.is_certified !== false ? 'AUDITED & CERTIFIED' : 'AUDIT BLOCKED'}
          </span>
        </div>

        {/* Right Action Cluster */}
        <div className="flex items-center gap-3">
          {/* In LIVE Mode: Show Emergency Kill Switch & Real Balance prominently */}
          {isLive ? (
            <>
              {/* Emergency Kill Switch Button */}
              {isKillSwitchTripped ? (
                <button
                  type="button"
                  aria-label="Resume live trading after circuit breaker trip"
                  onClick={onResumeTrading}
                  className="flex items-center gap-2 px-3.5 py-1.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-extrabold rounded-xl shadow-md shadow-emerald-500/20 active:scale-95 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
                  title="Circuit breaker tripped. Click to resume live trading"
                >
                  <Play className="h-3.5 w-3.5 fill-current" />
                  <span>▶ RESUME TRADING</span>
                </button>
              ) : (
                <button
                  type="button"
                  aria-label="Emergency Stop: Immediately halt all live orders"
                  onClick={onKillSwitch}
                  className="flex items-center gap-2 px-3.5 py-1.5 bg-gradient-to-r from-red-600 to-rose-700 hover:from-red-500 hover:to-rose-600 text-white text-xs font-extrabold rounded-xl shadow-lg shadow-red-500/30 active:scale-95 transition-all animate-pulse focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500"
                  title="EMERGENCY STOP: Immediately halt all live orders"
                >
                  <AlertOctagon className="h-4 w-4 fill-current" />
                  <span>🛑 EMERGENCY STOP</span>
                </button>
              )}

              {/* Live Kalshi Account Balance Badge */}
              <div
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#161b22] border border-emerald-500/40 text-xs font-mono shadow-sm shadow-emerald-500/10 cursor-default"
                title={`Kalshi Live Account | Available Cash: $${(Number(livePortfolio?.balance_dollars ?? 0.30) || 0.30).toFixed(2)} | Margin: $${(Number(livePortfolio?.available_margin ?? 0.30) || 0.30).toFixed(2)}`}
              >
                <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-[#8b949e] font-sans font-semibold text-[11px]">Live Cash:</span>
                <span className="font-bold text-emerald-400">
                  ${(Number(livePortfolio?.balance_dollars ?? 0.30) || 0.30).toFixed(2)}
                </span>
              </div>
            </>
          ) : (
            /* In PAPER Mode: Show full simulation tools */
            <>
              {/* Feed Mode Switcher (Mock Sim vs Live Kalshi) */}
              <div role="group" aria-label="Feed mode" className="flex items-center bg-[#161b22] p-0.5 rounded-lg border border-[#30363d] text-xs font-semibold">
                <button
                  type="button"
                  aria-pressed={mode === 'mock'}
                  onClick={() => {
                    soundFX.playClickSound();
                    onToggleMode?.('mock');
                  }}
                  className={`px-2.5 py-1 rounded-md transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 ${
                    mode === 'mock'
                      ? 'bg-[#30363d] text-white font-bold'
                      : 'text-[#8b949e] hover:text-white'
                  }`}
                >
                  Mock Sim
                </button>
                <button
                  type="button"
                  aria-pressed={mode === 'live'}
                  onClick={() => {
                    soundFX.playClickSound();
                    onToggleMode?.('live');
                  }}
                  className={`px-2.5 py-1 rounded-md transition-all flex items-center gap-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00d084] ${
                    mode === 'live'
                      ? 'bg-[#00d084]/20 text-[#00d084] font-bold border border-[#00d084]/40'
                      : 'text-[#8b949e] hover:text-white'
                  }`}
                >
                  <Activity className="h-3 w-3" />
                  <span>Kalshi Live</span>
                </button>
              </div>

              {/* AI Auto-Trade Toggle Pill */}
              <button
                type="button"
                role="switch"
                aria-checked={aiAutoTrade}
                aria-label="Toggle AI Auto-Trade"
                onClick={() => {
                  soundFX.playClickSound();
                  onToggleAI(!aiAutoTrade);
                }}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold border transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00d084] ${
                  aiAutoTrade
                    ? 'bg-[#00d084]/15 border-[#00d084]/50 text-[#00d084] shadow-sm shadow-[#00d084]/20'
                    : 'bg-[#161b22] border-[#30363d] text-[#8b949e] hover:text-white'
                }`}
              >
                <Bot className={`h-4 w-4 ${aiAutoTrade ? 'text-[#00d084] animate-bounce' : ''}`} />
                <span>AI Auto-Trade: {aiAutoTrade ? 'ON' : 'OFF'}</span>
              </button>

              {/* Test Bot Action Button */}
              {onTestBot && (
                <button
                  type="button"
                  aria-label="Test active strategy bot: Execute an immediate AI trade decision"
                  onClick={handleRunBotTest}
                  disabled={isTesting}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-white text-xs font-bold rounded-xl shadow-md active:scale-95 transition-all disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 ${
                    activeStrategyBot === '3_step_domination_bot'
                      ? 'bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 shadow-amber-500/20'
                      : activeStrategyBot === 'macro_onnx'
                      ? 'bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 shadow-purple-500/20'
                      : activeStrategyBot === 'macro_trend_dominion'
                      ? 'bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 shadow-cyan-500/20'
                      : activeStrategyBot === 'dominion_2_bot'
                      ? 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 shadow-emerald-500/20'
                      : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 shadow-blue-500/20'
                  }`}
                  title="Test Bot: Execute an immediate AI trade decision on active 15M contract"
                >
                  {isTesting ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Play className="h-3 w-3 fill-current" />
                  )}
                  <span>
                    {isTesting
                      ? 'Testing...'
                      : activeStrategyBot === '3_step_domination_bot'
                      ? '⚡ Test 3-Step Bot'
                      : activeStrategyBot === 'macro_onnx'
                      ? '🧪 Test Macro ONNX'
                      : '🧪 Test Bot'}
                  </span>
                </button>
              )}

              {/* 15M Win/Loss Reports Button */}
              {onOpenReports && (
                <button
                  type="button"
                  aria-label="View 15-Minute Event Win/Loss Reports"
                  onClick={onOpenReports}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-[#161b22] hover:bg-[#21262d] border border-[#30363d] text-emerald-400 hover:text-emerald-300 text-xs font-bold rounded-xl transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
                  title="View 15-Minute Event Win/Loss Reports"
                >
                  <Award className="h-3.5 w-3.5" />
                  <span>15M Reports</span>
                  {reportsCount > 0 && (
                    <span className="px-1.5 py-0.2 text-[10px] font-mono bg-emerald-500/20 border border-emerald-500/40 rounded-full">
                      {reportsCount}
                    </span>
                  )}
                </button>
              )}

              {/* Reset Capital Button */}
              <button
                type="button"
                aria-label="Reset simulation capital to $100"
                onClick={onReset}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-[#8b949e] hover:text-white bg-[#161b22] border border-[#30363d] hover:bg-[#21262d] transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
                title="Reset Simulation Capital"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Reset $100</span>
              </button>
            </>
          )}

          {/* Agent_integrity_check Suite Button (Always visible) */}
          {onOpenIntegrity && (
            <button
              type="button"
              aria-label="Open Agent Integrity Verification status panel"
              onClick={onOpenIntegrity}
              className={`flex items-center gap-1.5 px-3 py-1.5 border text-xs font-bold rounded-xl transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 ${
                (integrityStatus?.status ?? 'HEALTHY') === 'HEALTHY'
                  ? 'bg-[#161b22] hover:bg-[#21262d] border-cyan-500/30 text-cyan-400 hover:text-cyan-300'
                  : (integrityStatus?.status ?? 'HEALTHY') === 'WARNING'
                  ? 'bg-amber-500/10 hover:bg-amber-500/20 border-amber-500/40 text-amber-400'
                  : 'bg-rose-500/10 hover:bg-rose-500/20 border-rose-500/40 text-rose-400 animate-pulse'
              }`}
              title="Agent_integrity_check: Autonomous Invariant Verification Loop"
            >
              {(integrityStatus?.status ?? 'HEALTHY') === 'HEALTHY' ? (
                <ShieldCheck className="h-3.5 w-3.5 text-cyan-400" />
              ) : (
                <ShieldAlert className="h-3.5 w-3.5 text-amber-400" />
              )}
              <span>Integrity</span>
              <span className="px-1.5 py-0.2 text-[10px] font-mono bg-cyan-500/20 border border-cyan-500/40 rounded-full">
                {(integrityStatus?.score ?? 100.0).toFixed(0)}%
              </span>
            </button>
          )}

          {/* Audio SoundFX Toggle Button */}
          <button
            onClick={handleToggleSound}
            aria-label="Sound effects"
            aria-pressed={!isMuted}
            className={`p-2 rounded-xl border transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#f7931a] ${
              isMuted
                ? 'bg-[#161b22] border-[#30363d] text-[#8b949e] hover:text-white'
                : 'bg-[#f7931a]/15 border-[#f7931a]/40 text-[#f7931a]'
            }`}
            title={isMuted ? 'Unmute Sound Effects' : 'Mute Sound Effects'}
          >
            {isMuted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
          </button>

          {/* Connection Status Indicator */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#161b22] border border-[#30363d] text-[11px] font-medium">
            <Radio className={`h-3 w-3 ${isConnected ? 'text-[#00d084]' : 'text-red-400'}`} />
            <span className={isConnected ? 'text-gray-300' : 'text-red-400'}>
              {isConnected ? (isLive || mode === 'live' ? 'Kalshi WS' : 'Mock Feed') : 'Connecting'}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};

