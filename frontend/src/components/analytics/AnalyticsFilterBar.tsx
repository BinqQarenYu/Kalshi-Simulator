import React from 'react';
import { Search } from 'lucide-react';
import { SubTabType } from './AnalyticsTypes';

interface AnalyticsFilterBarProps {
  activeSubTab: SubTabType;
  searchTerm: string;
  setSearchTerm: (term: string) => void;
  botFilter: string;
  setBotFilter: (bot: any) => void;
  sideFilter: 'all' | 'yes' | 'no';
  setSideFilter: (side: 'all' | 'yes' | 'no') => void;
  outcomeFilter: 'all' | 'win' | 'loss' | 'flat';
  setOutcomeFilter: (outcome: 'all' | 'win' | 'loss' | 'flat') => void;
}

export const AnalyticsFilterBar: React.FC<AnalyticsFilterBarProps> = ({
  activeSubTab,
  searchTerm,
  setSearchTerm,
  botFilter,
  setBotFilter,
  sideFilter,
  setSideFilter,
  outcomeFilter,
  setOutcomeFilter,
}) => {
  if (activeSubTab === 'validation') return null;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900/70 p-3 rounded-xl border border-slate-800 text-xs">
      <div className="flex items-center gap-2 flex-1 min-w-[200px] max-w-md">
        <Search className="w-4 h-4 text-slate-500" />
        <input
          type="text"
          placeholder={`Search ${activeSubTab === '15m_reports' ? '15M reports (ticker, cycle, ID)...' : 'ticker, ID...'}`}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 w-full"
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {/* Bot System Filter (for 15M reports) */}
        {activeSubTab === '15m_reports' && (
          <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
            <span className="text-[10px] text-slate-500 px-1 font-semibold uppercase">Bot:</span>
            {[
              { id: 'all', label: 'All Bots' },
              { id: 'macro_onnx', label: '🧠 Macro ONNX' },
              { id: 'macro_trend_dominion', label: '📈 Macro Trend' },
              { id: 'dominion_2_bot', label: '👑 Dominion 2' },
              { id: '3_step_domination_bot', label: '⚡ Domination' },
              { id: 'onnx_ml_bot', label: '🔬 ONNX ML' },
              { id: 'live', label: '🔴 Live' },
            ].map((b) => (
              <button
                key={b.id}
                onClick={() => setBotFilter(b.id as any)}
                className={`px-2 py-0.5 rounded-md font-bold text-[10px] transition ${
                  botFilter === b.id ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white'
                }`}
              >
                {b.label}
              </button>
            ))}
          </div>
        )}

        {/* Side Filter */}
        <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
          <span className="text-[10px] text-slate-500 px-1 font-semibold uppercase">Side:</span>
          {(['all', 'yes', 'no'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setSideFilter(s)}
              className={`px-2 py-0.5 rounded-md font-bold uppercase text-[10px] transition ${
                sideFilter === s ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Outcome Filter */}
        {(activeSubTab === '15m_reports' || activeSubTab === 'settlements') && (
          <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
            <span className="text-[10px] text-slate-500 px-1 font-semibold uppercase">Outcome:</span>
            {(['all', 'win', 'loss'] as const).map((o) => (
              <button
                key={o}
                onClick={() => setOutcomeFilter(o)}
                className={`px-2 py-0.5 rounded-md font-bold uppercase text-[10px] transition ${
                  outcomeFilter === o ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white'
                }`}
              >
                {o}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
