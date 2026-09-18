import React from 'react';
import { Activity, Award, DollarSign, Percent, ShieldAlert, TrendingUp } from 'lucide-react';
import { PortfolioMetrics } from './AnalyticsTypes';

interface AnalyticsKpiCardsProps {
  metrics: PortfolioMetrics | null;
}

export const AnalyticsKpiCards: React.FC<AnalyticsKpiCardsProps> = ({ metrics }) => {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-xl shadow-sm">
        <div className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5 uppercase">
          <Award className="w-3.5 h-3.5 text-amber-400" /> SHARPE RATIO
        </div>
        <div className="text-lg sm:text-xl font-bold text-emerald-400 mt-1 font-mono">
          {metrics?.sharpe_ratio != null ? metrics.sharpe_ratio.toFixed(2) : '--'}
        </div>
        <div className="text-[10px] text-slate-500 mt-0.5">365-Day 15M Annualized</div>
      </div>

      <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-xl shadow-sm">
        <div className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5 uppercase">
          <TrendingUp className="w-3.5 h-3.5 text-emerald-400" /> SORTINO RATIO
        </div>
        <div className="text-lg sm:text-xl font-bold text-emerald-400 mt-1 font-mono">
          {metrics?.sortino_ratio != null ? metrics.sortino_ratio.toFixed(2) : '--'}
        </div>
        <div className="text-[10px] text-slate-500 mt-0.5">Downside Risk Guard</div>
      </div>

      <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-xl shadow-sm">
        <div className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5 uppercase">
          <Percent className="w-3.5 h-3.5 text-blue-400" /> WIN RATE
        </div>
        <div className="text-lg sm:text-xl font-bold text-white mt-1 font-mono">
          {metrics?.win_rate_pct != null ? `${metrics.win_rate_pct.toFixed(1)}%` : '--'}
        </div>
        <div className="text-[10px] text-slate-500 mt-0.5">
          {metrics ? `${metrics.wins ?? 0}W / ${metrics.losses ?? 0}L (${metrics.total_trades ?? 0} cycles)` : '--'}
        </div>
      </div>

      <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-xl shadow-sm">
        <div className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5 uppercase">
          <ShieldAlert className="w-3.5 h-3.5 text-rose-400" /> MAX DRAWDOWN
        </div>
        <div className="text-lg sm:text-xl font-bold text-rose-400 mt-1 font-mono">
          {metrics?.max_drawdown_pct != null ? `${metrics.max_drawdown_pct.toFixed(2)}%` : '--'}
        </div>
        <div className="text-[10px] text-slate-500 mt-0.5">15% Gate Threshold</div>
      </div>

      <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-xl shadow-sm">
        <div className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5 uppercase">
          <Activity className="w-3.5 h-3.5 text-cyan-400" /> PROFIT FACTOR
        </div>
        <div className="text-lg sm:text-xl font-bold text-cyan-400 mt-1 font-mono">
          {metrics?.profit_factor != null ? metrics.profit_factor.toFixed(2) : '--'}
        </div>
        <div className="text-[10px] text-slate-500 mt-0.5">
          {metrics?.payoff_ratio != null ? `Payoff: ${metrics.payoff_ratio.toFixed(2)}x` : '--'}
        </div>
      </div>

      <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-xl shadow-sm">
        <div className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5 uppercase">
          <DollarSign className="w-3.5 h-3.5 text-emerald-400" /> NET REALIZED P&L
        </div>
        <div
          className={`text-lg sm:text-xl font-bold mt-1 font-mono ${
            metrics && (metrics.net_pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
          }`}
        >
          {metrics?.net_pnl != null ? `${metrics.net_pnl >= 0 ? '+' : ''}$${metrics.net_pnl.toFixed(2)}` : '--'}
        </div>
        <div className="text-[10px] text-slate-500 mt-0.5">
          {metrics?.total_roi_pct != null ? `ROI: ${metrics.total_roi_pct >= 0 ? '+' : ''}${metrics.total_roi_pct.toFixed(1)}%` : '--'}
        </div>
      </div>
    </div>
  );
};
