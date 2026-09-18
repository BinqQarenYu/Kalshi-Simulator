import React from 'react';
import {
  Award,
  CheckCircle2,
  CheckSquare,
  ChevronLeft,
  ChevronRight,
  Cpu,
  Crown,
  Radio,
  Square,
  Trash2,
  TrendingUp,
  XCircle,
  Zap,
} from 'lucide-react';
import { WinLossEventReport } from '../../types';
import { ITEMS_PER_PAGE } from './AnalyticsTypes';

interface WinLoss15mSubtabProps {
  domStats15m: any;
  onnxStats15m: any;
  combinedStats15m: any;
  liveStats15m: any;
  paginatedWinLoss: {
    items: WinLossEventReport[];
    totalPages: number;
    totalCount: number;
  };
  selectedIds: Set<string | number>;
  toggleSelectId: (id: string | number) => void;
  toggleSelectAllCurrentPage: (ids: (string | number)[]) => void;
  handleDeleteSingle: (type: '15m_reports', id: string | number) => void;
  page: number;
  setPage: React.Dispatch<React.SetStateAction<number>>;
  isMacroOnnxBot: (r: WinLossEventReport) => boolean;
  isMacroBot: (r: WinLossEventReport) => boolean;
  isDom2Bot: (r: WinLossEventReport) => boolean;
  isDomBot: (r: WinLossEventReport) => boolean;
  isOnnxBot: (r: WinLossEventReport) => boolean;
}

export const WinLoss15mSubtab: React.FC<WinLoss15mSubtabProps> = ({
  domStats15m,
  onnxStats15m,
  combinedStats15m,
  liveStats15m,
  paginatedWinLoss,
  selectedIds,
  toggleSelectId,
  toggleSelectAllCurrentPage,
  handleDeleteSingle,
  page,
  setPage,
  isMacroOnnxBot,
  isMacroBot,
  isDom2Bot,
  isDomBot,
  isOnnxBot,
}) => {
  return (
    <div>
      {/* Top 15M Multi-Bot KPI Summary Matrix */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3 p-4 bg-slate-950/70 border-b border-slate-800">
        {/* Card 1: 3-Step Domination Bot */}
        <div className="bg-slate-900/90 border border-sky-500/30 rounded-xl p-3.5 flex flex-col justify-between shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-sky-400 uppercase tracking-wider flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5" />
              3-Step Domination Bot (15M)
            </span>
            <span className="px-1.5 py-0.5 text-[9px] font-mono bg-sky-500/10 border border-sky-500/30 rounded text-sky-300">
              {domStats15m.total} Events
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 mt-2 pt-2 border-t border-slate-800/80">
            <div>
              <div className="text-[9px] text-slate-500 uppercase font-semibold">Win Rate</div>
              <div className="text-sm font-bold font-mono text-white">
                {(domStats15m?.winRate ?? 0).toFixed(1)}%
              </div>
              <div className="text-[9px] text-slate-500 font-mono">
                {domStats15m?.wins ?? 0}W / {domStats15m?.losses ?? 0}L
              </div>
            </div>
            <div>
              <div className="text-[9px] text-slate-500 uppercase font-semibold">Net P&L</div>
              <div
                className={`text-sm font-bold font-mono ${
                  (domStats15m?.totalPnL ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {(domStats15m?.totalPnL ?? 0) >= 0 ? '+' : ''}${(domStats15m?.totalPnL ?? 0).toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-[9px] text-slate-500 uppercase font-semibold">Profit Factor</div>
              <div className="text-sm font-bold font-mono text-cyan-400">
                {(domStats15m?.profitFactor ?? 1.0).toFixed(2)}x
              </div>
            </div>
          </div>
        </div>

        {/* Card 2: ONNX ML Ensemble */}
        <div className="bg-slate-900/90 border border-purple-500/30 rounded-xl p-3.5 flex flex-col justify-between shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-purple-400 uppercase tracking-wider flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5" />
              ONNX ML Ensemble (15M)
            </span>
            <span className="px-1.5 py-0.5 text-[9px] font-mono bg-purple-500/10 border border-purple-500/30 rounded text-purple-300">
              {onnxStats15m?.total ?? 0} Events
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 mt-2 pt-2 border-t border-slate-800/80">
            <div>
              <div className="text-[9px] text-slate-500 uppercase font-semibold">Win Rate</div>
              <div className="text-sm font-bold font-mono text-white">
                {(onnxStats15m?.winRate ?? 0).toFixed(1)}%
              </div>
              <div className="text-[9px] text-slate-500 font-mono">
                {onnxStats15m?.wins ?? 0}W / {onnxStats15m?.losses ?? 0}L
              </div>
            </div>
            <div>
              <div className="text-[9px] text-slate-500 uppercase font-semibold">Net P&L</div>
              <div
                className={`text-sm font-bold font-mono ${
                  (onnxStats15m?.totalPnL ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {(onnxStats15m?.totalPnL ?? 0) >= 0 ? '+' : ''}${(onnxStats15m?.totalPnL ?? 0).toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-[9px] text-slate-500 uppercase font-semibold">Profit Factor</div>
              <div className="text-sm font-bold font-mono text-cyan-400">
                {(onnxStats15m?.profitFactor ?? 1.0).toFixed(2)}x
              </div>
            </div>
          </div>
        </div>

        {/* Card 3: Combined Overall 15M Portfolio */}
        <div className="bg-slate-900/90 border border-emerald-500/30 rounded-xl p-3.5 flex flex-col justify-between shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5">
              <Award className="w-3.5 h-3.5" />
              Combined 15M (Overall)
            </span>
            <span className="px-1.5 py-0.5 text-[9px] font-mono bg-emerald-500/10 border border-emerald-500/30 rounded text-emerald-300">
              {combinedStats15m?.total ?? 0} Total
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 mt-2 pt-2 border-t border-slate-800/80">
            <div>
              <div className="text-[9px] text-slate-500 uppercase font-semibold">Win Rate</div>
              <div className="text-sm font-bold font-mono text-white">
                {(combinedStats15m?.winRate ?? 0).toFixed(1)}%
              </div>
              <div className="text-[9px] text-slate-500 font-mono">
                {combinedStats15m?.wins ?? 0}W / {combinedStats15m?.losses ?? 0}L
              </div>
            </div>
            <div>
              <div className="text-[9px] text-slate-500 uppercase font-semibold">Net P&L</div>
              <div
                className={`text-sm font-bold font-mono ${
                  (combinedStats15m?.totalPnL ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {(combinedStats15m?.totalPnL ?? 0) >= 0 ? '+' : ''}${(combinedStats15m?.totalPnL ?? 0).toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-[9px] text-slate-500 uppercase font-semibold">Profit Factor</div>
              <div className="text-sm font-bold font-mono text-cyan-400">
                {(combinedStats15m?.profitFactor ?? 1.0).toFixed(2)}x
              </div>
            </div>
          </div>
        </div>

        {/* Card 4: Live Real-Money Production (15M) */}
        <div className="bg-slate-900/90 border border-rose-500/40 rounded-xl p-3.5 flex flex-col justify-between shadow-sm relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-rose-400 uppercase tracking-wider flex items-center gap-1.5">
              <Radio className="w-3.5 h-3.5 text-rose-400 animate-pulse" />
              Live Production (15M Real)
            </span>
            <span className="px-1.5 py-0.5 text-[9px] font-mono bg-rose-500/15 border border-rose-500/40 rounded text-rose-300 font-bold">
              {liveStats15m?.total ?? 0} Fills
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 mt-2 pt-2 border-t border-slate-800/80">
            <div>
              <div className="text-[9px] text-slate-500 uppercase font-semibold">Win Rate</div>
              <div className="text-sm font-bold font-mono text-white">
                {(liveStats15m?.winRate ?? 0).toFixed(1)}%
              </div>
              <div className="text-[9px] text-slate-500 font-mono">
                {liveStats15m?.wins ?? 0}W / {liveStats15m?.losses ?? 0}L
              </div>
            </div>
            <div>
              <div className="text-[9px] text-slate-500 uppercase font-semibold">Net P&L</div>
              <div
                className={`text-sm font-bold font-mono ${
                  (liveStats15m?.totalPnL ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
                }`}
              >
                {(liveStats15m?.totalPnL ?? 0) >= 0 ? '+' : ''}${(liveStats15m?.totalPnL ?? 0).toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-[9px] text-slate-500 uppercase font-semibold">Profit Factor</div>
              <div className="text-sm font-bold font-mono text-cyan-400">
                {(liveStats15m?.profitFactor ?? 1.0).toFixed(2)}x
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Reports Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-slate-800/80 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-700">
            <tr>
              <th className="py-3 px-3 w-8 text-center">
                <button
                  onClick={() => toggleSelectAllCurrentPage(paginatedWinLoss.items.map((r) => r.report_id))}
                  className="text-slate-400 hover:text-white"
                  title="Select/Deselect All on Page"
                >
                  {paginatedWinLoss.items.length > 0 &&
                  paginatedWinLoss.items.every((r) => selectedIds.has(r.report_id)) ? (
                    <CheckSquare className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <Square className="w-4 h-4 text-slate-500" />
                  )}
                </button>
              </th>
              <th className="py-3 px-3">System / Bot</th>
              <th className="py-3 px-3.5">Cycle Window (ET)</th>
              <th className="py-3 px-3">Contract / Strike</th>
              <th className="py-3 px-3 text-center">Bot Action</th>
              <th className="py-3 px-3 text-right">Entry $\to$ Settle</th>
              <th className="py-3 px-3 text-center">Outcome</th>
              <th className="py-3 px-3 text-right">Realized P&L</th>
              <th className="py-3 px-3">AI Rationale & Microstructure</th>
              <th className="py-3 px-3 text-center">Delete</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {paginatedWinLoss.items.length === 0 ? (
              <tr>
                <td colSpan={10} className="py-10 text-center text-slate-500 font-sans">
                  <Award className="h-8 w-8 mx-auto mb-2 text-slate-600" />
                  No 15-minute event reports recorded yet. Click &quot;🧪 Run 15M Test Bot&quot; above to simulate immediate trade events for both bots.
                </td>
              </tr>
            ) : (
              paginatedWinLoss.items.map((report) => {
                const isWin = report.outcome === 'win';
                const diffStrike = (report.settlement_btc_price || 0) - (report.strike_price || 0);
                const isSelected = selectedIds.has(report.report_id);
                const onnx = isOnnxBot(report);
                const live = report.execution_mode === 'live' || report.bot_type === 'live';

                return (
                  <tr
                    key={report.report_id}
                    className={`hover:bg-slate-800/40 transition-colors ${
                      isSelected ? 'bg-emerald-500/10' : ''
                    }`}
                  >
                    <td className="py-3 px-3 text-center">
                      <button
                        onClick={() => toggleSelectId(report.report_id)}
                        className="text-slate-400 hover:text-white"
                      >
                        {isSelected ? (
                          <CheckSquare className="w-4 h-4 text-emerald-400" />
                        ) : (
                          <Square className="w-4 h-4 text-slate-600" />
                        )}
                      </button>
                    </td>

                    {/* Bot Badge */}
                    <td className="py-3 px-3 whitespace-nowrap">
                      {isMacroOnnxBot(report) ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/40">
                          <Cpu className="w-3 h-3 text-purple-400" />
                          Macro ONNX
                        </span>
                      ) : isMacroBot(report) ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                          <TrendingUp className="w-3 h-3 text-cyan-400" />
                          Macro Trend
                        </span>
                      ) : isDom2Bot(report) ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                          <Crown className="w-3 h-3 text-emerald-400" />
                          Dominion 2
                        </span>
                      ) : isDomBot(report) ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
                          <Zap className="w-3 h-3 text-amber-400" />
                          3-Step Dom
                        </span>
                      ) : isOnnxBot(report) ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/40">
                          <Cpu className="w-3 h-3 text-blue-400" />
                          ONNX ML
                        </span>
                      ) : live ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40">
                          <Radio className="w-3 h-3 text-rose-400" />
                          Live Real
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-sky-500/15 text-sky-300 border border-sky-500/30">
                          <Zap className="w-3 h-3 text-sky-400" />
                          Domination
                        </span>
                      )}
                    </td>

                    {/* Cycle Time */}
                    <td className="py-3 px-3.5 whitespace-nowrap">
                      <div className="font-sans font-semibold text-slate-200 text-xs">{report.cycle_time}</div>
                      <div className="text-[10px] text-slate-500 font-mono">{report.report_id}</div>
                    </td>

                    {/* Ticker & Strike */}
                    <td className="py-3 px-3 whitespace-nowrap">
                      <div className="text-amber-300 font-bold text-xs">
                        ${report.strike_price ? report.strike_price.toLocaleString('en-US', { minimumFractionDigits: 2 }) : '0.00'}
                      </div>
                      <div className="text-[10px] text-slate-400">
                        Spot: ${report.settlement_btc_price ? report.settlement_btc_price.toLocaleString('en-US', { minimumFractionDigits: 2 }) : '0.00'}
                        <span className={(diffStrike || 0) >= 0 ? ' text-emerald-400' : ' text-rose-400'}>
                          {' '}({(diffStrike || 0) >= 0 ? '+' : ''}${(diffStrike || 0).toFixed(2)})
                        </span>
                      </div>
                    </td>

                    {/* Bot Action */}
                    <td className="py-3 px-3 text-center whitespace-nowrap">
                      <span
                        className={`inline-block px-2.5 py-1 rounded-md text-[11px] font-bold uppercase ${
                          report.bot_side === 'yes'
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                            : 'bg-rose-500/20 text-rose-400 border border-rose-500/40'
                        }`}
                      >
                        {(report.bot_side || 'BUY').toUpperCase()} ({report.contracts ?? 0} cts)
                      </span>
                    </td>

                    {/* Entry -> Settle */}
                    <td className="py-3 px-3 text-right whitespace-nowrap">
                      <div className="text-slate-200 text-xs">
                        {report.entry_price != null ? (report.entry_price * 100).toFixed(1) : '0.0'}¢ $\to$ ${report.settlement_price != null ? report.settlement_price.toFixed(2) : '0.00'}
                      </div>
                      <div className="text-[10px] text-slate-500">
                        Cost: ${(report.entry_price != null && report.contracts != null ? report.entry_price * report.contracts : 0).toFixed(2)}
                      </div>
                    </td>

                    {/* Outcome */}
                    <td className="py-3 px-3 text-center whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                          isWin
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                            : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                        }`}
                      >
                        {isWin ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
                        {(report.outcome || 'PENDING').toUpperCase()}
                      </span>
                    </td>

                    {/* Realized PnL */}
                    <td className="py-3 px-3 text-right whitespace-nowrap">
                      <div className={`text-xs font-bold ${(report.pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {(report.pnl ?? 0) >= 0 ? '+' : ''}${report.pnl != null ? report.pnl.toFixed(2) : '0.00'}
                      </div>
                      <div className={`text-[10px] ${(report.roi_pct ?? 0) >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                        {(report.roi_pct ?? 0) >= 0 ? '+' : ''}{report.roi_pct != null ? report.roi_pct.toFixed(1) : '0.0'}% ROI
                      </div>
                    </td>

                    {/* Rationale */}
                    <td className="py-3 px-3 font-sans text-slate-300 text-xs max-w-xs">
                      <div className="font-semibold text-slate-200 truncate" title={report.ai_rationale}>
                        {report.ai_rationale || '--'}
                      </div>
                      <div className="text-[10px] text-slate-500 font-mono flex items-center gap-2 mt-0.5">
                        <span>Conf: {report.ai_confidence != null ? (report.ai_confidence * 100).toFixed(1) : '0.0'}%</span>
                        <span>•</span>
                        <span>VPIN: {report.vpin_score != null ? report.vpin_score.toFixed(2) : '0.00'}</span>
                        <span>•</span>
                        <span>Edge: {report.ev_edge != null ? (report.ev_edge * 100).toFixed(1) : '0.0'}%</span>
                      </div>
                    </td>

                    {/* Row Delete */}
                    <td className="py-3 px-3 text-center">
                      <button
                        onClick={() => handleDeleteSingle('15m_reports', report.report_id)}
                        className="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition"
                        title="Delete this 15M report"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      {paginatedWinLoss.totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800 bg-slate-950/60 text-xs">
          <span className="text-slate-400">
            Showing {(page - 1) * ITEMS_PER_PAGE + 1} -{' '}
            {Math.min(page * ITEMS_PER_PAGE, paginatedWinLoss.totalCount)} of {paginatedWinLoss.totalCount} reports
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="p-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-slate-300 font-mono">
              Page {page} of {paginatedWinLoss.totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(paginatedWinLoss.totalPages, p + 1))}
              disabled={page === paginatedWinLoss.totalPages}
              className="p-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
