/**
 * @file OrderEntryPanel.tsx
 * @description Right-side 1-Click execution panel matching Kalshi UI with BUY/SELL toggle,
 * LIMIT/MARKET modes, UP/DOWN contract selection cards, dynamic cost/payout math, live account balance freeze & deposit notifications.
 */

import React, { useState } from 'react';
import { MarketState, PortfolioState, LivePortfolioState } from '../types';
import { Zap, HelpCircle, Check, Sparkles, AlertTriangle, Lock, ArrowUpRight } from 'lucide-react';
import { soundFX } from '../utils/audioFX';
import { getAssetMeta } from '../utils/assets';

interface OrderEntryPanelProps {
  market: MarketState;
  portfolio: PortfolioState;
  livePortfolio?: LivePortfolioState | null;
  tradingMode?: 'paper' | 'live';
  onPlaceOrder: (
    side: 'yes' | 'no',
    size: number,
    limitPrice?: number,
    orderType?: 'market' | 'limit',
    restingOnly?: boolean
  ) => Promise<any>;
}

export const OrderEntryPanel: React.FC<OrderEntryPanelProps> = ({
  market,
  portfolio,
  livePortfolio,
  tradingMode = 'paper',
  onPlaceOrder,
}) => {
  const is5m = market.timeframe === '5m';
  const isLive = tradingMode === 'live' && !is5m;
  const assetMeta = getAssetMeta(market.active_asset);
  const [tradeMode, setTradeMode] = useState<'BUY' | 'SELL'>('BUY');
  const [orderType, setOrderType] = useState<'LIMIT' | 'MARKET'>('LIMIT');
  const [side, setSide] = useState<'yes' | 'no'>('yes');
  const [shares, setShares] = useState<number>(isLive ? 1 : 10);
  const [limitPriceCents, setLimitPriceCents] = useState<number>(4.6);
  const [restingOnly, setRestingOnly] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [orderFeedback, setOrderFeedback] = useState<string | null>(null);

  // Calculations
  const pricePerContract = limitPriceCents / 100;
  const totalCost = shares * pricePerContract;
  const maxPayout = shares * 1.0; // Kalshi binary contract payout ($1.00)

  // Live account balance & freeze calculations
  const availableLiveCash = Number(livePortfolio?.balance_dollars ?? 0.0) || 0.0;
  const isLiveFrozen = isLive && (availableLiveCash <= 0.05 || availableLiveCash < totalCost);

  const handleExecute = async () => {
    if (isLive && isLiveFrozen) {
      soundFX.playLossSound();
      setOrderFeedback(`⚠️ Live balance ($${availableLiveCash.toFixed(2)}) is insufficient. Please load funds into your Kalshi account.`);
      return;
    }

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
      if (res?.success) {
        soundFX.playOrderFillSound();
        if (res.status === 'resting') {
          setOrderFeedback(`Resting limit order placed @ ${(res.limit_price * 100).toFixed(1)}¢!`);
        } else {
          setOrderFeedback(`Order filled @ ${(res.fill_price * 100).toFixed(1)}¢!`);
        }
      } else {
        soundFX.playLossSound();
        setOrderFeedback(res?.reason || res?.error || 'Order rejected (Insufficient funds)');
      }
    } catch (e) {
      soundFX.playLossSound();
      setOrderFeedback('Error placing order');
    } finally {
      setIsSubmitting(false);
      setTimeout(() => setOrderFeedback(null), 5000);
    }
  };

  return (
    <div className="bg-[#111620] border border-[#21262d] rounded-2xl p-4 sm:p-5 flex flex-col gap-4 shadow-xl">
      {/* 5M Expansion Notice Banner */}
      {is5m && (
        <div className="flex items-center gap-2 p-2.5 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs font-bold text-amber-300 shadow-sm">
          <Lock className="h-4 w-4 shrink-0 text-amber-400" />
          <span>5M Sprint Event: Paper Live Only. Live real-money trading is disabled.</span>
        </div>
      )}

      {/* Top Header Mode Toggle */}
      <div className="flex items-center justify-between pb-2 border-b border-[#21262d]">
        <button
          type="button"
          aria-label="Toggle combo mode"
          onClick={() => soundFX.playClickSound()}
          className="flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold text-purple-400 bg-purple-500/10 border border-purple-500/30 hover:bg-purple-500/20 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400"
        >
          <Sparkles className="h-3.5 w-3.5" />
          <span>COMBO</span>
        </button>

        <div className="flex items-center gap-3">
          <div
            role="group"
            aria-label="Trade action"
            className="flex items-center bg-[#161b22] p-0.5 rounded-lg border border-[#30363d] text-xs font-bold"
          >
            <button
              type="button"
              aria-pressed={tradeMode === 'BUY'}
              aria-label="Buy contracts"
              onClick={() => {
                soundFX.playClickSound();
                setTradeMode('BUY');
              }}
              className={`px-3 py-1 rounded-md transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400 ${
                tradeMode === 'BUY' ? 'bg-[#30363d] text-white' : 'text-[#8b949e] hover:text-white'
              }`}
            >
              BUY
            </button>
            <button
              type="button"
              aria-pressed={tradeMode === 'SELL'}
              aria-label="Sell contracts"
              onClick={() => {
                soundFX.playClickSound();
                setTradeMode('SELL');
              }}
              className={`px-3 py-1 rounded-md transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400 ${
                tradeMode === 'SELL' ? 'bg-[#30363d] text-white' : 'text-[#8b949e] hover:text-white'
              }`}
            >
              SELL
            </button>
          </div>

          <select
            value={orderType}
            aria-label="Order execution type"
            onChange={(e) => {
              soundFX.playClickSound();
              setOrderType(e.target.value as 'LIMIT' | 'MARKET');
            }}
            className="bg-[#161b22] text-xs font-bold text-white border border-[#30363d] rounded-lg px-2 py-1 outline-none cursor-pointer focus-visible:ring-2 focus-visible:ring-purple-400"
          >
            <option value="LIMIT">LIMIT</option>
            <option value="MARKET">MARKET</option>
          </select>
        </div>
      </div>

      {/* Target Pill Header */}
      <div className="flex items-center gap-2 text-xs font-semibold text-gray-300">
        <span
          className="flex h-5 w-5 items-center justify-center rounded-full text-black text-[11px] font-bold"
          style={{ backgroundColor: assetMeta.color }}
        >
          {assetMeta.symbol}
        </span>
        <span>
          {assetMeta.name} 15 min · <strong className="text-white">{market.target_strike_str} target</strong>
        </span>
      </div>

      {/* Big UP / DOWN Option Buttons (exact Kalshi UI) */}
      <div role="group" aria-label="Contract direction" className="grid grid-cols-2 gap-2.5">
        {/* UP Button */}
        <button
          type="button"
          aria-pressed={side === 'yes'}
          aria-label={`Trade UP at ${market.yes_cents_str}`}
          onClick={() => {
            soundFX.playClickSound();
            setSide('yes');
            const askCents = parseFloat(((market.best_yes_ask ?? 0.5) * 100).toFixed(1));
            setLimitPriceCents(askCents || 50.0);
          }}
          className={`flex items-center justify-between p-3 rounded-xl border transition-all text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00d084] ${
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
          aria-pressed={side === 'no'}
          aria-label={`Trade DOWN at ${market.no_cents_str}`}
          onClick={() => {
            soundFX.playClickSound();
            setSide('no');
            const askCents = parseFloat(((market.best_no_ask ?? 0.5) * 100).toFixed(1));
            setLimitPriceCents(askCents || 50.0);
          }}
          className={`flex items-center justify-between p-3 rounded-xl border transition-all text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ff4d4d] ${
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
          <div className="flex items-center gap-1.5 text-[11px]">
            {isLive ? (
              <span className="text-emerald-400 font-mono" title="Live Kalshi Actual Account Cash">
                Live Available: <strong className={`${availableLiveCash <= 0.05 ? 'text-amber-400' : 'text-emerald-300'}`}>${availableLiveCash.toFixed(2)}</strong>
              </span>
            ) : (
              <span className="text-gray-300">
                Paper Balance: <strong className="text-white font-mono">${portfolio.balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong>
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <input
            id="shares-input"
            type="number"
            min={1}
            max={isLive ? 1 : 5000}
            value={shares}
            onChange={(e) => setShares(isLive ? 1 : Math.max(1, parseInt(e.target.value) || 0))}
            className="w-full bg-[#161b22] border border-[#30363d] rounded-xl px-3 py-2 text-right font-mono text-sm font-bold text-white outline-none focus:border-[#00d084] focus-visible:ring-2 focus-visible:ring-[#00d084]"
          />
        </div>
        {/* Quick Share Chips */}
        <div className="flex items-center justify-between gap-1.5 mt-1.5">
          <div role="group" aria-label="Quick share selection" className="flex gap-1.5">
            {(isLive ? [1] : [5, 10, 20, 50]).map((count) => (
              <button
                key={count}
                type="button"
                aria-pressed={shares === count}
                aria-label={`Set ${count} shares`}
                onClick={() => {
                  soundFX.playClickSound();
                  setShares(count);
                }}
                className={`px-2 py-0.5 text-[10px] font-bold rounded-md border transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 ${
                  shares === count
                    ? isLive ? 'bg-rose-500/30 text-rose-300 border-rose-500/50' : 'bg-[#30363d] text-white border-gray-500'
                    : 'bg-[#161b22] text-[#8b949e] border-[#30363d] hover:text-white'
                }`}
              >
                +{count}
              </button>
            ))}
          </div>
          {isLive && (
            <span className="text-[10px] font-mono text-amber-400/90 font-semibold">
              Live Max: 1 Contract / Asset
            </span>
          )}
        </div>
      </div>

      {/* Limit Price Input */}
      {orderType === 'LIMIT' && (
        <div>
          <div className="flex items-center justify-between text-xs font-semibold text-[#8b949e] mb-1">
            <div className="flex items-center gap-1">
              <label htmlFor="limit-price-input">Limit price</label>
            <HelpCircle className="h-3 w-3 text-[#8b949e]" aria-hidden="true" />
            </div>
            <span className="text-[11px] text-gray-400">
              Ask: <strong className="text-white">{market.yes_cents_str}</strong> · Bid: <strong className="text-white">{((market.best_yes_bid ?? 0.5) * 100).toFixed(1)}¢</strong>
            </span>
          </div>
          <div className="relative">
            <input
              id="limit-price-input"
              type="number"
              step="0.1"
              min="0.1"
              max="99.9"
              value={Number.isFinite(limitPriceCents) ? parseFloat(limitPriceCents.toFixed(1)) : ''}
              onChange={(e) => {
                const parsed = parseFloat(e.target.value);
                setLimitPriceCents(Number.isFinite(parsed) ? parseFloat(parsed.toFixed(1)) : 0);
              }}
              className="w-full bg-[#161b22] border border-[#30363d] rounded-xl px-3 py-2 text-right font-mono text-sm font-bold text-white outline-none focus:border-[#00d084] focus-visible:ring-2 focus-visible:ring-[#00d084] pr-8"
            />
            <span className="absolute right-3 top-2.5 text-xs text-[#8b949e] font-mono">¢</span>
          </div>
          {/* Quick Step Controls */}
          <div className="flex items-center justify-end gap-1.5 mt-1">
            <button
              type="button"
              aria-label="Decrease limit price by 1 cent"
              onClick={() => {
                soundFX.playClickSound();
                setLimitPriceCents((prev) => Math.max(0.1, parseFloat((prev - 1.0).toFixed(1))));
              }}
              className="px-2 py-0.5 text-[10px] font-mono font-bold bg-[#161b22] text-slate-300 border border-[#30363d] rounded hover:border-slate-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#00d084]"
            >
              -1¢
            </button>
            <button
              type="button"
              aria-label="Decrease limit price by 0.1 cents"
              onClick={() => {
                soundFX.playClickSound();
                setLimitPriceCents((prev) => Math.max(0.1, parseFloat((prev - 0.1).toFixed(1))));
              }}
              className="px-2 py-0.5 text-[10px] font-mono font-bold bg-[#161b22] text-slate-300 border border-[#30363d] rounded hover:border-slate-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#00d084]"
            >
              -0.1¢
            </button>
            <button
              type="button"
              aria-label="Increase limit price by 0.1 cents"
              onClick={() => {
                soundFX.playClickSound();
                setLimitPriceCents((prev) => Math.min(99.9, parseFloat((prev + 0.1).toFixed(1))));
              }}
              className="px-2 py-0.5 text-[10px] font-mono font-bold bg-[#161b22] text-slate-300 border border-[#30363d] rounded hover:border-slate-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#00d084]"
            >
              +0.1¢
            </button>
            <button
              type="button"
              aria-label="Increase limit price by 1 cent"
              onClick={() => {
                soundFX.playClickSound();
                setLimitPriceCents((prev) => Math.min(99.9, parseFloat((prev + 1.0).toFixed(1))));
              }}
              className="px-2 py-0.5 text-[10px] font-mono font-bold bg-[#161b22] text-slate-300 border border-[#30363d] rounded hover:border-slate-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#00d084]"
            >
              +1¢
            </button>
          </div>
        </div>
      )}

      {/* Submit as Resting Order Only Toggle */}
      {orderType === 'LIMIT' && (
        <div className="flex items-center justify-between text-xs text-gray-300 py-1">
          <span id="resting-only-label">Submit as resting order only</span>
          <button
            id="resting-only-switch"
            type="button"
            role="switch"
            aria-checked={restingOnly}
            aria-labelledby="resting-only-label"
            onClick={() => {
              soundFX.playClickSound();
              setRestingOnly(!restingOnly);
            }}
            className={`w-9 h-5 flex items-center rounded-full p-1 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00d084] ${
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

      {/* LIVE BALANCE DEPLETED / INSUFFICIENT FUNDS ALERT BANNER */}
      {isLive && isLiveFrozen && (
        <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-start gap-2.5 text-xs animate-in fade-in">
          <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="font-bold text-white flex items-center justify-between">
              <span>Live Balance Depleted (${availableLiveCash.toFixed(2)})</span>
              <span className="px-1.5 py-0.2 text-[9px] font-mono bg-amber-500/20 text-amber-300 border border-amber-500/40 rounded font-bold uppercase">
                BETS FROZEN
              </span>
            </div>
            <p className="text-[11px] text-amber-200/80 mt-1 leading-relaxed">
              Available live cash is insufficient to place this order (need ${totalCost.toFixed(2)}). All live bets are currently frozen.
            </p>
            <div className="mt-2 flex items-center gap-2">
              <a
                href="https://kalshi.com"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 px-2.5 py-1 text-[10px] font-bold text-black bg-amber-400 hover:bg-amber-300 rounded-lg shadow-sm transition-colors"
              >
                <span>Deposit Funds on Kalshi</span>
                <ArrowUpRight className="h-3 w-3" />
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Order Feedback Alert */}
      {orderFeedback && (
        <div className="bg-[#161b22] border border-[#30363d] text-white px-3 py-2 rounded-xl text-xs font-mono text-center animate-fadeIn">
          {orderFeedback}
        </div>
      )}

      {/* Main 1-Click Action Button */}
      <button
        type="button"
        disabled={isSubmitting || (isLive && isLiveFrozen)}
        onClick={handleExecute}
        className={`w-full py-3.5 rounded-xl font-extrabold text-sm flex items-center justify-center gap-2 shadow-xl transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed ${
          isLive && isLiveFrozen
            ? 'bg-[#21262d] text-gray-400 border border-amber-500/30'
            : side === 'yes'
            ? 'bg-[#00d084] hover:bg-[#00b573] text-black shadow-[#00d084]/20'
            : 'bg-[#ff4d4d] hover:bg-[#e63e3e] text-white shadow-[#ff4d4d]/20'
        }`}
      >
        {isLive && isLiveFrozen ? (
          <>
            <Lock className="h-4 w-4 text-amber-400" />
            <span>🔒 Live Bets Frozen (Deposit Required)</span>
          </>
        ) : isSubmitting ? (
          <span>Transacting...</span>
        ) : (
          <>
            <Zap className="h-4 w-4 fill-current" />
            <span>⚡ Buy {side.toUpperCase()} with 1-Click ({isLive ? 'LIVE' : 'PAPER'})</span>
          </>
        )}
      </button>
    </div>
  );
};
