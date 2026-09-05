/**
 * @file LiveTradeModal.tsx
 * @description High-visibility safety confirmation modal for routing orders to Kalshi live/demo exchange.
 * Enforces pre-flight inspection of contract ticker, count, max cost, payout, and dry-run safety toggle.
 */

import React, { useState } from 'react';
import { ShieldAlert, Zap, AlertTriangle, X, CheckCircle2 } from 'lucide-react';
import { soundFX } from '../utils/audioFX';

interface LiveTradeModalProps {
  isOpen: boolean;
  ticker: string;
  side: 'yes' | 'no';
  count: number;
  priceDollars: number;
  orderType: 'market' | 'limit';
  action: 'buy' | 'sell';
  onClose: () => void;
  onConfirm: (dryRun: boolean) => Promise<void>;
}

export const LiveTradeModal: React.FC<LiveTradeModalProps> = ({
  isOpen,
  ticker,
  side,
  count,
  priceDollars,
  orderType,
  action,
  onClose,
  onConfirm,
}) => {
  const [isDryRun, setIsDryRun] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  if (!isOpen) return null;

  const totalCost = count * priceDollars;
  const maxPayout = count * 1.0;

  const handleConfirm = async () => {
    soundFX.playClickSound();
    setIsSubmitting(true);
    try {
      await onConfirm(isDryRun);
    } finally {
      setIsSubmitting(false);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-fadeIn">
      <div className="bg-[#111620] border border-[#30363d] rounded-2xl w-full max-w-md p-5 sm:p-6 shadow-2xl space-y-4">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-[#21262d] pb-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-[#f7931a]/15 text-[#f7931a] border border-[#f7931a]/30">
              <ShieldAlert className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold uppercase tracking-wider text-white">
                Live Order Confirmation
              </h2>
              <span className="text-[11px] text-[#8b949e]">
                Pre-Flight Exchange Safety Verification
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close Live Order Confirmation"
            className="text-gray-400 hover:text-white p-1 rounded-lg hover:bg-[#161b22] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#3b82f6]"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        {/* Order Details Matrix */}
        <div className="bg-[#0d1117] border border-[#21262d] rounded-xl p-3.5 space-y-2 font-mono text-xs">
          <div className="flex justify-between">
            <span className="text-[#8b949e]">Target Contract:</span>
            <span className="text-white font-bold">{ticker}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#8b949e]">Side / Action:</span>
            <span
              className={`font-bold uppercase ${
                side === 'yes' ? 'text-[#00d084]' : 'text-[#ff4d4d]'
              }`}
            >
              {action} {side} ({count} Contracts)
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#8b949e]">Order Execution Type:</span>
            <span className="text-white font-bold uppercase">{orderType}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#8b949e]">Limit / Est. Price:</span>
            <span className="text-white font-bold">${priceDollars.toFixed(2)}</span>
          </div>
          <div className="border-t border-[#21262d] pt-2 flex justify-between">
            <span className="text-[#8b949e]">Estimated Total Capital:</span>
            <span className="text-white font-bold text-sm">${totalCost.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#8b949e]">Max Potential Settlement Payout:</span>
            <span className="text-[#00d084] font-bold">${maxPayout.toFixed(2)}</span>
          </div>
        </div>

        {/* Dry-Run Toggle Bar */}
        <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-3 flex items-center justify-between">
          <div className="space-y-0.5">
            <div id="dry-run-label" className="text-xs font-bold text-white flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-[#3b82f6]" aria-hidden="true" />
              <span>Safety Dry-Run Mode</span>
            </div>
            <p className="text-[11px] text-[#8b949e]">
              {isDryRun
                ? 'Validates without routing real funds to exchange'
                : '⚡ Live order will be submitted directly to Kalshi!'}
            </p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={isDryRun}
            aria-labelledby="dry-run-label"
            onClick={() => {
              soundFX.playClickSound();
              setIsDryRun(!isDryRun);
            }}
            className={`w-11 h-6 flex items-center rounded-full p-1 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#3b82f6] ${
              isDryRun ? 'bg-[#3b82f6]' : 'bg-[#ff4d4d]'
            }`}
          >
            <div
              className={`bg-white w-4 h-4 rounded-full shadow-md transform transition-transform ${
                isDryRun ? 'translate-x-0' : 'translate-x-5'
              }`}
            />
          </button>
        </div>

        {!isDryRun && (
          <div className="bg-[#ff4d4d]/10 border border-[#ff4d4d]/30 text-[#ff4d4d] px-3 py-2 rounded-xl text-[11px] flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            <span>Caution: Real exchange orders cannot be recalled once matched.</span>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 py-2.5 rounded-xl text-xs font-bold bg-[#161b22] hover:bg-[#21262d] text-gray-300 transition-colors border border-[#30363d]"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={isSubmitting}
            onClick={handleConfirm}
            className={`flex-1 py-2.5 rounded-xl text-xs font-extrabold flex items-center justify-center gap-1.5 shadow-lg transition-all active:scale-95 disabled:opacity-50 ${
              isDryRun
                ? 'bg-[#3b82f6] hover:bg-[#2563eb] text-white shadow-[#3b82f6]/20'
                : 'bg-[#ff4d4d] hover:bg-[#e63e3e] text-white shadow-[#ff4d4d]/20'
            }`}
          >
            <Zap className="h-3.5 w-3.5 fill-current" />
            <span>{isSubmitting ? 'Transacting...' : isDryRun ? 'Simulate (Dry-Run)' : 'Confirm & Route'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
