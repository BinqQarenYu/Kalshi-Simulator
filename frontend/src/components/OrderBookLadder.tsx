import React, { useState, useMemo } from 'react';
import { OrderBookLadderRow } from '../types';
import { soundFX } from '../utils/audioFX';

interface OrderBookLadderProps {
  ladder: OrderBookLadderRow[];
  onSelectPrice: (priceCents: number) => void;
}

export const OrderBookLadder: React.FC<OrderBookLadderProps> = React.memo(({
  ladder,
  onSelectPrice,
}) => {
  const [filterSide, setFilterSide] = useState<'all' | 'yes' | 'no'>('all');

  const filteredLadder = useMemo(() => {
    if (filterSide === 'all') return ladder;
    return ladder.filter((r) => r.side === filterSide);
  }, [ladder, filterSide]);

  const yesRows = useMemo(() => ladder.filter((r) => r.side === 'yes'), [ladder]);
  const noRows = useMemo(() => ladder.filter((r) => r.side === 'no'), [ladder]);

  const bestYes = yesRows[0];
  const bestNo = noRows[0];

  const spreadCents = useMemo(() => {
    if (!bestYes || !bestNo) return null;
    const yesCents = bestYes.price_raw * 100;
    const noCents = bestNo.price_raw * 100;
    const impliedYesAsk = 100 - noCents;
    return Math.max(0, Math.round((impliedYesAsk - yesCents) * 10) / 10);
  }, [bestYes, bestNo]);

  const totalContracts = useMemo(() => {
    return filteredLadder.reduce((acc, r) => acc + r.contracts, 0);
  }, [filteredLadder]);

  return (
    <div className="bg-[#0d1117] p-3 sm:p-4 rounded-xl border border-[#21262d]/60 shadow-inner">
      {/* Top Controls: Filter Pills & Spread Pill */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-[#21262d]">
        <div role="group" aria-label="Filter order book depth" className="flex items-center gap-1.5 bg-[#161b22] p-0.5 rounded-lg border border-[#30363d]">
          <button
            type="button"
            aria-pressed={filterSide === 'all'}
            onClick={() => {
              soundFX.playClickSound();
              setFilterSide('all');
            }}
            className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#f7931a] ${
              filterSide === 'all'
                ? 'bg-slate-700 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            All Depth ({ladder.length})
          </button>
          <button
            type="button"
            aria-pressed={filterSide === 'yes'}
            onClick={() => {
              soundFX.playClickSound();
              setFilterSide('yes');
            }}
            className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all flex items-center gap-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#f7931a] ${
              filterSide === 'yes'
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-sm'
                : 'text-slate-400 hover:text-emerald-400'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            YES (Up)
          </button>
          <button
            type="button"
            aria-pressed={filterSide === 'no'}
            onClick={() => {
              soundFX.playClickSound();
              setFilterSide('no');
            }}
            className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all flex items-center gap-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#f7931a] ${
              filterSide === 'no'
                ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40 shadow-sm'
                : 'text-slate-400 hover:text-amber-400'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            NO (Down)
          </button>
        </div>

        {/* Live Spread Indicator */}
        <div className="flex items-center gap-2 text-[11px] font-mono text-slate-300 bg-[#161b22] px-2.5 py-1 rounded-lg border border-[#30363d]">
          <span className="text-slate-500">Spread:</span>
          <span className="font-bold text-emerald-400">{spreadCents !== null ? `${spreadCents.toFixed(1)}¢` : '1.0¢'}</span>
          <span className="text-slate-600">|</span>
          <span className="text-slate-500">Depth:</span>
          <span className="font-bold text-slate-200">{totalContracts.toLocaleString()}</span>
        </div>
      </div>

      {/* Table Header */}
      <div className="grid grid-cols-4 pb-2 pt-2 text-[10px] font-bold uppercase tracking-wider text-[#8b949e] border-b border-[#21262d]">
        <div className="col-span-1">Side & Price</div>
        <div className="col-span-1 text-center">Probability</div>
        <div className="col-span-1 text-right">Contracts</div>
        <div className="col-span-1 text-right">Total ($)</div>
      </div>

      {/* Ladder Rows */}
      <div className="divide-y divide-[#161b22] pt-1 font-mono text-xs max-h-[380px] overflow-y-auto pr-1">
        {filteredLadder.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-500">
            Awaiting Level-2 order book depth synchronization...
          </div>
        ) : (
          filteredLadder.map((row, idx) => {
            const isYes = row.side === 'yes';
            const textColor = isYes ? 'text-emerald-400' : 'text-amber-400';
            const badgeBg = isYes ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' : 'bg-amber-500/20 text-amber-300 border-amber-500/30';
            const depthBg = isYes ? 'rgba(16, 185, 129, 0.16)' : 'rgba(245, 158, 11, 0.16)';
            const hoverBorder = isYes ? 'hover:border-emerald-500/40' : 'hover:border-amber-500/40';

            const handleSelect = () => {
              soundFX.playClickSound();
              onSelectPrice(parseFloat((row.price_raw * 100).toFixed(1)));
            };

            return (
              <div
                key={`${row.side}-${row.price_cents}-${idx}`}
                role="button"
                tabIndex={0}
                aria-label={`Set limit price to ${row.price_cents} for ${row.side.toUpperCase()} contract`}
                onClick={handleSelect}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    handleSelect();
                  }
                }}
                title={`Click or press Enter to set Limit Order at ${row.price_cents}`}
                className={`relative grid grid-cols-4 py-2 px-1.5 cursor-pointer hover:bg-[#161b22] rounded items-center group transition-all border border-transparent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#f7931a] ${hoverBorder}`}
              >
                {/* Instantaneous Hardware-Accelerated Depth Bar */}
                <div
                  className="absolute left-0 top-0 bottom-0 pointer-events-none rounded transition-all duration-150"
                  style={{
                    width: `${row.depth_pct}%`,
                    backgroundColor: depthBg,
                    willChange: 'width',
                  }}
                />

                {/* Side & Price Column */}
                <div className="col-span-1 flex items-center gap-1.5 z-10">
                  <span className={`px-1.5 py-0.2 text-[9px] font-bold uppercase rounded border ${badgeBg}`}>
                    {row.side}
                  </span>
                  <span className={`font-bold ${textColor}`}>
                    {row.price_cents}
                  </span>
                </div>

                {/* Probability Estimate */}
                <div className="col-span-1 text-center text-slate-400 text-[11px] z-10">
                  {(row.price_raw * 100).toFixed(0)}%
                </div>

                {/* Contracts Column */}
                <div className="col-span-1 text-right text-gray-100 font-semibold z-10">
                  {row.contracts.toLocaleString()}
                </div>

                {/* Total Dollar Value */}
                <div className="col-span-1 text-right text-[#8b949e] group-hover:text-white font-medium z-10">
                  {row.total}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
});
