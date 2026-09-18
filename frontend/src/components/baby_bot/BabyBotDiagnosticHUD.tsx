/**
 * @file BabyBotDiagnosticHUD.tsx
 * @description The "Why No Trade?" Pre-Flight Diagnostic HUD for BabyBotConsole.
 * Evaluates continuous microstructure guardian gates:
 * 1. Dynamic Moat Gate
 * 2. VPIN Safety Gate
 * 3. Cycle Lock Gate
 * 4. Edge / EV Gate
 */

import React from 'react';
import { ShieldCheck } from 'lucide-react';
import { PreflightGates, AISignals } from '../../types';

interface BabyBotDiagnosticHUDProps {
  preflightGates?: PreflightGates;
  diffVal: number;
  vpin: number;
  aiSignals?: AISignals;
}

export const BabyBotDiagnosticHUD: React.FC<BabyBotDiagnosticHUDProps> = ({
  preflightGates,
  diffVal,
  vpin,
  aiSignals,
}) => {
  const isMoatPass = (preflightGates?.moat_gate?.status ?? (Math.abs(diffVal) >= 40.25 ? 'PASS' : 'VETO')) === 'PASS';
  const isVpinPass = (preflightGates?.vpin_gate?.status ?? (vpin < 0.60 ? 'PASS' : 'VETO')) === 'PASS';
  const isCyclePass = (preflightGates?.cycle_lock_gate?.status ?? 'READY') === 'READY';
  const isEdgePass = (preflightGates?.edge_gate?.status ?? (aiSignals?.recommended_side !== 'wait' ? 'PASS' : 'WAIT')) === 'PASS';

  const hasVeto = (
    preflightGates?.moat_gate?.status === 'VETO' ||
    preflightGates?.vpin_gate?.status === 'VETO' ||
    preflightGates?.cycle_lock_gate?.status === 'LOCKED'
  );

  return (
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
            isMoatPass
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-amber-500/15 border-amber-500/40 text-amber-300 ring-1 ring-amber-500/30'
          }`}
          title={preflightGates?.moat_gate?.reason || `Moat: |Diff| $${Math.abs(diffVal).toFixed(2)} vs $40.25 Floor`}
        >
          <div className="text-[8px] text-gray-400 uppercase font-bold">Dynamic Moat</div>
          <div className="font-bold text-[10px] mt-0.5">
            {preflightGates?.moat_gate?.status ?? (Math.abs(diffVal) >= 40.25 ? 'PASS' : 'VETO')}
          </div>
        </div>

        {/* Gate 2: VPIN Safety */}
        <div
          className={`p-1.5 rounded border text-center transition-all ${
            isVpinPass
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-rose-500/15 border-rose-500/40 text-rose-300 ring-1 ring-rose-500/30'
          }`}
          title={preflightGates?.vpin_gate?.reason || `VPIN: ${vpin.toFixed(2)} vs 0.60 Threshold`}
        >
          <div className="text-[8px] text-gray-400 uppercase font-bold">VPIN Safety</div>
          <div className="font-bold text-[10px] mt-0.5">
            {preflightGates?.vpin_gate?.status ?? (vpin < 0.60 ? 'PASS' : 'VETO')}
          </div>
        </div>

        {/* Gate 3: Cycle Lock */}
        <div
          className={`p-1.5 rounded border text-center transition-all ${
            isCyclePass
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-rose-500/15 border-rose-500/40 text-rose-300'
          }`}
          title={preflightGates?.cycle_lock_gate?.reason || '1 trade per 15M cycle protection'}
        >
          <div className="text-[8px] text-gray-400 uppercase font-bold">Cycle Lock</div>
          <div className="font-bold text-[10px] mt-0.5">
            {preflightGates?.cycle_lock_gate?.status ?? 'READY'}
          </div>
        </div>

        {/* Gate 4: Edge / EV */}
        <div
          className={`p-1.5 rounded border text-center transition-all ${
            isEdgePass
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-slate-800/80 border-slate-700 text-slate-400'
          }`}
          title={preflightGates?.edge_gate?.reason || 'Waiting for statistical edge > 5%'}
        >
          <div className="text-[8px] text-gray-400 uppercase font-bold">Edge / EV</div>
          <div className="font-bold text-[10px] mt-0.5">
            {preflightGates?.edge_gate?.status ?? (aiSignals?.recommended_side !== 'wait' ? 'PASS' : 'WAIT')}
          </div>
        </div>
      </div>

      {/* Dynamic Veto Explanation Bar */}
      {hasVeto && (
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
  );
};
