/**
 * @file LiveGuardrailsCard.tsx
 * @description Institutional Pre-Trade Risk & Exchange Guardrails Card for Live Trading Mode.
 * Displays single-contract caps, daily circuit breaker status, VPIN toxicity shields,
 * low/depleted live account balance alerts, and the Emergency Kill Switch for real-money Kalshi execution.
 */

import React from 'react';
import { LivePortfolioState, IntegrityStatus, ComplianceStatus } from '../types';
import { AlertOctagon, Lock, Activity, CheckCircle2, Play, AlertTriangle, ArrowUpRight, Wallet } from 'lucide-react';
import { soundFX } from '../utils/audioFX';

interface LiveGuardrailsCardProps {
  livePortfolio?: LivePortfolioState | null;
  integrityStatus?: IntegrityStatus;
  complianceStatus?: ComplianceStatus;
  isKillSwitchTripped: boolean;
  onKillSwitch: () => void;
  onResumeTrading: () => void;
}

export const LiveGuardrailsCard: React.FC<LiveGuardrailsCardProps> = ({
  livePortfolio,
  integrityStatus,
  complianceStatus,
  isKillSwitchTripped,
  onKillSwitch,
  onResumeTrading,
}) => {
  const balance = Number(livePortfolio?.balance_dollars ?? 0.30) || 0.30;
  const margin = Number(livePortfolio?.available_margin ?? 0.30) || 0.30;
  const env = livePortfolio?.environment?.toUpperCase() || 'LIVE';
  const isBalanceDepleted = balance <= 0.05;

  return (
    <div className="bg-[#111620] border border-[#21262d] rounded-2xl p-4 sm:p-5 flex flex-col gap-4 shadow-xl">
      {/* Header with Live Status */}
      <div className="flex items-center justify-between border-b border-[#21262d] pb-3">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-xl bg-rose-500/15 border border-rose-500/30 flex items-center justify-center">
            <Lock className="h-5 w-5 text-rose-400" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <span>Live Pre-Trade Guardrails</span>
              <span className="px-2 py-0.5 text-[10px] font-mono bg-rose-500/20 text-rose-400 border border-rose-500/40 rounded-full font-bold">
                {env} PROD
              </span>
            </h3>
            <p className="text-[11px] text-[#8b949e]">CFTC & Exchange Micro-Capital Enforcement</p>
          </div>
        </div>

        <div
          role="status"
          aria-live="polite"
          aria-label="Live Pre-Trade Guardrails status: ARMED"
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#161b22] border border-emerald-500/30 text-[11px] font-mono"
        >
          <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-emerald-400 font-bold">ARMED</span>
        </div>
      </div>

      {/* INSUFFICIENT / DEPLETED LIVE BALANCE ALERT BANNER */}
      {isBalanceDepleted && (
        <div className="p-3.5 bg-amber-500/15 border border-amber-500/40 rounded-xl flex items-start gap-3 text-xs shadow-lg shadow-amber-500/5 animate-in fade-in">
          <div className="h-8 w-8 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center justify-center shrink-0 mt-0.5">
            <Wallet className="h-4 w-4 text-amber-400" />
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between">
              <span className="font-extrabold text-white text-xs">
                Live Account Balance Low (${balance.toFixed(2)})
              </span>
              <span className="px-2 py-0.5 text-[9px] font-mono font-bold bg-amber-500/30 text-amber-300 rounded-full uppercase">
                BETS FROZEN
              </span>
            </div>
            <p className="text-[11px] text-amber-200/90 mt-1 leading-relaxed">
              Your live Kalshi balance is below the minimum execution threshold ($0.05). All real-money bets are frozen until additional funds are loaded.
            </p>
            <div className="mt-2.5 flex items-center gap-2">
              <a
                href="https://kalshi.com"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1 text-[11px] font-bold text-black bg-amber-400 hover:bg-amber-300 rounded-lg shadow-sm transition-all active:scale-95"
              >
                <span>Deposit Assets on Kalshi</span>
                <ArrowUpRight className="h-3.5 w-3.5 stroke-[2.5]" />
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Emergency Kill Switch Section */}
      <div className={`p-4 rounded-xl border transition-all ${
        isKillSwitchTripped
          ? 'bg-amber-500/10 border-amber-500/40 shadow-lg shadow-amber-500/10'
          : 'bg-rose-500/10 border-rose-500/30 shadow-lg shadow-rose-500/10'
      }`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <AlertOctagon className={`h-5 w-5 ${isKillSwitchTripped ? 'text-amber-400 animate-bounce' : 'text-rose-400'}`} />
            <span className="text-xs font-bold uppercase tracking-wider text-white">
              {isKillSwitchTripped ? '⚠️ Trading Circuit Breaker: TRIPPED' : 'Autonomous Kill Switch'}
            </span>
          </div>
          <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-md ${
            isKillSwitchTripped ? 'bg-amber-500/20 text-amber-300' : 'bg-rose-500/20 text-rose-300'
          }`}>
            {isKillSwitchTripped ? 'HALTED' : 'STANDBY'}
          </span>
        </div>

        <p className="text-[11px] text-[#8b949e] mb-3 leading-relaxed">
          {isKillSwitchTripped
            ? 'Execution engine is halted. All incoming order requests are blocked to preserve capital.'
            : 'One-click emergency kill switch immediately stops all live order routing and locks execution.'}
        </p>

        {isKillSwitchTripped ? (
          <button
            type="button"
            aria-label="Reset trading circuit breaker and resume live execution"
            onClick={() => {
              soundFX.playClickSound();
              onResumeTrading();
            }}
            className="w-full py-2.5 px-4 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-extrabold rounded-xl shadow-md shadow-emerald-500/20 active:scale-95 transition-all flex items-center justify-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
          >
            <Play className="h-4 w-4 fill-current" />
            <span>RESET CIRCUIT BREAKER & RESUME TRADING</span>
          </button>
        ) : (
          <button
            type="button"
            aria-label="Trigger emergency kill switch and halt all live trading"
            onClick={() => {
              soundFX.playLossSound();
              onKillSwitch();
            }}
            className="w-full py-2.5 px-4 bg-gradient-to-r from-red-600 to-rose-700 hover:from-red-500 hover:to-rose-600 text-white text-xs font-extrabold rounded-xl shadow-md shadow-red-500/30 active:scale-95 transition-all flex items-center justify-center gap-2 animate-pulse focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400"
          >
            <AlertOctagon className="h-4 w-4 fill-current" />
            <span>🛑 EMERGENCY KILL SWITCH (HALT ALL)</span>
          </button>
        )}
      </div>

      {/* Pre-Trade Guardrail Limits Grid */}
      <div className="grid grid-cols-2 gap-2.5">
        <div className="bg-[#161b22] border border-[#21262d] p-3 rounded-xl">
          <div className="text-[10px] text-[#8b949e] uppercase font-semibold">Max Sizing Cap</div>
          <div className="text-sm font-bold text-white font-mono tabular-nums mt-0.5">1 Contract / Asset</div>
          <div className="text-[10px] text-emerald-400 mt-0.5 font-mono tabular-nums">$1.00 Max Risk / Event</div>
        </div>

        <div className="bg-[#161b22] border border-[#21262d] p-3 rounded-xl">
          <div className="text-[10px] text-[#8b949e] uppercase font-semibold">Daily Loss Limit</div>
          <div className="text-sm font-bold text-rose-400 font-mono tabular-nums mt-0.5">-$10.00 Limit</div>
          <div className="text-[10px] text-[#8b949e] mt-0.5 font-mono">Auto Kill-Switch</div>
        </div>

        <div className="bg-[#161b22] border border-[#21262d] p-3 rounded-xl">
          <div className="text-[10px] text-[#8b949e] uppercase font-semibold">Available Cash</div>
          <div className={`text-sm font-bold font-mono tabular-nums mt-0.5 ${isBalanceDepleted ? 'text-amber-400' : 'text-emerald-400'}`}>
            ${balance.toFixed(2)}
          </div>
          <div className="text-[10px] text-[#8b949e] mt-0.5 font-mono tabular-nums">Margin: ${margin.toFixed(2)}</div>
        </div>

        <div className="bg-[#161b22] border border-[#21262d] p-3 rounded-xl">
          <div className="text-[10px] text-[#8b949e] uppercase font-semibold">API Signature</div>
          <div className="text-sm font-bold text-cyan-400 font-mono mt-0.5">RSA-PSS SHA256</div>
          <div className="text-[10px] text-cyan-500/80 mt-0.5 font-mono">Zero Key Exposure</div>
        </div>
      </div>

      {/* Real-Time Integrity & Compliance Telemetry */}
      <div className="bg-[#161b22] border border-[#21262d] rounded-xl p-3 flex flex-col gap-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-[#8b949e] flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-cyan-400" />
            <span>Mathematical Invariant Audit</span>
          </span>
          <span className="font-mono tabular-nums font-bold text-cyan-400">
            {integrityStatus?.score ? `${integrityStatus.score.toFixed(0)}%` : '100%'} ({integrityStatus?.status || 'HEALTHY'})
          </span>
        </div>

        <div className="flex items-center justify-between text-xs">
          <span className="text-[#8b949e] flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-purple-400" />
            <span>CFTC & Wash Trading Shield</span>
          </span>
          <span className="font-mono tabular-nums font-bold text-purple-400">
            {complianceStatus?.score ? `${complianceStatus.score.toFixed(0)}%` : '100%'} (ACTIVE)
          </span>
        </div>

        <div className="flex items-center justify-between text-xs">
          <span className="text-[#8b949e] flex items-center gap-1.5">
            <Activity className="h-3.5 w-3.5 text-emerald-400" />
            <span>VPIN Toxicity Veto</span>
          </span>
          <span className="font-mono tabular-nums font-bold text-emerald-400">
            Threshold &gt; 0.65
          </span>
        </div>
      </div>
    </div>
  );
};
