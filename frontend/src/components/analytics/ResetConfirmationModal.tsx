import React from 'react';
import { AlertTriangle, RefreshCw, Trash2 } from 'lucide-react';
import { SystemFilter } from './AnalyticsTypes';

interface ResetConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  resetTarget: string;
  setResetTarget: (target: string) => void;
  selectedSystem: SystemFilter;
  resetting: boolean;
  resetMessage: string | null;
  onConfirmReset: () => void;
}

export const ResetConfirmationModal: React.FC<ResetConfirmationModalProps> = ({
  isOpen,
  onClose,
  resetTarget,
  setResetTarget,
  selectedSystem,
  resetting,
  resetMessage,
  onConfirmReset,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 max-w-md w-full shadow-2xl space-y-4">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-rose-500/20 text-rose-400 rounded-xl border border-rose-500/30">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white">Reset Historical Reports & Ledger</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Clear historical records and recalculate efficiency metrics.
            </p>
          </div>
        </div>

        <div className="space-y-2 bg-slate-950/80 p-3.5 rounded-xl border border-slate-800 text-xs">
          <div className="text-slate-300 font-semibold mb-1">Select Target Scope to Reset:</div>

          <label className="flex items-center gap-2.5 cursor-pointer p-2 rounded-lg hover:bg-slate-800/50">
            <input
              type="radio"
              name="resetTarget"
              checked={resetTarget === '15m_reports'}
              onChange={() => setResetTarget('15m_reports')}
              className="text-emerald-500 focus:ring-emerald-500"
            />
            <span className="text-slate-200">
              Reset <strong className="text-emerald-400">15-Minute Event Reports</strong> only
            </span>
          </label>

          <label className="flex items-center gap-2.5 cursor-pointer p-2 rounded-lg hover:bg-slate-800/50">
            <input
              type="radio"
              name="resetTarget"
              checked={resetTarget === 'trades'}
              onChange={() => setResetTarget('trades')}
              className="text-blue-500 focus:ring-blue-500"
            />
            <span className="text-slate-200">
              Reset <strong className="text-blue-400">Trade Journal Executions</strong> only
            </span>
          </label>

          <label className="flex items-center gap-2.5 cursor-pointer p-2 rounded-lg hover:bg-slate-800/50">
            <input
              type="radio"
              name="resetTarget"
              checked={resetTarget === 'settlements'}
              onChange={() => setResetTarget('settlements')}
              className="text-purple-500 focus:ring-purple-500"
            />
            <span className="text-slate-200">
              Reset <strong className="text-purple-400">Settlements History</strong> only
            </span>
          </label>

          <label className="flex items-center gap-2.5 cursor-pointer p-2 rounded-lg hover:bg-slate-800/50">
            <input
              type="radio"
              name="resetTarget"
              checked={resetTarget === 'ai'}
              onChange={() => setResetTarget('ai')}
              className="text-amber-500 focus:ring-amber-500"
            />
            <span className="text-slate-200">
              Reset <strong className="text-amber-400">AI Decisions History</strong> only
            </span>
          </label>

          <label className="flex items-center gap-2.5 cursor-pointer p-2 rounded-lg hover:bg-slate-800/50">
            <input
              type="radio"
              name="resetTarget"
              checked={resetTarget === 'selected'}
              onChange={() => setResetTarget('selected')}
              className="text-amber-500 focus:ring-amber-500"
            />
            <span className="text-slate-200">
              Reset <strong className="text-amber-400">{selectedSystem === 'all' ? 'All Systems' : selectedSystem}</strong> only
            </span>
          </label>

          <label className="flex items-center gap-2.5 cursor-pointer p-2 rounded-lg hover:bg-slate-800/50">
            <input
              type="radio"
              name="resetTarget"
              checked={resetTarget === 'all'}
              onChange={() => setResetTarget('all')}
              className="text-rose-500 focus:ring-rose-500"
            />
            <span className="text-slate-200">
              Reset <strong className="text-rose-400">Complete Ledger Globally</strong> (Factory Wipe)
            </span>
          </label>
        </div>

        {resetMessage && (
          <div className="p-2.5 rounded-xl bg-slate-800 text-xs text-emerald-400 text-center font-mono border border-slate-700">
            {resetMessage}
          </div>
        )}

        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            onClick={onClose}
            disabled={resetting}
            className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-xl transition"
          >
            Cancel
          </button>
          <button
            onClick={onConfirmReset}
            disabled={resetting}
            className="px-4 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-500 rounded-xl transition flex items-center gap-1.5 shadow-md disabled:opacity-50"
          >
            {resetting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
            Confirm Reset
          </button>
        </div>
      </div>
    </div>
  );
};
