import React, { useState, useEffect } from 'react';
import { Target, Zap, Clock, Activity, AlertCircle, RefreshCw, Power } from 'lucide-react';

export const ArbitrageRadarView: React.FC = () => {
  const [radarData, setRadarData] = useState<any>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/api/state');
        if (res.ok) {
          const data = await res.json();
          setRadarData(data.arbitrage_radar);
        }
      } catch (err) {
        console.error('Failed to fetch radar state:', err);
      }
    };
    
    fetchData();
    const intv = setInterval(fetchData, 2000);
    return () => clearInterval(intv);
  }, []);

  const toggleArbitrage = async () => {
    try {
      await fetch('/api/arbitrage/toggle', { method: 'POST' });
    } catch (err) {
      console.error('Failed to toggle:', err);
    }
  };

  const isEnabled = radarData?.enabled !== false;

  return (
    <div className="flex flex-col h-full bg-[#0a0f16] text-[#cdd9e5] p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center bg-[#111720] border border-[#1f2937] p-4 rounded-xl">
        <div className="flex items-center gap-4">
          <div className={`w-12 h-12 rounded-full flex items-center justify-center ${isEnabled ? 'bg-amber-500/20' : 'bg-red-500/20'}`}>
            <Zap className={`w-6 h-6 ${isEnabled ? 'text-amber-400' : 'text-red-400'}`} />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Cross-Exchange Arbitrage Radar</h1>
            <p className="text-[#8c9ba5] text-sm">Live multi-leg routing matrix (Kalshi / Polymarket / Binance). Target EV spread threshold: {'>='} 3¢.</p>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <button 
            onClick={toggleArbitrage}
            className={`px-4 py-2 flex items-center gap-2 rounded-lg font-bold text-sm transition-all border ${
              isEnabled 
                ? 'bg-red-500/10 text-red-400 border-red-500/30 hover:bg-red-500/20' 
                : 'bg-green-500/10 text-green-400 border-green-500/30 hover:bg-green-500/20'
            }`}
          >
            <Power className="w-4 h-4" />
            {isEnabled ? 'STOP ARBITRAGE' : 'START ARBITRAGE'}
          </button>
          <div className="flex items-center gap-3 px-4 py-2 bg-[#1a212b] rounded-lg border border-[#2d3748]">
             <Activity className={`w-4 h-4 ${isEnabled ? 'text-cyan-400 animate-pulse' : 'text-red-400'}`} />
             <span className="font-mono text-sm">
               {!isEnabled ? (
                 <span className="text-red-400">PAUSED</span>
               ) : radarData && radarData.opportunities && radarData.opportunities.length > 0 ? (
                 <span className="text-green-400 font-bold">MISPRICING DETECTED</span>
               ) : (
                 <span className="text-amber-400">SCANNING (NO ARB)</span>
               )}
             </span>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Active Spread Panel */}
        <div className="bg-[#111720] border border-[#1f2937] rounded-xl flex flex-col">
          <div className="px-4 py-3 border-b border-[#1f2937] flex items-center gap-2">
            <Target className="w-4 h-4 text-[#00c978]" />
            <h2 className="font-semibold text-white">Live Spread Targets</h2>
          </div>
          
          <div className="p-4 flex-1 flex flex-col gap-4 overflow-y-auto">
            {!isEnabled ? (
              <div className="flex flex-col items-center justify-center py-12 text-[#8c9ba5] space-y-4">
                <Power className="w-8 h-8 text-red-500/50" />
                <p>Scanner offline. Capital protection mode active.</p>
              </div>
            ) : (!radarData || (!radarData.opportunities?.length)) ? (
              <div className="flex flex-col items-center justify-center py-12 text-[#8c9ba5] space-y-4">
                <RefreshCw className="w-8 h-8 animate-spin text-[#374151]" />
                <p>Tracking {(radarData?.markets_tracked || 0)} markets across Kalshi, Polymarket, and Binance (Awaiting Option Parity Match).</p>
              </div>
            ) : (
              radarData.opportunities.map((opp: any, idx: number) => (
                <div key={idx} className="bg-[#17212b] border border-[#2d3748] rounded-lg p-4">
                  <div className="flex justify-between items-center mb-3">
                    <span className="font-bold text-white">{opp.type}</span>
                    <span className="text-green-400 font-mono font-bold">Profit: {parseFloat(opp.net_profit).toFixed(4)}¢</span>
                  </div>
                  <div className="text-sm text-[#8c9ba5] font-mono">
                    [Leg 1] Kalshi YES: {opp.kalshi_leg} <br />
                    [Leg 2] Polymarket NO: {opp.pm_leg} <br />
                    Total Cost: {opp.total_cost}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* System Logs Panel */}
        <div className="bg-[#111720] border border-[#1f2937] rounded-xl flex flex-col">
          <div className="px-4 py-3 border-b border-[#1f2937] flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-cyan-400" />
            <h2 className="font-semibold text-white">Atomic Router Engine</h2>
          </div>
          <div className="p-4 flex-1 text-sm font-mono text-[#8c9ba5]">
            <p className="mb-2">{'>'} Initializing Atomic Router (Phase 3)...</p>
            <p className="mb-2">{'>'} Binance Prediction Mapping Status: <span className="text-amber-400">{radarData?.binance_status || 'Awaiting'}</span></p>
            <p className="mb-2">{'>'} Kalshi Taker Fee Base: 2¢ (Capped)</p>
            <p className="mb-2">{'>'} Polymarket Maker Fee: 0¢</p>
            <p className="mb-2">{'>'} Execution sequence locked: Maker (PM) first, Taker (Kalshi) on fill.</p>
          </div>
        </div>

      </div>
    </div>
  );
};
