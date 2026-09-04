/**
 * @file PortfolioDrawer.tsx
 * @description Renders portfolio metrics, active open positions with 1-Click Close/Liquidate action,
 * resting limit orders queue with Cancel action, and recent contract expiration settlements.
 * Reconciles Live Real Exchange Ledger (for live trading) and Paper Simulation Portfolio (for paper trading),
 * granting manual position closing / liquidation capabilities across both live and paper modes.
 */

import React, { useState } from 'react';
import { PortfolioState, LivePortfolioState } from '../types';
import { Wallet, CheckCircle2, XCircle, Clock, X, Trash2, ShieldAlert, RefreshCw, Activity, Layers, Lock, ShieldCheck } from 'lucide-react';
import { soundFX } from '../utils/audioFX';

interface PortfolioDrawerProps {
  /** Real-time virtual portfolio state snapshot */
  portfolio: PortfolioState;
  /** Real-time Kalshi live exchange portfolio state */
  livePortfolio?: LivePortfolioState | null;
  /** Active trading mode ('paper' | 'live') */
  tradingMode?: 'paper' | 'live';
  /** Callback to immediately liquidate and close an open position */
  onClosePosition: (ticker: string, executionMode?: 'paper' | 'live') => Promise<any>;
  /** Callback to cancel an active resting limit order */
  onCancelOrder?: (orderId: string, executionMode?: 'paper' | 'live') => Promise<any>;
  /** Callback to manually reset tripped circuit breaker */
  onResetCircuitBreaker?: () => Promise<any>;
}

export const PortfolioDrawer: React.FC<PortfolioDrawerProps> = ({
  portfolio,
  livePortfolio,
  tradingMode = 'paper',
  onClosePosition,
  onCancelOrder,
  onResetCircuitBreaker,
}) => {
  const isLive = tradingMode === 'live';
  const [activeAccountTab, setActiveAccountTab] = useState<'paper' | 'live'>(isLive ? 'live' : 'paper');
  const [closingTickers, setClosingTickers] = useState<Record<string, boolean>>({});
  const [cancellingOrders, setCancellingOrders] = useState<Record<string, boolean>>({});
  const [isResettingCb, setIsResettingCb] = useState(false);
  const isPnlPositive = portfolio.realized_pnl >= 0;
  const isCbTripped = !!portfolio.circuit_breaker_tripped;

  // Sync active account tab when tradingMode prop changes
  React.useEffect(() => {
    setActiveAccountTab(isLive ? 'live' : 'paper');
  }, [isLive]);

  const handleClose = async (ticker: string) => {
    soundFX.playClickSound();
    setClosingTickers((prev) => ({ ...prev, [ticker]: true }));
    try {
      const mode = isLive || activeAccountTab === 'live' ? 'live' : 'paper';
      const res = await onClosePosition(ticker, mode);
      if (res?.success) {
        soundFX.playWinSound();
      } else {
        soundFX.playLossSound();
      }
    } finally {
      setClosingTickers((prev) => ({ ...prev, [ticker]: false }));
    }
  };

  const handleCancel = async (orderId: string) => {
    soundFX.playClickSound();
    setCancellingOrders((prev) => ({ ...prev, [orderId]: true }));
    try {
      const mode = isLive || activeAccountTab === 'live' ? 'live' : 'paper';
      await onCancelOrder?.(orderId, mode);
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
      {/* Header & Mode-Specific Title */}
      <div className="flex items-center justify-between border-b border-[#21262d] pb-3">
        {isLive ? (
          /* Live Trading Mode Header */
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-rose-500/15 border border-rose-500/30 flex items-center justify-center">
              <Lock className="h-4 w-4 text-rose-400" />
            </div>
            <div>
              <h3 className="text-xs font-extrabold uppercase tracking-wider text-white flex items-center gap-2">
                <span>Kalshi Real Exchange Positions & Ledger</span>
                <span className="px-2 py-0.5 text-[9px] font-mono bg-rose-500/20 text-rose-300 border border-rose-500/40 rounded-full font-bold">
                  {livePortfolio?.environment?.toUpperCase() || 'LIVE'} PROD
                </span>
              </h3>
              <p className="text-[11px] text-[#8b949e]">Real-money exchange settlement, manual closing & margin tracking</p>
            </div>
          </div>
        ) : (
          /* Paper Trading Mode Header */
          <div className="flex items-center gap-2">
            <div className="flex bg-[#161b22] p-0.5 rounded-xl border border-[#30363d] text-xs font-semibold">
              <button
                type="button"
                onClick={() => {
                  soundFX.playClickSound();
                  setActiveAccountTab('paper');
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
                  activeAccountTab === 'paper'
                    ? 'bg-[#30363d] text-white font-bold shadow-sm'
                    : 'text-[#8b949e] hover:text-white'
                }`}
              >
                <Layers className="h-3.5 w-3.5 text-blue-400" />
                <span>Predictions Paper Account</span>
                <span className="font-mono text-[11px] text-gray-300 ml-1 font-normal">
                  (${portfolio.equity.toFixed(2)})
                </span>
              </button>
              <button
                type="button"
                onClick={() => {
                  soundFX.playClickSound();
                  setActiveAccountTab('live');
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all ${
                  activeAccountTab === 'live'
                    ? 'bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/40 shadow-sm'
                    : 'text-[#8b949e] hover:text-white'
                }`}
              >
                <Activity className="h-3.5 w-3.5 text-emerald-400" />
                <span>Kalshi Live Account</span>
                {livePortfolio?.is_authenticated && (
                  <span className="font-mono text-[11px] text-emerald-300 ml-1 font-normal">
                    (${livePortfolio.balance_dollars.toFixed(2)})
                  </span>
                )}
              </button>
            </div>
          </div>
        )}

        {livePortfolio && (
          <div className="flex items-center gap-2 text-xs font-mono">
            <span className="text-[#8b949e] text-[10px] hidden sm:inline">
              Synced {new Date(livePortfolio.updated_at).toLocaleTimeString()}
            </span>
          </div>
        )}
      </div>

      {/* Circuit Breaker Tripped Alert Banner (Paper Account Only) */}
      {!isLive && activeAccountTab === 'paper' && isCbTripped && (
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

      {/* LIVE ACCOUNT VIEW (Shown in Live Mode or when Live tab selected in Paper mode) */}
      {(isLive || activeAccountTab === 'live') && (
        <div className="flex flex-col gap-4">
          {/* Live Metrics Row */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 border-b border-[#21262d] pb-4">
            <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-3">
              <div className="text-[11px] font-semibold text-[#8b949e] uppercase">Live Cash Balance</div>
              <div className={`text-lg font-mono font-extrabold mt-0.5 ${
                (livePortfolio?.balance_dollars ?? 0) <= 0.05 ? 'text-amber-400' : 'text-emerald-400'
              }`}>
                ${(livePortfolio?.balance_dollars ?? 0).toFixed(2)}
              </div>
            </div>
            <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-3">
              <div className="text-[11px] font-semibold text-[#8b949e] uppercase">Available Margin</div>
              <div className="text-lg font-mono font-extrabold text-white mt-0.5">
                ${(livePortfolio?.available_margin ?? 0).toFixed(2)}
              </div>
            </div>
            <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-3">
              <div className="text-[11px] font-semibold text-[#8b949e] uppercase">Payout Pending</div>
              <div className="text-lg font-mono font-extrabold text-blue-400 mt-0.5">
                ${(livePortfolio?.payout_pending ?? 0).toFixed(2)}
              </div>
            </div>
            <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-3">
              <div className="text-[11px] font-semibold text-[#8b949e] uppercase">Live Positions</div>
              <div className="text-lg font-mono font-extrabold text-white mt-0.5">
                {livePortfolio?.positions?.filter((p) => p.position > 0 || p.resting_orders_count > 0).length ?? 0}
              </div>
            </div>
          </div>

          {/* Live Exchange Positions Table with Manual Cancel / Close Action */}
          <div>
            {(() => {
              const activeLivePositions = (livePortfolio?.positions || []).filter(
                (p) => p.position > 0 || p.resting_orders_count > 0
              );
              return (
                <>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-white mb-2 flex items-center gap-1.5">
                    <Activity className="h-3.5 w-3.5 text-emerald-400" />
                    <span>Kalshi Live Exchange Positions ({activeLivePositions.length})</span>
                  </h4>

                  {activeLivePositions.length === 0 ? (
                    <div className="text-center py-6 text-xs text-[#8b949e] bg-[#161b22] rounded-xl border border-[#30363d]">
                      No open positions on Kalshi live exchange account.
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs font-mono">
                        <thead>
                          <tr className="text-[#8b949e] border-b border-[#21262d]">
                            <th className="pb-2">Ticker</th>
                            <th className="pb-2">Side</th>
                            <th className="pb-2 text-right">Contracts</th>
                            <th className="pb-2 text-right">Fees Paid</th>
                            <th className="pb-2 text-right">Realized P&L</th>
                            <th className="pb-2 text-right">Resting</th>
                            <th className="pb-2 text-right">Action</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#161b22]">
                          {activeLivePositions.map((pos, idx) => {
                            const isClosing = !!closingTickers[pos.ticker];
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
                                <td className="py-2.5 text-right font-bold text-gray-200">{pos.position ?? 0}</td>
                                <td className="py-2.5 text-right text-gray-400">${pos.fees_paid != null ? pos.fees_paid.toFixed(2) : '0.00'}</td>
                                <td className={`py-2.5 text-right font-bold ${
                                  (pos.realized_pnl ?? 0) >= 0 ? 'text-[#00d084]' : 'text-[#ff4d4d]'
                                }`}>
                                  {(pos.realized_pnl ?? 0) >= 0 ? '+' : ''}${pos.realized_pnl != null ? pos.realized_pnl.toFixed(2) : '0.00'}
                                </td>
                                <td className="py-2.5 text-right text-gray-300">{pos.resting_orders_count ?? 0}</td>
                                <td className="py-2.5 text-right">
                                  <button
                                    type="button"
                                    disabled={isClosing}
                                    onClick={() => handleClose(pos.ticker)}
                                    className="px-2.5 py-1 text-[10px] font-bold rounded-lg bg-red-500/15 hover:bg-red-500/30 text-red-300 border border-red-500/40 transition-all active:scale-95 disabled:opacity-50 inline-flex items-center gap-1 shadow-sm"
                                    title={pos.position > 0 ? `Cancel / Liquidate ${pos.position} contracts on Kalshi Live` : `Dismiss / Cancel record for ${pos.ticker}`}
                                  >
                                    <X className="h-3 w-3" />
                                    <span>{isClosing ? 'Closing...' : (pos.position > 0 ? 'Close' : 'Clear')}</span>
                                  </button>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              );
            })()}
          </div>
        </div>
      )}

      {/* PAPER SIMULATOR VIEW (Only shown in Paper Trading Mode) */}
      {!isLive && activeAccountTab === 'paper' && (
        <div className="flex flex-col gap-4">
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
                {isPnlPositive ? '+' : ''}${(portfolio.realized_pnl ?? 0).toFixed(2)}
              </div>
            </div>

            {/* Unrealized P&L */}
            <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-3">
              <div className="text-[11px] font-semibold text-[#8b949e] uppercase">Unrealized P&L</div>
              <div className={`text-lg font-mono font-extrabold mt-0.5 ${
                (portfolio.unrealized_pnl ?? 0) >= 0 ? 'text-[#00d084]' : 'text-[#ff4d4d]'
              }`}>
                {(portfolio.unrealized_pnl ?? 0) >= 0 ? '+' : ''}${(portfolio.unrealized_pnl ?? 0).toFixed(2)}
              </div>
            </div>

            {/* Win Rate */}
            <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-3">
              <div className="text-[11px] font-semibold text-[#8b949e] uppercase">Win Rate</div>
              <div className="text-lg font-mono font-extrabold text-white mt-0.5 flex items-center gap-1.5">
                <span>{(portfolio.win_rate ?? 0).toFixed(1)}%</span>
                <span className="text-xs text-[#8b949e] font-normal">
                  ({portfolio.wins ?? 0}/{portfolio.total_trades ?? 0})
                </span>
              </div>
            </div>
          </div>

          {/* Active Positions Table (Paper) */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-white mb-2 flex items-center gap-1.5">
              <Wallet className="h-3.5 w-3.5 text-blue-400" />
              <span>Simulated Positions ({(portfolio.positions || []).length})</span>
            </h4>

            {(portfolio.positions || []).length === 0 ? (
              <div className="text-center py-5 text-xs text-[#8b949e] bg-[#161b22] rounded-xl border border-[#30363d]">
                No simulated positions open.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="text-[#8b949e] border-b border-[#21262d]">
                      <th className="pb-2">Contract</th>
                      <th className="pb-2">Side</th>
                      <th className="pb-2 text-right">Size</th>
                      <th className="pb-2 text-right">Entry</th>
                      <th className="pb-2 text-right">Mark</th>
                      <th className="pb-2 text-right">Unrealized</th>
                      <th className="pb-2 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#161b22]">
                    {(portfolio.positions || []).map((pos) => {
                      const isClosing = !!closingTickers[pos.ticker];
                      const isUpnlPositive = (pos.unrealized_pnl ?? 0) >= 0;
                      return (
                        <tr key={pos.ticker} className="hover:bg-[#161b22]/50 transition-colors">
                          <td className="py-2.5 font-bold text-white">{pos.ticker}</td>
                          <td className="py-2.5">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold uppercase ${
                              pos.side === 'yes' ? 'bg-[#00d084]/20 text-[#00d084]' : 'bg-[#ff4d4d]/20 text-[#ff4d4d]'
                            }`}>
                              {pos.side}
                            </span>
                          </td>
                          <td className="py-2.5 text-right font-bold text-gray-200">{pos.size ?? (pos as any).position ?? 0}</td>
                          <td className="py-2.5 text-right text-gray-400">${pos.entry_price != null ? pos.entry_price.toFixed(3) : '0.000'}</td>
                          <td className="py-2.5 text-right text-white font-bold">${pos.current_price != null ? pos.current_price.toFixed(3) : '0.000'}</td>
                          <td className={`py-2.5 text-right font-bold ${
                            isUpnlPositive ? 'text-[#00d084]' : 'text-[#ff4d4d]'
                          }`}>
                            {isUpnlPositive ? '+' : ''}${pos.unrealized_pnl != null ? pos.unrealized_pnl.toFixed(2) : '0.00'}
                          </td>
                          <td className="py-2.5 text-right">
                            <button
                              type="button"
                              disabled={isClosing}
                              onClick={() => handleClose(pos.ticker)}
                              className="px-2.5 py-1 text-[10px] font-bold rounded-lg bg-red-500/10 hover:bg-red-500/25 text-red-400 border border-red-500/30 transition-all active:scale-95 disabled:opacity-50 inline-flex items-center gap-1"
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

          {/* Resting Orders Queue */}
          {openOrders.length > 0 && (
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-white mb-2 flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5 text-amber-400" />
                <span>Resting Orders ({openOrders.length})</span>
              </h4>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="text-[#8b949e] border-b border-[#21262d]">
                      <th className="pb-2">Side</th>
                      <th className="pb-2 text-right">Size</th>
                      <th className="pb-2 text-right">Limit Price</th>
                      <th className="pb-2 text-right">Status</th>
                      <th className="pb-2 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#161b22]">
                    {openOrders.map((ord) => (
                      <tr key={ord.order_id} className="hover:bg-[#161b22]/50 transition-colors">
                        <td className="py-2.5">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold uppercase ${
                            ord.side === 'yes' ? 'bg-[#00d084]/20 text-[#00d084]' : 'bg-[#ff4d4d]/20 text-[#ff4d4d]'
                          }`}>
                            {ord.side}
                          </span>
                        </td>
                        <td className="py-2.5 text-right text-gray-200">{ord.size ?? 0}</td>
                        <td className="py-2.5 text-right text-white font-bold">${ord.limit_price != null ? ord.limit_price.toFixed(3) : '--'}</td>
                        <td className="py-2.5 text-right text-amber-400 uppercase text-[10px] font-bold">
                          {ord.status}
                        </td>
                        <td className="py-2.5 text-right">
                          <button
                            type="button"
                            disabled={!!cancellingOrders[ord.order_id]}
                            onClick={() => handleCancel(ord.order_id)}
                            className="px-2 py-1 text-[10px] font-bold rounded-lg bg-gray-500/10 hover:bg-gray-500/25 text-gray-300 border border-gray-500/30 transition-all active:scale-95 disabled:opacity-50"
                          >
                            {cancellingOrders[ord.order_id] ? 'Cancelling...' : 'Cancel'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Recent Expiration Settlements */}
          {portfolio.settlements && portfolio.settlements.length > 0 && (
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-white mb-2 flex items-center gap-1.5">
                <CheckCircle2 className="h-3.5 w-3.5 text-purple-400" />
                <span>Recent Settlements ({portfolio.settlements.length})</span>
              </h4>
              <div className="overflow-x-auto max-h-48 overflow-y-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="text-[#8b949e] border-b border-[#21262d]">
                      <th className="pb-2">Ticker</th>
                      <th className="pb-2">Side</th>
                      <th className="pb-2 text-right">P&L</th>
                      <th className="pb-2 text-right">Outcome</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#161b22]">
                    {portfolio.settlements.slice(0, 10).map((st, idx) => (
                      <tr key={idx} className="hover:bg-[#161b22]/50 transition-colors">
                        <td className="py-2 text-gray-300">{st.ticker}</td>
                        <td className="py-2">
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${
                            st.side === 'yes' ? 'bg-[#00d084]/20 text-[#00d084]' : 'bg-[#ff4d4d]/20 text-[#ff4d4d]'
                          }`}>
                            {st.side}
                          </span>
                        </td>
                        <td className={`py-2 text-right font-bold ${
                          st.pnl >= 0 ? 'text-[#00d084]' : 'text-[#ff4d4d]'
                        }`}>
                          {st.pnl >= 0 ? '+' : ''}${st.pnl.toFixed(2)}
                        </td>
                        <td className="py-2 text-right">
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${
                            st.outcome === 'win' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                          }`}>
                            {st.outcome}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
