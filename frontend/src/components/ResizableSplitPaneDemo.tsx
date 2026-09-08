/**
 * @file ResizableSplitPaneDemo.tsx
 * @description Interactive showcase demonstration of the 3-column ResizableSplitPane component.
 * Demonstrates:
 * - Dynamic percentage resizing with pure mouse hooks.
 * - Min-width constraints (150px / 12% min).
 * - Tactile draggable dividers with hover & active glowing teal states.
 * - Live size telemetry pills & quick layout preset buttons.
 */

import React, { useState } from 'react';
import { ResizableSplitPane } from './ResizableSplitPane';
import {
  Layout,
  Maximize2,
  RotateCcw,
  Sliders,
  Cpu,
  BarChart2,
  Layers,
  Activity,
  ShieldAlert,
} from 'lucide-react';

export const ResizableSplitPaneDemo: React.FC = () => {
  const [panelSizes, setPanelSizes] = useState<[number, number, number]>([20, 55, 25]);

  return (
    <div className="w-full h-screen flex flex-col bg-[#0c0f12] text-white font-sans overflow-hidden">
      {/* Top Demo Toolbar */}
      <header className="h-12 px-4 bg-[#12161a] border-b border-[#262d35] flex items-center justify-between shrink-0 select-none z-30">
        <div className="flex items-center gap-2.5">
          <div className="w-3 h-3 rounded-full bg-[#00bda5] shadow-sm shadow-[#00bda5]/60 animate-pulse" />
          <span className="font-extrabold text-sm tracking-tight text-white flex items-center gap-1.5">
            <span>3-Column Split Pane Engine</span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#00bda5]/15 text-[#2dd4bf] border border-[#00bda5]/30">
              Interactive Component
            </span>
          </span>
        </div>

        {/* Live Size Telemetry & Presets */}
        <div className="flex items-center gap-3 text-xs font-mono">
          <span className="text-[#8c9ba5] hidden md:inline">Current Widths:</span>
          <span className="px-2 py-0.5 rounded bg-[#07080c] border border-[#262d35] text-white font-bold">
            {panelSizes[0].toFixed(1)}% │ {panelSizes[1].toFixed(1)}% │ {panelSizes[2].toFixed(1)}%
          </span>

          <div className="h-4 w-px bg-[#262d35]" />

          {/* Quick Preset Buttons */}
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setPanelSizes([20, 55, 25])}
              className="px-2 py-1 rounded bg-[#171c22] hover:bg-[#222933] border border-[#262d35] text-[11px] text-[#8c9ba5] hover:text-white transition"
              title="Standard Cockpit [20% | 55% | 25%]"
            >
              Default
            </button>
            <button
              onClick={() => setPanelSizes([15, 70, 15])}
              className="px-2 py-1 rounded bg-[#171c22] hover:bg-[#222933] border border-[#262d35] text-[11px] text-[#8c9ba5] hover:text-white transition"
              title="Wide Workstation [15% | 70% | 15%]"
            >
              Wide Center
            </button>
            <button
              onClick={() => setPanelSizes([30, 40, 30])}
              className="px-2 py-1 rounded bg-[#171c22] hover:bg-[#222933] border border-[#262d35] text-[11px] text-[#8c9ba5] hover:text-white transition"
              title="Balanced Tri-Split [30% | 40% | 30%]"
            >
              Tri-Balanced
            </button>
          </div>
        </div>
      </header>

      {/* Main Resizable Split Pane Container */}
      <div className="flex-1 w-full h-[calc(100vh-48px)] overflow-hidden">
        <ResizableSplitPane
          defaultSizes={panelSizes}
          minPercentageSizes={[12, 25, 15]}
          minPixelSizes={[160, 280, 200]}
          storageKey="kalshi_demo_split_pane_sizes"
          onResize={(newSizes) => setPanelSizes(newSizes)}
          className="bg-[#090b0e]"
          leftPanel={
            <div className="w-full h-full p-4 bg-[#12161a] flex flex-col justify-between overflow-y-auto">
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#8c9ba5]">
                  <Layout className="w-4 h-4 text-[#00bda5]" />
                  <span>Panel 1: Navigation</span>
                </div>
                <p className="text-xs text-[#8c9ba5] leading-relaxed">
                  Left panel constrained with <b>min-width: 160px</b> / <b>12%</b>. Try dragging the divider to the left or right!
                </p>
                <div className="space-y-1.5 font-mono text-xs">
                  {['BTC-15M Sniper', 'ETH-15M Flow', 'SOL-5M Sprint', 'DOGE-15M Trend'].map((item, idx) => (
                    <div
                      key={idx}
                      className="p-2 rounded bg-[#171c22] border border-[#262d35] hover:border-[#00bda5]/50 cursor-pointer flex items-center justify-between text-slate-200"
                    >
                      <span>{item}</span>
                      <span className="text-[10px] text-[#00bda5] font-bold">L1</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="p-3 rounded bg-[#07080c] border border-[#262d35] text-[11px] font-mono text-[#8c9ba5]">
                <span>Width: </span>
                <span className="text-white font-bold">{panelSizes[0].toFixed(1)}%</span>
              </div>
            </div>
          }
          centerPanel={
            <div className="w-full h-full p-6 bg-[#0c0f12] flex flex-col justify-between overflow-y-auto">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-white">
                    <BarChart2 className="w-4 h-4 text-[#00bda5]" />
                    <span>Panel 2: Central Workstation</span>
                  </div>
                  <span className="text-xs font-mono text-[#34d399] font-bold">
                    Flex Active · Min 280px
                  </span>
                </div>
                <div className="p-4 rounded-xl bg-[#12161a] border border-[#262d35] space-y-3">
                  <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                    <Activity className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Dynamic Resizing Microstructure</span>
                  </h3>
                  <p className="text-xs text-[#8c9ba5] leading-relaxed font-mono">
                    This central pane smoothly adjusts its flex-basis in real-time as either Divider 1 or Divider 2 is dragged.
                    Total panel percentages strictly conserve $s_0 + s_1 + s_2 = 100\%$ with zero sub-pixel drifting.
                  </p>
                  <div className="grid grid-cols-3 gap-2 pt-2 text-center font-mono text-xs">
                    <div className="p-2 rounded bg-[#07080c] border border-[#262d35]">
                      <div className="text-[10px] text-[#8c9ba5]">GUTTER 1</div>
                      <div className="font-bold text-[#00bda5] mt-0.5">Col-Resize</div>
                    </div>
                    <div className="p-2 rounded bg-[#07080c] border border-[#262d35]">
                      <div className="text-[10px] text-[#8c9ba5]">RESET ACTION</div>
                      <div className="font-bold text-white mt-0.5">Double Click</div>
                    </div>
                    <div className="p-2 rounded bg-[#07080c] border border-[#262d35]">
                      <div className="text-[10px] text-[#8c9ba5]">PERSISTENCE</div>
                      <div className="font-bold text-[#34d399] mt-0.5">localStorage</div>
                    </div>
                  </div>
                </div>
              </div>
              <div className="p-3 rounded bg-[#12161a] border border-[#262d35] flex items-center justify-between text-xs font-mono text-[#8c9ba5]">
                <span>Center Workstation Width:</span>
                <span className="text-[#00bda5] font-bold text-sm">{panelSizes[1].toFixed(1)}%</span>
              </div>
            </div>
          }
          rightPanel={
            <div className="w-full h-full p-4 bg-[#12161a] flex flex-col justify-between overflow-y-auto">
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#8c9ba5]">
                  <Cpu className="w-4 h-4 text-purple-400" />
                  <span>Panel 3: Docked Cockpit</span>
                </div>
                <p className="text-xs text-[#8c9ba5] leading-relaxed">
                  Right rail constrained with <b>min-width: 200px</b> / <b>15%</b>.
                </p>
                <div className="p-3 rounded-lg bg-[#07080c] border border-purple-500/20 space-y-2 font-mono text-xs">
                  <div className="flex justify-between text-[11px]">
                    <span className="text-[#8c9ba5]">Execution Lane:</span>
                    <span className="text-purple-400 font-bold">LANE 2 (SHADOW)</span>
                  </div>
                  <div className="flex justify-between text-[11px]">
                    <span className="text-[#8c9ba5]">Target Bot:</span>
                    <span className="text-white font-bold">ONNX Macro v2</span>
                  </div>
                  <div className="flex justify-between text-[11px]">
                    <span className="text-[#8c9ba5]">Latency:</span>
                    <span className="text-emerald-400 font-bold">0.38ms (CPU)</span>
                  </div>
                </div>
              </div>
              <div className="p-3 rounded bg-[#07080c] border border-[#262d35] text-[11px] font-mono text-[#8c9ba5]">
                <span>Width: </span>
                <span className="text-white font-bold">{panelSizes[2].toFixed(1)}%</span>
              </div>
            </div>
          }
        />
      </div>
    </div>
  );
};

export default ResizableSplitPaneDemo;
