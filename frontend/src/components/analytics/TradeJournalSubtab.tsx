import React from 'react';
import { CheckSquare, ChevronLeft, ChevronRight, Square, Trash2 } from 'lucide-react';
import {
  formatETDate,
  formatETTime,
  HistoricalTrade,
  ITEMS_PER_PAGE,
} from './AnalyticsTypes';

interface TradeJournalSubtabProps {
  paginatedTrades: {
    items: HistoricalTrade[];
    totalPages: number;
    totalCount: number;
  };
  selectedIds: Set<string | number>;
  toggleSelectId: (id: string | number) => void;
  toggleSelectAllCurrentPage: (ids: (string | number)[]) => void;
  handleDeleteSingle: (type: 'journal', id: string | number) => void;
  page: number;
  setPage: React.Dispatch<React.SetStateAction<number>>;
}

export const TradeJournalSubtab: React.FC<TradeJournalSubtabProps> = ({
  paginatedTrades,
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
                      paginatedTrades.items.map((t) => t.id || t.trade_id)
                    )
                  }
                  className="text-slate-400 hover:text-white"
                  title="Select/Deselect All on Page"
                >
                  {paginatedTrades.items.length > 0 &&
                  paginatedTrades.items.every((t) => selectedIds.has(t.id) || selectedIds.has(t.trade_id)) ? (
                    <CheckSquare className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <Square className="w-4 h-4 text-slate-500" />
                  )}
                </button>
              </th>
              <th className="py-3 px-4">Trade ID</th>
              <th className="py-3 px-3">Date & Time (ET)</th>
              <th className="py-3 px-3">Ticker</th>
              <th className="py-3 px-3">Side</th>
              <th className="py-3 px-3">Size</th>
              <th className="py-3 px-3">Price</th>
              <th className="py-3 px-3">Notional</th>
              <th className="py-3 px-3">Bot / Mode</th>
              <th className="py-3 px-3">Status</th>
              <th className="py-3 px-3 text-center">Delete</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {paginatedTrades.items.length === 0 ? (
              <tr>
                <td colSpan={11} className="py-8 text-center text-slate-500 font-sans">
                  No trade executions matching current filter criteria.
                </td>
              </tr>
            ) : (
              paginatedTrades.items.map((t) => {
                const isSelected = selectedIds.has(t.id) || selectedIds.has(t.trade_id);
                return (
                  <tr
                    key={t.id}
                    className={`hover:bg-slate-800/40 transition ${
                      isSelected ? 'bg-emerald-500/10' : ''
                    }`}
                  >
                    <td className="py-2.5 px-3 text-center">
                      <button
                        onClick={() => toggleSelectId(t.id || t.trade_id)}
                        className="text-slate-400 hover:text-white"
                      >
                        {isSelected ? (
                          <CheckSquare className="w-4 h-4 text-emerald-400" />
                        ) : (
                          <Square className="w-4 h-4 text-slate-600" />
                        )}
                      </button>
                    </td>
                    <td className="py-2.5 px-4 font-semibold text-slate-300">{t.trade_id}</td>
                    <td className="py-2.5 px-3 text-slate-300">
                      <span className="text-slate-500 mr-1.5">
                        {formatETDate(t.timestamp_epoch_ms || t.timestamp_utc)}
                      </span>
                      {formatETTime(t.timestamp_epoch_ms || t.timestamp_utc)}
                    </td>
                    <td className="py-2.5 px-3 text-amber-300 font-bold">{t.ticker}</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          t.side.toLowerCase() === 'yes'
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : 'bg-rose-500/20 text-rose-300'
                        }`}
                      >
                        {t.side.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-white font-bold">{t.size}</td>
                    <td className="py-2.5 px-3 text-slate-200">{(t.price * 100).toFixed(1)}¢</td>
                    <td className="py-2.5 px-3 text-slate-200">${t.gross_value.toFixed(2)}</td>
                    <td className="py-2.5 px-3">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300 border border-slate-700">
                        {t.bot_type ? t.bot_type.replace('_bot', '') : t.execution_mode}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-emerald-400 font-semibold">{t.status}</td>
                    <td className="py-2.5 px-3 text-center">
                      <button
                        onClick={() => handleDeleteSingle('journal', t.trade_id || t.id)}
                        className="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition"
                        title="Delete this trade"
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
      {paginatedTrades.totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800 bg-slate-950/60 text-xs">
          <span className="text-slate-400">
            Showing {(page - 1) * ITEMS_PER_PAGE + 1} -{' '}
            {Math.min(page * ITEMS_PER_PAGE, paginatedTrades.totalCount)} of{' '}
            {paginatedTrades.totalCount} trades
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
              Page {page} of {paginatedTrades.totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(paginatedTrades.totalPages, p + 1))}
              disabled={page === paginatedTrades.totalPages}
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
