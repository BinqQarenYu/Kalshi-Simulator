import React, { useState } from 'react';
import { Settings, CheckCircle, XCircle, TrendingUp, DollarSign, Activity, Clock, BarChart2, Zap, LayoutDashboard, List, History } from 'lucide-react';
import Decimal from 'decimal.js';

interface MarketMakerViewProps {
  reports: any[];
  tradingMode: 'paper' | 'live';
  portfolio?: any;
}

export const MarketMakerView: React.FC<MarketMakerViewProps> = ({ reports, tradingMode, portfolio }) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'positions' | 'history'>('overview');

  // Filter for Bot 6 trades
  const mmReports = reports.filter(
    (r) => r.bot_type === 'market_maker' || r.bot_type === 'bot6_market_maker' || r.ai_rationale?.includes('MM ') || r.reasoning?.includes('MM ')
  );

  // Calculate KPIs
  const totalTrades = mmReports.length;
  const wins = mmReports.filter((r) => r.outcome === 'win' || r.is_win).length;
  const winRate = totalTrades > 0 ? ((wins / totalTrades) * 100).toFixed(1) : '0.0';
  
  let totalPnL = new Decimal(0);
  mmReports.forEach((r) => {
    totalPnL = totalPnL.plus(new Decimal(r.pnl || r.net_pnl || 0));
  });

  // Calculate Net Inventory across MM trades as proxy if not passing full position array
  let netInventory = 0;
  mmReports.forEach(r => {
    const side = (r.side || r.bot_side)?.toLowerCase();
    const size = parseInt(r.contracts_traded || r.size || '1');
    if (side === 'yes') netInventory += size;
    else if (side === 'no') netInventory -= size;
  });

  const positions = portfolio?.positions ? Object.values(portfolio.positions) : [];
  const totalPositions = positions.length;

  return (
    <div className="flex-1 overflow-y-auto p-8 space-y-6 bg-[#0c0f12]">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Zap className="w-6 h-6 text-purple-400" />
            Bot 6 (Market Maker)
          </h1>
          <p className="text-[#8c9ba5] mt-1 text-sm">
            L2 Depth Spread Capture Engine. High-frequency limit orders.
          </p>
        </div>
      </div>

      {/* TABS */}
      <div className="flex items-center gap-6 border-b border-[#2a3038] mb-6">
        <button
          onClick={() => setActiveTab('overview')}
          className={`pb-2 text-sm font-semibold transition-all border-b-2 ${
            activeTab === 'overview' ? 'text-purple-400 border-purple-400' : 'text-[#8c9ba5] border-transparent hover:text-white'
          } flex items-center gap-2`}
        >
          <LayoutDashboard className="w-4 h-4" />
          Overview
        </button>
        <button
          onClick={() => setActiveTab('positions')}
          className={`pb-2 text-sm font-semibold transition-all border-b-2 ${
            activeTab === 'positions' ? 'text-purple-400 border-purple-400' : 'text-[#8c9ba5] border-transparent hover:text-white'
          } flex items-center gap-2`}
        >
          <List className="w-4 h-4" />
          Positions ({totalPositions})
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={`pb-2 text-sm font-semibold transition-all border-b-2 ${
            activeTab === 'history' ? 'text-purple-400 border-purple-400' : 'text-[#8c9ba5] border-transparent hover:text-white'
          } flex items-center gap-2`}
        >
          <History className="w-4 h-4" />
          Trade History ({totalTrades})
        </button>
      </div>

      {activeTab === 'overview' && (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="bg-[#171c22] rounded-xl p-4 border border-[#2a3038] flex flex-col justify-between">
              <div className="flex items-center justify-between text-[#8c9ba5] mb-2">
                <span className="text-sm font-semibold tracking-wider">TOTAL QUOTES</span>
                <Activity className="w-4 h-4 text-purple-400" />
              </div>
              <span className="text-2xl font-bold text-white">{totalTrades}</span>
            </div>
            
            <div className="bg-[#171c22] rounded-xl p-4 border border-[#2a3038] flex flex-col justify-between">
              <div className="flex items-center justify-between text-[#8c9ba5] mb-2">
                <span className="text-sm font-semibold tracking-wider">WIN RATE</span>
                <TrendingUp className="w-4 h-4 text-purple-400" />
              </div>
              <span className="text-2xl font-bold text-white">{winRate}%</span>
            </div>
            
            <div className="bg-[#171c22] rounded-xl p-4 border border-[#2a3038] flex flex-col justify-between">
              <div className="flex items-center justify-between text-[#8c9ba5] mb-2">
                <span className="text-sm font-semibold tracking-wider">NET P&L</span>
                <DollarSign className="w-4 h-4 text-purple-400" />
              </div>
              <span className={`text-2xl font-bold ${totalPnL.gte(0) ? 'text-[#00f7a7]' : 'text-red-500'}`}>
                ${totalPnL.toFixed(2)}
              </span>
            </div>
            
            <div className="bg-[#171c22] rounded-xl p-4 border border-[#2a3038] flex flex-col justify-between">
              <div className="flex items-center justify-between text-[#8c9ba5] mb-2">
                <span className="text-sm font-semibold tracking-wider">NET INVENTORY</span>
                <BarChart2 className="w-4 h-4 text-purple-400" />
              </div>
              <span className={`text-2xl font-bold ${netInventory === 0 ? 'text-[#8c9ba5]' : netInventory > 0 ? 'text-[#00f7a7]' : 'text-red-500'}`}>
                {netInventory > 0 ? `+${netInventory} YES` : netInventory < 0 ? `${Math.abs(netInventory)} NO` : 'FLAT'}
              </span>
            </div>
          </div>

          {/* Parameters Panel */}
          <div className="bg-[#171c22] rounded-xl p-6 border border-[#2a3038] mb-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Settings className="w-5 h-5 text-purple-400" />
                Bot 6 Parameters (UNBOUND)
              </h2>
              <span className={`px-2 py-1 text-xs font-bold rounded-md ${
                tradingMode === 'live' ? 'bg-[#00f7a7]/20 text-[#00f7a7] border border-[#00f7a7]/30' : 'bg-gray-500/20 text-gray-300 border border-gray-500/30'
              }`}>
                {tradingMode === 'live' ? 'LIVE' : 'PAPER'}
              </span>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
              <div className="p-3 bg-[#0c0f12] rounded-lg border border-[#2a3038]">
                <div className="text-xs text-[#8c9ba5] mb-1">Min Spread</div>
                <div className="font-mono text-white text-sm">2.0 ¢</div>
              </div>
              <div className="p-3 bg-[#0c0f12] rounded-lg border border-[#2a3038]">
                <div className="text-xs text-[#8c9ba5] mb-1">Max Contracts</div>
                <div className="font-mono text-white text-sm">10 (UNBOUND)</div>
              </div>
              <div className="p-3 bg-[#0c0f12] rounded-lg border border-[#2a3038]">
                <div className="text-xs text-[#8c9ba5] mb-1">Inventory Skew</div>
                <div className="font-mono text-purple-400 text-sm">1.0 ¢</div>
              </div>
              <div className="p-3 bg-[#0c0f12] rounded-lg border border-[#2a3038]">
                <div className="text-xs text-[#8c9ba5] mb-1">Vol Multiplier</div>
                <div className="font-mono text-purple-400 text-sm">2.0x</div>
              </div>
              <div className="p-3 bg-[#0c0f12] rounded-lg border border-[#2a3038]">
                <div className="text-xs text-[#8c9ba5] mb-1">Adverse Veto</div>
                <div className="font-mono text-red-400 text-sm">&gt; 3.0% Spike</div>
              </div>
            </div>
          </div>
        </>
      )}

      {activeTab === 'positions' && (
        <div className="bg-[#171c22] rounded-xl border border-[#2a3038] overflow-hidden">
          <div className="px-6 py-4 border-b border-[#2a3038] flex items-center justify-between bg-[#0c0f12]/50">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-purple-400" />
              Open Positions ({totalPositions})
            </h3>
            <span className="text-xs text-[#8c9ba5]">Click a row for details</span>
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-[#8c9ba5]">
              <thead className="bg-[#0c0f12] text-xs uppercase font-semibold border-b border-[#2a3038]">
                <tr>
                  <th className="px-6 py-4">MARKET ID</th>
                  <th className="px-6 py-4">OUTCOME</th>
                  <th className="px-6 py-4">SIZE</th>
                  <th className="px-6 py-4">AVG PRICE</th>
                  <th className="px-6 py-4">REALIZED PNL</th>
                  <th className="px-6 py-4">UNREALIZED PNL</th>
                  <th className="px-6 py-4">TOTAL PNL</th>
                </tr>
              </thead>
              <tbody>
                {positions.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-6 py-8 text-center text-[#8c9ba5]">
                      No open positions holding inventory.
                    </td>
                  </tr>
                ) : (
                  positions.map((pos: any, idx: number) => {
                    const realized = 0.00;
                    const unrealized = Number(pos.unrealized_pnl || 0);
                    const total = realized + unrealized;
                    return (
                      <tr key={idx} className="border-b border-[#2a3038]/50 hover:bg-[#2a3038]/30 transition-colors cursor-pointer">
                        <td className="px-6 py-4 font-mono text-white">{pos.ticker}</td>
                        <td className="px-6 py-4">
                          <span className={`font-bold ${pos.side?.toLowerCase() === 'yes' ? 'text-[#00f7a7]' : 'text-red-500'}`}>
                            {pos.side?.toUpperCase() || 'YES'}
                          </span>
                        </td>
                        <td className="px-6 py-4 font-mono text-white">{pos.size}.0</td>
                        <td className="px-6 py-4 font-mono">${Number(pos.avg_entry_price || 0).toFixed(4)}</td>
                        <td className="px-6 py-4 font-mono text-[#00f7a7]">${realized.toFixed(2)}</td>
                        <td className={`px-6 py-4 font-mono ${unrealized >= 0 ? 'text-[#00f7a7]' : 'text-red-500'}`}>
                          {unrealized >= 0 ? '+' : ''}${unrealized.toFixed(2)}
                        </td>
                        <td className={`px-6 py-4 font-mono ${total >= 0 ? 'text-[#00f7a7]' : 'text-red-500'}`}>
                          {total >= 0 ? '+' : ''}${total.toFixed(2)}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'history' && (
        <div className="bg-[#171c22] rounded-xl border border-[#2a3038] overflow-hidden">
          <div className="px-6 py-4 border-b border-[#2a3038] flex items-center justify-between bg-[#0c0f12]/50">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Clock className="w-4 h-4 text-purple-400" />
              Bot 6 MM Execution Tape ({totalTrades})
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
                </tr>
              </thead>
              <tbody>
                {mmReports.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-[#8c9ba5]">
                      No Bot 6 Market Making trades found. Waiting for spread edge...
                    </td>
                  </tr>
                ) : (
                  mmReports.sort((a, b) => new Date(b.timestamp || b.cycle_time).getTime() - new Date(a.timestamp || a.cycle_time).getTime()).map((report, idx) => (
                    <tr key={idx} className="border-b border-[#2a3038]/50 hover:bg-[#2a3038]/30 transition-colors">
                      <td className="px-4 py-3 font-mono text-xs">{new Date(report.timestamp || report.cycle_time).toLocaleString()}</td>
                      <td className="px-4 py-3 font-mono text-white">{report.ticker}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                          (report.side || report.bot_side)?.toLowerCase() === 'yes' ? 'bg-[#00f7a7]/20 text-[#00f7a7]' : 'bg-red-500/20 text-red-500'
                        }`}>
                          {(report.side || report.bot_side)?.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono">{report.entry_price ? `$${Number(report.entry_price).toFixed(2)}` : '-'}</td>
                      <td className="px-4 py-3">
                        {report.outcome === 'win' || report.is_win ? (
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
                        Number(report.pnl || report.net_pnl || 0) >= 0 ? 'text-[#00f7a7]' : 'text-red-500'
                      }`}>
                        {Number(report.pnl || report.net_pnl || 0) >= 0 ? '+' : ''}${Number(report.pnl || report.net_pnl || 0).toFixed(2)}
                      </td>
                      <td className="px-4 py-3 text-xs">{report.bot_type || 'Bot 6 MM'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
