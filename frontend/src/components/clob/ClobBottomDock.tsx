import React from 'react';
import { ChevronDown, Code, RefreshCw, RotateCcw, Sliders, TrendingDown, TrendingUp, X, Zap } from 'lucide-react';
import { soundFX } from '../../utils/audioFX';

export type ChartTheme = 'institutional' | 'heatmap_high_contrast' | 'cyberpunk' | 'monochrome';

interface ClobBottomDockProps {
  chartTheme: ChartTheme;
  setChartTheme: (theme: ChartTheme | ((prev: ChartTheme) => ChartTheme)) => void;
  isPineEditorOpen: boolean;
  setIsPineEditorOpen: (val: boolean) => void;
  pineScriptCode: string;
  setPineScriptCode: (code: string) => void;
  isTradingPanelOpen: boolean;
  setIsTradingPanelOpen: (val: boolean) => void;
  orderSide: 'yes' | 'no';
  setOrderSide: (side: 'yes' | 'no') => void;
  orderLimitPrice: number;
  setOrderLimitPrice: (price: number) => void;
  handleExecuteTrade: (side: 'yes' | 'no') => void;
  orderStatusMessage: string | null;
  onResetTrading: () => void;
}

export const ClobBottomDock: React.FC<ClobBottomDockProps> = ({
  chartTheme,
  setChartTheme,
  isPineEditorOpen,
  setIsPineEditorOpen,
  pineScriptCode,
  setPineScriptCode,
  isTradingPanelOpen,
  setIsTradingPanelOpen,
  orderSide,
  setOrderSide,
  orderLimitPrice,
  setOrderLimitPrice,
  handleExecuteTrade,
  orderStatusMessage,
  onResetTrading,
}) => {
  return (
    <>
          {/* Bottom Dock Strip: Theme Selector, Pine Editor, Reset, Trading Panel */}
          <div className="h-10 px-4 bg-[#0c1017] border-t border-[#1f2937] flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2 text-xs font-mono">
              {/* Theme Dropdown */}
              <div className="relative">
                <button
                  onClick={() => {
                    soundFX.playClickSound();
                    setChartTheme((prev) =>
                      prev === 'institutional'
                        ? 'heatmap_high_contrast'
                        : prev === 'heatmap_high_contrast'
                        ? 'cyberpunk'
                        : 'institutional'
                    );
                  }}
                  className="px-2.5 py-1 rounded bg-[#131923] text-slate-300 hover:text-white border border-[#1f2937] flex items-center gap-1.5 text-[11px]"
                  title="Switch Color Theme"
                >
                  <span>Stock Theme: {chartTheme.replace(/_/g, ' ').toUpperCase()}</span>
                  <ChevronDown className="w-3 h-3 text-[#64748b]" />
                </button>
              </div>

              {/* Pine Editor Drawer Button */}
              <button
                onClick={() => {
                  soundFX.playClickSound();
                  setIsPineEditorOpen(!isPineEditorOpen);
                }}
                className={`px-2.5 py-1 rounded border transition flex items-center gap-1.5 text-[11px] ${
                  isPineEditorOpen
                    ? 'bg-[#38bdf8]/20 text-[#38bdf8] border-[#38bdf8]/40'
                    : 'bg-[#131923] text-slate-300 border-[#1f2937] hover:text-white'
                }`}
                title="Open Pine Script Strategy Editor"
              >
                <Code className="w-3.5 h-3.5 text-[#38bdf8]" />
                <span>Pine Editor</span>
              </button>

              {/* Trading Reset Button */}
              <button
                onClick={() => {
                  soundFX.playClickSound();
                  onResetTrading();
                }}
                className="px-2.5 py-1 rounded bg-[#131923] text-slate-300 hover:text-white border border-[#1f2937] flex items-center gap-1.5 text-[11px]"
                title="Reset Chart Zoom & Overlays"
              >
                <RefreshCw className="w-3.5 h-3.5 text-amber-400" />
                <span>Trading Reset</span>
              </button>
            </div>

            {/* Rapid Trading Panel Toggle Button */}
            <button
              onClick={() => {
                soundFX.playClickSound();
                setIsTradingPanelOpen(!isTradingPanelOpen);
              }}
              className={`px-3 py-1 rounded font-bold transition flex items-center gap-1.5 text-xs font-mono ${
                isTradingPanelOpen
                  ? 'bg-[#00c978] text-black shadow'
                  : 'bg-[#131923] text-[#00c978] border border-[#00c978]/40 hover:bg-[#00c978]/10'
              }`}
              title="Open Rapid Execution Ticket"
            >
              <Zap className="w-3.5 h-3.5" />
              <span>Trading Panel</span>
            </button>
          </div>

          {/* Expandable Pine Script Editor Drawer */}
          {isPineEditorOpen && (
            <div className="h-56 bg-[#0a0e14] border-t border-[#1f2937] p-3 flex flex-col font-mono text-xs z-30">
              <div className="flex items-center justify-between pb-2 border-b border-[#1f2937]">
                <div className="flex items-center gap-2">
                  <Code className="w-4 h-4 text-[#38bdf8]" />
                  <span className="font-bold text-white">Pine Script v5 Editor · Kalshi Simulator Strategy Engine</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      soundFX.playWinSound();
                      setIsPineEditorOpen(false);
                    }}
                    className="px-2.5 py-1 rounded bg-[#00c978] text-black font-bold hover:bg-emerald-400 transition"
                  >
                    Save & Compile
                  </button>
                  <button
                    onClick={() => setIsPineEditorOpen(false)}
                    className="p-1 text-[#64748b] hover:text-white"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <textarea
                value={pineScriptCode}
                onChange={(e) => setPineScriptCode(e.target.value)}
                className="flex-1 mt-2 bg-[#080b10] border border-[#1f2937] rounded p-2 text-emerald-400 font-mono text-xs resize-none focus:outline-none focus:border-[#38bdf8]"
                spellCheck={false}
              />
            </div>
          )}

          {/* Expandable Rapid Trading Panel Dock */}
          {isTradingPanelOpen && (
            <div className="bg-[#0e131b] border-t border-[#1f2937] p-4 flex flex-wrap items-center justify-between gap-4 font-mono text-xs z-30">
              {/* Order Sizing & Price Inputs */}
              <div className="flex items-center gap-4">
                <div className="space-y-1">
                  <label className="text-[10px] text-[#8c9ba5] uppercase font-bold">Side</label>
                  <div className="flex items-center gap-1 bg-[#131923] p-0.5 rounded border border-[#1f2937]">
                    <button
                      onClick={() => {
                        soundFX.playClickSound();
                        setOrderSide('yes');
                      }}
                      className={`px-3 py-1 rounded font-bold transition ${
                        orderSide === 'yes' ? 'bg-[#10b981] text-black' : 'text-[#8c9ba5] hover:text-white'
                      }`}
                    >
                      YES
                    </button>
                    <button
                      onClick={() => {
                        soundFX.playClickSound();
                        setOrderSide('no');
                      }}
                      className={`px-3 py-1 rounded font-bold transition ${
                        orderSide === 'no' ? 'bg-[#f43f5e] text-white' : 'text-[#8c9ba5] hover:text-white'
                      }`}
                    >
                      NO
                    </button>
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] text-[#8c9ba5] uppercase font-bold">Limit Price (¢)</label>
                  <input
                    type="number"
                    min={1}
                    max={99}
                    value={orderLimitPrice}
                    onChange={(e) => setOrderLimitPrice(Number(e.target.value))}
                    className="w-20 bg-[#131923] border border-[#1f2937] rounded px-2.5 py-1 text-white font-bold text-center focus:outline-none focus:border-[#00c978]"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] text-[#8c9ba5] uppercase font-bold">Quantity</label>
                  <div className="px-3 py-1 rounded bg-[#131923] border border-[#1f2937] text-amber-300 font-bold text-center">
                    1 (Hard Sizing Cap)
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-3">
                <button
                  onClick={() => handleExecuteTrade('yes')}
                  className="px-4 py-2 rounded bg-[#10b981] hover:bg-emerald-400 text-black font-extrabold shadow-lg transition flex items-center gap-1.5 cursor-pointer"
                >
                  <TrendingUp className="w-4 h-4" />
                  <span>Buy YES ({orderLimitPrice}¢)</span>
                </button>
                <button
                  onClick={() => handleExecuteTrade('no')}
                  className="px-4 py-2 rounded bg-[#f43f5e] hover:bg-rose-400 text-white font-extrabold shadow-lg transition flex items-center gap-1.5 cursor-pointer"
                >
                  <TrendingDown className="w-4 h-4" />
                  <span>Buy NO ({100 - orderLimitPrice}¢)</span>
                </button>
                <button
                  onClick={() => setIsTradingPanelOpen(false)}
                  className="p-2 text-[#64748b] hover:text-white"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Status Message */}
              {orderStatusMessage && (
                <div className="w-full text-center text-[#00c978] font-bold text-xs">
                  {orderStatusMessage}
                </div>
              )}
            </div>
          )}
    </>
  );
};
