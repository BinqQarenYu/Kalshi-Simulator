import React from 'react';
import { Timer, CheckCircle, XCircle, TrendingUp, DollarSign, Activity, Settings, Clock, BarChart2 } from 'lucide-react';
import Decimal from 'decimal.js';

interface SprintBotViewProps {
  reports: any[];
  tradingMode: 'paper' | 'live';
}

export const SprintBotView: React.FC<SprintBotViewProps> = ({ reports, tradingMode }) => {
  // Filter for 5M reports
  const sprintReports = reports.filter(
    (r) => r.timeframe === '5m' || (r.ticker?.includes('5M') && !r.ticker?.includes('15M'))
  );

  // Calculate KPIs
  const totalTrades = sprintReports.length;
  const wins = sprintReports.filter((r) => r.is_win).length;
  const winRate = totalTrades > 0 ? ((wins / totalTrades) * 100).toFixed(1) : '0.0';
  
  const netPnL = sprintReports.reduce((sum, r) => {
    return sum.plus(new Decimal(r.pnl || 0));
  }, new Decimal(0));
  
  const avgTrade = totalTrades > 0 ? netPnL.dividedBy(totalTrades) : new Decimal(0);

  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-[#171c22] rounded-xl p-4 border border-[#2a3038] flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#8c9ba5] mb-2">
            <span className="text-sm font-semibold tracking-wider">TOTAL TRADES</span>
            <Activity className="w-4 h-4" />
          </div>
          <span className="text-2xl font-bold text-white">{totalTrades}</span>
        </div>
        
        <div className="bg-[#171c22] rounded-xl p-4 border border-[#2a3038] flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#8c9ba5] mb-2">
            <span className="text-sm font-semibold tracking-wider">WIN RATE</span>
            <TrendingUp className="w-4 h-4" />
          </div>
          <span className="text-2xl font-bold text-white">{winRate}%</span>
        </div>
        
        <div className="bg-[#171c22] rounded-xl p-4 border border-[#2a3038] flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#8c9ba5] mb-2">
            <span className="text-sm font-semibold tracking-wider">NET P&L</span>
            <DollarSign className="w-4 h-4" />
          </div>
          <span className={`text-2xl font-bold ${netPnL.gte(0) ? 'text-[#00f7a7]' : 'text-red-500'}`}>
            ${netPnL.toFixed(2)}
          </span>
        </div>
        
        <div className="bg-[#171c22] rounded-xl p-4 border border-[#2a3038] flex flex-col justify-between">
          <div className="flex items-center justify-between text-[#8c9ba5] mb-2">
            <span className="text-sm font-semibold tracking-wider">AVG TRADE</span>
            <BarChart2 className="w-4 h-4" />
          </div>
          <span className={`text-2xl font-bold ${avgTrade.gte(0) ? 'text-[#00f7a7]' : 'text-red-500'}`}>
            ${avgTrade.toFixed(2)}
          </span>
        </div>
      </div>

      {/* Parameters Panel */}
      <div className="bg-[#171c22] rounded-xl p-6 border border-[#2a3038]">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Settings className="w-5 h-5 text-orange-400" />
            Bot 5 Parameters
          </h2>
          <span className={`px-2 py-1 text-xs font-bold rounded-md ${
            tradingMode === 'live' ? 'bg-[#00f7a7]/20 text-[#00f7a7] border border-[#00f7a7]/30' : 'bg-gray-500/20 text-gray-300 border border-gray-500/30'
          }`}>
            {tradingMode === 'live' ? 'LIVE' : 'PAPER'}
          </span>
        </div>
        
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <div className="p-3 bg-[#0c0f12] rounded-lg border border-[#2a3038]">
            <div className="text-xs text-[#8c9ba5] mb-1">Cycle Duration</div>
            <div className="font-mono text-white text-sm">300s (5m)</div>
          </div>
          <div className="p-3 bg-[#0c0f12] rounded-lg border border-[#2a3038]">
            <div className="text-xs text-[#8c9ba5] mb-1">Max Contracts</div>
            <div className="font-mono text-white text-sm">1 / Trade</div>
          </div>
          <div className="p-3 bg-[#0c0f12] rounded-lg border border-[#2a3038]">
            <div className="text-xs text-[#8c9ba5] mb-1">Playbook Phases</div>
            <div className="font-mono text-white text-[10px] leading-tight">
              P1 (200-300s)<br/>
              P2 (80-200s)<br/>
              P3 (20-80s)<br/>
              Lock (&lt;20s)
            </div>
          </div>
          <div className="p-3 bg-[#0c0f12] rounded-lg border border-[#2a3038]">
            <div className="text-xs text-[#8c9ba5] mb-1">VPIN Threshold</div>
            <div className="font-mono text-white text-sm">0.65</div>
          </div>
          <div className="p-3 bg-[#0c0f12] rounded-lg border border-[#2a3038]">
            <div className="text-xs text-[#8c9ba5] mb-1">Min Edge</div>
            <div className="font-mono text-[#00f7a7] text-sm">1.5%</div>
          </div>
          <div className="p-3 bg-[#0c0f12] rounded-lg border border-[#2a3038]">
            <div className="text-xs text-[#8c9ba5] mb-1">Circuit Breaker</div>
            <div className="font-mono text-red-400 text-sm">25% DD</div>
          </div>
        </div>
      </div>

      {/* Trade History */}
      <div className="bg-[#171c22] rounded-xl border border-[#2a3038] overflow-hidden">
        <div className="px-6 py-4 border-b border-[#2a3038] flex items-center justify-between bg-[#0c0f12]/50">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Clock className="w-4 h-4 text-[#8c9ba5]" />
            5M Sprint Trade History
          </h3>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-[#8c9ba5]">
            <thead className="bg-[#0c0f12] text-xs uppercase font-semibold border-b border-[#2a3038]">
              <tr>
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3">Ticker</th>
                <th className="px-4 py-3">Side</th>
                <th className="px-4 py-3">Entry</th>
                <th className="px-4 py-3">Outcome</th>
                <th className="px-4 py-3">P&L</th>
                <th className="px-4 py-3">Bot Type</th>
                <th className="px-4 py-3">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {sprintReports.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-[#8c9ba5]">
                    No 5M Sprint trades found.
                  </td>
                </tr>
              ) : (
                sprintReports.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()).map((report, idx) => (
                  <tr key={idx} className="border-b border-[#2a3038]/50 hover:bg-[#2a3038]/30 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs">{new Date(report.timestamp).toLocaleString()}</td>
                    <td className="px-4 py-3 font-mono text-white">{report.ticker}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                        report.side === 'yes' ? 'bg-[#00f7a7]/20 text-[#00f7a7]' : 'bg-red-500/20 text-red-500'
                      }`}>
                        {report.side?.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono">{report.entry_price ? `$${report.entry_price.toFixed(2)}` : '-'}</td>
                    <td className="px-4 py-3">
                      {report.is_win ? (
                        <span className="flex items-center gap-1 text-[#00f7a7] text-xs font-bold">
                          <CheckCircle className="w-3 h-3" /> WIN
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-red-500 text-xs font-bold">
                          <XCircle className="w-3 h-3" /> LOSS
                        </span>
                      )}
                    </td>
                    <td className={`px-4 py-3 font-mono font-bold ${
                      Number(report.pnl) >= 0 ? 'text-[#00f7a7]' : 'text-red-500'
                    }`}>
                      {Number(report.pnl) >= 0 ? '+' : ''}${Number(report.pnl || 0).toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-xs">{report.bot_type || 'Sprint'}</td>
                    <td className="px-4 py-3 font-mono">{report.ai_confidence ? `${(report.ai_confidence * 100).toFixed(0)}%` : '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
