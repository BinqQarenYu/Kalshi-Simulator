/**
 * @file TradeTape.tsx
 * @description Institutional real-time trade tape component showing continuous trade prints,
 * contract counts, price points, and side indicators (YES / NO) with glanceable telemetry and accessibility enhancements.
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
        className="p-8 text-center text-[#8b949e] font-mono text-xs flex flex-col items-center justify-center gap-2"
      >
        <span className="w-2 h-2 rounded-full bg-[#f7931a] animate-ping" aria-hidden="true" />
        <span>Listening for real-time exchange trade prints...</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col w-full gap-2">
      {/* Telemetry Summary Bar */}
      {telemetry && (
        <div className="flex items-center justify-between px-3 py-1.5 bg-[#161b22] border border-[#21262d] rounded-lg text-[11px] font-mono tabular-nums text-[#8b949e]">
          <div className="flex items-center gap-2">
            <Activity className="h-3.5 w-3.5 text-cyan-400 shrink-0" aria-hidden="true" />
            <span>Tape Stream ({telemetry.count} prints)</span>
          </div>
          <div className="flex items-center gap-3">
            <span>Latest: <strong className="text-white">{telemetry.latestPrice}</strong></span>
            <span className="text-[#30363d]">|</span>
            <span>Volume: <strong className="text-emerald-400">{telemetry.totalVolume.toLocaleString()} cts</strong></span>
          </div>
        </div>
      )}

      {/* Accessible Scrollable Table Region */}
      <div
        tabIndex={0}
        role="region"
        aria-label="Real-time exchange trade tape history"
        className="w-full overflow-x-auto max-h-[340px] overflow-y-auto rounded-lg border border-[#21262d]/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500/50"
      >
        <table className="w-full text-left text-xs font-mono tabular-nums" aria-label="Real-time exchange trade prints">
          <thead className="text-[10px] uppercase tracking-wider text-[#8b949e] bg-[#161b22] sticky top-0 z-10 border-b border-[#21262d]">
            <tr>
              <th scope="col" className="py-2 px-4 font-semibold">Time</th>
              <th scope="col" className="py-2 px-4 font-semibold">Side</th>
              <th scope="col" className="py-2 px-4 text-right font-semibold">Price</th>
              <th scope="col" className="py-2 px-4 text-right font-semibold">Volume</th>
              <th scope="col" className="py-2 px-4 text-right font-semibold">Notional</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#21262d]/50">
            {items.map((item, idx) => {
              const isYes = item.side?.toLowerCase() === 'yes';
              return (
                <tr
                  key={`${item.time}-${item.ticker}-${idx}`}
                  className="hover:bg-[#161b22]/70 focus-within:bg-[#161b22]/70 transition-colors"
                >
                  <td className="py-1.5 px-4 text-[#8b949e]">{item.time}</td>
                  <td className="py-1.5 px-4">
                    <span
                      aria-label={`Side ${isYes ? 'YES' : 'NO'}`}
                      className={`inline-flex items-center gap-1 font-bold ${
                        isYes ? 'text-[#00d084]' : 'text-[#ff4d4d]'
                      }`}
                    >
                      {isYes ? (
                        <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
                      ) : (
                        <ArrowDownRight className="h-3 w-3" aria-hidden="true" />
                      )}
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
    </div>
  );
});
