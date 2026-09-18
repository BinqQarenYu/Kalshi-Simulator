import React from 'react';
import { CheckCircle2, Lock, ShieldAlert } from 'lucide-react';
import { ForwardValidationStatus } from './AnalyticsTypes';

interface ValidationGateSubtabProps {
  validationStatus: ForwardValidationStatus | null;
}

export const ValidationGateSubtab: React.FC<ValidationGateSubtabProps> = ({
  validationStatus,
}) => {
  return (
    <div className="p-5 flex flex-col gap-6">
      {/* Top Readiness Banner */}
      <div
        className={`p-4 rounded-xl border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 ${
          validationStatus?.real_money_readiness.is_ready_for_real_money
            ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
            : 'bg-amber-950/30 border-amber-500/30 text-amber-300'
        }`}
      >
        <div className="flex items-center gap-3">
          {validationStatus?.real_money_readiness.is_ready_for_real_money ? (
            <div className="p-2.5 bg-emerald-500/20 rounded-lg text-emerald-400 border border-emerald-500/30">
              <CheckCircle2 className="w-6 h-6" />
            </div>
          ) : (
            <div className="p-2.5 bg-amber-500/20 rounded-lg text-amber-400 border border-amber-500/30">
              <Lock className="w-6 h-6" />
            </div>
          )}
          <div>
            <h3 className="text-base font-bold text-white">
              {validationStatus?.real_money_readiness.is_ready_for_real_money
                ? 'REAL-MONEY READY: All 5 Validation Gates Passed'
                : 'FORWARD VALIDATION IN PROGRESS (Phase 2)'}
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {validationStatus?.real_money_readiness.is_ready_for_real_money
                ? 'Statistical expectancy, profit factor, drawdown, and integrity gates verified under live exchange friction.'
                : 'Executing continuous 15-minute expiration forward cycles before real capital deployment.'}
            </p>
          </div>
        </div>

        <div className="text-right flex flex-col sm:items-end">
          <span className="text-[10px] uppercase font-bold text-slate-400">100-Cycle Gate Progress</span>
          <span className="text-lg font-mono font-extrabold text-white">
            {validationStatus?.forward_testing.total_cycles_completed ?? 0} /{' '}
            {validationStatus?.forward_testing.target_cycles ?? 100} Cycles
          </span>
          <span className="text-xs font-mono text-amber-400">
            {validationStatus?.forward_testing.progress_pct ?? 0}% Complete
          </span>
        </div>
      </div>

      {/* Progress Bar */}
      <div>
        <div className="flex justify-between text-xs font-semibold text-slate-400 mb-1.5">
          <span>Forward Sample Progress</span>
          <span>{validationStatus?.forward_testing.progress_pct ?? 0}%</span>
        </div>
        <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
          <div
            className="bg-gradient-to-r from-amber-500 to-emerald-500 h-2.5 rounded-full transition-all duration-500"
            style={{ width: `${validationStatus?.forward_testing.progress_pct ?? 0}%` }}
          />
        </div>
      </div>

      {/* 5 Validation Gates Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {validationStatus?.gates &&
          Object.entries(validationStatus.gates).map(([key, gate]) => (
            <div
              key={key}
              className={`p-4 rounded-xl border ${
                gate.passed ? 'bg-emerald-950/20 border-emerald-500/30' : 'bg-slate-900 border-slate-800'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-300">{gate.name}</span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-extrabold uppercase ${
                    gate.passed ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'
                  }`}
                >
                  {gate.passed ? 'PASSED' : 'PENDING'}
                </span>
              </div>
              <div className="mt-3 flex items-baseline justify-between font-mono">
                <div>
                  <div className="text-[10px] text-slate-500 uppercase">Current Value</div>
                  <div className="text-base font-bold text-white mt-0.5">{gate.current}</div>
                </div>
                <div className="text-right">
                  <div className="text-[10px] text-slate-500 uppercase">Threshold</div>
                  <div className="text-xs font-semibold text-slate-400 mt-0.5">{gate.threshold}</div>
                </div>
              </div>
            </div>
          ))}
      </div>

      {/* Phase 3 Micro-Capital Safeguards Summary */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300 mb-3 flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-amber-400" />
          <span>Phase 3 Micro-Capital Live Safeguards</span>
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono">
          <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800">
            <div className="text-[#8b949e] text-[10px] uppercase">Single-Contract Sizing Cap</div>
            <div className="text-emerald-400 font-bold text-sm mt-0.5">
              Max {validationStatus?.real_money_readiness.micro_capital_cap.max_contracts_per_trade ?? 2} Contracts
              ($1.50 Max Risk)
            </div>
          </div>
          <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800">
            <div className="text-[#8b949e] text-[10px] uppercase">Daily Circuit Breaker</div>
            <div className="text-rose-400 font-bold text-sm mt-0.5">
              -${validationStatus?.real_money_readiness.micro_capital_cap.daily_max_loss_circuit_breaker ?? 10.0} Max
              Loss Kill
            </div>
          </div>
          <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800">
            <div className="text-[#8b949e] text-[10px] uppercase">Live Exchange Bankroll</div>
            <div className="text-blue-400 font-bold text-sm mt-0.5">
              ${(Number(validationStatus?.real_money_readiness.live_account?.balance_dollars ?? 0.3) || 0.3).toFixed(2)} Available
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
