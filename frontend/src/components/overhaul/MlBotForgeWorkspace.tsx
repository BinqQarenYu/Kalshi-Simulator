import React, { useEffect, useState } from 'react';
import Decimal from 'decimal.js';
import {
  Bot,
  Cpu,
  GitBranch,
  Layers,
  Play,
  Plus,
  RefreshCw,
  Rocket,
  ShieldCheck,
  Sliders,
  Trash2,
  CheckCircle2,
} from 'lucide-react';
import { CryptoAsset } from '../../types';
import { RobotUnitAvatar } from './RobotUnitAvatar';
import { AwsCloudBridgePanel } from './AwsCloudBridgePanel';

export type ForgeTab =
  | 'bot_builder'
  | 'onnx_studio'
  | 'hmm_studio'
  | 'ensemble_lab'
  | 'seal_pipeline'
  | 'aws_bridge';

interface MlBotForgeWorkspaceProps {
  activeStrategyBot: string;
  onSelectStrategy: (botId: string) => void;
  onSelectAsset?: (asset: CryptoAsset) => void;
  initialTab?: ForgeTab;
}

export const MlBotForgeWorkspace: React.FC<MlBotForgeWorkspaceProps> = ({
  activeStrategyBot,
  onSelectStrategy,
  onSelectAsset,
  initialTab = 'bot_builder',
}) => {
  const [activeTab, setActiveTab] = useState<ForgeTab>(initialTab);
  const [overview, setOverview] = useState<any>({
    fleet_bots: [],
    custom_bots: [],
    onnx_assets: [],
    hmm_assets: [],
    ensemble_weights: {},
    aws_fleet: null,
  });

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);
  const [isBusy, setIsBusy] = useState<boolean>(false);
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  // 1. Custom Bot Builder Form State
  const [botName, setBotName] = useState<string>('Omega V5 Neural Sentinel');
  const [botAsset, setBotAsset] = useState<'BTC' | 'ETH'>('BTC');
  const [botTimeframe, setBotTimeframe] = useState<'15m' | '1h' | '24h'>('15m');
  const [botArchetype, setBotArchetype] = useState<string>('Multi-Turnover Neural Hybrid');
  const [botOnnxId, setBotOnnxId] = useState<string>('btc_gold_32d');
  const [botHmmId, setBotHmmId] = useState<string>('hmm_btc_3state');
  const [evFloor, setEvFloor] = useState<string>('0.05');
  const [discountCap, setDiscountCap] = useState<string>('0.52');
  const [doubtRoi, setDoubtRoi] = useState<string>('0.40');
  const [proximityMoat, setProximityMoat] = useState<string>('28.00');
  const [robotChassis, setRobotChassis] = useState<string>('titan_v4');
  const [accentColor, setAccentColor] = useState<string>('#10b981');
  const [deployImmediately, setDeployImmediately] = useState<boolean>(true);

  // 2. ONNX Trainer State
  const [onnxAsset, setOnnxAsset] = useState<'BTC' | 'ETH'>('BTC');
  const [onnxArch, setOnnxArch] = useState<'14d_microstructure' | '32d_gold'>('32d_gold');
  const [onnxEpochs, setOnnxEpochs] = useState<number>(60);
  const [onnxLr, setOnnxLr] = useState<string>('0.0005');

  // 3. HMM Trainer State
  const [hmmAsset, setHmmAsset] = useState<'BTC' | 'ETH'>('BTC');
  const [hmmWindow, setHmmWindow] = useState<number>(1440);

  // 4. Ensemble Feature Weight Lab State
  const [ensAsset, setEnsAsset] = useState<'BTC' | 'ETH'>('BTC');
  const [wOfi, setWOfi] = useState<string>('0.24');
  const [wVpin, setWVpin] = useState<string>('0.16');
  const [wVel, setWVel] = useState<string>('0.22');
  const [wCdf, setWCdf] = useState<string>('0.14');
  const [wHmm, setWHmm] = useState<string>('0.10');
  const [wOnnx, setWOnnx] = useState<string>('0.14');

  const loadForgeOverview = async () => {
    try {
      const res = await fetch('/api/forge/overview');
      if (res.ok) {
        const data = await res.json();
        setOverview(data);
      }
    } catch (err) {
      console.error('Failed to load forge overview:', err);
    }
  };

  useEffect(() => {
    loadForgeOverview();
  }, []);

  const notify = (msg: string) => {
    setFeedbackMsg(msg);
    setTimeout(() => setFeedbackMsg(null), 4000);
  };

  const handleAssetChangeForBuilder = (asset: 'BTC' | 'ETH') => {
    setBotAsset(asset);
    if (asset === 'ETH') {
      setBotOnnxId('eth_gold_32d');
      setBotHmmId('hmm_eth_3state');
      setProximityMoat('2.50');
    } else {
      setBotOnnxId('btc_gold_32d');
      setBotHmmId('hmm_btc_3state');
      setProximityMoat('28.00');
    }
  };

  const handleCreateCustomBot = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsBusy(true);
    try {
      const res = await fetch('/api/forge/bots/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: botName,
          asset: botAsset,
          timeframe: botTimeframe,
          archetype: botArchetype,
          onnx_asset_id: botOnnxId,
          hmm_asset_id: botHmmId,
          ev_floor: evFloor,
          discount_cap: discountCap,
          doubt_harvest_roi: doubtRoi,
          proximity_moat: proximityMoat,
          robot_chassis: robotChassis,
          accent_color: accentColor,
          activate_immediately: deployImmediately,
        }),
      });
      if (res.ok) {
        const json = await res.json();
        notify(json.message || 'Custom bot forged & sealed');
        await loadForgeOverview();
        if (deployImmediately && json.bot?.id) {
          onSelectStrategy(botAsset === 'ETH' ? 'eth_bot1_v4' : 'bot1_v4_domination');
          if (onSelectAsset) onSelectAsset(botAsset);
        }
      }
    } catch (err) {
      console.error('Create bot error:', err);
    } finally {
      setIsBusy(false);
    }
  };

  const handleTrainOnnx = async () => {
    setIsBusy(true);
    try {
      const res = await fetch('/api/forge/onnx/train', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset: onnxAsset,
          architecture: onnxArch,
          epochs: onnxEpochs,
          learning_rate: onnxLr,
        }),
      });
      if (res.ok) {
        const json = await res.json();
        notify(json.message || 'ONNX model trained and exported');
        await loadForgeOverview();
      }
    } catch (err) {
      console.error('ONNX train error:', err);
    } finally {
      setIsBusy(false);
    }
  };

  const handleTrainHmm = async () => {
    setIsBusy(true);
    try {
      const res = await fetch('/api/forge/hmm/train', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset: hmmAsset,
          n_states: 3,
          window_candles: hmmWindow,
        }),
      });
      if (res.ok) {
        const json = await res.json();
        notify(json.message || 'HMM 3-state regime brain calibrated');
        await loadForgeOverview();
      }
    } catch (err) {
      console.error('HMM train error:', err);
    } finally {
      setIsBusy(false);
    }
  };

  const handleEvaluateEnsemble = async () => {
    setIsBusy(true);
    try {
      const res = await fetch('/api/forge/ensemble/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset: ensAsset,
          ofi_weight: wOfi,
          vpin_shield_weight: wVpin,
          spot_velocity_weight: wVel,
          moneyness_cdf_weight: wCdf,
          hmm_regime_weight: wHmm,
          onnx_confidence_weight: wOnnx,
        }),
      });
      if (res.ok) {
        const json = await res.json();
        notify(
          `Calibrated ${ensAsset} Ensemble · Win Rate ${json.ensemble?.win_rate_pct}% · PF ${json.ensemble?.profit_factor}`
        );
        await loadForgeOverview();
      }
    } catch (err) {
      console.error('Ensemble evaluate error:', err);
    } finally {
      setIsBusy(false);
    }
  };

  const handlePromoteBot = async (botId: string, stage: 'incubator' | 'certified' | 'live_sealed') => {
    setIsBusy(true);
    try {
      const res = await fetch('/api/forge/bots/promote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bot_id: botId, target_stage: stage }),
      });
      if (res.ok) {
        const json = await res.json();
        notify(`Promoted ${botId} to ${stage.toUpperCase()} (Seal ${json.seal_hash})`);
        await loadForgeOverview();
      }
    } catch (err) {
      console.error('Promote bot error:', err);
    } finally {
      setIsBusy(false);
    }
  };

  const handleDeleteCustomBot = async (botId: string) => {
    try {
      const res = await fetch(`/api/forge/bots/${encodeURIComponent(botId)}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        notify(`Removed custom bot ${botId}`);
        await loadForgeOverview();
      }
    } catch (err) {
      console.error('Delete custom bot error:', err);
    }
  };

  const currentEnsembleResult = overview.ensemble_weights?.[ensAsset] || {
    win_rate_pct: '64.20',
    profit_factor: '1.68',
    expected_value_cents: '6.40',
    evaluated_cycles: 120,
  };

  return (
    <div className="w-full max-w-[1600px] mx-auto px-6 py-5 space-y-5">
      {/* Header & Sub-Navigation */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-xs font-medium text-[#10b981] tracking-wide">
            Quantitative Model Training, Asset Binding & Seal Certification
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white font-display">
            ML & Bot Asset Forge
          </h1>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {feedbackMsg && (
            <span className="text-xs font-mono text-[#10b981] bg-[#121621] border border-[#10b981]/40 px-3 py-1.5 rounded-lg">
              {feedbackMsg}
            </span>
          )}

          <div className="flex items-center bg-[#121621] border border-[#1e2536] rounded-lg p-1 gap-1 overflow-x-auto">
            {[
              { id: 'bot_builder', label: '1. Custom Bot Builder' },
              { id: 'onnx_studio', label: '2. ONNX Trainer (BTC/ETH)' },
              { id: 'hmm_studio', label: '3. HMM Regime Trainer' },
              { id: 'ensemble_lab', label: '4. Ensemble ML Lab' },
              { id: 'seal_pipeline', label: '5. Seal & Live Deploy' },
              { id: 'aws_bridge', label: '6. AWS EC2 Bridge (13.63.158.94)' },
            ].map((t) => (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id as ForgeTab)}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap shrink-0 ${
                  activeTab === t.id
                    ? 'bg-[#6366f1] text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* TAB 1: CUSTOM BOT BUILDER */}
      {activeTab === 'bot_builder' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
          {/* Left 7 Cols: Bot Configuration & Asset Binding Form */}
          <form
            onSubmit={handleCreateCustomBot}
            className="lg:col-span-7 bg-[#121621] border border-[#1e2536] rounded-xl p-6 space-y-5"
          >
            <div className="border-b border-[#1e2536] pb-3 flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold text-white font-display">
                  Forge Custom Trading Bot
                </h2>
                <p className="text-xs text-slate-400">
                  Bind asset-specific ONNX & HMM brains with strict Decimal risk guardrails
                </p>
              </div>
              <span className="text-xs font-mono tabular-nums text-[#10b981]">
                1-Contract Micro-Bankroll Enforced
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="sm:col-span-2">
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Bot Designation Name
                </label>
                <input
                  type="text"
                  value={botName}
                  onChange={(e) => setBotName(e.target.value)}
                  required
                  className="w-full bg-[#0b0d13] border border-[#1e2536] rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#6366f1]"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Target Crypto Asset
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {(['BTC', 'ETH'] as const).map((a) => (
                    <button
                      type="button"
                      key={a}
                      onClick={() => handleAssetChangeForBuilder(a)}
                      className={`py-2 rounded-lg text-xs font-semibold border transition-colors ${
                        botAsset === a
                          ? 'bg-[#6366f1] border-[#6366f1] text-white'
                          : 'bg-[#0b0d13] border-[#1e2536] text-slate-400 hover:text-white'
                      }`}
                    >
                      {a}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Cycle Horizon
                </label>
                <select
                  value={botTimeframe}
                  onChange={(e) => setBotTimeframe(e.target.value as '15m' | '1h' | '24h')}
                  className="w-full bg-[#0b0d13] border border-[#1e2536] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-[#6366f1]"
                >
                  <option value="15m">15-Minute Cycle (KX15M)</option>
                  <option value="1h">1-Hour Cycle (KXH)</option>
                  <option value="24h">Daily Settlement (KXD)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Bound ONNX Brain Asset
                </label>
                <select
                  value={botOnnxId}
                  onChange={(e) => setBotOnnxId(e.target.value)}
                  className="w-full bg-[#0b0d13] border border-[#1e2536] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-[#6366f1]"
                >
                  {(overview.onnx_assets || []).map((oa: any) => (
                    <option key={oa.id} value={oa.id}>
                      {oa.name} ({oa.validation_accuracy}%)
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">
                  Bound HMM Regime Asset
                </label>
                <select
                  value={botHmmId}
                  onChange={(e) => setBotHmmId(e.target.value)}
                  className="w-full bg-[#0b0d13] border border-[#1e2536] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-[#6366f1]"
                >
                  {(overview.hmm_assets || []).map((ha: any) => (
                    <option key={ha.id} value={ha.id}>
                      {ha.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Decimal Quantitative Guardrail Sliders */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <div className="bg-[#0b0d13] border border-[#1e2536] rounded-lg p-3.5">
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-slate-300">Minimum EV Floor ($)</span>
                  <span className="font-mono tabular-nums text-[#10b981]">+${evFloor}</span>
                </div>
                <input
                  type="range"
                  min="0.02"
                  max="0.15"
                  step="0.01"
                  value={evFloor}
                  onChange={(e) => setEvFloor(new Decimal(e.target.value).toFixed(2))}
                  className="w-full accent-[#10b981]"
                />
              </div>

              <div className="bg-[#0b0d13] border border-[#1e2536] rounded-lg p-3.5">
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-slate-300">Entry Discount Price Cap ($)</span>
                  <span className="font-mono tabular-nums text-[#06b6d4]">${discountCap}</span>
                </div>
                <input
                  type="range"
                  min="0.35"
                  max="0.65"
                  step="0.01"
                  value={discountCap}
                  onChange={(e) => setDiscountCap(new Decimal(e.target.value).toFixed(2))}
                  className="w-full accent-[#06b6d4]"
                />
              </div>

              <div className="bg-[#0b0d13] border border-[#1e2536] rounded-lg p-3.5">
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-slate-300">Doubt-Harvester Early Exit ROI</span>
                  <span className="font-mono tabular-nums text-[#6366f1]">
                    +{new Decimal(doubtRoi).mul(100).toFixed(0)}%
                  </span>
                </div>
                <input
                  type="range"
                  min="0.15"
                  max="0.80"
                  step="0.05"
                  value={doubtRoi}
                  onChange={(e) => setDoubtRoi(new Decimal(e.target.value).toFixed(2))}
                  className="w-full accent-[#6366f1]"
                />
              </div>

              <div className="bg-[#0b0d13] border border-[#1e2536] rounded-lg p-3.5">
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-slate-300">Strike Proximity Moat ($)</span>
                  <span className="font-mono tabular-nums text-[#f59e0b]">${proximityMoat}</span>
                </div>
                <input
                  type="range"
                  min={botAsset === 'ETH' ? '1.00' : '10.00'}
                  max={botAsset === 'ETH' ? '12.00' : '80.00'}
                  step={botAsset === 'ETH' ? '0.50' : '2.00'}
                  value={proximityMoat}
                  onChange={(e) => setProximityMoat(new Decimal(e.target.value).toFixed(2))}
                  className="w-full accent-[#f59e0b]"
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-4 pt-3 border-t border-[#1e2536]">
              <label className="inline-flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                <input
                  type="checkbox"
                  checked={deployImmediately}
                  onChange={(e) => setDeployImmediately(e.target.checked)}
                  className="rounded border-slate-600 accent-[#10b981]"
                />
                <span>Issue SHA-256 Seal & activate in engine immediately</span>
              </label>

              <button
                type="submit"
                disabled={isBusy}
                className="px-5 py-2.5 rounded-lg bg-[#10b981] hover:bg-[#059669] text-slate-950 font-semibold text-xs inline-flex items-center gap-2 transition-colors whitespace-nowrap shrink-0"
              >
                <Plus className="w-4 h-4" />
                <span>Forge & Seal Bot Unit</span>
              </button>
            </div>
          </form>

          {/* Right 5 Cols: Live Robot Chassis Customizer & Custom Fleet List */}
          <div className="lg:col-span-5 bg-[#121621] border border-[#1e2536] rounded-xl p-6 flex flex-col justify-between space-y-5">
            <div>
              <h2 className="text-base font-semibold text-white font-display">
                Robot Chassis & Telemetry Preview
              </h2>
              <p className="text-xs text-slate-400">
                Customize the kinematic robot unit representing this bot in the Arena
              </p>

              <div className="my-5 p-5 rounded-xl bg-[#0b0d13] border border-[#1e2536] flex flex-col items-center text-center">
                <RobotUnitAvatar
                  chassis={robotChassis}
                  accentColor={accentColor}
                  isActive={true}
                  isArmed={true}
                  stage={deployImmediately ? 'live_sealed' : 'incubator'}
                  size="lg"
                />
                <div className="mt-3 text-base font-bold text-white font-display">{botName}</div>
                <div className="text-xs font-mono tabular-nums text-slate-400 mt-1">
                  {botAsset} · {botTimeframe.toUpperCase()} · {botOnnxId} · {botHmmId}
                </div>
              </div>

              {/* Chassis & Color Selectors */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-slate-400 mb-1">Chassis Spec</label>
                  <select
                    value={robotChassis}
                    onChange={(e) => setRobotChassis(e.target.value)}
                    className="w-full bg-[#0b0d13] border border-[#1e2536] rounded-lg px-3 py-2 text-xs text-white"
                  >
                    <option value="titan_v4">Titan V4 Heavy</option>
                    <option value="valkyrie_eth">Valkyrie Optical</option>
                    <option value="synapse_dual">Synapse Dual-Core</option>
                    <option value="atlas_macro">Atlas Macro Unit</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs text-slate-400 mb-1">Reactor Core Hue</label>
                  <div className="flex items-center gap-2 pt-1">
                    {['#10b981', '#06b6d4', '#6366f1', '#f59e0b', '#ec4899'].map((clr) => (
                      <button
                        type="button"
                        key={clr}
                        onClick={() => setAccentColor(clr)}
                        className={`w-6 h-6 rounded-full border-2 ${
                          accentColor === clr ? 'border-white scale-110' : 'border-transparent'
                        }`}
                        style={{ backgroundColor: clr }}
                        aria-label={`Select color ${clr}`}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* User-Created Custom Bots List */}
            <div className="pt-4 border-t border-[#1e2536]">
              <div className="text-xs font-medium text-slate-300 mb-2">
                Custom Forged Bots ({(overview.custom_bots || []).length})
              </div>
              <div className="space-y-2 max-h-[160px] overflow-y-auto">
                {(overview.custom_bots || []).length === 0 ? (
                  <div className="text-xs text-slate-500 font-mono py-2">
                    No custom bots forged yet — configure parameters and click Forge & Seal Bot Unit.
                  </div>
                ) : (
                  (overview.custom_bots || []).map((cb: any) => (
                    <div
                      key={cb.id}
                      className="flex items-center justify-between px-3 py-2 rounded-lg bg-[#0b0d13] border border-[#1e2536] text-xs"
                    >
                      <div>
                        <div className="text-white font-medium">{cb.name}</div>
                        <div className="text-[11px] font-mono text-slate-400">
                          {cb.asset} · {cb.timeframe} · Seal {cb.seal_hash}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleDeleteCustomBot(cb.id)}
                        className="text-slate-400 hover:text-[#f43f5e] p-1"
                        title="Remove custom bot"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: ASSET-SPECIFIC ONNX TRAINER & EXPORTER (BTC & ETH) */}
      {activeTab === 'onnx_studio' && (
        <div className="space-y-5">
          <div className="bg-[#121621] border border-[#1e2536] rounded-xl p-5 flex flex-wrap items-end justify-between gap-4">
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Target Crypto Asset</label>
                <div className="flex bg-[#0b0d13] border border-[#1e2536] rounded-lg p-1">
                  {(['BTC', 'ETH'] as const).map((a) => (
                    <button
                      key={a}
                      onClick={() => setOnnxAsset(a)}
                      className={`px-3.5 py-1 text-xs font-semibold rounded-md ${
                        onnxAsset === a ? 'bg-[#6366f1] text-white' : 'text-slate-400'
                      }`}
                    >
                      {a}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs text-slate-400 mb-1">Neural Architecture</label>
                <select
                  value={onnxArch}
                  onChange={(e) => setOnnxArch(e.target.value as '14d_microstructure' | '32d_gold')}
                  className="bg-[#0b0d13] border border-[#1e2536] rounded-lg px-3 py-1.5 text-xs text-white"
                >
                  <option value="32d_gold">32-D Gold Champion MLP (128x64x32)</option>
                  <option value="14d_microstructure">14-D Microstructure MLP (64x32)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs text-slate-400 mb-1">Training Epochs</label>
                <input
                  type="number"
                  min={10}
                  max={500}
                  value={onnxEpochs}
                  onChange={(e) => setOnnxEpochs(Number(e.target.value))}
                  className="w-24 bg-[#0b0d13] border border-[#1e2536] rounded-lg px-3 py-1.5 text-xs font-mono text-white"
                />
              </div>

              <div>
                <label className="block text-xs text-slate-400 mb-1">Learning Rate</label>
                <input
                  type="text"
                  value={onnxLr}
                  onChange={(e) => setOnnxLr(e.target.value)}
                  className="w-28 bg-[#0b0d13] border border-[#1e2536] rounded-lg px-3 py-1.5 text-xs font-mono text-white"
                />
              </div>
            </div>

            <button
              onClick={handleTrainOnnx}
              disabled={isBusy}
              className="px-5 py-2.5 rounded-lg bg-[#6366f1] hover:bg-[#4f46e5] text-white font-semibold text-xs inline-flex items-center gap-2 transition-colors whitespace-nowrap shrink-0"
            >
              <Cpu className="w-4 h-4" />
              <span>Train & Export {onnxAsset} .ONNX Asset</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {(overview.onnx_assets || []).map((oa: any) => {
              const curve: number[] = (oa.loss_curve || ['0.90', '0.75', '0.60', '0.50']).map(Number);
              return (
                <div
                  key={oa.id}
                  className="bg-[#121621] border border-[#1e2536] rounded-xl p-5 flex flex-col justify-between space-y-4"
                >
                  <div className="flex items-start justify-between border-b border-[#1e2536] pb-3">
                    <div>
                      <div className="text-xs font-mono text-[#06b6d4]">
                        {oa.asset} · {oa.input_dim}-D Tensor · {oa.model_path}
                      </div>
                      <h3 className="text-base font-bold text-white font-display mt-0.5">
                        {oa.name}
                      </h3>
                    </div>
                    <span className="text-xs font-mono tabular-nums text-[#10b981]">
                      Acc {oa.validation_accuracy}%
                    </span>
                  </div>

                  {/* Mini SVG Loss Curve */}
                  <div className="bg-[#0b0d13] border border-[#1e2536] rounded-lg p-3">
                    <div className="flex justify-between text-[11px] font-mono text-slate-400 mb-1">
                      <span>Cross-Entropy Loss Trajectory</span>
                      <span>Final Loss: {oa.final_loss}</span>
                    </div>
                    <svg viewBox="0 0 320 70" className="w-full h-16">
                      <polyline
                        fill="none"
                        stroke="#6366f1"
                        strokeWidth="2"
                        points={curve
                          .map((v, i) => {
                            const x = 12 + (i / Math.max(1, curve.length - 1)) * 296;
                            const y = 60 - ((1.0 - Math.min(0.99, Math.max(0.3, v))) / 0.7) * 48;
                            return `${x.toFixed(1)},${y.toFixed(1)}`;
                          })
                          .join(' ')}
                      />
                    </svg>
                  </div>

                  <div className="flex flex-wrap items-center justify-between text-xs font-mono tabular-nums text-slate-400">
                    <span>Epochs: {oa.epochs_trained}</span>
                    <span>·</span>
                    <span>Samples: {oa.samples_count}</span>
                    <span>·</span>
                    <span>Latency: {oa.inference_latency_ms}ms</span>
                    <span>·</span>
                    <span>SHA: {oa.sha256}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* TAB 3: HMM 3-STATE MACRO REGIME STUDIO (BTC & ETH) */}
      {activeTab === 'hmm_studio' && (
        <div className="space-y-5">
          <div className="bg-[#121621] border border-[#1e2536] rounded-xl p-5 flex flex-wrap items-end justify-between gap-4">
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Target Crypto Asset</label>
                <div className="flex bg-[#0b0d13] border border-[#1e2536] rounded-lg p-1">
                  {(['BTC', 'ETH'] as const).map((a) => (
                    <button
                      key={a}
                      onClick={() => setHmmAsset(a)}
                      className={`px-3.5 py-1 text-xs font-semibold rounded-md ${
                        hmmAsset === a ? 'bg-[#06b6d4] text-slate-950' : 'text-slate-400'
                      }`}
                    >
                      {a}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs text-slate-400 mb-1">Training Rolling Window (Candles)</label>
                <input
                  type="number"
                  min={288}
                  max={10000}
                  step={144}
                  value={hmmWindow}
                  onChange={(e) => setHmmWindow(Number(e.target.value))}
                  className="w-36 bg-[#0b0d13] border border-[#1e2536] rounded-lg px-3 py-1.5 text-xs font-mono text-white"
                />
              </div>
            </div>

            <button
              onClick={handleTrainHmm}
              disabled={isBusy}
              className="px-5 py-2.5 rounded-lg bg-[#06b6d4] hover:bg-[#0891b2] text-slate-950 font-semibold text-xs inline-flex items-center gap-2 transition-colors whitespace-nowrap shrink-0"
            >
              <GitBranch className="w-4 h-4" />
              <span>Fit & Calibrate {hmmAsset} 3-State HMM</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {(overview.hmm_assets || []).map((ha: any) => (
              <div
                key={ha.id}
                className="bg-[#121621] border border-[#1e2536] rounded-xl p-5 space-y-4"
              >
                <div className="flex items-center justify-between border-b border-[#1e2536] pb-3">
                  <div>
                    <div className="text-xs font-mono text-[#06b6d4]">
                      {ha.asset} · Gaussian Baum-Welch EM
                    </div>
                    <h3 className="text-base font-bold text-white font-display mt-0.5">
                      {ha.name}
                    </h3>
                  </div>
                  <div className="text-right font-mono tabular-nums">
                    <div className="text-xs text-[#10b981] font-semibold">
                      Regime: {ha.active_regime}
                    </div>
                    <div className="text-[11px] text-slate-400">
                      Conf: {(Number(ha.confidence) * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>

                {/* 3x3 Transition Matrix Table */}
                <div>
                  <div className="text-xs text-slate-400 mb-2">
                    3×3 Markov State Transition Probability Matrix
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs font-mono tabular-nums border-collapse">
                      <thead>
                        <tr className="border-b border-[#1e2536] text-slate-400">
                          <th className="py-2 text-left">From \ To</th>
                          {ha.states.map((st: string) => (
                            <th key={st} className="py-2 text-right">
                              {st}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {(ha.transition_matrix || []).map((row: string[], rIdx: number) => (
                          <tr key={rIdx} className="border-b border-[#1e2536]/60">
                            <td className="py-2 text-slate-300 font-semibold">
                              {ha.states[rIdx]}
                            </td>
                            {row.map((cell: string, cIdx: number) => (
                              <td
                                key={cIdx}
                                className={`py-2 text-right ${
                                  rIdx === cIdx ? 'text-[#10b981] font-bold' : 'text-slate-300'
                                }`}
                              >
                                {(Number(cell) * 100).toFixed(0)}%
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="flex items-center justify-between text-xs font-mono tabular-nums text-slate-400 pt-2">
                  <span>Fitted Candles: {ha.samples_fitted}</span>
                  <span>·</span>
                  <span>Log-Likelihood: {ha.log_likelihood}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 4: ENSEMBLE & FEATURE WEIGHT LAB */}
      {activeTab === 'ensemble_lab' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-7 bg-[#121621] border border-[#1e2536] rounded-xl p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-[#1e2536] pb-3">
              <div>
                <h2 className="text-base font-semibold text-white font-display">
                  Multi-Signal Ensemble Weight Calibrator
                </h2>
                <p className="text-xs text-slate-400">
                  Tune relative feature weights and run empirical cycle validation
                </p>
              </div>
              <div className="flex bg-[#0b0d13] border border-[#1e2536] rounded-lg p-1">
                {(['BTC', 'ETH'] as const).map((a) => (
                  <button
                    key={a}
                    onClick={() => setEnsAsset(a)}
                    className={`px-3 py-1 text-xs font-semibold rounded-md ${
                      ensAsset === a ? 'bg-[#6366f1] text-white' : 'text-slate-400'
                    }`}
                  >
                    {a}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {[
                { label: 'OFI L1 Orderflow Imbalance', val: wOfi, set: setWOfi },
                { label: 'VPIN Toxicity Shield', val: wVpin, set: setWVpin },
                { label: 'Spot Lead-Lag Velocity', val: wVel, set: setWVel },
                { label: 'Digital Moneyness CDF', val: wCdf, set: setWCdf },
                { label: 'QuoLas HMM Regime Multiplier', val: wHmm, set: setWHmm },
                { label: 'ONNX Neural Probability', val: wOnnx, set: setWOnnx },
              ].map((item, idx) => (
                <div key={idx} className="bg-[#0b0d13] border border-[#1e2536] rounded-lg p-3.5">
                  <div className="flex justify-between text-xs mb-1.5">
                    <span className="text-slate-300">{item.label}</span>
                    <span className="font-mono tabular-nums text-[#6366f1]">{item.val}</span>
                  </div>
                  <input
                    type="range"
                    min="0.05"
                    max="0.50"
                    step="0.01"
                    value={item.val}
                    onChange={(e) => item.set(new Decimal(e.target.value).toFixed(2))}
                    className="w-full accent-[#6366f1]"
                  />
                </div>
              ))}
            </div>

            <div className="pt-3 border-t border-[#1e2536] flex justify-end">
              <button
                onClick={handleEvaluateEnsemble}
                disabled={isBusy}
                className="px-5 py-2.5 rounded-lg bg-[#6366f1] hover:bg-[#4f46e5] text-white font-semibold text-xs inline-flex items-center gap-2"
              >
                <Sliders className="w-4 h-4" />
                <span>Normalize & Run Empirical Backtest ({ensAsset})</span>
              </button>
            </div>
          </div>

          <div className="lg:col-span-5 bg-[#121621] border border-[#1e2536] rounded-xl p-6 flex flex-col justify-between">
            <div>
              <h2 className="text-base font-semibold text-white font-display border-b border-[#1e2536] pb-3">
                Empirical Backtest Benchmark · {ensAsset}
              </h2>
              <div className="grid grid-cols-2 gap-4 my-5">
                <div className="bg-[#0b0d13] border border-[#1e2536] rounded-xl p-4">
                  <div className="text-xs text-slate-400">Empirical Win Rate</div>
                  <div className="text-2xl font-bold font-mono tabular-nums text-[#10b981] mt-1">
                    {currentEnsembleResult.win_rate_pct}%
                  </div>
                </div>
                <div className="bg-[#0b0d13] border border-[#1e2536] rounded-xl p-4">
                  <div className="text-xs text-slate-400">Profit Factor</div>
                  <div className="text-2xl font-bold font-mono tabular-nums text-white mt-1">
                    {currentEnsembleResult.profit_factor}
                  </div>
                </div>
                <div className="bg-[#0b0d13] border border-[#1e2536] rounded-xl p-4">
                  <div className="text-xs text-slate-400">Expected Value / Trade</div>
                  <div className="text-2xl font-bold font-mono tabular-nums text-[#06b6d4] mt-1">
                    +{currentEnsembleResult.expected_value_cents}¢
                  </div>
                </div>
                <div className="bg-[#0b0d13] border border-[#1e2536] rounded-xl p-4">
                  <div className="text-xs text-slate-400">Evaluated Cycles</div>
                  <div className="text-2xl font-bold font-mono tabular-nums text-slate-200 mt-1">
                    {currentEnsembleResult.evaluated_cycles}
                  </div>
                </div>
              </div>
            </div>

            <div className="text-xs text-slate-400 font-mono border-t border-[#1e2536] pt-3">
              Weights are normalized with exact Decimal arithmetic and persisted in data/forge_models_registry.json.
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: ONE-CLICK PAPER INCUBATOR -> LIVE SEAL DEPLOYMENT PIPELINE */}
      {activeTab === 'seal_pipeline' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {[
            {
              stage: 'incubator',
              title: '01. Paper Incubator Trial',
              desc: 'Shadow & simulated cycle evaluation before live capital exposure',
              nextStage: 'certified' as const,
              nextLabel: 'Run 5-Pillar Audit',
            },
            {
              stage: 'certified',
              title: '02. 5-Pillar Certified',
              desc: 'Passed Decimal Math, 1-Contract Cap, CFTC & EV Floor audits',
              nextStage: 'live_sealed' as const,
              nextLabel: 'Issue SHA-256 Live Seal',
            },
            {
              stage: 'live_sealed',
              title: '03. SHA-256 Sealed (Live Ready)',
              desc: 'Cryptographically sealed on disk and authorized for live Kalshi execution',
              nextStage: null,
              nextLabel: 'Deploy Active Lock',
            },
          ].map((col) => {
            const botsInCol = (overview.fleet_bots || []).filter((b: any) => b.stage === col.stage);
            return (
              <div
                key={col.stage}
                className="bg-[#121621] border border-[#1e2536] rounded-xl p-5 flex flex-col justify-between space-y-4"
              >
                <div className="border-b border-[#1e2536] pb-3">
                  <h2 className="text-base font-bold text-white font-display">{col.title}</h2>
                  <p className="text-xs text-slate-400 mt-0.5">{col.desc}</p>
                </div>

                <div className="space-y-3 flex-1">
                  {botsInCol.length === 0 ? (
                    <div className="text-xs text-slate-500 font-mono py-8 text-center">
                      No bots currently in this stage
                    </div>
                  ) : (
                    botsInCol.map((bot: any) => (
                      <div
                        key={bot.id}
                        className="p-3.5 rounded-xl bg-[#0b0d13] border border-[#1e2536] flex items-center justify-between gap-3"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <RobotUnitAvatar
                            chassis={bot.robot_chassis}
                            accentColor={bot.accent_color}
                            isActive={bot.is_active}
                            isArmed={bot.is_armed}
                            stage={bot.stage}
                            size="sm"
                          />
                          <div className="min-w-0">
                            <div className="text-xs font-semibold text-white truncate">
                              {bot.name}
                            </div>
                            <div className="text-[11px] font-mono tabular-nums text-slate-400">
                              {bot.asset} · Win {bot.win_rate_pct}% · PF {bot.profit_factor}
                            </div>
                            <div className="text-[10px] font-mono text-[#10b981] mt-0.5">
                              SHA: {bot.seal_hash}
                            </div>
                          </div>
                        </div>

                        {col.nextStage ? (
                          <button
                            onClick={() => handlePromoteBot(bot.id, col.nextStage!)}
                            className="px-3 py-1.5 rounded-lg bg-[#6366f1] hover:bg-[#4f46e5] text-white text-xs font-semibold whitespace-nowrap shrink-0"
                          >
                            {col.nextLabel}
                          </button>
                        ) : (
                          <button
                            onClick={() => handlePromoteBot(bot.id, 'live_sealed')}
                            className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap shrink-0 ${
                              bot.is_active
                                ? 'bg-[#10b981]/20 text-[#10b981] border border-[#10b981]/40'
                                : 'bg-[#10b981] hover:bg-[#059669] text-slate-950'
                            }`}
                          >
                            {bot.is_active ? 'Active Lock' : 'Activate'}
                          </button>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* TAB 6: AWS EC2 CLOUD FLEET BRIDGE (13.63.158.94) */}
      {activeTab === 'aws_bridge' && (
        <AwsCloudBridgePanel
          awsFleet={overview.aws_fleet}
          onnxAssets={overview.onnx_assets || []}
          hmmAssets={overview.hmm_assets || []}
          onRefresh={loadForgeOverview}
          onNotify={notify}
        />
      )}
    </div>
  );
};
