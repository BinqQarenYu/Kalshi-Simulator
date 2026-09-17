/**
 * @file TradeTape.tsx
 * @description Institutional real-time trade tape component showing continuous trade prints,
<<<<<<< HEAD
 * contract counts, price points, and side indicators (YES / NO) with glanceable telemetry and accessibility enhancements.
=======
 * contract counts, price points, side indicators (YES / NO), and full keyboard/screen reader accessibility.
>>>>>>> origin/palette-trade-tape-ux-accessibility-sweep-6787729153568931860
 */

import React, { useMemo } from 'react';
import { TradeTapeItem } from '../types';
import { ArrowUpRight, ArrowDownRight, Activity } from 'lucide-react';

interface TradeTapeProps {
  tradeTape: TradeTapeItem[];
  maxItems?: number;
}

export const TradeTape: React.FC<TradeTapeProps> = React.memo(({ tradeTape = [], maxItems = 30 }) => {
  const items = useMemo(() => tradeTape.slice(0, maxItems), [tradeTape, maxItems]);

  const telemetry = useMemo(() => {
    if (!items.length) return null;
    const latestPrice = items[0]?.price_cents ?? '—';
    const totalVolume = items.reduce((acc, item) => acc + (item.contracts || 0), 0);
    return { latestPrice, totalVolume, count: items.length };
  }, [items]);

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
    <div
      tabIndex={0}
      aria-label="Live Trade Tape feed"
      className="w-full overflow-x-auto max-h-[360px] overflow-y-auto focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00d084] rounded-lg"
    >
      <table className="w-full text-left text-xs font-mono" aria-label="Live Trade Tape prints">
        <thead className="text-[10px] uppercase tracking-wider text-[#8b949e] bg-[#161b22] sticky top-0 z-10 border-b border-[#21262d]">
          <tr>
            <th scope="col" className="py-2 px-4">Time</th>
            <th scope="col" className="py-2 px-4">Side</th>
            <th scope="col" className="py-2 px-4 text-right">Price</th>
            <th scope="col" className="py-2 px-4 text-right">Volume</th>
            <th scope="col" className="py-2 px-4 text-right">Notional</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[#21262d]/50">
          {items.map((item, idx) => {
            const isYes = item.side?.toLowerCase() === 'yes';
            return (
              <tr
                key={`${item.time}-${item.ticker}-${idx}`}
                className="hover:bg-[#161b22]/50 transition-colors"
              >
                <td className="py-1.5 px-4 text-[#8b949e]">{item.time}</td>
                <td className="py-1.5 px-4">
                  <span
                    className={`inline-flex items-center gap-1 font-bold ${
                      isYes ? 'text-[#00d084]' : 'text-[#ff4d4d]'
                    }`}
                  >
                    {isYes ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                    {isYes ? 'YES' : 'NO'}
                  </span>
                </td>
                <td className="py-1.5 px-4 text-right font-bold text-white">
                  {item.price_cents}
                </td>
                <td className="py-1.5 px-4 text-right text-white">
                  {item.contracts} ct{item.contracts !== 1 ? 's' : ''}
                </td>
                <td className="py-1.5 px-4 text-right text-[#8b949e] text-[11px]">
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
