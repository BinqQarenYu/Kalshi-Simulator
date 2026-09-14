/**
 * @file TradeTape.tsx
 * @description Institutional real-time trade tape component showing continuous trade prints,
 * contract counts, price points, side indicators (YES / NO), and full keyboard/screen reader accessibility.
 */

import React from 'react';
import { TradeTapeItem } from '../types';
import { ArrowUpRight, ArrowDownRight, Activity } from 'lucide-react';

interface TradeTapeProps {
  tradeTape: TradeTapeItem[];
  maxItems?: number;
}

export const TradeTape: React.FC<TradeTapeProps> = React.memo(({ tradeTape = [], maxItems = 30 }) => {
  const items = tradeTape.slice(0, maxItems);

  if (!items.length) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="p-8 text-center text-[#8b949e] font-mono text-xs flex flex-col items-center justify-center gap-2.5 bg-[#0d1117]/60 rounded-xl border border-[#21262d]/60"
      >
        <div className="relative flex items-center justify-center">
          <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-ping opacity-75 absolute" />
          <span className="w-2 h-2 rounded-full bg-cyan-500" />
        </div>
        <div className="flex items-center gap-1.5 text-slate-300 font-semibold">
          <Activity className="h-3.5 w-3.5 text-cyan-400" />
          <span>Listening for real-time exchange trade prints...</span>
        </div>
        <p className="text-[11px] text-[#8b949e] max-w-xs">
          Live Level-2 market prints and WebCLOB matching execution telemetry will stream here automatically.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full overflow-x-auto max-h-[360px] overflow-y-auto rounded-xl border border-[#21262d] bg-[#0d1117]/80 shadow-inner">
      <table className="w-full text-left text-xs font-mono tabular-nums border-collapse" aria-label="Real-time exchange trade tape prints">
        <thead className="text-[10px] uppercase tracking-wider text-[#8b949e] bg-[#161b22] sticky top-0 z-10 border-b border-[#21262d]">
          <tr>
            <th scope="col" className="py-2.5 px-4 font-semibold text-slate-400">Time</th>
            <th scope="col" className="py-2.5 px-4 font-semibold text-slate-400">Side</th>
            <th scope="col" className="py-2.5 px-4 text-right font-semibold text-slate-400">Price</th>
            <th scope="col" className="py-2.5 px-4 text-right font-semibold text-slate-400">Volume</th>
            <th scope="col" className="py-2.5 px-4 text-right font-semibold text-slate-400">Notional</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[#21262d]/50">
          {items.map((item, idx) => {
            const isYes = item.side?.toLowerCase() === 'yes';
            const priceText = typeof item.price_cents === 'number' ? `${item.price_cents}¢` : item.price_cents;
            const contractsText = `${item.contracts} ct${item.contracts !== 1 ? 's' : ''}`;
            const ariaLabelText = `${item.time} - ${isYes ? 'YES' : 'NO'} trade at ${priceText}, volume ${contractsText}, notional value ${item.val_str}`;

            return (
              <tr
                key={`${item.time}-${item.ticker}-${idx}`}
                tabIndex={0}
                aria-label={ariaLabelText}
                className="hover:bg-[#161b22] focus-visible:bg-[#161b22] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50 transition-colors group"
              >
                <td className="py-2 px-4 text-[#8b949e] font-mono text-[11px] whitespace-nowrap">{item.time}</td>
                <td className="py-2 px-4 whitespace-nowrap">
                  <span
                    className={`inline-flex items-center gap-1 font-bold px-2 py-0.5 rounded text-[11px] border ${
                      isYes
                        ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                        : 'text-rose-400 bg-rose-500/10 border-rose-500/20'
                    }`}
                  >
                    {isYes ? <ArrowUpRight className="h-3 w-3 stroke-[2.5]" /> : <ArrowDownRight className="h-3 w-3 stroke-[2.5]" />}
                    {isYes ? 'YES' : 'NO'}
                  </span>
                </td>
                <td className="py-2 px-4 text-right font-bold text-slate-100 font-mono text-xs">
                  {priceText}
                </td>
                <td className="py-2 px-4 text-right text-slate-200 font-mono text-xs">
                  {contractsText}
                </td>
                <td className="py-2 px-4 text-right text-[#8b949e] font-mono text-[11px]">
                  {item.val_str}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
});
