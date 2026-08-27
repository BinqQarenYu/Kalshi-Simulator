import React from 'react';
import { OrderBookLadderRow } from '../types';

interface OrderBookLadderProps {
  ladder: OrderBookLadderRow[];
  onSelectPrice: (priceCents: number) => void;
}

export const OrderBookLadder: React.FC<OrderBookLadderProps> = ({
  ladder,
  onSelectPrice,
}) => {
  return (
    <div className="bg-[#0d1117] p-4">
      {/* Table Header */}
      <div className="grid grid-cols-3 pb-2 text-[11px] font-bold uppercase tracking-wider text-[#8b949e] border-b border-[#21262d]">
        <div>Price</div>
        <div className="text-right">Contracts</div>
        <div className="text-right">Total</div>
      </div>

      {/* Ladder Rows */}
      <div className="divide-y divide-[#161b22] pt-1 font-mono text-xs">
        {ladder.map((row, idx) => {
          const isRed = row.price_raw >= 0.045; // visually highlight near-the-money
          const textColor = isRed ? 'text-[#ff4d4d]' : 'text-[#ff7b7b]';
          const depthBg = isRed ? 'rgba(255, 77, 77, 0.08)' : 'rgba(255, 123, 123, 0.06)';

          return (
            <div
              key={idx}
              onClick={() => onSelectPrice(row.price_raw * 100)}
              className="relative grid grid-cols-3 py-2 px-1 cursor-pointer hover:bg-[#161b22] transition-colors rounded items-center group"
            >
              {/* Visual Depth Bar filling from right */}
              <div
                className="absolute left-0 top-0 bottom-0 pointer-events-none rounded transition-all duration-300"
                style={{
                  width: `${row.depth_pct}%`,
                  backgroundColor: depthBg,
                }}
              />

              {/* Price Column */}
              <div className={`font-bold z-10 ${textColor}`}>
                {row.price_cents}
              </div>

              {/* Contracts Column */}
              <div className="text-right text-gray-300 font-semibold z-10">
                {row.contracts.toLocaleString()}
              </div>

              {/* Total Dollar Value */}
              <div className="text-right text-[#8b949e] group-hover:text-white font-medium z-10">
                {row.total}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
