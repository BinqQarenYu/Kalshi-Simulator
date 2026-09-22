import React, { useState, useEffect } from 'react';
import { AlertTriangle, Check, RefreshCw } from 'lucide-react';
import { NeuralEngineSpec } from '../types';
import { StrategyParameters } from './onnx/OnnxConstants';
import { OnnxHeaderBar } from './onnx/OnnxHeaderBar';
import { NeuralFleetMatrix } from './onnx/NeuralFleetMatrix';
import { StrategyDialsMatrix } from './onnx/StrategyDialsMatrix';
import { OnnxModals } from './onnx/OnnxModals';

export const ONNXSettingsPanel: React.FC = () => {
  const [params, setParams] = useState<StrategyParameters | null>(null);
  const [activeInfo, setActiveInfo] = useState<string | null>(null);
  const [selectedEngine, setSelectedEngine] = useState<NeuralEngineSpec | null>(null);
  const [saving, setSaving] = useState<boolean>(false);
  const [success, setSuccess] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchParams = () => {
    fetch('/api/bot/parameters')
      .then((r) => r.json())
      .then((d) => {
        const p = d.parameters || d;
        setParams({
          brain_priority_mode: p.brain_priority_mode || 'TREND_ALIGNED_SCALP',
          contract_scaling_mode: p.contract_scaling_mode || 'TIER_0_STRICT_1',
          entry_discount_depth: p.entry_discount_depth ?? p.discount_limit_price ?? 0.52,
          discount_limit_price: p.discount_limit_price ?? p.entry_discount_depth ?? 0.52,
          momentum_max_price: p.momentum_max_price ?? 0.62,
          min_confidence: p.min_confidence ?? 0.70,
          min_ev_dollars: p.min_ev_dollars ?? 0.02,
          taker_cross_ev_threshold: p.taker_cross_ev_threshold ?? 0.04,
          max_temporal_skew_ms: p.max_temporal_skew_ms ?? 1000.0,
          gamma_cliff_seconds: p.gamma_cliff_seconds ?? 90.0,
          auto_cancel_on_veto: p.auto_cancel_on_veto !== undefined ? p.auto_cancel_on_veto : true,
          dynamic_volatility_mode: p.dynamic_volatility_mode || 'REALIZED_ATR',
          volatility_floor: p.volatility_floor ?? 10.0,
          volatility_ceiling: p.volatility_ceiling ?? 45.0,
          vpin_toxic_threshold: p.vpin_toxic_threshold ?? 0.70,
          dynamic_moat_multiplier: p.dynamic_moat_multiplier ?? 1.36,
          current_atr: p.current_atr ?? 14.0,
          cross_brain_skew_ms: p.cross_brain_skew_ms ?? 0.0,
          is_temporally_synced: p.is_temporally_synced !== undefined ? p.is_temporally_synced : true,
          slower_brain: p.slower_brain || 'IN_SYNC',
          hmm_regime: p.hmm_regime || 'NONE',
          max_contracts: 1,
        });
      })
      .catch((err) => {
        console.error('Error fetching ONNX parameters:', err);
      });
  };

  useEffect(() => {
    fetchParams();
    const interval = setInterval(fetchParams, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (activeInfo) setActiveInfo(null);
        if (selectedEngine) setSelectedEngine(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeInfo, selectedEngine]);

  const handleChange = (key: keyof StrategyParameters, value: any) => {
    if (!params) return;
    setParams({ ...params, [key]: value });
  };

  const saveParams = async () => {
    if (!params) return;
    setSaving(true);
    setSuccess(false);
    setErrorMsg(null);
    try {
      const payload = {
        brain_priority_mode: params.brain_priority_mode,
        contract_scaling_mode: params.contract_scaling_mode,
        entry_discount_depth: Number(params.entry_discount_depth),
        discount_limit_price: Number(params.entry_discount_depth),
        momentum_max_price: Number(params.momentum_max_price),
        min_confidence: Number(params.min_confidence),
        min_ev_dollars: Number(params.min_ev_dollars),
        taker_cross_ev_threshold: Number(params.taker_cross_ev_threshold),
        max_temporal_skew_ms: Number(params.max_temporal_skew_ms),
        gamma_cliff_seconds: Number(params.gamma_cliff_seconds),
        auto_cancel_on_veto: Boolean(params.auto_cancel_on_veto),
        dynamic_volatility_mode: params.dynamic_volatility_mode,
        volatility_floor: Number(params.volatility_floor),
        volatility_ceiling: Number(params.volatility_ceiling),
        vpin_toxic_threshold: Number(params.vpin_toxic_threshold),
        dynamic_moat_multiplier: Number(params.dynamic_moat_multiplier),
      };

      const res = await fetch('/api/bot/parameters', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: Failed to update parameters`);
      }

      setSuccess(true);
      setTimeout(() => setSuccess(false), 2500);
    } catch (e: any) {
      console.error(e);
      setErrorMsg(e.message || 'Failed saving parameters');
      setTimeout(() => setErrorMsg(null), 4000);
    } finally {
      setSaving(false);
    }
  };

  if (!params) {
    return (
      <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-6 font-mono text-slate-400 flex items-center justify-center gap-2">
        <RefreshCw className="w-4 h-4 animate-spin text-[#00bda5]" />
        <span>Loading Institutional ONNX Parameter Matrix...</span>
      </div>
    );
  }

  return (
    <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-5 font-mono text-xs shadow-xl">
      {/* Top Header & Telemetry Status */}
      <OnnxHeaderBar
        params={params}
        saving={saving}
        onRefresh={fetchParams}
        onSave={saveParams}
      />

      {/* Feedback Banner */}
      {success && (
        <div className="text-xs text-emerald-400 bg-emerald-500/10 p-2.5 rounded-lg border border-emerald-500/30 flex items-center gap-2 animate-in fade-in">
          <Check className="w-4 h-4 text-emerald-400" />
          <span>Institutional parameter matrix successfully committed to live execution daemon.</span>
        </div>
      )}

      {errorMsg && (
        <div className="text-xs text-rose-400 bg-rose-500/10 p-2.5 rounded-lg border border-rose-500/30 flex items-center gap-2 animate-in fade-in">
          <AlertTriangle className="w-4 h-4 text-rose-400" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Neural Engine Fleet & Multi-Brain Architecture Matrix */}
      <NeuralFleetMatrix onSelectEngine={(eng) => setSelectedEngine(eng)} />

      {/* 4-Quadrant Control Matrix */}
      <StrategyDialsMatrix
        params={params}
        handleChange={handleChange}
        setActiveInfo={setActiveInfo}
      />

      {/* Parameter Docs & Engine Specs Modals */}
      <OnnxModals
        activeInfo={activeInfo}
        onCloseInfo={() => setActiveInfo(null)}
        selectedEngine={selectedEngine}
        onCloseEngine={() => setSelectedEngine(null)}
      />
    </div>
  );
};

export default ONNXSettingsPanel;
