/**
 * @file CouncilModal.tsx
 * @description LangGraph 7-Councilor Crucible & Task Granulizer Modal.
 * Visualizes the 7 orthogonal domain experts, flaw registry, consensus verdict,
 * and Agent Codeflow 4-phase granular task contracts.
 */

import React, { useState, useEffect } from 'react';
import {
  Scale,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  X,
  Send,
  Loader2,
  Layers,
  FileCode,
  Flame,
  Info,
} from 'lucide-react';
import {
  CouncilorInfo,
  CouncilDeliberationState,
} from '../types';
import { fetchCouncilRoster, deliberateProposal } from '../utils/councilApi';

interface CouncilModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const CouncilModal: React.FC<CouncilModalProps> = ({ isOpen, onClose }) => {
  const [roster, setRoster] = useState<CouncilorInfo[]>([]);
  const [invariants, setInvariants] = useState<string[]>([]);
  const [promptInput, setPromptInput] = useState('');
  const [targetAsset, setTargetAsset] = useState('BTC');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deliberationState, setDeliberationState] = useState<CouncilDeliberationState | null>(null);

  useEffect(() => {
    if (isOpen && roster.length === 0) {
      fetchCouncilRoster()
        .then((data) => {
          setRoster(data.councilors);
          setInvariants(data.invariants);
        })
        .catch((err) => setError(err.message));
    }
  }, [isOpen, roster.length]);

  if (!isOpen) return null;

  const handleDeliberate = async () => {
    if (!promptInput.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const state = await deliberateProposal(promptInput, targetAsset);
      setDeliberationState(state);
    } catch (err: any) {
      setError(err.message || 'Deliberation request failed');
    } finally {
      setLoading(false);
    }
  };

  const setSample = (text: string) => {
    setPromptInput(text);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-5xl rounded-xl border border-slate-700 bg-slate-900 shadow-2xl flex flex-col max-h-[90vh] overflow-hidden text-slate-100">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 bg-slate-950/80 px-6 py-4">
          <div className="flex items-center space-x-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400">
              <Scale className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                LangGraph Council of 7
                <span className="text-xs font-mono font-normal px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/40">
                  Adversarial Crucible
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Rule 9 Zero-Float &amp; 3-Stage Engineering Pipeline: Deliberate First, Document, Granulize, Verify.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* 7 Councilors Grid */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4 text-emerald-400" />
                The 7 Orthogonal Domain Councilors
              </h3>
              <span className="text-[11px] text-slate-500">Fast-Track &amp; Full Crucible Ready</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2.5">
              {roster.map((c) => {
                const vote = deliberationState?.council_votes?.[c.id];
                const verdict = vote?.verdict;

                return (
                  <div
                    key={c.id}
                    className={`rounded-lg border p-2.5 flex flex-col justify-between text-xs transition ${
                      verdict === 'PASS'
                        ? 'border-emerald-500/40 bg-emerald-950/20'
                        : verdict === 'VETO'
                        ? 'border-rose-500/50 bg-rose-950/30'
                        : verdict === 'ADJUST'
                        ? 'border-amber-500/40 bg-amber-950/20'
                        : 'border-slate-800 bg-slate-950/40'
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-200">{c.name}</span>
                        {verdict === 'PASS' && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />}
                        {verdict === 'VETO' && <XCircle className="h-3.5 w-3.5 text-rose-400" />}
                        {verdict === 'ADJUST' && <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />}
                      </div>
                      <div className="text-[10px] text-slate-400 mt-1 line-clamp-1">{c.domain}</div>
                    </div>

                    <div className="mt-2 pt-2 border-t border-slate-800/80">
                      <div className="text-[9px] text-slate-500 truncate" title={c.gate}>
                        {c.gate}
                      </div>
                      {verdict && (
                        <div
                          className={`mt-1 font-mono font-bold text-[10px] uppercase ${
                            verdict === 'PASS'
                              ? 'text-emerald-400'
                              : verdict === 'VETO'
                              ? 'text-rose-400'
                              : 'text-amber-400'
                          }`}
                        >
                          {verdict}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Proposal Input Box */}
          <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                <Flame className="h-4 w-4 text-amber-400" />
                Submit Strategy / Architectural Proposal
              </label>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-slate-400">Target Asset:</span>
                <select
                  value={targetAsset}
                  onChange={(e) => setTargetAsset(e.target.value)}
                  className="bg-slate-900 border border-slate-700 text-xs text-slate-200 rounded px-2 py-0.5 focus:outline-none"
                >
                  <option value="BTC">BTC</option>
                  <option value="ETH">ETH</option>
                  <option value="SYSTEM">SYSTEM</option>
                </select>
              </div>
            </div>

            <textarea
              rows={3}
              value={promptInput}
              onChange={(e) => setPromptInput(e.target.value)}
              placeholder="e.g. Implement passive maker limit order with Decimal math, Kelly scaling, and 1-contract micro-bankroll armor..."
              className="w-full rounded-lg border border-slate-700 bg-slate-900/80 p-3 text-xs text-slate-100 placeholder-slate-500 focus:border-amber-500 focus:outline-none"
            />

            <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
              <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
                <span className="text-slate-500">Quick Tests:</span>
                <button
                  type="button"
                  onClick={() => setSample('Deploy passive maker limit order with Decimal math and 1-contract micro-bankroll')}
                  className="rounded bg-slate-800/80 px-2 py-0.5 text-slate-300 hover:bg-slate-700 transition"
                >
                  Sound Proposal
                </button>
                <button
                  type="button"
                  onClick={() => setSample('Use float(price) and cross the wide spread instantly with no lock')}
                  className="rounded bg-slate-800/80 px-2 py-0.5 text-rose-300 hover:bg-slate-700 transition"
                >
                  Fatal Proposal
                </button>
              </div>

              <button
                type="button"
                onClick={handleDeliberate}
                disabled={loading || !promptInput.trim()}
                className="flex items-center gap-2 rounded-lg bg-amber-500 hover:bg-amber-600 disabled:bg-slate-800 disabled:text-slate-500 text-slate-950 font-bold px-4 py-2 text-xs transition"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                {loading ? 'Council Deliberating...' : 'Convene Council Crucible'}
              </button>
            </div>
          </div>

          {/* Deliberation Results */}
          {deliberationState && (
            <div className="space-y-4 animate-in fade-in duration-200">
              {/* Verdict Banner */}
              <div
                className={`rounded-xl border p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-3 ${
                  deliberationState.consensus_verdict === 'APPROVED'
                    ? 'border-emerald-500/50 bg-emerald-950/30'
                    : deliberationState.consensus_verdict === 'REJECTED'
                    ? 'border-rose-500/50 bg-rose-950/30'
                    : 'border-amber-500/50 bg-amber-950/30'
                }`}
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                      Consensus Verdict:
                    </span>
                    <span
                      className={`font-mono font-extrabold text-sm px-2.5 py-0.5 rounded ${
                        deliberationState.consensus_verdict === 'APPROVED'
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                          : deliberationState.consensus_verdict === 'REJECTED'
                          ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                          : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                      }`}
                    >
                      {deliberationState.consensus_verdict || 'HALTED'}
                    </span>
                    <span className="text-xs text-slate-400">
                      (Debate Round {deliberationState.debate_round}/{deliberationState.max_rounds})
                    </span>
                  </div>
                  <p className="text-xs text-slate-200 mt-1 font-medium">
                    {deliberationState.synthesized_solution}
                  </p>
                </div>
              </div>

              {/* Flaw Registry */}
              {deliberationState.flaw_registry && deliberationState.flaw_registry.length > 0 && (
                <div className="rounded-xl border border-rose-900/40 bg-slate-950/60 p-4">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-rose-300 flex items-center gap-1.5 mb-2.5">
                    <AlertTriangle className="h-4 w-4 text-rose-400" />
                    Identified Flaw Registry ({deliberationState.flaw_registry.length})
                  </h4>
                  <div className="space-y-2">
                    {deliberationState.flaw_registry.map((flaw, idx) => (
                      <div
                        key={idx}
                        className="rounded-lg border border-slate-800 bg-slate-900/60 p-2.5 text-xs flex flex-col md:flex-row md:items-center justify-between gap-2"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono font-bold text-rose-400 text-[11px]">{flaw.flaw_id}</span>
                            <span className="px-1.5 py-0.2 rounded bg-slate-800 text-slate-300 text-[10px] uppercase">
                              {flaw.category}
                            </span>
                            <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold uppercase ${
                              flaw.severity === 'FATAL' ? 'bg-rose-500/20 text-rose-300' : 'bg-amber-500/20 text-amber-300'
                            }`}>
                              {flaw.severity}
                            </span>
                          </div>
                          <p className="text-slate-300 mt-1">{flaw.description}</p>
                        </div>
                        <div className="text-[11px] text-emerald-300 bg-emerald-950/30 border border-emerald-900/50 rounded p-1.5 md:max-w-xs">
                          <span className="font-bold text-slate-400">Fix: </span>
                          {flaw.counter_measure}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Agent Codeflow Granular Task Contract */}
              {deliberationState.task_contract && deliberationState.task_contract.length > 0 && (
                <div className="rounded-xl border border-emerald-900/40 bg-slate-950/60 p-4">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-emerald-300 flex items-center gap-1.5 mb-2.5">
                    <Layers className="h-4 w-4 text-emerald-400" />
                    Agent Codeflow: 4-Phase Granular Task Contract
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                    {deliberationState.task_contract.map((task) => (
                      <div
                        key={task.step_id}
                        className="rounded-lg border border-slate-800 bg-slate-900/60 p-3 text-xs space-y-1.5"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-mono font-bold text-emerald-400">Step {task.step_id}: {task.phase}</span>
                          <span className="px-1.5 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300 uppercase">
                            {task.allowed_access}
                          </span>
                        </div>
                        <div className="font-mono text-[11px] text-slate-400 truncate flex items-center gap-1">
                          <FileCode className="h-3.5 w-3.5 text-slate-500" />
                          {task.target_file}
                        </div>
                        <p className="text-slate-300 text-[11px]">{task.action_description}</p>
                        <div className="text-[10px] text-emerald-400/90 bg-emerald-950/20 rounded p-1 border border-emerald-900/30">
                          <span className="font-bold text-slate-400">Done: </span>
                          {task.definition_of_done}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-slate-800 bg-slate-950 px-6 py-3 flex items-center justify-between text-[11px] text-slate-500">
          <div className="flex items-center gap-2">
            <Info className="h-3.5 w-3.5" />
            <span>Invariants Locked: {invariants.join(' • ')}</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
