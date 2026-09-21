import React, { useState, useEffect } from 'react';
import { Target, Zap, Activity, AlertCircle, RefreshCw, Power } from 'lucide-react';

export const ArbitrageRadarView: React.FC = () => {
  const [radarData, setRadarData] = useState<any>(null);
  const [isToggling, setIsToggling] = useState<boolean>(false);

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
    setIsToggling(true);
    try {
      await fetch('/api/arbitrage/toggle', { method: 'POST' });
    } catch (err) {
      console.error('Failed to toggle:', err);
    } finally {
      setIsToggling(false);
    }
  };

  const isEnabled = radarData?.enabled !== false;
  const hasOpps = radarData && radarData.opportunities && radarData.opportunities.length > 0;

  const statusMessage = !isEnabled
    ? 'Arbitrage scanner paused'
    : hasOpps
    ? 'Mispricing opportunity detected across exchange legs'
    : 'Scanning markets for option parity mispricing';

  return (
    <div className="flex flex-col h-full bg-[#0a0f16] text-[#cdd9e5] p-6 space-y-6 font-mono text-xs">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center bg-[#111720] border border-[#1f2937] p-4 rounded-xl gap-4 shadow-lg">
        <div className="flex items-center gap-4">
          <div
            className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors ${
              isEnabled ? 'bg-amber-500/20 border border-amber-500/40' : 'bg-red-500/20 border border-red-500/40'
            }`}
            aria-hidden="true"
          >
            <Zap className={`w-6 h-6 ${isEnabled ? 'text-amber-400' : 'text-red-400'}`} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight font-sans">Cross-Exchange Arbitrage Radar</h1>
            <p className="text-[#8c9ba5] text-xs font-mono mt-0.5">
              Live multi-leg routing matrix (Kalshi / Polymarket / Binance). Target EV spread threshold: <span className="font-bold text-amber-300">&ge; 3&cent;</span>.
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-3 self-end sm:self-auto">
          <button 
            type="button"
            onClick={toggleArbitrage}
            disabled={isToggling}
            aria-label={isEnabled ? 'Stop cross-exchange arbitrage scanner' : 'Start cross-exchange arbitrage scanner'}
            className={`px-4 py-2 flex items-center gap-2 rounded-lg font-bold text-xs transition-all border cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 disabled:opacity-50 ${
              isEnabled 
                ? 'bg-red-500/10 text-red-400 border-red-500/30 hover:bg-red-500/20' 
                : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20'
            }`}
          >
            {isToggling ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Power className="w-4 h-4" />}
            <span>{isEnabled ? 'STOP ARBITRAGE' : 'START ARBITRAGE'}</span>
          </button>

          <div
            role="status"
            aria-live="polite"
            aria-label={`Scanner status: ${statusMessage}`}
            className="flex items-center gap-2.5 px-3.5 py-2 bg-[#1a212b] rounded-lg border border-[#2d3748]"
          >
             <Activity className={`w-4 h-4 shrink-0 ${isEnabled ? 'text-cyan-400 animate-pulse' : 'text-red-400'}`} aria-hidden="true" />
             <span className="font-mono text-xs font-bold tabular-nums">
               {!isEnabled ? (
                 <span className="text-red-400">PAUSED</span>
               ) : hasOpps ? (
                 <span className="text-emerald-400">MISPRICING DETECTED</span>
               ) : (
                 <span className="text-amber-400">SCANNING (NO ARB)</span>
               )}
             </span>
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 flex-1">
        
        {/* Active Spread Panel */}
        <div className="bg-[#111720] border border-[#1f2937] rounded-xl flex flex-col shadow-md">
          <div className="px-4 py-3 border-b border-[#1f2937] flex items-center gap-2">
            <Target className="w-4 h-4 text-emerald-400 shrink-0" aria-hidden="true" />
            <h2 className="font-bold text-white text-xs uppercase tracking-wider">Live Spread Targets</h2>
          </div>
          
          <div className="p-4 flex-1 flex flex-col gap-4 overflow-y-auto min-h-[220px]">
            {!isEnabled ? (
              <div className="flex flex-col items-center justify-center my-auto text-[#8c9ba5] space-y-3 py-8">
                <Power className="w-8 h-8 text-red-500/50" aria-hidden="true" />
                <p className="text-xs font-mono text-center">Scanner offline. Capital protection mode active.</p>
              </div>
            ) : (!radarData || (!radarData.opportunities?.length)) ? (
              <div className="flex flex-col items-center justify-center my-auto text-[#8c9ba5] space-y-3 py-8">
                <RefreshCw className="w-8 h-8 animate-spin text-[#374151]" aria-hidden="true" />
                <p className="text-xs font-mono text-center max-w-xs">
                  Tracking <span className="text-cyan-300 font-bold tabular-nums">{radarData?.markets_tracked || 0}</span> markets across Kalshi, Polymarket, and Binance (Awaiting Option Parity Match).
                </p>
              </div>
            ) : (
              radarData.opportunities.map((opp: any, idx: number) => (
                <div key={idx} className="bg-[#17212b] border border-[#2d3748] rounded-lg p-3.5 space-y-2">
                  <div className="flex justify-between items-center border-b border-[#262d35] pb-2">
                    <span className="font-bold text-white text-xs">{opp.type || 'Cross-Leg Spread'}</span>
                    <span className="text-emerald-400 font-mono font-bold text-xs tabular-nums">
                      Profit: +{parseFloat(opp.net_profit || '0').toFixed(4)}&cent;
                    </span>
                  </div>
                  <div className="text-xs text-[#8c9ba5] font-mono space-y-1">
                    <div className="flex justify-between">
                      <span>[Leg 1] Kalshi YES:</span>
                      <span className="text-slate-200 font-bold tabular-nums">{opp.kalshi_leg}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>[Leg 2] Polymarket NO:</span>
                      <span className="text-slate-200 font-bold tabular-nums">{opp.pm_leg}</span>
                    </div>
                    <div className="flex justify-between pt-1 border-t border-white/5 text-[11px]">
                      <span>Total Cost:</span>
                      <span className="text-amber-300 font-bold tabular-nums">{opp.total_cost}</span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* System Logs Panel */}
        <div className="bg-[#111720] border border-[#1f2937] rounded-xl flex flex-col shadow-md">
          <div className="px-4 py-3 border-b border-[#1f2937] flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-cyan-400 shrink-0" aria-hidden="true" />
            <h2 className="font-bold text-white text-xs uppercase tracking-wider">Atomic Router Engine</h2>
          </div>
          <div className="p-4 flex-1 text-xs font-mono text-[#8c9ba5] space-y-2.5">
            <p className="flex items-center gap-1.5">
              <span className="text-cyan-400 font-bold">&gt;</span> Initializing Atomic Router (Phase 3)...
            </p>
            <p className="flex items-center gap-1.5">
              <span className="text-cyan-400 font-bold">&gt;</span> Binance Prediction Mapping Status:
              <span className="text-amber-400 font-bold ml-1">{radarData?.binance_status || 'Awaiting'}</span>
            </p>
            <p className="flex items-center gap-1.5">
              <span className="text-cyan-400 font-bold">&gt;</span> Kalshi Taker Fee Base: <span className="text-slate-200 tabular-nums">2&cent;</span> (Capped)
            </p>
            <p className="flex items-center gap-1.5">
              <span className="text-cyan-400 font-bold">&gt;</span> Polymarket Maker Fee: <span className="text-emerald-400 tabular-nums">0&cent;</span>
            </p>
            <p className="flex items-center gap-1.5">
              <span className="text-cyan-400 font-bold">&gt;</span> Execution sequence locked: Maker (PM) first, Taker (Kalshi) on fill.
            </p>
          </div>
        </div>

      </div>
    </div>
  );
};
