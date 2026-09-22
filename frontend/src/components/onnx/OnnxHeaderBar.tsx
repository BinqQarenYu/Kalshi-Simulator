import React from 'react';
import { Activity, Clock, Layers, RefreshCw, Save, Shield, Zap } from 'lucide-react';
import { StrategyParameters } from './OnnxConstants';

interface OnnxHeaderBarProps {
  params: StrategyParameters;
  saving: boolean;
  onRefresh: () => void;
  onSave: () => void;
}

export const OnnxHeaderBar: React.FC<OnnxHeaderBarProps> = ({
  params,
  saving,
  onRefresh,
  onSave,
}) => {
  return (
    <>
      {/* Top Header & Save Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#262d35] pb-4">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center shrink-0">
            <Layers className="w-4 h-4 text-cyan-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                The ONNX Strategy — Institutional Cockpit Dials
              </h2>
              <span className="px-1.5 py-0.2 text-[9px] font-mono bg-cyan-500/25 text-cyan-300 border border-cyan-500/40 rounded-full font-bold">
                Dual-Brain Live Engine
              </span>
            </div>
            <p className="text-[11px] text-[#8c9ba5] mt-0.5">
              Fine-tune high-frequency contradiction arbitrage, lead-lag synchronization, and gamma cutoff shields.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-auto">
          <button
            type="button"
            aria-label="Reload parameters from live engine"
            onClick={onRefresh}
            title="Reload from Live Engine"
            className="p-1.5 rounded-lg border border-[#262d35] bg-[#161b22] text-gray-400 hover:text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            aria-label="Apply and save strategy dials to live engine"
            onClick={onSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-bold text-[#12161a] bg-[#00bda5] hover:bg-[#2dd4bf] rounded-lg transition-all shadow-md active:scale-95 disabled:opacity-50 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
          >
            {saving ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            <span>{saving ? 'Syncing...' : 'Apply & Save Dials'}</span>
          </button>
        </div>
      </div>

      {/* Live Telemetry Status Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 bg-[#0a0c10] border border-[#21262d] rounded-lg p-2.5">
        <div className="flex items-center gap-2">
          <Clock className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
          <div>
            <div className="text-[9px] text-[#8c9ba5] uppercase">Cross-Brain Skew</div>
            <div className={`font-bold font-mono ${params.cross_brain_skew_ms! > params.max_temporal_skew_ms! ? 'text-rose-400' : 'text-cyan-300'}`}>
              {params.cross_brain_skew_ms?.toFixed(1)}ms {params.is_temporally_synced ? '✅' : '⚠️'}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Activity className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <div>
            <div className="text-[9px] text-[#8c9ba5] uppercase">Realized 1M Vol (σ)</div>
            <div className="font-bold font-mono text-emerald-300">
              ${params.current_atr?.toFixed(2)}/min
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Shield className="w-3.5 h-3.5 text-amber-400 shrink-0" />
          <div>
            <div className="text-[9px] text-[#8c9ba5] uppercase">Markov Macro</div>
            <div className="font-bold font-mono text-amber-300">
              {params.hmm_regime || 'STABLE_RANGE'}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Zap className="w-3.5 h-3.5 text-purple-400 shrink-0" />
          <div>
            <div className="text-[9px] text-[#8c9ba5] uppercase">Sizing Armor</div>
            <div className="font-bold font-mono text-purple-300">
              STRICT 1 CT ($0-$75)
            </div>
          </div>
        </div>
      </div>
    </>
  );
};
