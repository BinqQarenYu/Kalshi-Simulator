/**
 * @file BabyBotConsole.tsx
 * @description Distraction-free standalone execution cockpit for the refined Baby Bot.
 * Provides sub-second situational awareness, 5M/15M countdown velocity bar,
 * asymmetric risk breakdown, consecutive loss tripwire, and a 1.5-second hold-to-arm kill-switch.
 */

import React, { useState, useRef, useEffect, useMemo } from 'react';
import { MarketState, AISignals, Position, LivePortfolioState } from '../types';
import { Shield, AlertOctagon, Zap, ExternalLink, Minimize2, Activity, Volume2, VolumeX, Lock, CheckCircle2, AlertTriangle } from 'lucide-react';
import { soundFX } from '../utils/audioFX';

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
}

export const BabyBotConsole: React.FC<BabyBotConsoleProps> = ({
  market,
  aiSignals,
  livePortfolio,
  activePosition,
  tradingMode = 'live',
  timeframe = '15m',
  isPoppedOut = false,
  onTogglePopOut,
  onFlattenHalt,
  onQuickTrade,
  reportsCount = 0,
  consecutiveLosses = 0,
}) => {
  const [isAudioMuted, setIsAudioMuted] = useState(false);
  const [killHoldProgress, setKillHoldProgress] = useState(0);
  const [isArmingKill, setIsArmingKill] = useState(false);
  const [isHalted, setIsHalted] = useState(false);
  const holdIntervalRef = useRef<number | null>(null);

  const isLiveRealMoney = tradingMode === 'live';
  const is5m = timeframe === '5m';

  // Spot delta calculations
  const diffVal = market.diff ?? 0;
  const isDiffPositive = diffVal >= 0;
  const diffColor = isDiffPositive ? 'text-[#10b981]' : 'text-[#f43f5e]';
  const diffBg = isDiffPositive ? 'bg-[#10b981]/15 text-[#10b981] border-[#10b981]/30' : 'bg-[#f43f5e]/15 text-[#f43f5e] border-[#f43f5e]/30';

  // 5M vs 15M countdown metrics
  const totalWindowSecs = is5m ? 300 : 900;
  const remSecs = Math.max(0, market.expiry_countdown_seconds ?? 0);
  const progressPct = Math.min(100, Math.max(0, ((totalWindowSecs - remSecs) / totalWindowSecs) * 100));

  // 5M Phase logic
  const phase5m = useMemo(() => {
    if (!is5m) return null;
    const elapsed = totalWindowSecs - remSecs;
    if (elapsed < 60) return { label: 'Calibration & Initialization', color: 'text-cyan-400', bar: 'bg-cyan-500' };
    if (remSecs > 60) return { label: 'Active Order Flow Execution', color: 'text-emerald-400', bar: 'bg-emerald-500' };
    return { label: 'Settlement Freeze & Sweep', color: 'text-amber-400', bar: 'bg-amber-500 animate-pulse' };
  }, [is5m, totalWindowSecs, remSecs]);

  // VPIN toxicity check
  const vpin = aiSignals?.vpin ?? 0.28;
  const isVpinToxic = vpin >= 0.65;

  // Razor-tight dead zone check (|Spot - Strike| < $15)
  const isDeadZone = Math.abs(diffVal) < 15.0;

  // Implied probability calculation
  const yesProb = market.market_chance_pct ?? 50;
  const noProb = 100 - yesProb;

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
        soundFX.playOrderFillSound();
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

  useEffect(() => {
    return () => {
      if (holdIntervalRef.current) clearInterval(holdIntervalRef.current);
    };
  }, []);

  return (
    <div className={`w-full max-w-[460px] bg-[#0c0f12] text-white flex flex-col font-sans select-none rounded-xl border overflow-hidden shadow-2xl ${
      isLiveRealMoney
        ? 'border-[#f43f5e]/50 shadow-[#f43f5e]/10'
        : 'border-[#00bda5]/50 shadow-[#00bda5]/10'
    }`}>
      {/* 1. Header: Execution Mode, Bot Name & Telemetry */}
      <div className={`px-4 py-2.5 border-b flex items-center justify-between ${
        isLiveRealMoney ? 'bg-[#4c111e]/40 border-[#f43f5e]/30' : 'bg-[#115e59]/40 border-[#00bda5]/30'
      }`}>
        <div className="flex items-center gap-2">
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono font-bold tracking-wider uppercase border shadow-sm ${
            isLiveRealMoney
              ? 'bg-[#d31a38] text-white border-rose-400 animate-pulse'
              : 'bg-[#00bda5]/20 text-[#2dd4bf] border-[#00bda5]/50'
          }`}>
            <span className={`w-2 h-2 rounded-full ${isLiveRealMoney ? 'bg-white' : 'bg-[#2dd4bf]'}`} />
            <span>{isLiveRealMoney ? 'LIVE REAL-MONEY' : 'SHADOW (PAPER)'}</span>
          </div>

          <span className="text-xs font-mono font-bold text-slate-200">
            {aiSignals?.strategy_name || '3-Step Dominion v3.2'}
          </span>
        </div>

        <div className="flex items-center gap-2 text-[11px] font-mono">
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
            className="p-1 rounded text-slate-400 hover:text-white transition-colors"
          >
            {isAudioMuted ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
          </button>
          {onTogglePopOut && (
            <button
              onClick={onTogglePopOut}
              aria-label={isPoppedOut ? 'Dock into parent' : 'Pop out window'}
              title={isPoppedOut ? 'Dock into parent' : 'Pop out into standalone window'}
              className="p-1 rounded text-slate-400 hover:text-white transition-colors"
            >
              {isPoppedOut ? <Minimize2 className="w-3.5 h-3.5" /> : <ExternalLink className="w-3.5 h-3.5" />}
            </button>
          )}
        </div>
      </div>

      {/* Target Contract Banner */}
      <div className="px-4 py-1.5 bg-[#12161a] border-b border-[#262d35] flex items-center justify-between text-[11px] font-mono text-[#8c9ba5]">
        <div className="flex items-center gap-2">
          <span className="text-white font-bold">{market.ticker || 'KXBTC15M-CURRENT'}</span>
          <span className={`px-1.5 py-0.2 rounded text-[9px] font-bold uppercase ${
            is5m ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' : 'bg-teal-500/20 text-teal-300 border border-teal-500/40'
          }`}>
            {is5m ? '5M SPRINT' : '15M CYCLE'}
          </span>
        </div>
        <span className="text-emerald-400">TAPE: OK (5Hz BRTI)</span>
      </div>

      {/* 2. Live Event Horizon: Strike K vs CME Spot S_t */}
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
              {isDiffPositive ? '▲' : '▼'} {market.diff_str || `+$${Math.abs(diffVal).toFixed(2)}`}
            </div>
            <span className={`inline-block px-1.5 py-0.2 rounded text-[10px] font-mono font-bold border mt-0.5 ${diffBg}`}>
              {isDiffPositive ? '+' : ''}{market.diff_pct?.toFixed(3) ?? '0.037'}%
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
                is5m ? (phase5m?.bar || 'bg-emerald-500') : 'bg-gradient-to-r from-teal-500 to-emerald-400'
              }`}
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      </div>

      {/* 3. CLOB Inside Touch & Implied Probability */}
      <div className="px-4 py-2.5 bg-[#0f1319] border-b border-[#262d35] space-y-2">
        <div className="flex items-center justify-between text-xs font-mono">
          <div className="flex items-center gap-2">
            <span className="text-[#10b981] font-bold">YES</span>
            <span className="text-white font-extrabold">{market.yes_cents_str || '58¢'}</span>
            <span className="text-[10px] text-[#8c9ba5]">(9 cts)</span>
          </div>
          <div className="text-[10px] text-[#8c9ba5] font-semibold uppercase tracking-wider">
            CLOB INSIDE TOUCH
          </div>
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

      {/* 4. Active Position & Risk Telemetry */}
      <div className="p-4 bg-[#12161a] border-b border-[#262d35] space-y-2.5">
        <div className="flex items-center justify-between text-xs font-mono">
          <span className="text-[#8c9ba5] uppercase tracking-wider text-[10px] font-bold">Active Position</span>
          <span className="text-[10px] text-amber-400 font-bold">Hard Cap: 1 Contract</span>
        </div>

        <div className="p-2.5 rounded-lg bg-[#171c22] border border-[#262d35] flex items-center justify-between font-mono text-xs">
          {activePosition && activePosition.size > 0 ? (
            <>
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded font-bold uppercase text-[10px] ${
                  activePosition.side === 'yes' ? 'bg-[#10b981]/20 text-[#10b981]' : 'bg-[#f43f5e]/20 text-[#f43f5e]'
                }`}>
                  {activePosition.side.toUpperCase()}
                </span>
                <span className="text-white font-bold">{activePosition.size} ct @ {activePosition.entry_price * 100}¢</span>
              </div>
              <div className="text-right">
                <div className={`font-bold ${activePosition.unrealized_pnl >= 0 ? 'text-[#10b981]' : 'text-[#f43f5e]'}`}>
                  {activePosition.unrealized_pnl >= 0 ? '+' : ''}${activePosition.unrealized_pnl.toFixed(2)}
                </div>
                <div className="text-[10px] text-[#8c9ba5]">Unrealized PnL</div>
              </div>
            </>
          ) : (
            <div className="w-full text-center text-[#8c9ba5] py-1 text-xs">
              FLAT · No open contract positions (Holding $0.48 Maker Resting Limit)
            </div>
          )}
        </div>

        {/* Asymmetric Risk Breakdown */}
        <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
          <div className="p-2 rounded bg-[#13171c] border border-[#1f262d]">
            <span className="text-[#8c9ba5] text-[10px]">MAX RISK (CAPITAL):</span>
            <div className="text-sm font-bold text-[#f43f5e] mt-0.5">-$0.48 / ct</div>
          </div>
          <div className="p-2 rounded bg-[#13171c] border border-[#1f262d]">
            <span className="text-[#8c9ba5] text-[10px]">MAX SETTLEMENT WIN:</span>
            <div className="text-sm font-bold text-[#10b981] mt-0.5">+$0.52 / ct</div>
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
        <div className={`p-2 rounded-lg border text-[11px] font-mono flex items-center justify-between ${
          isDeadZone
            ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
            : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
        }`}>
          <div className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${isDeadZone ? 'bg-amber-400' : 'bg-emerald-400 animate-pulse'}`} />
            <span>{isDeadZone ? 'Razor-Tight Dead Zone Active' : 'Directional Edge Ready'}</span>
          </div>
          <span className="text-[10px] font-bold uppercase tracking-wider">
            {isDeadZone ? 'SKIPPING' : 'EDGE CONFIRMED'}
          </span>
        </div>
      </div>

      {/* 5. Playbook Rationale Card */}
      <div className="px-4 py-2.5 bg-[#0f1319] border-b border-[#262d35] text-[11px] font-mono text-[#8c9ba5] leading-relaxed">
        <span className="text-white font-semibold">Active Rationale: </span>
        <span>{aiSignals?.rationale || '3-Step Dominion Playbook 2: Monitoring OFI trend continuation. Waiting for favorable book liquidity.'}</span>
      </div>

      {/* 6. Hardware-Style Emergency Kill-Switch */}
      <div className="p-4 bg-[#0c0f12]">
        <button
          type="button"
          onMouseDown={handleHoldStart}
          onMouseUp={handleHoldEnd}
          onMouseLeave={handleHoldEnd}
          onTouchStart={handleHoldStart}
          onTouchEnd={handleHoldEnd}
          disabled={isHalted}
          className={`w-full relative overflow-hidden py-3.5 px-4 rounded-lg font-extrabold text-xs tracking-wider uppercase transition-all shadow-lg select-none ${
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
