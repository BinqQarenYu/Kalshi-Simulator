/**
 * @file TradeTape.tsx
 * @description Institutional real-time trade tape component showing continuous trade prints,
 * contract counts, price points, and side indicators (YES / NO).
 */

import React from 'react';
import { TradeTapeItem } from '../types';
import { ArrowUpRight, ArrowDownRight } from 'lucide-react';

interface TradeTapeProps {
  tradeTape: TradeTapeItem[];
  maxItems?: number;
}

export const TradeTape: React.FC<TradeTapeProps> = React.memo(({ tradeTape = [], maxItems = 30 }) => {
  const items = tradeTape.slice(0, maxItems);

  if (!items.length) {
    return (
      <div className="p-8 text-center text-[#8b949e] font-mono text-xs flex flex-col items-center justify-center gap-2">
        <span className="w-2 h-2 rounded-full bg-[#f7931a] animate-ping" />
        <span>Listening for real-time exchange trade prints...</span>
      </div>
    );
  }

  return (
    <div className="w-full overflow-x-auto max-h-[360px] overflow-y-auto">
      <table className="w-full text-left text-xs font-mono">
        <thead className="text-[10px] uppercase tracking-wider text-[#8b949e] bg-[#161b22] sticky top-0 z-10 border-b border-[#21262d]">
          <tr>
            <th className="py-2 px-4">Time</th>
            <th className="py-2 px-4">Side</th>
            <th className="py-2 px-4 text-right">Price</th>
            <th className="py-2 px-4 text-right">Volume</th>
            <th className="py-2 px-4 text-right">Notional</th>
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
