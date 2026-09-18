import React from 'react';
import { Activity, Check, Coins, Cpu, Globe, Layers, Shield, X } from 'lucide-react';
import { PARAM_DOCS } from './OnnxConstants';
import { NeuralEngineSpec } from '../../types';

interface OnnxModalsProps {
  activeInfo: string | null;
  onCloseInfo: () => void;
  selectedEngine: NeuralEngineSpec | null;
  onCloseEngine: () => void;
}

export const OnnxModals: React.FC<OnnxModalsProps> = ({
  activeInfo,
  onCloseInfo,
  selectedEngine,
  onCloseEngine,
}) => {
  return (
    <>
      {/* Deep (i) Parameter Inspection Modal */}
      {activeInfo && PARAM_DOCS[activeInfo] && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="param-doc-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in"
          onClick={onCloseInfo}
        >
          <div
            className="bg-[#0f131d] border border-[#28324a] rounded-xl max-w-lg w-full p-5 space-y-3.5 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-[#262d35] pb-2.5">
              <div className="flex items-center gap-2">
                <span id="param-doc-title" className="font-bold text-white text-sm">{PARAM_DOCS[activeInfo].title}</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                  {PARAM_DOCS[activeInfo].symbol}
                </span>
              </div>
              <button
                type="button"
                aria-label="Close parameter guidance modal"
                onClick={onCloseInfo}
                className="text-gray-400 hover:text-white p-1 rounded-lg hover:bg-white/5 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-1">
              <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Quantitative Mathematical Formulation</div>
              <div className="text-xs font-mono text-cyan-300 bg-[#090c14] p-2.5 rounded-lg border border-white/5 whitespace-pre-line">
                {PARAM_DOCS[activeInfo].formula}
              </div>
            </div>

            <div className="space-y-1">
              <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Institutional Mechanism &amp; Role</div>
              <div className="text-xs text-slate-300 bg-[#090c14] p-2.5 rounded-lg border border-white/5 leading-relaxed">
                {PARAM_DOCS[activeInfo].mechanism}
              </div>
            </div>

            <div className="space-y-1">
              <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Recommended Institutional Calibration</div>
              <div className="text-xs text-emerald-300 bg-[#090c14] p-2.5 rounded-lg border border-white/5 font-mono">
                {PARAM_DOCS[activeInfo].recommendation}
              </div>
            </div>

            <div className="text-xs text-rose-300 bg-rose-500/10 p-2.5 rounded-lg border border-rose-500/30 leading-relaxed">
              ⚠️ <strong>RISK WARNING:</strong> {PARAM_DOCS[activeInfo].warning}
            </div>

            <div className="flex justify-end pt-1">
              <button
                type="button"
                aria-label="Close guidance details"
                onClick={onCloseInfo}
                className="px-4 py-1.5 bg-[#1e293b] hover:bg-[#334155] text-white text-xs font-bold rounded-lg border border-[#334155] transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Deep Neural Engine Specification Modal */}
      {selectedEngine && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="engine-spec-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in"
          onClick={onCloseEngine}
        >
          <div
            className="bg-[#0f131d] border border-[#28324a] rounded-2xl max-w-2xl w-full p-6 space-y-4 shadow-2xl overflow-y-auto max-h-[90vh]"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-[#262d35] pb-3">
              <div className="flex items-center gap-3">
                <div className={`h-9 w-9 rounded-xl flex items-center justify-center shrink-0 border ${
                  selectedEngine.id === 'brain_3_gold_spacetime'
                    ? 'bg-amber-500/20 border-amber-500/40'
                    : 'bg-cyan-500/20 border-cyan-500/40'
                }`}>
                  {selectedEngine.id === 'brain_3_gold_spacetime' ? (
                    <Coins className="w-5 h-5 text-amber-400" />
                  ) : (
                    <Cpu className="w-5 h-5 text-cyan-400" />
                  )}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 id="engine-spec-title" className="font-bold text-white text-sm">{selectedEngine.name}</h3>
                    <span className={`px-2 py-0.5 text-[9px] font-mono font-bold rounded-full border ${
                      selectedEngine.status === 'ACTIVE_LANE_1'
                        ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                        : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                    }`}>
                      {selectedEngine.status === 'ACTIVE_LANE_1' ? 'LANE 1 LIVE' : 'STANDALONE LAB ENGINE'}
                    </span>
                  </div>
                  <div className="text-xs font-mono text-gray-400 mt-0.5">
                    Model Binary: <span className="text-cyan-300">{selectedEngine.filename}</span> • {selectedEngine.version}
                  </div>
                </div>
              </div>
              <button
                type="button"
                aria-label="Close engine specification modal"
                onClick={onCloseEngine}
                className="text-gray-400 hover:text-white p-1.5 rounded-lg hover:bg-white/5 transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Top Specs Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs font-mono">
              <div className="bg-[#090c14] p-2.5 rounded-xl border border-white/5">
                <span className="text-gray-500 text-[9px] block uppercase">Vector Dim</span>
                <span className="font-bold text-cyan-300 text-sm">{selectedEngine.dimension}-D</span>
              </div>
              <div className="bg-[#090c14] p-2.5 rounded-xl border border-white/5">
                <span className="text-gray-500 text-[9px] block uppercase">Inference Speed</span>
                <span className="font-bold text-emerald-300 text-sm">&lt; {selectedEngine.latency_budget_ms}ms</span>
              </div>
              <div className="bg-[#090c14] p-2.5 rounded-xl border border-white/5">
                <span className="text-gray-500 text-[9px] block uppercase">Input Shape</span>
                <span className="font-bold text-purple-300 text-[11px] truncate block">{selectedEngine.input_shape}</span>
              </div>
              <div className="bg-[#090c14] p-2.5 rounded-xl border border-white/5">
                <span className="text-gray-500 text-[9px] block uppercase">Output Shape</span>
                <span className="font-bold text-amber-300 text-[11px] truncate block">{selectedEngine.output_shape}</span>
              </div>
            </div>

            {/* Neural Graph Architecture */}
            <div className="space-y-1.5">
              <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-cyan-400" />
                <span>Neural Architecture Topology</span>
              </div>
              <div className="bg-[#090c14] p-3 rounded-xl border border-white/5 font-mono text-xs text-slate-200">
                {selectedEngine.architecture}
              </div>
            </div>

            {/* Mathematical & Physical Feature Breakdown */}
            {selectedEngine.physics_features && (
              <div className="space-y-1.5">
                <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Feature Formulation &amp; Physics Dimensions</span>
                </div>
                <div className="bg-[#090c14] p-3 rounded-xl border border-white/5 space-y-1.5">
                  {selectedEngine.physics_features.map((feat, idx) => (
                    <div key={idx} className="flex items-start gap-2 text-xs font-mono text-slate-300">
                      <span className="text-cyan-400 font-bold shrink-0">#{idx + 1}</span>
                      <span>{feat}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tri-Venue Adapter Protocol */}
            {selectedEngine.adapters && (
              <div className="space-y-1.5">
                <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Globe className="w-3.5 h-3.5 text-blue-400" />
                  <span>Tri-Venue Adapter Protocol &amp; Settlement Routing</span>
                </div>
                <div className="bg-[#090c14] p-3 rounded-xl border border-white/5 space-y-2">
                  {selectedEngine.adapters.map((adapter, idx) => (
                    <div key={idx} className="flex items-center justify-between text-xs font-mono bg-[#12161f] p-2 rounded-lg border border-white/5">
                      <div className="flex items-center gap-2">
                        <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                        <span className="text-white">{adapter}</span>
                      </div>
                      <span className="text-[9px] text-emerald-300 bg-emerald-500/15 px-2 py-0.5 rounded border border-emerald-500/30">
                        VERIFIED
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Invariant Guarantees Strip */}
            <div className="p-3 rounded-xl bg-cyan-950/20 border border-cyan-500/30 text-xs text-cyan-200 space-y-1">
              <div className="font-bold flex items-center gap-1.5 uppercase text-[10px]">
                <Shield className="w-3.5 h-3.5 text-cyan-400" />
                <span>Microstructure Safety &amp; Decoupled Invariant</span>
              </div>
              <p className="text-[11px] text-slate-300">
                This ONNX engine operates strictly with <strong>zero IEEE-754 floating-point drift</strong> (Python <code>Decimal</code> throughout settlement logic) and enforces micro-bankroll armor (1 contract hard-cap).
              </p>
            </div>

            {/* Close Action */}
            <div className="flex justify-end pt-1">
              <button
                type="button"
                aria-label="Close engine specification details"
                onClick={onCloseEngine}
                className="px-5 py-2 bg-[#1e293b] hover:bg-[#334155] text-white text-xs font-bold rounded-xl border border-[#334155] transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400"
              >
                Close Engine Specs
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
