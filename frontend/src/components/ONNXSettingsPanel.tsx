import React, { useState, useEffect } from 'react';
import { Save, AlertTriangle, Cpu, Activity, RefreshCw } from 'lucide-react';

export const ONNXSettingsPanel: React.FC = () => {
  const [params, setParams] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    fetch('/api/bot/parameters')
      .then(r => r.json())
      .then(d => setParams(d.parameters || {}))
      .catch(console.error);
  }, []);

  const handleChange = (key: string, value: string) => {
    setParams({ ...params, [key]: parseFloat(value) });
  };

  const saveParams = async () => {
    setSaving(true);
    setSuccess(false);
    try {
      const payload = {
        discount_limit_price: params.discount_limit_price,
        momentum_max_price: params.momentum_max_price,
        min_ev_dollars: params.min_ev_dollars,
        min_confidence: params.min_confidence,
        vpin_toxic_threshold: params.vpin_toxic_threshold,
      };
      await fetch('/api/bot/parameters', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      setSuccess(true);
      setTimeout(() => setSuccess(false), 2000);
    } catch (e) {
      console.error(e);
    }
    setSaving(false);
  };

  if (!params) return <div className="p-4 text-slate-400">Loading parameters...</div>;

  return (
    <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-5 font-mono">
      <div className="flex items-center justify-between border-b border-[#262d35] pb-3">
        <div className="flex items-center gap-2.5">
          <Cpu className="w-5 h-5 text-purple-400" />
          <h2 className="text-sm font-bold uppercase tracking-wider text-white">ONNX Microstructure Benchmark Parameters</h2>
        </div>
        <button
          onClick={saveParams}
          disabled={saving}
          className="flex items-center gap-1 px-3 py-1.5 text-xs font-bold text-[#12161a] bg-[#00bda5] hover:bg-[#00cba0] rounded transition-colors disabled:opacity-50"
        >
          {saving ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
          Apply & Save
        </button>
      </div>

      {success && (
        <div className="text-xs text-emerald-400 bg-emerald-500/10 p-2 rounded border border-emerald-500/20">
          ✅ ONNX Parameters synced to live engine successfully.
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        
        {/* Confidence */}
        <div className="space-y-1">
          <label className="text-xs text-[#8c9ba5] font-semibold flex items-center gap-1">
            Min Neural Confidence
            <div className="group relative cursor-help">
              <div className="w-3 h-3 rounded-full bg-slate-700 text-white text-[9px] flex items-center justify-center">i</div>
              <div className="absolute bottom-full mb-1 hidden group-hover:block w-48 p-2 bg-slate-800 text-slate-200 text-[10px] rounded border border-slate-600 z-10 shadow-xl">
                The minimum probability score the ONNX Deep Learning model must output before it takes a trade. A 0.70 means the neural net is 70% sure it will win.
              </div>
            </div>
          </label>
          <div className="relative">
            <input type="number" step="0.01" min="0.50" max="0.99"
              value={params.min_confidence || 0.52}
              onChange={e => handleChange('min_confidence', e.target.value)}
              className="w-full bg-[#0a0c10] border border-[#262d35] rounded p-2 text-white text-sm focus:outline-none focus:border-purple-500"
            />
          </div>
        </div>

        {/* Discount Limit */}
        <div className="space-y-1">
          <label className="text-xs text-[#8c9ba5] font-semibold flex items-center gap-1">
            Discount Maker Limit ($)
            <div className="group relative cursor-help">
              <div className="w-3 h-3 rounded-full bg-slate-700 text-white text-[9px] flex items-center justify-center">i</div>
              <div className="absolute bottom-full mb-1 hidden group-hover:block w-48 p-2 bg-slate-800 text-slate-200 text-[10px] rounded border border-slate-600 z-10 shadow-xl">
                The max price the bot will bid for limit resting orders. Keeps Maker fees at .00.
              </div>
            </div>
          </label>
          <div className="relative">
            <span className="absolute left-2 top-2 text-[#8c9ba5] text-sm">$</span>
            <input type="number" step="0.01" min="0.10" max="0.65"
              value={params.discount_limit_price || 0.48}
              onChange={e => handleChange('discount_limit_price', e.target.value)}
              className="w-full bg-[#0a0c10] border border-[#262d35] rounded p-2 pl-6 text-white text-sm focus:outline-none focus:border-purple-500"
            />
          </div>
        </div>

        {/* Min EV */}
        <div className="space-y-1">
          <label className="text-xs text-[#8c9ba5] font-semibold flex items-center gap-1">
            Min Net EV ($)
            <div className="group relative cursor-help">
              <div className="w-3 h-3 rounded-full bg-slate-700 text-white text-[9px] flex items-center justify-center">i</div>
              <div className="absolute bottom-full mb-1 hidden group-hover:block w-48 p-2 bg-slate-800 text-slate-200 text-[10px] rounded border border-slate-600 z-10 shadow-xl">
                The minimum mathematically expected value of the trade.
              </div>
            </div>
          </label>
          <div className="relative">
            <span className="absolute left-2 top-2 text-[#8c9ba5] text-sm">$</span>
            <input type="number" step="0.01" min="0.01" max="0.50"
              value={params.min_ev_dollars || 0.02}
              onChange={e => handleChange('min_ev_dollars', e.target.value)}
              className="w-full bg-[#0a0c10] border border-[#262d35] rounded p-2 pl-6 text-white text-sm focus:outline-none focus:border-purple-500"
            />
          </div>
        </div>

      </div>
    </div>
  );
};
