/**
 * @file PresetVaultModal.tsx
 * @description Institutional Bot Preset Vault & Configuration Lifecycle Management Modal.
 * Enables zero-downtime saving, atomic loading/hot-swapping, unloading (reverting to baseline),
 * and importing/uploading of JSON trading presets with strict pre-flight invariant validation.
 */

import React, { useState, useEffect, useRef } from 'react';
import { BotPreset, PresetListResponse } from '../types';
import { 
  Sliders, 
  Save, 
  Upload, 
  Download, 
  RotateCcw, 
  Trash2, 
  ShieldCheck, 
  CheckCircle2, 
  AlertTriangle, 
  Zap, 
  X, 
  FileText, 
  Clock, 
  User, 
  Hash, 
  Loader2 
} from 'lucide-react';
import { soundFX } from '../utils/audioFX';

interface PresetVaultModalProps {
  isOpen: boolean;
  onClose: () => void;
  onPresetApplied?: (presetName: string) => void;
}

export const PresetVaultModal: React.FC<PresetVaultModalProps> = ({
  isOpen,
  onClose,
  onPresetApplied,
}) => {
  const [presets, setPresets] = useState<BotPreset[]>([]);
  const [activePreset, setActivePreset] = useState<BotPreset | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);
  
  // Save form states
  const [showSaveForm, setShowSaveForm] = useState<boolean>(false);
  const [saveName, setSaveName] = useState<string>('');
  const [saveDesc, setSaveDesc] = useState<string>('');
  const [saveAuthor, setSaveAuthor] = useState<string>('Operator');
  const [isSaving, setIsSaving] = useState<boolean>(false);

  // File upload input ref
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);

  const fetchPresets = async () => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/bot/presets');
      if (res.ok) {
        const data: PresetListResponse = await res.json();
        setPresets(data.presets || []);
        setActivePreset(data.active_preset || null);
      } else {
        setStatusMessage({ text: 'Failed to fetch presets from engine.', type: 'error' });
      }
    } catch (err: any) {
      setStatusMessage({ text: `Network error: ${err.message}`, type: 'error' });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchPresets();
      setStatusMessage(null);
    }
  }, [isOpen]);

  const handleActivate = async (presetId: string, presetName: string) => {
    setIsLoading(true);
    try {
      const res = await fetch('/api/bot/presets/load', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset_id: presetId }),
      });
      const data = await res.json();
      if (res.ok) {
        soundFX.playOrderFillSound();
        setStatusMessage({ text: `⚡ Activated preset: ${presetName}`, type: 'success' });
        await fetchPresets();
        if (onPresetApplied) onPresetApplied(presetName);
      } else {
        soundFX.playLossSound();
        setStatusMessage({ text: `VETO: ${data.detail || data.message || 'Failed to load preset'}`, type: 'error' });
      }
    } catch (err: any) {
      soundFX.playLossSound();
      setStatusMessage({ text: `Error: ${err.message}`, type: 'error' });
    } finally {
      setIsLoading(false);
    }
  };

  const handleUnloadBaseline = async () => {
    if (!window.confirm('Revert all live bot dials back to the Council Certified Baseline (v3.2)?')) {
      return;
    }
    setIsLoading(true);
    try {
      const res = await fetch('/api/bot/presets/unload', {
        method: 'POST',
      });
      const data = await res.json();
      if (res.ok) {
        soundFX.playOrderFillSound();
        setStatusMessage({ text: '🔄 Reverted to Council Baseline v3.2', type: 'success' });
        await fetchPresets();
        if (onPresetApplied) onPresetApplied('Council Baseline v3.2');
      } else {
        soundFX.playLossSound();
        setStatusMessage({ text: `VETO: ${data.detail || data.message || 'Failed to revert to baseline'}`, type: 'error' });
      }
    } catch (err: any) {
      soundFX.playLossSound();
      setStatusMessage({ text: `Error: ${err.message}`, type: 'error' });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveSnapshot = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!saveName.trim()) return;
    setIsSaving(true);
    try {
      const res = await fetch('/api/bot/presets/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          preset_name: saveName.trim(),
          description: saveDesc.trim(),
          author: saveAuthor.trim() || 'Operator',
        }),
      });
      const data = await res.json();
      if (res.ok) {
        soundFX.playOrderFillSound();
        setStatusMessage({ text: `💾 Preset snapshot '${saveName}' saved to vault.`, type: 'success' });
        setSaveName('');
        setSaveDesc('');
        setShowSaveForm(false);
        await fetchPresets();
      } else {
        soundFX.playLossSound();
        setStatusMessage({ text: `VETO: ${data.detail || data.message || 'Failed to save preset'}`, type: 'error' });
      }
    } catch (err: any) {
      soundFX.playLossSound();
      setStatusMessage({ text: `Error saving preset: ${err.message}`, type: 'error' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setStatusMessage(null);
    try {
      const text = await file.text();
      // Optional client pre-check
      JSON.parse(text);

      const res = await fetch('/api/bot/presets/upload', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset_json: text, apply_immediately: false }),
      });
      const data = await res.json();
      if (res.ok) {
        soundFX.playOrderFillSound();
        setStatusMessage({ text: `📥 Successfully imported '${data.preset?.preset_name || file.name}' to vault!`, type: 'success' });
        await fetchPresets();
      } else {
        soundFX.playLossSound();
        setStatusMessage({ text: `UPLOAD VETO: ${data.detail || data.message || 'Preset failed safety audit'}`, type: 'error' });
      }
    } catch (err: any) {
      soundFX.playLossSound();
      setStatusMessage({ text: `Malformed JSON or Upload Error: ${err.message}`, type: 'error' });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async (presetId: string, presetName: string) => {
    if (!window.confirm(`Delete preset '${presetName}' from the vault?`)) {
      return;
    }
    try {
      const res = await fetch(`/api/bot/presets/${presetId}`, {
        method: 'DELETE',
      });
      const data = await res.json();
      if (res.ok) {
        setStatusMessage({ text: `Preset '${presetName}' deleted.`, type: 'success' });
        await fetchPresets();
      } else {
        soundFX.playLossSound();
        setStatusMessage({ text: `Cannot delete: ${data.detail || data.message}`, type: 'error' });
      }
    } catch (err: any) {
      setStatusMessage({ text: `Error deleting preset: ${err.message}`, type: 'error' });
    }
  };

  const handleExport = (presetId: string) => {
    window.open(`/api/bot/presets/export/${presetId}`, '_blank');
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="relative w-full max-w-4xl max-h-[90vh] flex flex-col bg-slate-900 border border-slate-700 rounded-xl shadow-2xl overflow-hidden font-sans text-slate-200">
        
        {/* Modal Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
              <Sliders className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold tracking-wide text-white uppercase">Bot Preset Vault</h2>
                <span className="px-2 py-0.5 text-[10px] font-mono tracking-wider font-semibold rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                  ZERO-DOWNTIME HOT-SWAP
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Save, load, upload, and hot-swap institutional trading configurations across all 5 assets.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Active Preset Banner */}
        <div className="px-6 py-3 bg-slate-800/40 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2.5">
            <span className="text-slate-400 uppercase tracking-wider font-mono text-[11px]">Active Profile:</span>
            <div className="flex items-center gap-2 px-3 py-1 bg-emerald-950/60 border border-emerald-500/40 rounded-full text-emerald-300 font-semibold font-mono">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              {activePreset ? activePreset.preset_name : 'Loading...'}
            </div>
            {activePreset?.is_council_certified && (
              <span className="flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded bg-amber-950/50 text-amber-300 border border-amber-700/40">
                <ShieldCheck className="w-3 h-3 text-amber-400" />
                COUNCIL CERTIFIED
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSaveForm(!showSaveForm)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600/90 hover:bg-indigo-500 text-white rounded font-medium text-xs shadow transition-colors"
            >
              <Save className="w-3.5 h-3.5" />
              Save Current Snapshot
            </button>

            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-200 rounded font-medium text-xs transition-colors"
            >
              {isUploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
              Upload JSON
            </button>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept=".json,application/json"
              className="hidden"
            />

            <button
              onClick={handleUnloadBaseline}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-950/40 hover:bg-rose-900/60 border border-rose-800/60 text-rose-300 rounded font-medium text-xs transition-colors"
              title="Revert all dials to Council Certified Baseline"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Revert to Baseline
            </button>
          </div>
        </div>

        {/* Status / Alert Bar */}
        {statusMessage && (
          <div
            className={`px-6 py-2 text-xs font-mono flex items-center justify-between border-b ${
              statusMessage.type === 'success'
                ? 'bg-emerald-950/70 text-emerald-300 border-emerald-800/60'
                : 'bg-rose-950/70 text-rose-300 border-rose-800/60'
            }`}
          >
            <div className="flex items-center gap-2">
              {statusMessage.type === 'success' ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-rose-400" />
              )}
              <span>{statusMessage.text}</span>
            </div>
            <button
              onClick={() => setStatusMessage(null)}
              className="text-slate-400 hover:text-white"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Expandable Save Snapshot Drawer */}
        {showSaveForm && (
          <form
            onSubmit={handleSaveSnapshot}
            className="px-6 py-4 bg-slate-950/80 border-b border-slate-800 space-y-3 animate-in slide-in-from-top-2 duration-150"
          >
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-indigo-400" />
                Create New Preset Snapshot From Live Dials
              </h3>
              <button
                type="button"
                onClick={() => setShowSaveForm(false)}
                className="text-xs text-slate-500 hover:text-slate-300"
              >
                Cancel
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="block text-[11px] font-mono text-slate-400 mb-1">Preset Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. BTC High-Vol Expansion"
                  value={saveName}
                  onChange={(e) => setSaveName(e.target.value)}
                  className="w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded text-xs text-white focus:outline-none focus:border-indigo-500 font-sans"
                />
              </div>

              <div>
                <label className="block text-[11px] font-mono text-slate-400 mb-1">Author / Desk</label>
                <input
                  type="text"
                  placeholder="Operator"
                  value={saveAuthor}
                  onChange={(e) => setSaveAuthor(e.target.value)}
                  className="w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded text-xs text-white focus:outline-none focus:border-indigo-500 font-sans"
                />
              </div>

              <div>
                <label className="block text-[11px] font-mono text-slate-400 mb-1">Description</label>
                <input
                  type="text"
                  placeholder="e.g. 51c discount cap with 2.50 Z-score moat"
                  value={saveDesc}
                  onChange={(e) => setSaveDesc(e.target.value)}
                  className="w-full px-3 py-1.5 bg-slate-900 border border-slate-700 rounded text-xs text-white focus:outline-none focus:border-indigo-500 font-sans"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-1">
              <button
                type="submit"
                disabled={isSaving || !saveName.trim()}
                className="flex items-center gap-1.5 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded font-medium text-xs transition-colors"
              >
                {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                Confirm & Snapshot to Vault
              </button>
            </div>
          </form>
        )}

        {/* Presets List Table / Cards */}
        <div className="flex-1 overflow-y-auto p-6 space-y-3">
          {isLoading && presets.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-slate-400 gap-2">
              <Loader2 className="w-5 h-5 animate-spin text-emerald-400" />
              <span>Scanning Preset Vault...</span>
            </div>
          ) : presets.length === 0 ? (
            <div className="text-center py-12 text-slate-500 font-mono text-xs">
              No presets found in vault. Save your first snapshot or upload a JSON configuration.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3">
              {presets.map((p) => {
                const isActive = p.is_active || (activePreset && p.preset_id === activePreset.preset_id);
                return (
                  <div
                    key={p.preset_id}
                    className={`relative p-4 rounded-lg border transition-all ${
                      isActive
                        ? 'bg-slate-800/80 border-emerald-500/60 shadow-lg shadow-emerald-950/20'
                        : 'bg-slate-800/30 border-slate-700/60 hover:bg-slate-800/50 hover:border-slate-600'
                    }`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-1 max-w-xl">
                        <div className="flex items-center gap-2">
                          <h4 className="font-bold text-sm text-white">{p.preset_name}</h4>
                          {isActive && (
                            <span className="px-2 py-0.5 text-[10px] font-mono font-bold uppercase rounded bg-emerald-950 text-emerald-300 border border-emerald-700">
                              ACTIVE
                            </span>
                          )}
                          {p.is_council_certified && (
                            <span className="px-2 py-0.5 text-[10px] font-mono uppercase rounded bg-amber-950/60 text-amber-300 border border-amber-700/60 flex items-center gap-1">
                              <ShieldCheck className="w-3 h-3 text-amber-400" />
                              COUNCIL CERTIFIED
                            </span>
                          )}
                          <span className="text-[10px] font-mono text-slate-500">v{p.version || '1.0'}</span>
                        </div>

                        <p className="text-xs text-slate-400 line-clamp-2">
                          {p.description || 'No description provided.'}
                        </p>

                        <div className="flex flex-wrap items-center gap-4 text-[11px] font-mono text-slate-500 pt-1">
                          {p.author && (
                            <span className="flex items-center gap-1">
                              <User className="w-3 h-3" />
                              {p.author}
                            </span>
                          )}
                          {p.created_at && (
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {new Date(p.created_at).toLocaleString()}
                            </span>
                          )}
                          {p.checksum && (
                            <span className="flex items-center gap-1 text-[10px] text-slate-600">
                              <Hash className="w-3 h-3" />
                              {p.checksum}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="flex items-center gap-2 self-center">
                        {!isActive ? (
                          <button
                            onClick={() => handleActivate(p.preset_id, p.preset_name)}
                            className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-semibold shadow transition-colors"
                          >
                            <Zap className="w-3.5 h-3.5" />
                            ACTIVATE
                          </button>
                        ) : (
                          <span className="px-3 py-1.5 bg-emerald-950 text-emerald-400 border border-emerald-800/80 rounded text-xs font-mono font-semibold flex items-center gap-1.5">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            LOADED
                          </span>
                        )}

                        <button
                          onClick={() => handleExport(p.preset_id)}
                          className="p-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-300 rounded transition-colors"
                          title="Export / Download JSON"
                        >
                          <Download className="w-4 h-4" />
                        </button>

                        {!p.is_council_certified && !isActive && (
                          <button
                            onClick={() => handleDelete(p.preset_id, p.preset_name)}
                            className="p-1.5 bg-slate-800 hover:bg-rose-950 border border-slate-700 hover:border-rose-700 text-slate-400 hover:text-rose-300 rounded transition-colors"
                            title="Delete Preset"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer / Safety Armor Notice */}
        <div className="px-6 py-3 bg-slate-950 border-t border-slate-800 flex items-center justify-between text-[11px] font-mono text-slate-500">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>PRE-FLIGHT SANITIZER ARMED: Sizing strictly capped to 1 contract, limit price &le; $0.52, dynamic spot velocity mandatory.</span>
          </div>
          <button
            onClick={onClose}
            className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded transition-colors"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
};
