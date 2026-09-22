import React from 'react';
import { BarChart2, Clock, Crosshair, Flame, Layers, Maximize2, Minimize2, MoreHorizontal, Sliders, TrendingUp } from 'lucide-react';
import { MarketState } from '../../types';
import { soundFX } from '../../utils/audioFX';

export type ChartStyle = 'candles' | 'line' | 'area';
export type DrawingTool = 'cursor' | 'crosshair' | 'trendline' | 'pitchfork' | 'fibonacci' | 'text' | 'patterns' | 'measure' | 'zoom' | 'magnet';

interface ChartControlsToolbarProps {
  market: MarketState;
  activeDrawingTool: DrawingTool;
  setActiveDrawingTool: (tool: DrawingTool) => void;
  selectedTimeframe: string;
  handleSwitchTimeframe: (tf: string) => void;
  chartStyle: ChartStyle;
  setChartStyle: (style: ChartStyle) => void;
  isIndicatorsModalOpen: boolean;
  setIsIndicatorsModalOpen: (val: boolean) => void;
  isHeatmapEnabled: boolean;
  setIsHeatmapEnabled: (val: boolean) => void;
  onToggleRightPanel?: () => void;
  isRightPanelHidden?: boolean;
}

export const ChartControlsToolbar: React.FC<ChartControlsToolbarProps> = ({
  market,
  activeDrawingTool,
  setActiveDrawingTool,
  selectedTimeframe,
  handleSwitchTimeframe,
  chartStyle,
  setChartStyle,
  isIndicatorsModalOpen,
  setIsIndicatorsModalOpen,
  isHeatmapEnabled,
  setIsHeatmapEnabled,
  onToggleRightPanel,
  isRightPanelHidden,
}) => {
  return (
          <div className="h-10 px-3 bg-[#0e131b] border-b border-[#1f2937] flex items-center justify-between shrink-0">
            {/* Left: Title & Actions */}
            <div className="flex items-center gap-3">
              <span className="text-xs font-mono font-bold uppercase tracking-wider text-white">
                Event Price Graph
              </span>
              <button
                onClick={() => soundFX.playClickSound()}
                className="text-[#64748b] hover:text-white"
                title="Graph options"
              >
                <MoreHorizontal className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Right: Chart Controls Toolbar */}
            <div className="flex items-center gap-2 text-xs font-mono">
              {/* Crosshair Tool Icon */}
              <button
                onClick={() => {
                  soundFX.playClickSound();
                  setActiveDrawingTool('crosshair');
                }}
                className={`p-1.5 rounded transition ${
                  activeDrawingTool === 'crosshair' ? 'bg-[#17202d] text-[#00c978]' : 'text-[#8c9ba5] hover:text-white'
                }`}
                title="Crosshair Tool"
              >
                <Crosshair className="w-4 h-4" />
              </button>

              {/* Timeframe Selector Dropdown */}
              <div className="flex items-center bg-[#131923] rounded border border-[#1f2937] p-0.5">
                {(['1m', '5m', '15m', '1h'] as const).map((tf) => (
                  <button
                    key={tf}
                    onClick={() => handleSwitchTimeframe(tf)}
                    className={`px-2 py-0.5 rounded text-[11px] font-bold transition ${
                      selectedTimeframe === tf
                        ? 'bg-[#00c978] text-black shadow'
                        : 'text-[#8c9ba5] hover:text-white'
                    }`}
                  >
                    {tf}
                  </button>
                ))}
              </div>

              {/* Chart Style Switcher (TradingView style: Candles / Line / Area) */}
              <div className="flex items-center bg-[#131923] rounded border border-[#1f2937] p-0.5">
                <button
                  onClick={() => {
                    soundFX.playClickSound();
                    setChartStyle('candles');
                  }}
                  className={`px-2 py-0.5 rounded text-[11px] font-bold flex items-center gap-1 transition ${
                    chartStyle === 'candles'
                      ? 'bg-[#00c978] text-black shadow'
                      : 'text-[#8c9ba5] hover:text-white'
                  }`}
                  title="Candlestick Chart"
                >
                  <BarChart2 className="w-3 h-3" />
                  <span>Candles</span>
                </button>
                <button
                  onClick={() => {
                    soundFX.playClickSound();
                    setChartStyle('line');
                  }}
                  className={`px-2 py-0.5 rounded text-[11px] font-bold flex items-center gap-1 transition ${
                    chartStyle === 'line'
                      ? 'bg-[#00c978] text-black shadow'
                      : 'text-[#8c9ba5] hover:text-white'
                  }`}
                  title="Smooth Line Chart"
                >
                  <TrendingUp className="w-3 h-3" />
                  <span>Line</span>
                </button>
                <button
                  onClick={() => {
                    soundFX.playClickSound();
                    setChartStyle('area');
                  }}
                  className={`px-2 py-0.5 rounded text-[11px] font-bold flex items-center gap-1 transition ${
                    chartStyle === 'area'
                      ? 'bg-[#00c978] text-black shadow'
                      : 'text-[#8c9ba5] hover:text-white'
                  }`}
                  title="Gradient Area Chart"
                >
                  <Layers className="w-3 h-3" />
                  <span>Area</span>
                </button>
              </div>

              {/* Time Left Countdown Pill */}
              <div className="flex items-center gap-1 px-2.5 py-0.5 rounded bg-[#17202d] border border-[#2d3d52] text-[11px] text-amber-300 font-bold">
                <Clock className="w-3 h-3 text-amber-400" />
                <span>Time left: {market?.expiry_countdown_str || '02:15'}</span>
              </div>

              {/* Indicators Modal Trigger */}
              <button
                onClick={() => {
                  soundFX.playClickSound();
                  setIsIndicatorsModalOpen(!isIndicatorsModalOpen);
                }}
                className="flex items-center gap-1 px-2 py-1 rounded bg-[#131923] text-slate-300 hover:text-white border border-[#1f2937] transition text-[11px]"
                title="Technical Indicators"
              >
                <Sliders className="w-3.5 h-3.5 text-[#38bdf8]" />
                <span>Indicators</span>
              </button>

              {/* Liquidity Heatmap Toggle Button */}
              <button
                onClick={() => {
                  soundFX.playClickSound();
                  setIsHeatmapEnabled(!isHeatmapEnabled);
                }}
                className={`flex items-center gap-1 px-2 py-1 rounded border transition text-[11px] font-bold ${
                  isHeatmapEnabled
                    ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm'
                    : 'bg-[#131923] text-[#8c9ba5] border-[#1f2937] hover:text-white'
                }`}
                title="Toggle DOM Liquidity Heatmap Cloud"
              >
                <Flame className={`w-3.5 h-3.5 ${isHeatmapEnabled ? 'text-amber-400' : 'text-[#8c9ba5]'}`} />
                <span>Heatmap</span>
              </button>

              {/* Maximize CLOB Terminal Toggle (Hide / Unhide Docked Baby Bot Rail) */}
              {onToggleRightPanel && (
                <button
                  onClick={() => {
                    soundFX.playClickSound();
                    onToggleRightPanel();
                  }}
                  className={`flex items-center gap-1 px-2 py-1 rounded border transition text-[11px] font-bold ${
                    isRightPanelHidden
                      ? 'bg-[#00c978] text-black border-[#00c978] shadow-sm'
                      : 'bg-[#131923] text-slate-300 hover:text-white border-[#1f2937]'
                  }`}
                  title={isRightPanelHidden ? 'Restore Docked Baby Bot Rail' : 'Maximize CLOB Terminal (Hide Bot Rail)'}
                >
                  {isRightPanelHidden ? (
                    <>
                      <Minimize2 className="w-3.5 h-3.5" />
                      <span>Maximized</span>
                    </>
                  ) : (
                    <>
                      <Maximize2 className="w-3.5 h-3.5" />
                      <span>Maximize</span>
                    </>
                  )}
                </button>
              )}

              {/* Fullscreen Toggle */}
              <button
                onClick={() => soundFX.playClickSound()}
                className="p-1.5 rounded text-[#8c9ba5] hover:text-white hover:bg-[#17202d] transition"
                title="Toggle Fullscreen"
              >
                <Maximize2 className="w-4 h-4" />
              </button>
            </div>
          </div>
  );
};
