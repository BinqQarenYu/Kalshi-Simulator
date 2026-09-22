import React from 'react';
import { CheckCircle2, CheckSquare, ChevronLeft, ChevronRight, Square, Trash2, XCircle } from 'lucide-react';
import {
  formatETDate,
  formatETTime,
  HistoricalSettlement,
  ITEMS_PER_PAGE,
} from './AnalyticsTypes';

interface SettlementsSubtabProps {
  paginatedSettlements: {
    items: HistoricalSettlement[];
    totalPages: number;
    totalCount: number;
  };
  selectedIds: Set<string | number>;
  toggleSelectId: (id: string | number) => void;
  toggleSelectAllCurrentPage: (ids: (string | number)[]) => void;
  handleDeleteSingle: (type: 'settlements', id: string | number) => void;
  page: number;
  setPage: React.Dispatch<React.SetStateAction<number>>;
}

export const SettlementsSubtab: React.FC<SettlementsSubtabProps> = ({
  paginatedSettlements,
  selectedIds,
  toggleSelectId,
  toggleSelectAllCurrentPage,
  handleDeleteSingle,
  page,
  setPage,
}) => {
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs font-mono">
          <thead className="bg-slate-800/80 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-700">
            <tr>
              <th className="py-3 px-3 w-8 text-center">
                <button
                  onClick={() =>
                    toggleSelectAllCurrentPage(
                      paginatedSettlements.items.map((s) => s.id || s.settlement_id)
                    )
                  }
                  className="text-slate-400 hover:text-white"
                  title="Select/Deselect All on Page"
                >
                  {paginatedSettlements.items.length > 0 &&
                  paginatedSettlements.items.every(
                    (s) => selectedIds.has(s.id) || selectedIds.has(s.settlement_id)
                  ) ? (
                    <CheckSquare className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <Square className="w-4 h-4 text-slate-500" />
                  )}
                </button>
              </th>
              <th className="py-3 px-4">Settlement ID</th>
              <th className="py-3 px-3">Date & Time (ET)</th>
              <th className="py-3 px-3">Ticker</th>
              <th className="py-3 px-3">Side</th>
              <th className="py-3 px-3">Size</th>
              <th className="py-3 px-3">Entry Price</th>
              <th className="py-3 px-3">Outcome</th>
              <th className="py-3 px-3">Realized P&L</th>
              <th className="py-3 px-3">Balance After</th>
              <th className="py-3 px-3 text-center">Delete</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {paginatedSettlements.items.length === 0 ? (
              <tr>
                <td colSpan={11} className="py-8 text-center text-slate-500 font-sans">
                  No settlements matching current filter criteria.
                </td>
              </tr>
            ) : (
              paginatedSettlements.items.map((s) => {
                const isSelected = selectedIds.has(s.id) || selectedIds.has(s.settlement_id);
                return (
                  <tr
                    key={s.id}
                    className={`hover:bg-slate-800/40 transition ${
                      isSelected ? 'bg-emerald-500/10' : ''
                    }`}
                  >
                    <td className="py-2.5 px-3 text-center">
                      <button
                        onClick={() => toggleSelectId(s.id || s.settlement_id)}
                        className="text-slate-400 hover:text-white"
                      >
                        {isSelected ? (
                          <CheckSquare className="w-4 h-4 text-emerald-400" />
                        ) : (
                          <Square className="w-4 h-4 text-slate-600" />
                        )}
                      </button>
                    </td>
                    <td className="py-2.5 px-4 font-semibold text-slate-300">{s.settlement_id}</td>
                    <td className="py-2.5 px-3 text-slate-300">
                      <span className="text-slate-500 mr-1.5">
                        {formatETDate(s.timestamp_epoch_ms || s.timestamp_utc)}
                      </span>
                      {formatETTime(s.timestamp_epoch_ms || s.timestamp_utc)}
                    </td>
                    <td className="py-2.5 px-3 text-amber-300 font-bold">{s.ticker}</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          s.side.toLowerCase() === 'yes'
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : 'bg-rose-500/20 text-rose-300'
                        }`}
                      >
                        {s.side.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-white font-bold">{s.size}</td>
                    <td className="py-2.5 px-3 text-slate-200">{(s.entry_price * 100).toFixed(1)}¢</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold flex items-center gap-1 w-fit ${
                          s.outcome.toLowerCase() === 'win'
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : s.outcome.toLowerCase() === 'loss'
                            ? 'bg-rose-500/20 text-rose-300'
                            : 'bg-slate-500/20 text-slate-300'
                        }`}
                      >
                        {s.outcome.toLowerCase() === 'win' ? (
                          <CheckCircle2 className="w-3 h-3" />
                        ) : s.outcome.toLowerCase() === 'loss' ? (
                          <XCircle className="w-3 h-3" />
                        ) : null}
                        {s.outcome.toUpperCase()}
                      </span>
                    </td>
                    <td
                      className={`py-2.5 px-3 font-bold ${
                        s.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
                      }`}
                    >
                      {s.pnl >= 0 ? '+' : ''}${s.pnl.toFixed(2)}
                    </td>
                    <td className="py-2.5 px-3 text-slate-300 font-semibold">
                      ${s.balance_after.toFixed(2)}
                    </td>
                    <td className="py-2.5 px-3 text-center">
                      <button
                        onClick={() => handleDeleteSingle('settlements', s.settlement_id || s.id)}
                        className="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition"
                        title="Delete this settlement"
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

      {/* Pagination */}
      {paginatedSettlements.totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800 bg-slate-950/60 text-xs">
          <span className="text-slate-400">
            Showing {(page - 1) * ITEMS_PER_PAGE + 1} -{' '}
            {Math.min(page * ITEMS_PER_PAGE, paginatedSettlements.totalCount)} of{' '}
            {paginatedSettlements.totalCount} settlements
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
              Page {page} of {paginatedSettlements.totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(paginatedSettlements.totalPages, p + 1))}
              disabled={page === paginatedSettlements.totalPages}
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
