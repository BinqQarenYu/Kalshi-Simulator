import React from 'react';
import { ChevronRight, Coins, Cpu, Globe, Layers } from 'lucide-react';
import { NEURAL_ENGINES } from './OnnxConstants';
import { NeuralEngineSpec } from '../../types';

interface NeuralFleetMatrixProps {
  onSelectEngine: (eng: NeuralEngineSpec) => void;
}

export const NeuralFleetMatrix: React.FC<NeuralFleetMatrixProps> = ({ onSelectEngine }) => {
  return (
    <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between border-b border-[#21262d] pb-2.5">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-cyan-400" />
          <span className="font-bold text-white uppercase text-[11px] tracking-wider">
            Neural Engine Fleet &amp; Multi-Brain Architecture Matrix
          </span>
        </div>
        <span className="text-[10px] text-gray-400 font-mono">
          3 ONNX Engines • 1 Standalone Multilateral Brain
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {NEURAL_ENGINES.map((eng) => {
          const isGold = eng.id === 'brain_3_gold_spacetime';
          return (
            <div
              key={eng.id}
              className={`p-3.5 rounded-xl border flex flex-col justify-between transition-all ${
                isGold
                  ? 'bg-amber-950/20 border-amber-500/40 hover:border-amber-400 shadow-sm'
                  : 'bg-[#0d1117] border-[#262d35] hover:border-cyan-500/40 shadow-sm'
              }`}
            >
              <div className="space-y-2.5">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    {isGold ? (
                      <div className="h-7 w-7 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center justify-center shrink-0">
                        <Coins className="w-4 h-4 text-amber-400" />
                      </div>
                    ) : (
                      <div className="h-7 w-7 rounded-lg bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center shrink-0">
                        <Layers className="w-4 h-4 text-cyan-400" />
                      </div>
                    )}
                    <div>
                      <div className="font-bold text-white text-xs flex items-center gap-1.5">
                        <span>{eng.name}</span>
                        {isGold && (
                          <span className="px-1.5 py-0.2 text-[8px] font-mono bg-amber-500/30 text-amber-200 border border-amber-500/50 rounded-full font-bold">
                            NEW
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] font-mono text-gray-400">{eng.filename}</div>
                    </div>
                  </div>
                  <span
                    className={`px-2 py-0.5 text-[9px] font-mono font-bold rounded-full border shrink-0 ${
                      eng.status === 'ACTIVE_LANE_1'
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                        : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                    }`}
                  >
                    {eng.status === 'ACTIVE_LANE_1' ? 'LANE 1 LIVE' : 'STANDALONE LAB'}
                  </span>
                </div>

                <p className="text-[10px] text-slate-300 leading-snug">
                  {eng.features_description}
                </p>

                <div className="grid grid-cols-2 gap-1.5 pt-0.5 text-[10px] font-mono">
                  <div className="bg-[#090c14] p-1.5 rounded border border-white/5">
                    <span className="text-gray-500 block text-[8px] uppercase">Tensor Dimension</span>
                    <span className="font-bold text-cyan-300">{eng.dimension}-D Vector</span>
                  </div>
                  <div className="bg-[#090c14] p-1.5 rounded border border-white/5">
                    <span className="text-gray-500 block text-[8px] uppercase">Latency Budget</span>
                    <span className="font-bold text-emerald-300">&lt; {eng.latency_budget_ms}ms</span>
                  </div>
                </div>

                {/* Venues & Target Assets Badges */}
                <div className="space-y-1 pt-1">
                  <div className="text-[9px] text-gray-400 font-semibold uppercase flex items-center gap-1">
                    <Globe className="w-2.5 h-2.5 text-blue-400" />
                    <span>Supported Venues &amp; Adapters</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-1">
                    {eng.supported_venues.map((venue) => (
                      <span
                        key={venue}
                        className="px-1.5 py-0.5 bg-blue-500/15 border border-blue-500/30 text-blue-300 text-[9px] font-mono rounded"
                      >
                        {venue}
                      </span>
                    ))}
                    {eng.target_assets.map((asset) => (
                      <span
                        key={asset}
                        className="px-1.5 py-0.5 bg-purple-500/15 border border-purple-500/30 text-purple-300 text-[9px] font-mono rounded"
                      >
                        {asset}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="pt-3 border-t border-white/5 mt-3 flex items-center justify-between">
                <span className="text-[9px] font-mono text-gray-500">
                  {eng.version}
                </span>
                <button
                  type="button"
                  aria-label={`Inspect specification details for ${eng.name}`}
                  onClick={() => onSelectEngine(eng)}
                  className="flex items-center gap-1 text-[10px] font-bold text-cyan-400 hover:text-cyan-300 transition-colors cursor-pointer px-2 py-1 rounded hover:bg-cyan-500/10 border border-transparent hover:border-cyan-500/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
                >
                  <span>Inspect Specs</span>
                  <ChevronRight className="w-3 h-3" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
