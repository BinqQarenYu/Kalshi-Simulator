/**
 * @file Header.tsx
 * @description Top navigation bar with Bitcoin symbol, active market timeframe selector (5m, 15m, 1h),
 * Feed Mode switcher (Mock Sim vs Live Kalshi), AI Copilot switch, audio FX toggle, and connection status.
 */

import React, { useState } from 'react';
import { MarketState, MemoryProfileData, IntegrityStatus, ComplianceStatus, SystemResourceMetrics, LivePortfolioState } from '../types';
import { Bot, RefreshCw, Radio, Share2, ArrowDownToLine, MessageSquare, Volume2, VolumeX, Activity, Zap, Play, Award, Loader2, ShieldCheck, ShieldAlert, Scale, Cpu, Wallet, AlertOctagon, BarChart3 } from 'lucide-react';
import { soundFX } from '../utils/audioFX';

interface HeaderProps {
  market: MarketState;
  isConnected: boolean;
  aiAutoTrade: boolean;
  timeframe: string;
  mode?: 'mock' | 'live';
  tradingMode?: 'paper' | 'live';
  mainView?: 'trading' | 'analytics';
  onSelectMainView?: (view: 'trading' | 'analytics') => void;
  isKillSwitchTripped?: boolean;
  livePortfolio?: LivePortfolioState | null;
  memoryProfile?: MemoryProfileData;
  reportsCount?: number;
  integrityStatus?: IntegrityStatus;
  complianceStatus?: ComplianceStatus;
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

export const Header: React.FC<HeaderProps> = ({
  market,
  isConnected,
  aiAutoTrade,
  timeframe,
  mode = 'mock',
  tradingMode = 'paper',
  mainView = 'trading',
  onSelectMainView,
  isKillSwitchTripped = false,
  livePortfolio,
  memoryProfile,
  reportsCount = 0,
  integrityStatus,
  complianceStatus,
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
        {/* Left: BTC Symbol + Title + Live Subtitle */}
        <div className="flex items-center gap-3.5">
          {/* Bitcoin Orange Icon */}
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-[#f7931a] to-[#e67e00] shadow-lg shadow-[#f7931a]/20">
            <span className="text-2xl font-bold text-white leading-none">₿</span>
          </div>

          <div>
            {/* Breadcrumb Navigation: BTC / 15 min */}
            <div className="flex items-center gap-1.5 text-xs text-[#8b949e] font-medium">
              <a
                href="https://kalshi.com/category/crypto/btc"
                target="_blank"
                rel="noreferrer"
                className="hover:text-[#f7931a] transition-colors text-white/90 font-semibold flex items-center gap-1"
              >
                BTC
              </a>
              <span className="text-[#484f58]">/</span>
              <a
                href="https://kalshi.com/category/crypto/frequency/fifteen_min"
                target="_blank"
                rel="noreferrer"
                className="hover:text-white transition-colors"
              >
                {timeframe === '15m' ? '15 min' : timeframe === '5m' ? '5 min' : '1 hour'}
              </a>

              {/* Timeframe Selector Pills */}
              <div className="flex gap-1 bg-[#161b22] p-0.5 rounded-lg border border-[#30363d] ml-2">
                {['5m', '15m', '1h'].map((tf) => (
                  <button
                    key={tf}
                    onClick={() => {
                      soundFX.playClickSound();
                      onSelectTimeframe(tf);
                    }}
                    className={`px-2 py-0.5 text-[11px] font-semibold rounded-md transition-all ${
                      timeframe === tf
                        ? 'bg-[#f7931a] text-black shadow-sm font-bold'
                        : 'text-[#8b949e] hover:text-white'
                    }`}
                  >
                    {tf.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2.5 mt-0.5">
              <h1 className="text-xl font-bold text-white tracking-tight">
                BTC {timeframe === '15m' ? '15 min' : timeframe === '5m' ? '5 min' : '1 hour'}
              </h1>
              <div className="flex items-center gap-1.5 text-xs text-[#8b949e]">
                <span className="text-white/80 font-medium">
                  {(() => {
                    try {
                      const now = new Date();
                      const cycleEnd = new Date(now.getTime() + (market.expiry_countdown_seconds ?? 0) * 1000);
                      const durMins = timeframe === '5m' ? 5 : timeframe === '1h' ? 60 : 15;
                      const cycleStart = new Date(cycleEnd.getTime() - durMins * 60 * 1000);
                      const offsetMin = -now.getTimezoneOffset();
                      const sign = offsetMin >= 0 ? '+' : '-';
                      const absHours = Math.floor(Math.abs(offsetMin) / 60);
                      const gmtStr = `GMT${sign}${absHours}`;
                      const dateStr = cycleStart.toLocaleDateString('en-US', { month: 'long', day: 'numeric' });
                      const sTime = cycleStart.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
                      const eTime = cycleEnd.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
                      return `${dateStr}, ${sTime} – ${eTime} ${gmtStr}`;
                    } catch {
                      return market.time_window_str || 'Live Expiry Window';
                    }
                  })()}
                </span>
                <span className="text-[#8b949e] font-normal hidden sm:inline">
                  ({market.time_window_str || '10:15 - 10:30 AM ET'})
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
          <div className="flex items-center bg-[#161b22] p-1 rounded-xl border border-[#30363d] text-xs font-bold shadow-md">
            <button
              onClick={() => {
                soundFX.playClickSound();
                onSelectMainView('trading');
              }}
              className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 ${
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
              onClick={() => {
                soundFX.playClickSound();
                onSelectMainView('analytics');
              }}
              className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 ${
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
        <div className="flex items-center bg-[#161b22] p-1 rounded-xl border border-[#30363d] text-xs font-bold shadow-md">
          <button
            onClick={() => {
              soundFX.playClickSound();
              onSelectTradingMode?.('paper');
            }}
            className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 ${
              !isLive
                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40 shadow-sm'
                : 'text-[#8b949e] hover:text-white border border-transparent'
            }`}
          >
            <span>📄 Paper Trading</span>
          </button>
          <button
            onClick={() => {
              soundFX.playClickSound();
              onSelectTradingMode?.('live');
            }}
            className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-1.5 ${
              isLive
                ? 'bg-rose-500/25 text-rose-400 border border-rose-500/50 shadow-md shadow-rose-500/20 font-extrabold'
                : 'text-[#8b949e] hover:text-white border border-transparent'
            }`}
          >
            <span className="h-2 w-2 rounded-full bg-rose-500 animate-pulse" />
            <span>🔴 Live Trading</span>
          </button>
        </div>

        {/* Right Action Cluster */}
        <div className="flex items-center gap-3">
          {/* In LIVE Mode: Show Emergency Kill Switch & Real Balance prominently */}
          {isLive ? (
            <>
              {/* Emergency Kill Switch Button */}
              {isKillSwitchTripped ? (
                <button
                  onClick={onResumeTrading}
                  className="flex items-center gap-2 px-3.5 py-1.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-extrabold rounded-xl shadow-md shadow-emerald-500/20 active:scale-95 transition-all"
                  title="Circuit breaker tripped. Click to resume live trading"
                >
                  <Play className="h-3.5 w-3.5 fill-current" />
                  <span>▶ RESUME TRADING</span>
                </button>
              ) : (
                <button
                  onClick={onKillSwitch}
                  className="flex items-center gap-2 px-3.5 py-1.5 bg-gradient-to-r from-red-600 to-rose-700 hover:from-red-500 hover:to-rose-600 text-white text-xs font-extrabold rounded-xl shadow-lg shadow-red-500/30 active:scale-95 transition-all animate-pulse"
                  title="EMERGENCY STOP: Immediately halt all live orders"
                >
                  <AlertOctagon className="h-4 w-4 fill-current" />
                  <span>🛑 EMERGENCY STOP</span>
                </button>
              )}

              {/* Live Kalshi Account Balance Badge */}
              <div
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#161b22] border border-emerald-500/40 text-xs font-mono shadow-sm shadow-emerald-500/10 cursor-default"
                title={`Kalshi Live Account | Available Cash: $${(livePortfolio?.balance_dollars ?? 0.30).toFixed(2)} | Margin: $${(livePortfolio?.available_margin ?? 0.30).toFixed(2)}`}
              >
                <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-[#8b949e] font-sans font-semibold text-[11px]">Live Cash:</span>
                <span className="font-bold text-emerald-400">
                  ${(livePortfolio?.balance_dollars ?? 0.30).toFixed(2)}
                </span>
              </div>
            </>
          ) : (
            /* In PAPER Mode: Show full simulation tools */
            <>
              {/* Feed Mode Switcher (Mock Sim vs Live Kalshi) */}
              <div className="flex items-center bg-[#161b22] p-0.5 rounded-lg border border-[#30363d] text-xs font-semibold">
                <button
                  onClick={() => {
                    soundFX.playClickSound();
                    onToggleMode?.('mock');
                  }}
                  className={`px-2.5 py-1 rounded-md transition-all ${
                    mode === 'mock'
                      ? 'bg-[#30363d] text-white font-bold'
                      : 'text-[#8b949e] hover:text-white'
                  }`}
                >
                  Mock Sim
                </button>
                <button
                  onClick={() => {
                    soundFX.playClickSound();
                    onToggleMode?.('live');
                  }}
                  className={`px-2.5 py-1 rounded-md transition-all flex items-center gap-1 ${
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
                onClick={() => {
                  soundFX.playClickSound();
                  onToggleAI(!aiAutoTrade);
                }}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold border transition-all ${
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
                  onClick={handleRunBotTest}
                  disabled={isTesting}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs font-bold rounded-xl shadow-md shadow-blue-500/20 active:scale-95 transition-all disabled:opacity-50"
                  title="Test Bot: Execute an immediate AI trade decision on active 15M contract"
                >
                  {isTesting ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Play className="h-3 w-3 fill-current" />
                  )}
                  <span>{isTesting ? 'Testing...' : '🧪 Test Bot'}</span>
                </button>
              )}

              {/* 15M Win/Loss Reports Button */}
              {onOpenReports && (
                <button
                  onClick={onOpenReports}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-[#161b22] hover:bg-[#21262d] border border-[#30363d] text-emerald-400 hover:text-emerald-300 text-xs font-bold rounded-xl transition-all"
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
                onClick={onReset}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-[#8b949e] hover:text-white bg-[#161b22] border border-[#30363d] hover:bg-[#21262d] transition-all"
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
              onClick={onOpenIntegrity}
              className={`flex items-center gap-1.5 px-3 py-1.5 border text-xs font-bold rounded-xl transition-all ${
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
            className={`p-2 rounded-xl border transition-all ${
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

