import React from 'react';
import { BarChart3, Cpu, Crown, Layers, Radio, Zap } from 'lucide-react';
import { SystemComparisonItem, SystemFilter } from './AnalyticsTypes';

interface MultiBotEfficiencyTableProps {
  systemComparison: SystemComparisonItem[];
  selectedSystem: SystemFilter;
  setSelectedSystem: (system: SystemFilter) => void;
}

export const MultiBotEfficiencyTable: React.FC<MultiBotEfficiencyTableProps> = ({
  systemComparison,
  selectedSystem,
  setSelectedSystem,
}) => {
  return (
    <div className="bg-slate-900/95 border border-slate-800 rounded-2xl p-4 sm:p-5 shadow-xl space-y-3.5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="h-8 w-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
            <BarChart3 className="h-4 w-4 text-emerald-400" />
          </div>
          <div>
            <h3 className="text-sm sm:text-base font-extrabold text-white flex items-center gap-2">
              <span>Multi-Bot Profitability & Efficiency Benchmark</span>
              <span className="px-2 py-0.5 text-[10px] font-mono bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 rounded-full font-bold">
                SIDE-BY-SIDE AUDIT
              </span>
            </h3>
            <p className="text-xs text-slate-400">
              Direct comparative performance across quantitative playbooks, deep neural models, and live fills.
            </p>
          </div>
        </div>
        <div className="text-[11px] text-slate-400 font-mono flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>SQLite WAL Sync Active</span>
        </div>
      </div>

      {/* Efficiency Summary Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px] font-bold tracking-wider">
              <th className="py-2.5 px-3">System / Strategy</th>
              <th className="py-2.5 px-3">Execution Mode</th>
              <th className="py-2.5 px-3 text-center">Trades (W/L)</th>
              <th className="py-2.5 px-3 text-right">Win Rate %</th>
              <th className="py-2.5 px-3 text-right">Net Realized P&L</th>
              <th className="py-2.5 px-3 text-right">Profit Factor</th>
              <th className="py-2.5 px-3 text-right">Expectancy / Trade</th>
              <th className="py-2.5 px-3 text-right">Sharpe Ratio</th>
              <th className="py-2.5 px-3 text-right">Max Drawdown</th>
              <th className="py-2.5 px-3 text-center">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono">
            {systemComparison.map((item) => {
              const m = item.metrics;
              const isSelected = selectedSystem === item.key;
              const isMostProfitable = item.key === '3_step_domination_bot' && m && m.net_pnl > 0;

              return (
                <tr
                  key={item.key}
                  onClick={() => setSelectedSystem(item.key)}
                  className={`cursor-pointer transition-colors ${
                    isSelected
                      ? 'bg-emerald-500/10 border-l-2 border-emerald-400'
                      : 'hover:bg-slate-800/50'
                  }`}
                >
                  <td className="py-3 px-3 font-sans">
                    <div className="flex items-center gap-2">
                      {item.icon === 'crown' && <Crown className="w-4 h-4 text-emerald-400 shrink-0" />}
                      {item.icon === 'zap' && <Zap className="w-4 h-4 text-amber-400 shrink-0" />}
                      {item.icon === 'cpu' && <Cpu className="w-4 h-4 text-purple-400 shrink-0" />}
                      {item.icon === 'radio' && <Radio className="w-4 h-4 text-rose-400 shrink-0 animate-pulse" />}
                      {item.icon === 'layers' && <Layers className="w-4 h-4 text-blue-400 shrink-0" />}
                      <div>
                        <div className="font-bold text-white flex items-center gap-1.5">
                          <span>{item.label}</span>
                          {isMostProfitable && (
                            <span className="px-1.5 py-0.2 text-[9px] font-bold bg-amber-400/20 text-amber-300 border border-amber-400/40 rounded-full">
                              🏆 HIGHEST PROFIT
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-slate-400 font-normal">{item.sublabel}</div>
                      </div>
                    </div>
                  </td>
                  <td className="py-3 px-3 font-sans">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        item.key === 'live'
                          ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                          : 'bg-blue-500/20 text-blue-300 border border-blue-500/40'
                      }`}
                    >
                      {item.key === 'live' ? 'REAL MONEY' : 'PAPER SIM'}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-center text-slate-200">
                    {m ? `${m.total_trades} (${m.wins}W / ${m.losses}L)` : '--'}
                  </td>
                  <td className="py-3 px-3 text-right font-bold text-white">
                    {m && m.total_trades > 0 && m.win_rate_pct != null ? `${m.win_rate_pct.toFixed(1)}%` : '0.0%'}
                  </td>
                  <td
                    className={`py-3 px-3 text-right font-bold text-sm ${
                      m && m.net_pnl > 0 ? 'text-emerald-400' : m && m.net_pnl < 0 ? 'text-rose-400' : 'text-slate-400'
                    }`}
                  >
                    {m && m.net_pnl != null ? `${m.net_pnl >= 0 ? '+' : ''}$${m.net_pnl.toFixed(2)}` : '$0.00'}
                  </td>
                  <td className="py-3 px-3 text-right font-bold text-cyan-400">
                    {m && m.total_trades > 0 && m.profit_factor != null ? m.profit_factor.toFixed(2) : '1.00'}
                  </td>
                  <td className="py-3 px-3 text-right text-emerald-400 font-semibold">
                    {m && m.total_trades > 0 && m.expectancy_per_trade != null
                      ? `${m.expectancy_per_trade >= 0 ? '+' : ''}$${m.expectancy_per_trade.toFixed(2)}`
                      : '$0.00'}
                  </td>
                  <td className="py-3 px-3 text-right text-blue-400">
                    {m && m.total_trades > 0 && m.sharpe_ratio != null ? m.sharpe_ratio.toFixed(2) : '0.00'}
                  </td>
                  <td className="py-3 px-3 text-right text-rose-400">
                    {m && m.total_trades > 0 && m.max_drawdown_pct != null ? `${m.max_drawdown_pct.toFixed(2)}%` : '0.00%'}
                  </td>
                  <td className="py-3 px-3 text-center font-sans">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedSystem(item.key);
                      }}
                      className={`px-2.5 py-1 text-[11px] font-bold rounded-lg transition ${
                        isSelected
                          ? 'bg-emerald-500 text-black font-extrabold shadow-sm'
                          : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                      }`}
                    >
                      {isSelected ? 'Active View' : 'Isolate Bot'}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
