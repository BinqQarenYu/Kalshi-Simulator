import React from 'react';
import { AISignals } from '../types';
import { Cpu, ShieldCheck, ShieldAlert, TrendingUp, DollarSign, Activity } from 'lucide-react';

interface AIMicrostructureCardProps {
  signals: AISignals;
}

export const AIMicrostructureCard: React.FC<AIMicrostructureCardProps> = ({ signals }) => {
  const pUpPct = (signals.p_up * 100).toFixed(1);
  const pDnPct = (signals.p_down * 100).toFixed(1);
  const pWaitPct = (signals.p_wait * 100).toFixed(1);

  return (
    <div className="bg-[#111620] border border-[#21262d] rounded-2xl p-4 sm:p-5 flex flex-col gap-4 shadow-xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#21262d] pb-2.5">
        <div className="flex items-center gap-2">
          <Cpu className="h-4 w-4 text-[#3b82f6]" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-white">
            Stage 1 & 2: ONNX AI Engine
          </h3>
        </div>
        <div className="flex items-center gap-1 text-[11px] font-mono text-gray-400">
          <span>nano_microscope_overhauled.onnx</span>
        </div>
      </div>

      {/* Stage 1: Directional Probabilities */}
      <div className="flex flex-col gap-2">
        <div className="flex justify-between items-center text-xs">
          <span className="text-[#8b949e] font-semibold">Directional Inference</span>
          <span className="text-[11px] font-mono text-gray-400">28-D Microstructure Tensor</span>
        </div>

        {/* Probability Bar */}
        <div className="h-3 w-full bg-[#161b22] rounded-full overflow-hidden flex border border-[#30363d]">
          <div
            style={{ width: `${pUpPct}%` }}
            className="bg-[#00d084] h-full transition-all duration-500"
            title={`P(UP): ${pUpPct}%`}
          />
          <div
            style={{ width: `${pWaitPct}%` }}
            className="bg-gray-500 h-full transition-all duration-500"
            title={`P(WAIT): ${pWaitPct}%`}
          />
          <div
            style={{ width: `${pDnPct}%` }}
            className="bg-[#ff4d4d] h-full transition-all duration-500"
            title={`P(DOWN): ${pDnPct}%`}
          />
        </div>

        <div className="grid grid-cols-3 text-center text-xs font-mono pt-1">
          <div className="text-[#00d084] font-bold">
            P(UP): {pUpPct}%
          </div>
          <div className="text-gray-400 font-medium">
            P(WAIT): {pWaitPct}%
          </div>
          <div className="text-[#ff4d4d] font-bold">
            P(DN): {pDnPct}%
          </div>
        </div>
      </div>

      {/* Stage 2: Mathematical EV & Kelly Optimizer */}
      <div className="grid grid-cols-2 gap-2.5 pt-1 text-xs">
        {/* Expected Value YES */}
        <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-2.5 flex flex-col gap-1">
          <div className="text-[11px] text-[#8b949e] flex items-center gap-1 font-semibold">
            <DollarSign className="h-3 w-3 text-[#00d084]" />
            <span>E[YES] Value</span>
          </div>
          <div className={`font-mono text-sm font-bold ${signals.ev_yes >= 0.02 ? 'text-[#00d084]' : 'text-gray-300'}`}>
            {signals.ev_yes >= 0 ? '+' : ''}${(signals.ev_yes * 100).toFixed(1)}¢
          </div>
          <div className="text-[10px] text-[#8b949e]">
            Kelly f*: {(signals.kelly_f_yes * 100).toFixed(1)}%
          </div>
        </div>

        {/* Expected Value NO */}
        <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-2.5 flex flex-col gap-1">
          <div className="text-[11px] text-[#8b949e] flex items-center gap-1 font-semibold">
            <DollarSign className="h-3 w-3 text-[#ff4d4d]" />
            <span>E[NO] Value</span>
          </div>
          <div className={`font-mono text-sm font-bold ${signals.ev_no >= 0.02 ? 'text-[#ff4d4d]' : 'text-gray-300'}`}>
            {signals.ev_no >= 0 ? '+' : ''}${(signals.ev_no * 100).toFixed(1)}¢
          </div>
          <div className="text-[10px] text-[#8b949e]">
            Kelly f*: {(signals.kelly_f_no * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      {/* VPIN Toxicity Guardrail */}
      <div className="flex items-center justify-between bg-[#161b22] border border-[#30363d] rounded-xl p-3 text-xs">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-[#f59e0b]" />
          <div>
            <div className="font-semibold text-white">VPIN Toxicity Index</div>
            <div className="text-[10px] text-[#8b949e]">Volume-Synchronized Imbalance</div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-mono font-bold text-white text-sm">
            {signals.vpin.toFixed(2)}
          </span>
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-bold text-[10px] ${
            signals.vpin_is_safe
              ? 'bg-[#00d084]/15 text-[#00d084] border border-[#00d084]/30'
              : 'bg-[#ff4d4d]/15 text-[#ff4d4d] border border-[#ff4d4d]/30'
          }`}>
            {signals.vpin_is_safe ? (
              <>
                <ShieldCheck className="h-3 w-3" />
                SAFE
              </>
            ) : (
              <>
                <ShieldAlert className="h-3 w-3" />
                VETO
              </>
            )}
          </span>
        </div>
      </div>

      {/* AI Decision Rationale */}
      <div className="p-2.5 rounded-xl bg-[#161b22] border border-[#30363d] text-xs">
        <div className="text-[10px] font-bold uppercase tracking-wider text-[#8b949e] mb-1">
          Quantitative Alpha Rationale
        </div>
        <p className="text-gray-300 font-medium leading-relaxed">
          {signals.rationale}
        </p>
      </div>
    </div>
  );
};
