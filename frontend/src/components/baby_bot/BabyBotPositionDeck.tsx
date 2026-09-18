/**
 * @file BabyBotPositionDeck.tsx
 * @description Active Position, Asymmetric Risk Breakdown, and Guardrail Health Telemetry for BabyBotConsole.
 */

import React from 'react';
import { Position } from '../../types';

interface BabyBotPositionDeckProps {
  activePosition?: Position | null;
  botParams: Record<string, any>;
  consecutiveLosses: number;
  vpin: number;
  isVpinToxic: boolean;
  isDeadZone: boolean;
}

export const BabyBotPositionDeck: React.FC<BabyBotPositionDeckProps> = ({
  activePosition,
  botParams,
  consecutiveLosses,
  vpin,
  isVpinToxic,
  isDeadZone,
}) => {
  const discountPrice = botParams.discount_limit_price || 0.52;

  return (
    <div className="p-4 bg-[#12161a] border-b border-[#262d35] space-y-2.5">
      <div className="flex items-center justify-between text-xs font-mono">
        <span className="text-[#8c9ba5] uppercase tracking-wider text-[10px] font-bold">Active Position</span>
        <span className="text-[10px] text-amber-400 font-bold">Hard Cap: 1 Contract</span>
      </div>

      <div className="p-2.5 rounded-lg bg-[#171c22] border border-[#262d35] flex items-center justify-between font-mono text-xs">
        {activePosition && activePosition.size > 0 ? (
          <>
            <div className="flex items-center gap-2">
              <span
                className={`px-2 py-0.5 rounded font-bold uppercase text-[10px] ${
                  activePosition.side === 'yes'
                    ? 'bg-[#10b981]/20 text-[#10b981]'
                    : 'bg-[#f43f5e]/20 text-[#f43f5e]'
                }`}
              >
                {activePosition.side.toUpperCase()}
              </span>
              <span className="text-white font-bold">
                {activePosition.size} ct @ {activePosition.entry_price * 100}¢
              </span>
            </div>
            <div className="text-right">
              <div
                className={`font-bold ${
                  activePosition.unrealized_pnl >= 0 ? 'text-[#10b981]' : 'text-[#f43f5e]'
                }`}
              >
                {activePosition.unrealized_pnl >= 0 ? '+' : ''}${activePosition.unrealized_pnl.toFixed(2)}
              </div>
              <div className="text-[10px] text-[#8c9ba5]">Unrealized PnL</div>
            </div>
          </>
        ) : (
          <div className="w-full text-center text-[#8c9ba5] py-1 text-xs">
            FLAT · No open contract positions (Holding ${discountPrice.toFixed(2)} Maker Resting Limit)
          </div>
        )}
      </div>

      {/* Asymmetric Risk Breakdown */}
      <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
        <div className="p-2 rounded bg-[#13171c] border border-[#1f262d]">
          <span className="text-[#8c9ba5] text-[10px]">MAX RISK (CAPITAL):</span>
          <div className="text-sm font-bold text-[#f43f5e] mt-0.5">
            -${discountPrice.toFixed(2)} / ct
          </div>
        </div>
        <div className="p-2 rounded bg-[#13171c] border border-[#1f262d]">
          <span className="text-[#8c9ba5] text-[10px]">MAX SETTLEMENT WIN:</span>
          <div className="text-sm font-bold text-[#10b981] mt-0.5">
            +${(1.0 - discountPrice).toFixed(2)} / ct
          </div>
        </div>
      </div>

      {/* Guardrail Health: Consecutive Losses & VPIN */}
      <div className="grid grid-cols-2 gap-2 text-[11px] font-mono pt-1">
        <div className="flex items-center justify-between p-2 rounded bg-[#13171c] border border-[#1f262d]">
          <span className="text-[#8c9ba5]">Loss Breaker:</span>
          <div className="flex items-center gap-1">
            {[0, 1, 2].map((idx) => (
              <span
                key={idx}
                className={`w-2 h-2 rounded-full border ${
                  idx < consecutiveLosses
                    ? 'bg-[#f43f5e] border-[#f43f5e]'
                    : 'bg-transparent border-[#8c9ba5]/40'
                }`}
              />
            ))}
            <span className="text-[10px] text-[#8c9ba5] ml-1">{consecutiveLosses}/3</span>
          </div>
        </div>

        <div className="flex items-center justify-between p-2 rounded bg-[#13171c] border border-[#1f262d]">
          <span className="text-[#8c9ba5]">VPIN Toxicity:</span>
          <span className={`font-bold ${isVpinToxic ? 'text-[#f43f5e]' : 'text-emerald-400'}`}>
            {vpin.toFixed(2)} {isVpinToxic ? '⚠️' : 'OK'}
          </span>
        </div>
      </div>

      {/* Coin-Flip Dead-Zone Indicator */}
      <div
        className={`p-2 rounded-lg border text-[11px] font-mono flex items-center justify-between ${
          isDeadZone
            ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
            : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
        }`}
      >
        <div className="flex items-center gap-1.5">
          <span
            className={`w-2 h-2 rounded-full ${isDeadZone ? 'bg-amber-400' : 'bg-emerald-400 animate-pulse'}`}
          />
          <span>{isDeadZone ? 'Razor-Tight Dead Zone Active' : 'Directional Edge Ready'}</span>
        </div>
        <span className="text-[10px] font-bold uppercase tracking-wider">
          {isDeadZone ? 'SKIPPING' : 'EDGE CONFIRMED'}
        </span>
      </div>
    </div>
  );
};
