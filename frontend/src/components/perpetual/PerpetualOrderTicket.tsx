/**
 * @file PerpetualOrderTicket.tsx
 * @description Unified Execution Ticket supporting both Manual and Bot-assisted Perpetual Orders.
 * Features:
 * 1. Mode switch: Manual vs Bot execution
 * 2. Long (Buy) / Short (Sell) directional selectors
 * 3. Leverage slider (1x to 50x) with dynamic margin requirement calculation
 * 4. Market / Limit order types
 * 5. Position liquidation estimation
 * 6. Single-click submission
 */

import React, { useState } from 'react';
import { usePerpetualTrading } from '../../context/PerpetualTradingContext';
import { ArrowUpRight, ArrowDownRight, Shield, Zap, Sliders, Info, Bot } from 'lucide-react';
import { soundFX } from '../../utils/audioFX';

export const PerpetualOrderTicket: React.FC = () => {
  const { selectedAsset, currentPrice, balance, openPosition, activeBotId, botConfigs } = usePerpetualTrading();

  const [tradeMode, setTradeMode] = useState<'manual' | 'bot'>('manual');
  const [side, setSide] = useState<'long' | 'short'>('long');
  const [orderType, setOrderType] = useState<'market' | 'limit'>('market');
  const [limitPrice, setLimitPrice] = useState<string>(currentPrice.toString());
  const [size, setSize] = useState<string>('0.05');
  const [leverage, setLeverage] = useState<number>(5);

  const activeBot = botConfigs[activeBotId];

  const numSize = parseFloat(size) || 0;
  const numLimit = parseFloat(limitPrice) || currentPrice;
  const executionPrice = orderType === 'market' ? currentPrice : numLimit;
  const notional = numSize * executionPrice;
  const requiredMargin = leverage > 0 ? notional / leverage : notional;

  // Estimated liquidation
  const liqBuffer = executionPrice * (1 / leverage) * 0.9;
  const estimatedLiq = side === 'long' ? executionPrice - liqBuffer : executionPrice + liqBuffer;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (numSize <= 0) return;

    soundFX.playOrderFillSound();
    openPosition(side, numSize, leverage, orderType, orderType === 'limit' ? numLimit : undefined);
  };

  return (
    <div className="bg-[#12161a] border border-[#1f2937] rounded-xl p-4 flex flex-col gap-4 text-xs font-mono shadow-xl">
      {/* Mode Header Switcher: Manual vs Bot Assisted */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <span className="font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
          <Zap className="w-3.5 h-3.5 text-cyan-400" />
          <span>Execution Ticket</span>
        </span>

        <div className="flex bg-[#1a2128] p-0.5 rounded-lg border border-slate-800">
          <button
            type="button"
            onClick={() => setTradeMode('manual')}
            className={`px-3 py-1 rounded text-[11px] font-bold transition-all ${
              tradeMode === 'manual'
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Manual
          </button>
          <button
            type="button"
            onClick={() => setTradeMode('bot')}
            className={`px-3 py-1 rounded text-[11px] font-bold transition-all flex items-center gap-1 ${
              tradeMode === 'bot'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Bot className="w-3 h-3" />
            <span>Bot Auto</span>
          </button>
        </div>
      </div>

      {tradeMode === 'bot' ? (
        /* Bot Mode Overview Card */
        <div className="space-y-3 py-2">
          <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 space-y-1.5">
            <div className="flex items-center justify-between font-bold">
              <span>{activeBot?.name || 'Automated Strategy'}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 uppercase">
                {activeBot?.isArmed ? 'ARMED & ROUTING' : 'STANDBY'}
              </span>
            </div>
            <div className="text-[11px] text-slate-300 leading-relaxed">
              {activeBot?.signals.rationale || 'Monitoring real-time order flow and volatility moats.'}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <div className="bg-[#1a2128] p-2 rounded border border-slate-800">
              <span className="text-slate-400 block text-[10px]">AI Conviction</span>
              <span className="text-cyan-400 font-bold text-sm">{activeBot?.signals.conviction || 0}%</span>
            </div>
            <div className="bg-[#1a2128] p-2 rounded border border-slate-800">
              <span className="text-slate-400 block text-[10px]">VPIN Toxicity</span>
              <span className="text-emerald-400 font-bold text-sm">{activeBot?.signals.vpin || 0.12}</span>
            </div>
          </div>

          <div className="text-[11px] text-slate-400 italic text-center py-2">
            Automated trades execute automatically based on parameter gates below the chart.
          </div>
        </div>
      ) : (
        /* Manual Order Form */
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Side Selector (Long vs Short) */}
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setSide('long')}
              className={`py-2 rounded-lg font-bold flex items-center justify-center gap-1.5 transition-all ${
                side === 'long'
                  ? 'bg-emerald-500 text-black shadow-lg shadow-emerald-500/30'
                  : 'bg-[#1a2128] text-slate-400 border border-slate-800 hover:text-white'
              }`}
            >
              <ArrowUpRight className="w-4 h-4" />
              <span>BUY / LONG</span>
            </button>

            <button
              type="button"
              onClick={() => setSide('short')}
              className={`py-2 rounded-lg font-bold flex items-center justify-center gap-1.5 transition-all ${
                side === 'short'
                  ? 'bg-rose-500 text-white shadow-lg shadow-rose-500/30'
                  : 'bg-[#1a2128] text-slate-400 border border-slate-800 hover:text-white'
              }`}
            >
              <ArrowDownRight className="w-4 h-4" />
              <span>SELL / SHORT</span>
            </button>
          </div>

          {/* Order Type Selector */}
          <div className="flex bg-[#1a2128] p-1 rounded-lg border border-slate-800 text-[11px]">
            <button
              type="button"
              onClick={() => setOrderType('market')}
              className={`flex-1 py-1 rounded text-center transition-all ${
                orderType === 'market' ? 'bg-slate-800 text-white font-bold' : 'text-slate-400 hover:text-white'
              }`}
            >
              Market
            </button>
            <button
              type="button"
              onClick={() => setOrderType('limit')}
              className={`flex-1 py-1 rounded text-center transition-all ${
                orderType === 'limit' ? 'bg-slate-800 text-white font-bold' : 'text-slate-400 hover:text-white'
              }`}
            >
              Limit
            </button>
          </div>

          {/* Limit Price Input */}
          {orderType === 'limit' && (
            <div className="space-y-1">
              <label className="text-slate-400 text-[10px] uppercase font-bold">Limit Price ($)</label>
              <input
                type="number"
                step="any"
                value={limitPrice}
                onChange={(e) => setLimitPrice(e.target.value)}
                className="w-full bg-[#1a2128] border border-slate-800 rounded-lg px-3 py-2 text-white font-bold focus:border-cyan-500 outline-none"
              />
            </div>
          )}

          {/* Order Size Input */}
          <div className="space-y-1">
            <div className="flex justify-between text-[10px] text-slate-400 font-bold uppercase">
              <span>Order Size ({selectedAsset})</span>
              <span>Bal: ${balance.toFixed(2)}</span>
            </div>
            <div className="relative">
              <input
                type="number"
                step="any"
                value={size}
                onChange={(e) => setSize(e.target.value)}
                className="w-full bg-[#1a2128] border border-slate-800 rounded-lg px-3 py-2 text-white font-bold focus:border-cyan-500 outline-none"
              />
              <span className="absolute right-3 top-2 text-slate-500 text-[11px]">{selectedAsset}</span>
            </div>
          </div>

          {/* Leverage Slider */}
          <div className="space-y-2 bg-[#1a2128]/50 p-2.5 rounded-lg border border-slate-800">
            <div className="flex justify-between items-center text-[11px]">
              <span className="text-slate-400 font-bold">Leverage</span>
              <span className="text-amber-400 font-extrabold bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/30">
                {leverage}x
              </span>
            </div>
            <input
              type="range"
              min="1"
              max="50"
              step="1"
              value={leverage}
              onChange={(e) => setLeverage(parseInt(e.target.value))}
              className="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-amber-400"
            />
            <div className="flex justify-between text-[9px] text-slate-500 font-mono">
              <span>1x</span>
              <span>10x</span>
              <span>25x</span>
              <span>50x</span>
            </div>
          </div>

          {/* Trade Metrics Breakdown */}
          <div className="space-y-1.5 text-[11px] border-t border-slate-800 pt-3">
            <div className="flex justify-between text-slate-400">
              <span>Notional Value:</span>
              <span className="text-white font-bold">${notional.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Required Margin:</span>
              <span className="text-cyan-400 font-bold">${requiredMargin.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Est. Liquidation Price:</span>
              <span className="text-rose-400 font-bold">${Math.max(0, estimatedLiq).toFixed(2)}</span>
            </div>
          </div>

          {/* Submit Action Button */}
          <button
            type="submit"
            className={`w-full py-3 rounded-lg font-bold text-xs uppercase tracking-wider transition-all shadow-lg ${
              side === 'long'
                ? 'bg-emerald-500 hover:bg-emerald-400 text-black shadow-emerald-500/20'
                : 'bg-rose-500 hover:bg-rose-400 text-white shadow-rose-500/20'
            }`}
          >
            {side === 'long' ? 'Open Long Position' : 'Open Short Position'}
          </button>
        </form>
      )}
    </div>
  );
};
