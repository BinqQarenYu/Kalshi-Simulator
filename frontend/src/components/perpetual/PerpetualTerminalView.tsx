/**
 * @file PerpetualTerminalView.tsx
 * @description Root view for the Perpetual Trading Terminal within Kalshi Simulator.
 * Unites:
 * 1. Top Ribbon: Asset Ticker, 24h Delta, Funding Rate, Active Bot Selector
 * 2. Independent Canvas Candlestick & Liquidity Chart
 * 3. Side Execution Ticket (Manual & Bot Mode with Leverage)
 * 4. Docked Bottom Parameter Tuning Deck & Signals Feed
 * 5. Open Positions Ledger
 */

import React from 'react';
import { PerpetualTradingProvider, usePerpetualTrading } from '../../context/PerpetualTradingContext';
import { PerpetualChart } from './PerpetualChart';
import { PerpetualOrderTicket } from './PerpetualOrderTicket';
import { PerpetualBotPanel } from './PerpetualBotPanel';
import { PerpetualPositionsTable } from './PerpetualPositionsTable';
import { PerpetualIncubationReport } from './PerpetualIncubationReport';
import { Bot, Clock, ArrowUpRight, TrendingUp, ShieldAlert, Cpu } from 'lucide-react';
import { soundFX } from '../../utils/audioFX';

const PerpetualTerminalContent: React.FC = () => {
  const {
    selectedAsset,
    currentPrice,
    priceChange24h,
    fundingRate,
    nextFundingIn,
    activeBotId,
    setActiveBotId,
    botConfigs,
  } = usePerpetualTrading();

  return (
    <div className="flex flex-col gap-4 p-4 min-w-0 max-w-full font-sans select-none bg-[#0f1319]">
      {/* Top Header Ribbon: Asset Info, Funding Rate, Bot Quick-Deploy Selector */}
      <div className="bg-[#12161a] border border-[#1f2937] rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-4 shadow-xl">
        {/* Left: Asset Price & Funding */}
        <div className="flex flex-wrap items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-cyan-500/15 border border-cyan-500/40 flex items-center justify-center font-bold text-cyan-400 text-sm">
              {selectedAsset}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-white text-base tracking-wide">
                  {selectedAsset}-PERPETUAL
                </span>
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-bold border border-cyan-500/30">
                  PERP
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs font-mono">
                <span className="text-white font-extrabold text-sm">
                  ${currentPrice.toFixed(selectedAsset === 'DOGE' ? 5 : 2)}
                </span>
                <span className="text-emerald-400 font-bold flex items-center">
                  <ArrowUpRight className="w-3 h-3" />
                  +{priceChange24h}%
                </span>
              </div>
            </div>
          </div>

          <div className="h-8 w-[1px] bg-slate-800 hidden md:block" />

          {/* Funding Rate Metric */}
          <div className="hidden md:flex flex-col font-mono text-xs">
            <span className="text-slate-400 text-[10px]">Funding / Countdown</span>
            <span className="text-amber-400 font-bold">
              {(fundingRate * 100).toFixed(4)}% in {nextFundingIn}
            </span>
          </div>
        </div>

        {/* Right: Quick Deploy Bot Selector */}
        <div className="flex items-center gap-3 font-mono text-xs">
          <span className="text-slate-400 text-[11px] hidden sm:inline">Active Robot Strategy:</span>
          <div className="relative">
            <select
              value={activeBotId}
              onChange={(e) => {
                soundFX.playClickSound();
                setActiveBotId(e.target.value);
              }}
              className="bg-[#1a2128] border border-cyan-500/50 text-cyan-300 rounded-lg px-3 py-2 text-xs font-bold focus:outline-none focus:ring-1 focus:ring-cyan-400 cursor-pointer shadow-sm"
            >
              {Object.values(botConfigs).map((b) => (
                <option key={b.id} value={b.id}>
                  🤖 {b.name} ({b.leverage}x)
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Main Grid: Chart & Order Ticket */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left 8 Cols: Dynamic Chart */}
        <div className="lg:col-span-8 flex flex-col gap-4">
          <div className="h-[460px]">
            <PerpetualChart />
          </div>
          <PerpetualBotPanel />
        </div>

        {/* Right 4 Cols: Order Execution Ticket */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          <PerpetualOrderTicket />
        </div>
      </div>

      {/* Bottom Ledger: Open Positions Table */}
      <PerpetualPositionsTable />
      
      {/* Incubation Reports */}
      <PerpetualIncubationReport />
    </div>
  );
};

export const PerpetualTerminalView: React.FC = () => {
  return (
    <PerpetualTradingProvider>
      <PerpetualTerminalContent />
    </PerpetualTradingProvider>
  );
};
