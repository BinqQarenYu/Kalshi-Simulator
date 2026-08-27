/**
 * @file OrderEntryPanel.tsx
 * @description Right-side 1-Click execution panel matching Kalshi UI with BUY/SELL toggle,
 * LIMIT/MARKET modes, UP/DOWN contract selection cards, dynamic cost/payout math, and sound FX.
 */

import React, { useState } from 'react';
import { MarketState, PortfolioState } from '../types';
import { Zap, HelpCircle, Check, Sparkles } from 'lucide-react';
import { soundFX } from '../utils/audioFX';

interface OrderEntryPanelProps {
  market: MarketState;
  portfolio: PortfolioState;
  onPlaceOrder: (side: 'yes' | 'no', size: number, limitPrice?: number, orderType?: 'market' | 'limit', restingOnly?: boolean) => Promise<any>;
}

export const OrderEntryPanel: React.FC<OrderEntryPanelProps> = ({
  market,
  portfolio,
  onPlaceOrder,
}) => {
  const [tradeMode, setTradeMode] = useState<'BUY' | 'SELL'>('BUY');
  const [orderType, setOrderType] = useState<'LIMIT' | 'MARKET'>('LIMIT');
  const [side, setSide] = useState<'yes' | 'no'>('yes');
  const [shares, setShares] = useState<number>(50);
  const [limitPriceCents, setLimitPriceCents] = useState<number>(4.6);
  const [restingOnly, setRestingOnly] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [orderFeedback, setOrderFeedback] = useState<string | null>(null);

  // Calculations
  const pricePerContract = limitPriceCents / 100;
  const totalCost = shares * pricePerContract;
  const maxPayout = shares * 1.0; // Kalshi binary contract payout ($1.00)

  const handleExecute = async () => {
    soundFX.playClickSound();
    setIsSubmitting(true);
    setOrderFeedback(null);
    try {
      const res = await onPlaceOrder(
        side,
        shares,
        orderType === 'LIMIT' ? pricePerContract : undefined,
        orderType === 'LIMIT' ? 'limit' : 'market',
        orderType === 'LIMIT' && restingOnly
      );
      if (res.success) {
        soundFX.playOrderFillSound();
        if (res.status === 'resting') {
          setOrderFeedback(`Resting limit order placed @ ${(res.limit_price * 100).toFixed(1)}¢!`);
        } else {
          setOrderFeedback(`Order filled @ ${(res.fill_price * 100).toFixed(1)}¢!`);
        }
      } else {
        soundFX.playLossSound();
        setOrderFeedback(`Order rejected: ${res.reason || 'Insufficient funds'}`);
      }
    } catch (e) {
      soundFX.playLossSound();
      setOrderFeedback('Error placing order');
    } finally {
      setIsSubmitting(false);
      setTimeout(() => setOrderFeedback(null), 4000);
    }
  };

  return (
    <div className="bg-[#111620] border border-[#21262d] rounded-2xl p-4 sm:p-5 flex flex-col gap-4 shadow-xl">
      {/* Top Header Mode Toggle */}
      <div className="flex items-center justify-between pb-2 border-b border-[#21262d]">
        <button
          onClick={() => soundFX.playClickSound()}
          className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold text-purple-400 bg-purple-500/10 border border-purple-500/30 hover:bg-purple-500/20 transition-all"
        >
          <Sparkles className="h-3.5 w-3.5" />
          <span>COMBO</span>
        </button>

        <div className="flex items-center gap-3">
          <div className="flex items-center bg-[#161b22] p-0.5 rounded-lg border border-[#30363d] text-xs font-bold">
            <button
              onClick={() => {
                soundFX.playClickSound();
                setTradeMode('BUY');
              }}
              className={`px-3 py-1 rounded-md transition-all ${
                tradeMode === 'BUY' ? 'bg-[#30363d] text-white' : 'text-[#8b949e] hover:text-white'
              }`}
            >
              BUY
            </button>
            <button
              onClick={() => {
                soundFX.playClickSound();
                setTradeMode('SELL');
              }}
              className={`px-3 py-1 rounded-md transition-all ${
                tradeMode === 'SELL' ? 'bg-[#30363d] text-white' : 'text-[#8b949e] hover:text-white'
              }`}
            >
              SELL
            </button>
          </div>

          <select
            value={orderType}
            onChange={(e) => {
              soundFX.playClickSound();
              setOrderType(e.target.value as 'LIMIT' | 'MARKET');
            }}
            className="bg-[#161b22] text-xs font-bold text-white border border-[#30363d] rounded-lg px-2 py-1 outline-none cursor-pointer"
          >
            <option value="LIMIT">LIMIT</option>
            <option value="MARKET">MARKET</option>
          </select>
        </div>
      </div>

      {/* Target Pill Header */}
      <div className="flex items-center gap-2 text-xs font-semibold text-gray-300">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#f7931a] text-black text-[11px] font-bold">
          ₿
        </span>
        <span>
          BTC 15 min · <strong className="text-white">{market.target_strike_str} target</strong>
        </span>
      </div>

      {/* Big UP / DOWN Option Buttons (exact Kalshi UI) */}
      <div className="grid grid-cols-2 gap-2.5">
        {/* UP Button */}
        <button
          type="button"
          onClick={() => {
            soundFX.playClickSound();
            setSide('yes');
            setLimitPriceCents(market.best_yes_ask * 100 || 3.4);
          }}
          className={`flex items-center justify-between p-3 rounded-xl border transition-all text-left ${
            side === 'yes'
              ? 'bg-[#00d084] text-black border-[#00d084] font-black shadow-lg shadow-[#00d084]/20 scale-[1.01]'
              : 'bg-[#161b22] text-white border-[#30363d] hover:border-[#00d084]/50'
          }`}
        >
          <div className="flex flex-col">
            <span className="text-xs uppercase font-extrabold">UP {market.yes_cents_str}</span>
          </div>
          {side === 'yes' && <Check className="h-4 w-4 stroke-[3]" />}
        </button>

        {/* DOWN Button */}
        <button
          type="button"
          onClick={() => {
            soundFX.playClickSound();
            setSide('no');
            setLimitPriceCents(market.best_no_ask * 100 || 96.9);
          }}
          className={`flex items-center justify-between p-3 rounded-xl border transition-all text-left ${
            side === 'no'
              ? 'bg-[#ff4d4d] text-white border-[#ff4d4d] font-black shadow-lg shadow-[#ff4d4d]/20 scale-[1.01]'
              : 'bg-[#161b22] text-white border-[#30363d] hover:border-[#ff4d4d]/50'
          }`}
        >
          <div className="flex flex-col">
            <span className="text-xs uppercase font-extrabold">DOWN {market.no_cents_str}</span>
            <span className="text-[10px] opacity-75 font-normal">3.25% Interest</span>
          </div>
          {side === 'no' && <Check className="h-4 w-4 stroke-[3]" />}
        </button>
      </div>

      {/* Shares Input */}
      <div>
        <div className="flex items-center justify-between text-xs font-semibold text-[#8b949e] mb-1">
          <label htmlFor="shares-input">Shares</label>
          <span className="text-[11px] text-gray-400">
            Predictions account · <strong className="text-white">${portfolio.balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong> available
          </span>
        </div>
        <div className="flex items-center gap-2">
          <input
            id="shares-input"
            type="number"
            min={1}
            max={5000}
            value={shares}
            onChange={(e) => setShares(Math.max(1, parseInt(e.target.value) || 0))}
            className="w-full bg-[#161b22] border border-[#30363d] rounded-xl px-3 py-2 text-right font-mono text-sm font-bold text-white outline-none focus:border-[#00d084]"
          />
        </div>
        {/* Quick Share Chips */}
        <div className="flex gap-1.5 mt-1.5">
          {[10, 50, 100, 250].map((count) => (
            <button
              key={count}
              type="button"
              onClick={() => {
                soundFX.playClickSound();
                setShares(count);
              }}
              className={`px-2 py-0.5 text-[10px] font-bold rounded-md border transition-all ${
                shares === count
                  ? 'bg-[#30363d] text-white border-gray-500'
                  : 'bg-[#161b22] text-[#8b949e] border-[#30363d] hover:text-white'
              }`}
            >
              +{count}
            </button>
          ))}
        </div>
      </div>

      {/* Limit Price Input */}
      {orderType === 'LIMIT' && (
        <div>
          <div className="flex items-center justify-between text-xs font-semibold text-[#8b949e] mb-1">
            <div className="flex items-center gap-1">
              <label htmlFor="limit-price-input">Limit price</label>
              <HelpCircle className="h-3 w-3 text-[#8b949e]" />
            </div>
            <span className="text-[11px] text-gray-400">
              Ask: <strong className="text-white">{market.yes_cents_str}</strong> · Bid: <strong className="text-white">{(market.best_yes_bid * 100).toFixed(1)}¢</strong>
            </span>
          </div>
          <div className="relative">
            <input
              id="limit-price-input"
              type="number"
              step="0.1"
              min="0.1"
              max="99.9"
              value={limitPriceCents}
              onChange={(e) => setLimitPriceCents(parseFloat(e.target.value) || 0)}
              className="w-full bg-[#161b22] border border-[#30363d] rounded-xl px-3 py-2 text-right font-mono text-sm font-bold text-white outline-none focus:border-[#00d084] pr-8"
            />
            <span className="absolute right-3 top-2.5 text-xs text-[#8b949e] font-mono">¢</span>
          </div>
        </div>
      )}

      {/* Submit as Resting Order Only Toggle */}
      {orderType === 'LIMIT' && (
        <div className="flex items-center justify-between text-xs text-gray-300 py-1">
          <span>Submit as resting order only</span>
          <button
            type="button"
            onClick={() => {
              soundFX.playClickSound();
              setRestingOnly(!restingOnly);
            }}
            className={`w-9 h-5 flex items-center rounded-full p-1 transition-colors ${
              restingOnly ? 'bg-[#00d084]' : 'bg-[#30363d]'
            }`}
          >
            <div
              className={`bg-white w-3.5 h-3.5 rounded-full shadow-md transform transition-transform ${
                restingOnly ? 'translate-x-4' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
      )}

      {/* Live Financial Breakdown */}
      <div className="space-y-1.5 text-xs border-t border-[#21262d] pt-3 text-[#8b949e]">
        <div className="flex justify-between">
          <span>Cost to buy {shares} contracts:</span>
          <span className="font-mono font-bold text-white">${totalCost.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span>Max Potential Payout:</span>
          <span className="font-mono font-bold text-[#00d084]">${maxPayout.toFixed(2)}</span>
        </div>
      </div>

      {/* Order Feedback Alert */}
      {orderFeedback && (
        <div className="bg-[#161b22] border border-[#30363d] text-white px-3 py-2 rounded-xl text-xs font-mono text-center animate-fadeIn">
          {orderFeedback}
        </div>
      )}

      {/* Main 1-Click Action Button */}
      <button
        type="button"
        disabled={isSubmitting}
        onClick={handleExecute}
        className={`w-full py-3.5 rounded-xl font-extrabold text-sm flex items-center justify-center gap-2 shadow-xl transition-all active:scale-95 disabled:opacity-50 ${
          side === 'yes'
            ? 'bg-[#00d084] hover:bg-[#00b573] text-black shadow-[#00d084]/20'
            : 'bg-[#ff4d4d] hover:bg-[#e63e3e] text-white shadow-[#ff4d4d]/20'
        }`}
      >
        <Zap className="h-4 w-4 fill-current" />
        <span>
          {isSubmitting
            ? 'Transacting...'
            : `⚡ Buy ${side.toUpperCase()} with 1-Click`}
        </span>
      </button>
    </div>
  );
};
