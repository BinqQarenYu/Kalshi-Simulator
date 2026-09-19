import React, { useState } from 'react';
import { Columns, ExternalLink, Maximize2, Minimize2, PanelRightClose, Square } from 'lucide-react';
import { BabyBotConsole } from '../BabyBotConsole';
import {
  AISignals,
  CryptoAsset,
  DualONNXTelemetry,
  HMMMacroRegimeTelemetry,
  LivePortfolioState,
  MacroDominionTelemetry,
  MarketState,
  Position,
  PreflightGates,
  SealRegistry,
} from '../../types';
import { soundFX } from '../../utils/audioFX';

interface BabyBotRightRailProps {
  isPoppedOutBabyBot: boolean;
  selectedBotId: string;
  isBabyBotConsoleMinimized: boolean;
  setIsBabyBotConsoleMinimized: (val: boolean | ((prev: boolean) => boolean)) => void;
  onTogglePopOutBabyBot: (botId?: string) => void;
  setIsBabyBotRailHidden: (val: boolean) => void;
  formatBotDisplayName: (botType?: string) => string;
  tradingMode: 'paper' | 'live';
  market: MarketState;
  aiSignals?: AISignals;
  livePortfolio?: LivePortfolioState | null;
  activePosition?: Position | null;
  timeframe: string;
  onFlattenHalt?: () => Promise<void> | void;
  onQuickTrade?: (side: 'yes' | 'no') => void;
  reportsCount: number;
  consecutiveLosses: number;
  handleSelectBot: (botId: string) => void;
  dualOnnxTelemetry?: DualONNXTelemetry;
  preflightGates?: PreflightGates;
  macroDominionTelemetry?: MacroDominionTelemetry;
  hmmMacroRegime?: HMMMacroRegimeTelemetry;
  setWorkbenchTab: (tab: 'orderbook' | 'tape' | 'positions' | 'reports') => void;
  sealOfExcellence?: SealRegistry;
  selectedTag: string | null;
  setSelectedTag: (tag: string | null) => void;
}

export const BabyBotRightRail: React.FC<BabyBotRightRailProps> = ({
  isPoppedOutBabyBot,
  selectedBotId,
  isBabyBotConsoleMinimized,
  setIsBabyBotConsoleMinimized,
  onTogglePopOutBabyBot,
  setIsBabyBotRailHidden,
  formatBotDisplayName,
  tradingMode,
  market,
  aiSignals,
  livePortfolio,
  activePosition,
  timeframe,
  onFlattenHalt,
  onQuickTrade,
  reportsCount,
  consecutiveLosses,
  handleSelectBot,
  dualOnnxTelemetry,
  preflightGates,
  macroDominionTelemetry,
  hmmMacroRegime,
  setWorkbenchTab,
  sealOfExcellence,
  selectedTag,
  setSelectedTag,
}) => {
  const [railMode, setRailMode] = useState<'single' | 'dual_split'>('single');

  return (
    <aside className="w-full h-full bg-[#12161a] flex flex-col shrink-0 overflow-y-auto select-none">
      {/* If Baby Bot is docked (not popped out into standalone window), render here */}
      {!isPoppedOutBabyBot ? (
        <div className="p-3 border-b border-[#262d35]">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#8c9ba5] flex items-center gap-1.5 truncate pr-1">
              <span>Docked:</span>
              <span className="text-[#00bda5] font-extrabold truncate">
                {selectedBotId === 'macro_onnx' || selectedBotId === 'onnx_microstructure_bot'
                  ? 'Bot 2 (ONNX Macro v2)'
                  : selectedBotId === '3_step_domination_bot'
                  ? 'Bot 1 V4 (3-Step Dom)'
                  : selectedBotId === 'macro_trend_dominion'
                  ? 'Bot 3 (Macro Trend)'
                  : selectedBotId === 'gold_onnx_bot'
                  ? 'Bot 4 (Gold ONNX)'
                  : 'Baby Bot'}
              </span>
            </span>
            <div className="flex items-center gap-1 shrink-0">
              {/* Dual Split Pane Layout Toggle */}
              <button
                onClick={() => {
                  soundFX.playClickSound();
                  setRailMode(railMode === 'single' ? 'dual_split' : 'single');
                }}
                title={railMode === 'dual_split' ? 'Single Column View' : 'Dual-Pane Split Multi-Bot View'}
                className={`p-1 rounded transition flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 border ${
                  railMode === 'dual_split'
                    ? 'bg-[#00bda5]/20 text-[#00bda5] border-[#00bda5]/50 font-bold'
                    : 'text-[#8c9ba5] hover:text-white border-[#262d35] hover:bg-[#17202d]'
                }`}
              >
                {railMode === 'dual_split' ? (
                  <>
                    <Columns className="w-3 h-3 text-[#00bda5]" />
                    <span>2-Pane</span>
                  </>
                ) : (
                  <>
                    <Square className="w-3 h-3" />
                    <span>Split</span>
                  </>
                )}
              </button>

              {/* Minimize / Expand Console button */}
              <button
                onClick={() => {
                  soundFX.playClickSound();
                  setIsBabyBotConsoleMinimized(!isBabyBotConsoleMinimized);
                }}
                title={isBabyBotConsoleMinimized ? 'Expand Baby Bot Console' : 'Minimize Baby Bot Console'}
                className="p-1 rounded text-[#8c9ba5] hover:text-white hover:bg-[#17202d] transition"
              >
                {isBabyBotConsoleMinimized ? (
                  <Maximize2 className="w-3 h-3 text-[#00bda5]" />
                ) : (
                  <Minimize2 className="w-3 h-3 text-[#8c9ba5]" />
                )}
              </button>

              {/* Pop out standalone button */}
              <button
                onClick={() => onTogglePopOutBabyBot(selectedBotId)}
                title="Pop out Baby Bot window"
                className="text-[11px] font-mono text-[#00bda5] hover:text-white flex items-center gap-1 p-1 rounded hover:bg-[#17202d]"
              >
                <ExternalLink className="w-3 h-3" />
                <span>Pop-out</span>
              </button>

              {/* Hide Rail button (Maximize Center / CLOB Terminal) */}
              <button
                onClick={() => {
                  soundFX.playClickSound();
                  setIsBabyBotRailHidden(true);
                }}
                title="Hide Right Rail (Maximize CLOB Terminal)"
                className="p-1 rounded text-[#8c9ba5] hover:text-white hover:bg-[#17202d] transition"
              >
                <PanelRightClose className="w-3.5 h-3.5 text-[#38bdf8]" />
              </button>
            </div>
          </div>

          {/* Docked Console Content: Single or Dual Split */}
          {railMode === 'dual_split' ? (
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-3 w-full">
              {/* Pane A: Active Bot Console */}
              <div className="border-r border-[#262d35] pr-2">
                <div className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#00bda5] mb-2 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#00bda5] animate-ping" />
                  <span>Pane A: Active Execution HUD</span>
                </div>
                <BabyBotConsole
                  market={market}
                  aiSignals={aiSignals}
                  livePortfolio={livePortfolio}
                  activePosition={activePosition}
                  tradingMode={tradingMode}
                  timeframe={timeframe}
                  isPoppedOut={false}
                  onTogglePopOut={() => onTogglePopOutBabyBot(selectedBotId)}
                  onFlattenHalt={onFlattenHalt}
                  onQuickTrade={onQuickTrade}
                  reportsCount={reportsCount}
                  consecutiveLosses={consecutiveLosses}
                  selectedBotId={selectedBotId}
                  onSelectBot={handleSelectBot}
                  dualOnnxTelemetry={dualOnnxTelemetry}
                  preflightGates={preflightGates}
                  macroDominionTelemetry={macroDominionTelemetry}
                  hmmMacroRegime={hmmMacroRegime}
                  onOpenReports={() => setWorkbenchTab('reports')}
                  sealOfExcellence={sealOfExcellence}
                />
              </div>

              {/* Pane B: Multi-Bot Fleet Matrix */}
              <div className="pl-1 space-y-3 font-mono text-xs">
                <div className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#38bdf8] mb-2 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#38bdf8]" />
                  <span>Pane B: Multi-Bot Fleet Matrix</span>
                </div>
                {[
                  { id: '3_step_domination_bot', name: '3-Step Dominion v3.2', lane: 'Lane 1 Live', winRate: '62.5%', pf: '1.45', status: 'SEALED_EXCELLENT', active: selectedBotId === '3_step_domination_bot' },
                  { id: 'bot1_v4_domination', name: 'Bot 1 V4 (Multi-Turnover)', lane: 'Lane 1 Live', winRate: '68.5%', pf: '1.82', status: 'SEALED_EXCELLENT', active: selectedBotId === 'bot1_v4_domination' },
                  { id: 'macro_onnx', name: 'Bot 2 (ONNX Macro v2)', lane: 'Lane 2 Incubator', winRate: '55.6%', pf: '1.12', status: 'IN_INCUBATION', active: selectedBotId === 'macro_onnx' },
                  { id: 'macro_trend_dominion', name: 'Bot 3 (Macro Trend)', lane: 'Lane 1 Live', winRate: '88.3%', pf: '4.63', status: 'SEALED_EXCELLENT', active: selectedBotId === 'macro_trend_dominion' },
                  { id: 'gold_onnx_bot', name: 'Bot 4 (Gold ONNX)', lane: 'Lane 2 Incubator', winRate: '0.0%', pf: '0.00', status: 'IN_INCUBATION', active: selectedBotId === 'gold_onnx_bot' },
                ].map((b) => (
                  <div
                    key={b.id}
                    onClick={() => handleSelectBot(b.id)}
                    className={`p-2.5 rounded-lg border transition cursor-pointer flex flex-col gap-1.5 ${
                      b.active
                        ? 'bg-[#00bda5]/10 border-[#00bda5] text-white'
                        : 'bg-[#13171c] border-[#262d35] hover:border-[#00bda5]/50 text-[#8c9ba5]'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-xs text-white">{b.name}</span>
                      <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase ${
                        b.status === 'SEALED_EXCELLENT' ? 'bg-[#00c978]/20 text-[#00c978]' : 'bg-amber-500/20 text-amber-300'
                      }`}>
                        {b.status === 'SEALED_EXCELLENT' ? 'SEALED' : 'INCUBATOR'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-[#8c9ba5]">
                      <span>{b.lane}</span>
                      <span>WR: <strong className="text-white">{b.winRate}</strong> │ PF: <strong className="text-white">{b.pf}</strong></span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : isBabyBotConsoleMinimized ? (
            <div
              onClick={() => {
                soundFX.playClickSound();
                setIsBabyBotConsoleMinimized(false);
              }}
              className="p-2.5 rounded-lg bg-[#17202d] border border-[#262d35] hover:border-[#00bda5]/50 cursor-pointer flex items-center justify-between font-mono text-xs transition shadow-sm"
              title="Click to expand full Baby Bot Console"
            >
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[#10b981] animate-ping" />
                <span className="font-bold text-white">
                  {formatBotDisplayName(selectedBotId)}
                </span>
                <span className={`text-[9px] px-1.5 py-0.2 rounded font-bold ${
                  tradingMode === 'live' ? 'bg-rose-500/20 text-rose-300' : 'bg-slate-700/40 text-slate-300'
                }`}>
                  {tradingMode.toUpperCase()}
                </span>
              </div>
              <div className="flex items-center gap-2 text-[10px] text-[#8c9ba5]">
                <span className="text-[#00c978] font-bold">1 Lot Cap</span>
                <span className="hover:text-white">▶ Expand</span>
              </div>
            </div>
          ) : (
            <BabyBotConsole
              market={market}
              aiSignals={aiSignals}
              livePortfolio={livePortfolio}
              activePosition={activePosition}
              tradingMode={tradingMode}
              timeframe={timeframe}
              isPoppedOut={false}
              onTogglePopOut={() => onTogglePopOutBabyBot(selectedBotId)}
              onFlattenHalt={onFlattenHalt}
              onQuickTrade={onQuickTrade}
              reportsCount={reportsCount}
              consecutiveLosses={consecutiveLosses}
              selectedBotId={selectedBotId}
              onSelectBot={handleSelectBot}
              dualOnnxTelemetry={dualOnnxTelemetry}
              preflightGates={preflightGates}
              macroDominionTelemetry={macroDominionTelemetry}
              hmmMacroRegime={hmmMacroRegime}
              onOpenReports={() => setWorkbenchTab('reports')}
              sealOfExcellence={sealOfExcellence}
            />
          )}
        </div>
      ) : (
        <div className="p-4 bg-[#171c22]/50 border-b border-[#262d35] text-center text-xs font-mono text-[#8c9ba5]">
          <div className="w-2 h-2 rounded-full bg-[#00bda5] animate-ping mx-auto mb-2" />
          <span>Baby Bot running in standalone pop-out window</span>
          <button
            onClick={() => onTogglePopOutBabyBot(selectedBotId)}
            className="mt-2 block mx-auto text-[11px] text-[#2dd4bf] hover:underline"
          >
            Dock back to rail
          </button>
        </div>
      )}

      {/* Trade Note Card (From HTML Proposal) */}
      <div className="p-4 border-b border-[#262d35] space-y-2">
        <h3 className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#8c9ba5]">
          Trade Note · #3318
        </h3>
        <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d] text-xs text-[#8c9ba5] leading-relaxed font-mono">
          <div className="text-white font-bold mb-1">3-STEP DOMINATION · 09:42 ET</div>
          Spot drifted $28 above strike in 90s post open. Ladder caught at YES=58¢, scaled out at T-30s during settlement at YES=71¢. Slippage +1.2¢ acceptable — book depth &ge; 14 lots. Liquidity guard served.
        </div>
      </div>

      {/* Today's Timeline (From HTML Proposal) */}
      <div className="p-4 border-b border-[#262d35] space-y-3">
        <h3 className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#8c9ba5]">
          Today's Timeline
        </h3>
        <div className="space-y-2 font-mono text-xs">
          {[
            { time: '09:42', text: '3-Step ladder WIN · BTC-15M', type: 'win' },
            { time: '09:27', text: 'Reclaim-fail NO hit · BTC-15M', type: 'win' },
            { time: '09:15', text: 'Wick Scalp LOSS · SOL-5M', type: 'loss' },
            { time: '08:45', text: 'ONNX Macro WIN · BTC-15M', type: 'win' },
            { time: '08:11', text: 'ETH Trend scratch · ETH-5M', type: 'flat' },
            { time: '07:58', text: 'Spot-drift ladder WIN · BTC-15M', type: 'win' },
            { time: '07:42', text: 'Wick Scalp LOSS · BTC-5M', type: 'loss' },
            { time: '07:30', text: 'Spot-drift ladder WIN · BTC-15M', type: 'win' },
          ].map((item, idx) => (
            <div key={idx} className="flex items-start gap-2.5">
              <span
                className={`w-2 h-2 rounded-full mt-1 shrink-0 ${
                  item.type === 'win'
                    ? 'bg-[#34d399]'
                    : item.type === 'loss'
                    ? 'bg-[#f43f5e]'
                    : 'bg-[#8c9ba5]'
                }`}
              />
              <span className="text-[#8c9ba5] text-[11px] shrink-0">{item.time}</span>
              <span className="text-slate-200 text-[11px]">{item.text}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Quick Tags (From HTML Proposal) */}
      <div className="p-4 space-y-2">
        <h3 className="text-[10px] font-mono font-bold uppercase tracking-wider text-[#8c9ba5]">
          Quick Tags
        </h3>
        <div className="flex flex-wrap gap-1.5 font-mono text-[10px]">
          {[
            'spot-drift',
            'reclaim-fail',
            'macro-trend',
            'vol-spike',
            'whipsaw',
            'book-thin',
            'atr-squeeze',
            'trend-cont',
          ].map((tag) => (
            <button
              key={tag}
              onClick={() => {
                soundFX.playClickSound();
                setSelectedTag(selectedTag === tag ? null : tag);
              }}
              className={`px-2 py-1 rounded transition-all border ${
                selectedTag === tag
                  ? 'bg-[#00bda5] text-black font-bold border-[#00bda5]'
                  : tag === 'whipsaw' || tag === 'book-thin'
                  ? 'bg-[#1a2128] text-[#f43f5e] border-[#262d35] hover:border-[#f43f5e]'
                  : 'bg-[#1a2128] text-[#8c9ba5] border-[#262d35] hover:text-white'
              }`}
            >
              {tag}
            </button>
          ))}
        </div>
      </div>
    </aside>
  );
};
