import React from 'react';
import { CheckSquare, ChevronLeft, ChevronRight, Square, Trash2 } from 'lucide-react';
import {
  AIPrediction,
  formatETDate,
  formatETTime,
  ITEMS_PER_PAGE,
} from './AnalyticsTypes';

interface AIPredictionsSubtabProps {
  paginatedAi: {
    items: AIPrediction[];
    totalPages: number;
    totalCount: number;
  };
  selectedIds: Set<string | number>;
  toggleSelectId: (id: string | number) => void;
  toggleSelectAllCurrentPage: (ids: (string | number)[]) => void;
  handleDeleteSingle: (type: 'ai', id: string | number) => void;
  page: number;
  setPage: React.Dispatch<React.SetStateAction<number>>;
}

export const AIPredictionsSubtab: React.FC<AIPredictionsSubtabProps> = ({
  paginatedAi,
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
                  onClick={() => toggleSelectAllCurrentPage(paginatedAi.items.map((p) => p.id))}
                  className="text-slate-400 hover:text-white"
                  title="Select/Deselect All on Page"
                >
                  {paginatedAi.items.length > 0 && paginatedAi.items.every((p) => selectedIds.has(p.id)) ? (
                    <CheckSquare className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <Square className="w-4 h-4 text-slate-500" />
                  )}
                </button>
              </th>
              <th className="py-3 px-4">Date & Time (ET)</th>
              <th className="py-3 px-3">Ticker</th>
              <th className="py-3 px-3">P(UP)</th>
              <th className="py-3 px-3">P(DOWN)</th>
              <th className="py-3 px-3">P(WAIT)</th>
              <th className="py-3 px-3">VPIN Toxicity</th>
              <th className="py-3 px-3">Decision Signal</th>
              <th className="py-3 px-3">Playbook Rationale</th>
              <th className="py-3 px-3 text-center">Delete</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50">
            {paginatedAi.items.length === 0 ? (
              <tr>
                <td colSpan={10} className="py-8 text-center text-slate-500 font-sans">
                  No AI predictions matching current criteria.
                </td>
              </tr>
            ) : (
              paginatedAi.items.map((p) => {
                const isSelected = selectedIds.has(p.id);
                return (
                  <tr key={p.id} className={`hover:bg-slate-800/40 transition ${isSelected ? 'bg-emerald-500/10' : ''}`}>
                    <td className="py-2.5 px-3 text-center">
                      <button
                        onClick={() => toggleSelectId(p.id)}
                        className="text-slate-400 hover:text-white"
                      >
                        {isSelected ? (
                          <CheckSquare className="w-4 h-4 text-emerald-400" />
                        ) : (
                          <Square className="w-4 h-4 text-slate-600" />
                        )}
                      </button>
                    </td>
                    <td className="py-2.5 px-4 text-slate-300">
                      <span className="text-slate-500 mr-1.5">
                        {formatETDate(p.timestamp_epoch_ms || p.timestamp_utc)}
                      </span>
                      {formatETTime(p.timestamp_epoch_ms || p.timestamp_utc)}
                    </td>
                    <td className="py-2.5 px-3 text-amber-300 font-bold">{p.ticker}</td>
                    <td className="py-2.5 px-3 text-emerald-400 font-bold">{(p.p_up * 100).toFixed(1)}%</td>
                    <td className="py-2.5 px-3 text-rose-400 font-bold">{(p.p_down * 100).toFixed(1)}%</td>
                    <td className="py-2.5 px-3 text-slate-400">{(p.p_wait * 100).toFixed(1)}%</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          p.vpin <= 0.35
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                            : p.vpin <= 0.65
                            ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                            : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                        }`}
                      >
                        {p.vpin.toFixed(2)} {p.vpin <= 0.35 ? 'SAFE' : p.vpin <= 0.65 ? 'WARN' : 'TOXIC'}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-bold text-white uppercase">{p.recommended_side}</td>
                    <td className="py-2.5 px-3 text-slate-400 truncate max-w-sm">{p.rationale || '--'}</td>
                    <td className="py-2.5 px-3 text-center">
                      <button
                        onClick={() => handleDeleteSingle('ai', p.id)}
                        className="p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition"
                        title="Delete this AI prediction"
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
      {paginatedAi.totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800 bg-slate-950/60 text-xs">
          <span className="text-slate-400">
            Showing {(page - 1) * ITEMS_PER_PAGE + 1} -{' '}
            {Math.min(page * ITEMS_PER_PAGE, paginatedAi.totalCount)} of {paginatedAi.totalCount} inferences
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
              Page {page} of {paginatedAi.totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(paginatedAi.totalPages, p + 1))}
              disabled={page === paginatedAi.totalPages}
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
