/**
 * @file PerpetualPositionsTable.tsx
 * @description Real-time ledger of active Perpetual Positions with PnL telemetry and Close actions.
 */

import React from 'react';
import { usePerpetualTrading } from '../../context/PerpetualTradingContext';
import { X, TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { soundFX } from '../../utils/audioFX';

export const PerpetualPositionsTable: React.FC = () => {
  const { positions, closePosition } = usePerpetualTrading();

  const handleClose = (posId: string) => {
    soundFX.playClickSound();
    closePosition(posId);
  };

  return (
    <div className="bg-[#12161a] border border-[#1f2937] rounded-xl p-4 flex flex-col gap-3 text-xs font-mono shadow-xl overflow-hidden">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
        <span className="font-bold text-white uppercase tracking-wider">
          Active Positions ({positions.length})
        </span>
        <span className="text-[10px] text-slate-400">Isolated Margin & Live Mark</span>
      </div>

      {positions.length === 0 ? (
        <div className="text-center py-6 text-slate-500 italic">
          No open perpetual positions. Submit an order from the ticket to engage.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="text-[10px] text-slate-400 border-b border-slate-800 uppercase font-bold">
                <th className="pb-2">Asset / Side</th>
                <th className="pb-2">Size</th>
                <th className="pb-2">Entry Price</th>
                <th className="pb-2">Mark Price</th>
                <th className="pb-2">Liq. Price</th>
                <th className="pb-2">Margin</th>
                <th className="pb-2">Unrealized PnL</th>
                <th className="pb-2 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {positions.map((pos) => {
                const isProfit = pos.unrealizedPnl >= 0;
                return (
                  <tr key={pos.id} className="hover:bg-slate-800/30 transition-all text-[11px]">
                    <td className="py-2.5 flex items-center gap-1.5 font-bold">
                      <span
                        className={`p-1 rounded ${
                          pos.side === 'long' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                        }`}
                      >
                        {pos.side === 'long' ? (
                          <ArrowUpRight className="w-3.5 h-3.5" />
                        ) : (
                          <ArrowDownRight className="w-3.5 h-3.5" />
                        )}
                      </span>
                      <span>{pos.asset}-PERP</span>
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-amber-400">
                        {pos.leverage}x
                      </span>
                    </td>
                    <td className="py-2.5 text-slate-200 font-bold">{pos.size}</td>
                    <td className="py-2.5 text-slate-300">${pos.entryPrice.toFixed(2)}</td>
                    <td className="py-2.5 text-slate-300">${pos.markPrice.toFixed(2)}</td>
                    <td className="py-2.5 text-rose-400">${pos.liquidationPrice.toFixed(2)}</td>
                    <td className="py-2.5 text-cyan-400 font-bold">${pos.margin.toFixed(2)}</td>
                    <td className="py-2.5">
                      <span
                        className={`font-bold ${
                          isProfit ? 'text-emerald-400' : 'text-rose-400'
                        }`}
                      >
                        {isProfit ? '+' : ''}${pos.unrealizedPnl.toFixed(2)} ({isProfit ? '+' : ''}
                        {pos.unrealizedPnlPct.toFixed(2)}%)
                      </span>
                    </td>
                    <td className="py-2.5 text-right">
                      <button
                        onClick={() => handleClose(pos.id)}
                        className="px-2.5 py-1 rounded bg-slate-800 hover:bg-rose-500/20 text-slate-300 hover:text-rose-400 border border-slate-700 hover:border-rose-500/40 transition-all font-bold"
                        title="Close Position at Market"
                      >
                        Close
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
