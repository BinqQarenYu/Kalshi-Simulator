/**
 * @file PortfolioDrawer.tsx
 * @description Renders portfolio metrics, active open positions with 1-Click Close/Liquidate action,
 * resting limit orders queue with Cancel action, and recent contract expiration settlements.
 */

import React, { useState } from 'react';
import { PortfolioState } from '../types';
import { Wallet, CheckCircle2, XCircle, Clock, X, Trash2, ShieldAlert, RefreshCw, Download, FileText } from 'lucide-react';
import { soundFX } from '../utils/audioFX';

interface PortfolioDrawerProps {
  /** Real-time virtual portfolio state snapshot */
  portfolio: PortfolioState;
  /** Callback to immediately liquidate and close an open position */
  onClosePosition: (ticker: string) => Promise<any>;
  /** Callback to cancel an active resting limit order */
  onCancelOrder?: (orderId: string) => Promise<any>;
  /** Callback to manually reset tripped circuit breaker */
  onResetCircuitBreaker?: () => Promise<any>;
}

export const PortfolioDrawer: React.FC<PortfolioDrawerProps> = ({
  portfolio,
  onClosePosition,
  onCancelOrder,
  onResetCircuitBreaker,
}) => {
  const [closingTickers, setClosingTickers] = useState<Record<string, boolean>>({});
  const [cancellingOrders, setCancellingOrders] = useState<Record<string, boolean>>({});
  const [isResettingCb, setIsResettingCb] = useState(false);
  const isPnlPositive = portfolio.realized_pnl >= 0;
  const isCbTripped = !!portfolio.circuit_breaker_tripped;

  const handleClose = async (ticker: string) => {
    soundFX.playClickSound();
    setClosingTickers((prev) => ({ ...prev, [ticker]: true }));
    try {
      await onClosePosition(ticker);
    } finally {
      setClosingTickers((prev) => ({ ...prev, [ticker]: false }));
    }
  };

  const handleCancel = async (orderId: string) => {
    soundFX.playClickSound();
    setCancellingOrders((prev) => ({ ...prev, [orderId]: true }));
    try {
      await onCancelOrder?.(orderId);
    } finally {
      setCancellingOrders((prev) => ({ ...prev, [orderId]: false }));
    }
  };

  const handleResetCb = async () => {
    soundFX.playClickSound();
    setIsResettingCb(true);
    try {
      await onResetCircuitBreaker?.();
    } finally {
      setIsResettingCb(false);
    }
  };

  const openOrders = portfolio.open_orders || [];

  return (
    <div className="bg-[#111620] border border-[#21262d] rounded-2xl p-4 sm:p-5 flex flex-col gap-4 shadow-xl">
      {/* Circuit Breaker Tripped Alert Banner */}
      {isCbTripped && (
        <div className="bg-red-950/50 border border-red-500/50 rounded-xl p-3.5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 animate-pulse">
          <div className="flex items-center gap-2.5">
            <ShieldAlert className="h-5 w-5 text-red-400 flex-shrink-0" />
            <div>
              <div className="text-xs font-bold uppercase text-red-300">
                Max Drawdown Circuit Breaker Tripped (Drawdown: {portfolio.current_drawdown_pct?.toFixed(1)}%)
              </div>
              <div className="text-[11px] text-red-200/80">
                All automated order execution is halted to protect capital.
              </div>
            </div>
          </div>
          <button
            type="button"
            disabled={isResettingCb}
            onClick={handleResetCb}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-red-500/20 hover:bg-red-500/30 text-red-200 border border-red-500/40 transition-all active:scale-95 disabled:opacity-50 self-end sm:self-auto"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isResettingCb ? 'animate-spin' : ''}`} />
            <span>{isResettingCb ? 'Resetting...' : 'Reset & Resume Trading'}</span>
          </button>
        </div>
      )}

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 border-b border-[#21262d] pb-4">
        {/* Total Equity */}
        <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-3">
          <div className="text-[11px] font-semibold text-[#8b949e] uppercase">Total Equity</div>
          <div className="text-lg font-mono font-extrabold text-white mt-0.5">
            ${portfolio.equity.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>

        {/* Realized P&L */}
        <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-3">
          <div className="text-[11px] font-semibold text-[#8b949e] uppercase">Realized P&L</div>
          <div className={`text-lg font-mono font-extrabold mt-0.5 ${
            isPnlPositive ? 'text-[#00d084]' : 'text-[#ff4d4d]'
          }`}>
            {isPnlPositive ? '+' : ''}${portfolio.realized_pnl.toFixed(2)}
          </div>
        </div>

        {/* Unrealized P&L */}
        <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-3">
          <div className="text-[11px] font-semibold text-[#8b949e] uppercase">Unrealized P&L</div>
          <div className={`text-lg font-mono font-extrabold mt-0.5 ${
            portfolio.unrealized_pnl >= 0 ? 'text-[#00d084]' : 'text-[#ff4d4d]'
          }`}>
            {portfolio.unrealized_pnl >= 0 ? '+' : ''}${portfolio.unrealized_pnl.toFixed(2)}
          </div>
        </div>

        {/* Win Rate */}
        <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-3">
          <div className="text-[11px] font-semibold text-[#8b949e] uppercase">Win Rate</div>
          <div className="text-lg font-mono font-extrabold text-white mt-0.5 flex items-center gap-1.5">
            <span>{portfolio.win_rate.toFixed(1)}%</span>
            <span className="text-xs text-[#8b949e] font-normal">
              ({portfolio.wins}/{portfolio.total_trades})
            </span>
          </div>
        </div>
      </div>

      {/* Open Positions Table with 1-Click Close Action */}
      <div>
        <h4 className="text-xs font-bold uppercase tracking-wider text-white mb-2 flex items-center gap-1.5">
          <Wallet className="h-3.5 w-3.5 text-[#f7931a]" />
          <span>Active Open Positions ({portfolio.positions.length})</span>
        </h4>

        {portfolio.positions.length === 0 ? (
          <div className="text-center py-5 text-xs text-[#8b949e] bg-[#161b22] rounded-xl border border-[#30363d]">
            No open contract positions. Place an order or enable AI Auto-Trade.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="text-[#8b949e] border-b border-[#21262d]">
                  <th className="pb-2">Ticker</th>
                  <th className="pb-2">Side</th>
                  <th className="pb-2 text-right">Contracts</th>
                  <th className="pb-2 text-right">Entry</th>
                  <th className="pb-2 text-right">Mark</th>
                  <th className="pb-2 text-right">Unrealized</th>
                  <th className="pb-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#161b22]">
                {portfolio.positions.map((pos, idx) => {
                  const isWin = pos.unrealized_pnl >= 0;
                  const isClosing = closingTickers[pos.ticker];

                  return (
                    <tr key={idx} className="hover:bg-[#161b22]/50 transition-colors">
                      <td className="py-2.5 font-bold text-white">{pos.ticker}</td>
                      <td className="py-2.5">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold uppercase ${
                          pos.side === 'yes' ? 'bg-[#00d084]/20 text-[#00d084]' : 'bg-[#ff4d4d]/20 text-[#ff4d4d]'
                        }`}>
                          {pos.side}
                        </span>
                      </td>
                      <td className="py-2.5 text-right font-bold text-gray-200">{pos.size}</td>
                      <td className="py-2.5 text-right text-gray-400">${pos.entry_price.toFixed(2)}</td>
                      <td className="py-2.5 text-right text-gray-200">${pos.current_price.toFixed(2)}</td>
                      <td className={`py-2.5 text-right font-bold ${
                        isWin ? 'text-[#00d084]' : 'text-[#ff4d4d]'
                      }`}>
                        {isWin ? '+' : ''}${pos.unrealized_pnl.toFixed(2)}
                      </td>
                      <td className="py-2.5 text-right">
                        <button
                          type="button"
                          disabled={isClosing}
                          onClick={() => handleClose(pos.ticker)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-bold bg-[#21262d] hover:bg-[#ff4d4d]/20 text-gray-300 hover:text-[#ff4d4d] border border-[#30363d] hover:border-[#ff4d4d]/40 transition-all active:scale-95 disabled:opacity-50"
                          title="Liquidate position immediately at market"
                        >
                          <X className="h-3 w-3" />
                          <span>{isClosing ? 'Closing...' : 'Close'}</span>
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

      {/* Active Resting Limit Orders Table */}
      {openOrders.length > 0 && (
        <div className="border-t border-[#21262d] pt-3">
          <h4 className="text-xs font-bold uppercase tracking-wider text-white mb-2 flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5 text-blue-400" />
            <span>Resting Limit Orders ({openOrders.length})</span>
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="text-[#8b949e] border-b border-[#21262d]">
                  <th className="pb-2">Order ID</th>
                  <th className="pb-2">Ticker</th>
                  <th className="pb-2">Side</th>
                  <th className="pb-2 text-right">Limit Price</th>
                  <th className="pb-2 text-right">Contracts</th>
                  <th className="pb-2 text-right">Time</th>
                  <th className="pb-2 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#161b22]">
                {openOrders.map((ord) => {
                  const isCancelling = cancellingOrders[ord.order_id];
                  return (
                    <tr key={ord.order_id} className="hover:bg-[#161b22]/50 transition-colors">
                      <td className="py-2.5 font-bold text-gray-300">{ord.order_id}</td>
                      <td className="py-2.5 text-white font-semibold">{ord.ticker}</td>
                      <td className="py-2.5">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold uppercase ${
                          ord.side === 'yes' ? 'bg-[#00d084]/20 text-[#00d084]' : 'bg-[#ff4d4d]/20 text-[#ff4d4d]'
                        }`}>
                          {ord.side}
                        </span>
                      </td>
                      <td className="py-2.5 text-right font-bold text-white">
                        {(ord.limit_price * 100).toFixed(1)}¢
                      </td>
                      <td className="py-2.5 text-right text-gray-200">{ord.size}</td>
                      <td className="py-2.5 text-right text-gray-400">{ord.created_at}</td>
                      <td className="py-2.5 text-right">
                        <button
                          type="button"
                          disabled={isCancelling}
                          onClick={() => handleCancel(ord.order_id)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-bold bg-[#21262d] hover:bg-yellow-500/20 text-gray-300 hover:text-yellow-400 border border-[#30363d] hover:border-yellow-500/40 transition-all active:scale-95 disabled:opacity-50"
                          title="Cancel resting limit order"
                        >
                          <Trash2 className="h-3 w-3" />
                          <span>{isCancelling ? 'Cancelling...' : 'Cancel'}</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Settled History */}
      {portfolio.settlements.length > 0 && (
        <div className="border-t border-[#21262d] pt-3">
          <h4 className="text-xs font-bold uppercase tracking-wider text-[#8b949e] mb-2">
            Recent Expirations & Settlements
          </h4>
          <div className="flex flex-col gap-1.5 max-h-36 overflow-y-auto pr-1">
            {portfolio.settlements.map((s, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between text-xs font-mono bg-[#161b22] px-3 py-1.5 rounded-lg border border-[#30363d]"
              >
                <div className="flex items-center gap-2">
                  {s.outcome === 'win' ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-[#00d084]" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5 text-[#ff4d4d]" />
                  )}
                  <span className="font-bold text-white">{s.ticker}</span>
                  <span className="text-[11px] text-gray-400 uppercase">({s.side} {s.size}x)</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-gray-400">{s.timestamp}</span>
                  <span className={`font-bold ${
                    s.pnl >= 0 ? 'text-[#00d084]' : 'text-[#ff4d4d]'
                  }`}>
                    {s.pnl >= 0 ? '+' : ''}${s.pnl.toFixed(2)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Structured Analytics Export Toolbar */}
      <div className="border-t border-[#21262d] pt-3 flex flex-wrap items-center justify-between gap-2">
        <div className="text-[11px] font-semibold text-[#8b949e] flex items-center gap-1">
          <Download className="h-3.5 w-3.5 text-blue-400" />
          <span>Export Analytics</span>
        </div>
        <div className="flex items-center gap-1.5">
          <a
            href="/api/export/trades?format=csv"
            download="kalshi_trades_export.csv"
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-bold bg-[#161b22] hover:bg-[#21262d] text-gray-300 hover:text-white border border-[#30363d] transition-all active:scale-95"
            title="Download full trade fill logs in CSV format"
          >
            <FileText className="h-3 w-3 text-emerald-400" />
            <span>Trades CSV</span>
          </a>
          <a
            href="/api/export/settlements?format=csv"
            download="kalshi_settlements_export.csv"
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-bold bg-[#161b22] hover:bg-[#21262d] text-gray-300 hover:text-white border border-[#30363d] transition-all active:scale-95"
            title="Download contract expiry settlements in CSV format"
          >
            <FileText className="h-3 w-3 text-blue-400" />
            <span>Settlements CSV</span>
          </a>
          <a
            href="/api/export/pnl?format=csv"
            download="kalshi_pnl_snapshot.csv"
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-bold bg-[#161b22] hover:bg-[#21262d] text-gray-300 hover:text-white border border-[#30363d] transition-all active:scale-95"
            title="Download P&L snapshot in CSV format"
          >
            <FileText className="h-3 w-3 text-purple-400" />
            <span>P&L CSV</span>
          </a>
        </div>
      </div>
    </div>
  );
};
