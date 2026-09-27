import React, { useEffect, useState } from 'react';
import { Cpu, RefreshCcw, Activity, CheckCircle, XCircle } from 'lucide-react';

interface IncubationReport {
  report_id: string;
  timestamp_utc: string;
  bot_type: string;
  ticker: string;
  outcome: string;
  realized_pnl: number;
}

export const PerpetualIncubationReport: React.FC = () => {
  const [reports, setReports] = useState<IncubationReport[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const fetchReports = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/reports/executive-summary/export.json');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      
      const macroReports = data.reports?.macro_trend_reports || [];
      const dom2Reports = data.reports?.dominion_2_reports || [];
      const domReports = data.reports?.domination_reports || [];
      const onnxReports = data.reports?.onnx_reports || [];
      const liveReports = data.reports?.live_reports || [];
      
      let allReports = [...macroReports, ...dom2Reports, ...domReports, ...onnxReports, ...liveReports];
      
      const uniqueReports = Array.from(new Map(allReports.map(item => [item.report_id, item])).values()) as IncubationReport[];
      uniqueReports.sort((a, b) => new Date(b.timestamp_utc).getTime() - new Date(a.timestamp_utc).getTime());
      
      setReports(uniqueReports);
    } catch (err: any) {
      console.error("Failed to fetch incubation reports:", err);
      setError("Failed to load incubation reports. Connection error or server offline.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
    const interval = setInterval(fetchReports, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="bg-[#12161a] border border-[#1f2937] rounded-xl overflow-hidden mt-4 shadow-xl font-sans select-none">
      <div className="px-4 py-3 bg-[#161b22] border-b border-[#1f2937] flex items-center justify-between">
        <div className="flex items-center gap-2 text-cyan-300">
          <Cpu className="w-4 h-4" />
          <h3 className="font-bold text-sm uppercase tracking-wider">Incubation \u0026 Win/Loss Reports</h3>
        </div>
        <button 
          onClick={fetchReports} 
          className="p-1.5 rounded bg-[#1a2128] hover:bg-[#1f2937] text-slate-400 hover:text-cyan-300 transition-colors"
          title="Refresh Reports"
        >
          <RefreshCcw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>
      
      <div className="overflow-x-auto min-h-[150px] max-h-[300px] overflow-y-auto">
        {error ? (
          <div className="flex flex-col items-center justify-center h-32 text-rose-400/80 text-xs">
            <XCircle className="w-6 h-6 mb-2 opacity-50" />
            {error}
          </div>
        ) : reports.length === 0 && !loading ? (
          <div className="flex flex-col items-center justify-center h-32 text-slate-500 text-xs">
            <Activity className="w-6 h-6 mb-2 opacity-30" />
            No incubation reports found in shadow buffer.
          </div>
        ) : (
          <table className="w-full text-xs text-left whitespace-nowrap">
            <thead className="bg-[#161b22] text-slate-500 uppercase font-mono text-[10px] sticky top-0 shadow-sm z-10">
              <tr>
                <th className="px-4 py-2 font-medium border-b border-[#1f2937]">Time (UTC)</th>
                <th className="px-4 py-2 font-medium border-b border-[#1f2937]">Bot Type</th>
                <th className="px-4 py-2 font-medium border-b border-[#1f2937]">Ticker</th>
                <th className="px-4 py-2 font-medium border-b border-[#1f2937]">Outcome</th>
                <th className="px-4 py-2 font-medium border-b border-[#1f2937] text-right">PnL</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1f2937]/50">
              {reports.map((report) => (
                <tr key={report.report_id} className="hover:bg-[#1a2128]/50 transition-colors group">
                  <td className="px-4 py-2.5 font-mono text-slate-400">
                    {new Date(report.timestamp_utc).toLocaleTimeString()}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-cyan-300 border border-slate-700/50">
                      {report.bot_type || 'UNKNOWN'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 font-mono font-medium text-slate-300">
                    {report.ticker}
                  </td>
                  <td className="px-4 py-2.5">
                    {report.outcome?.toUpperCase() === 'WIN' ? (
                      <span className="flex items-center gap-1.5 text-emerald-400 font-bold">
                        <CheckCircle className="w-3.5 h-3.5" /> WIN
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5 text-rose-400 font-bold">
                        <XCircle className="w-3.5 h-3.5" /> LOSS
                      </span>
                    )}
                  </td>
                  <td className={`px-4 py-2.5 font-mono text-right font-bold ${
                    (report.realized_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                  }`}>
                    {(report.realized_pnl || 0) >= 0 ? '+' : ''}
                    ${(report.realized_pnl || 0).toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
