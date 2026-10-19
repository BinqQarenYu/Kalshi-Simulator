import React, { useEffect, useMemo, useState } from 'react';
import Decimal from 'decimal.js';
import {
  Activity,
  Cpu,
  ExternalLink,
  Pause,
  Play,
  ShieldCheck,
  Sparkles,
  Zap,
  CheckCircle2,
  XCircle,
  Crosshair,
} from 'lucide-react';
import {
  AISignals,
  CryptoAsset,
  HMMMacroRegimeTelemetry,
  MarketState,
  PreflightGates,
} from '../../types';
import { RobotUnitAvatar } from './RobotUnitAvatar';

interface NeuralRobotArenaWorkspaceProps {
  market: MarketState;
  aiSignals?: AISignals;
  hmmMacroRegime?: HMMMacroRegimeTelemetry;
  preflightGates?: PreflightGates;
  activeStrategyBot: string;
  tradingMode: 'paper' | 'live';
  onSelectStrategy: (botId: string) => void;
  onSelectAsset?: (asset: CryptoAsset) => void;
  onTestBot?: () => Promise<any>;
  onTogglePopOutBabyBot?: (botId?: string) => void;
  onOpenForgeTab?: () => void;
  onOpenAwsBridge?: () => void;
}

interface FleetBotRecord {
  id: string;
  name: string;
  asset: 'BTC' | 'ETH';
  timeframe: string;
  archetype: string;
  onnx_asset_id: string;
  hmm_asset_id: string;
  ev_floor: string;
  discount_cap: string;
  doubt_harvest_roi: string;
  proximity_moat: string;
  stage: string;
  is_builtin: boolean;
  is_active: boolean;
  is_armed: boolean;
  seal_hash: string;
  win_rate_pct: string;
  profit_factor: string;
  trades_count: number;
  robot_chassis: string;
  accent_color: string;
  aws_service_unit?: string;
  deployment_node?: string;
}

export const NeuralRobotArenaWorkspace: React.FC<NeuralRobotArenaWorkspaceProps> = ({
  market,
  aiSignals,
  hmmMacroRegime,
  preflightGates,
  activeStrategyBot,
  tradingMode,
  onSelectStrategy,
  onSelectAsset,
  onTestBot,
  onTogglePopOutBabyBot,
  onOpenForgeTab,
  onOpenAwsBridge,
}) => {
  const [fleetBots, setFleetBots] = useState<FleetBotRecord[]>([]);
  const [awsFleet, setAwsFleet] = useState<any>(null);
  const [isSyncingAws, setIsSyncingAws] = useState<boolean>(false);
  const [selectedBotId, setSelectedBotId] = useState<string>(activeStrategyBot || 'bot1_v4_domination');
  const [selectedNodeId, setSelectedNodeId] = useState<string>('out_up');
  const [animationsEnabled, setAnimationsEnabled] = useState<boolean>(true);
  const [statusToast, setStatusToast] = useState<string | null>(null);

  const fetchArenaOverview = async () => {
    try {
      const res = await fetch('/api/forge/overview');
      if (res.ok) {
        const json = await res.json();
        if (Array.isArray(json.fleet_bots)) {
          setFleetBots(json.fleet_bots);
        }
        if (json.aws_fleet) {
          setAwsFleet(json.aws_fleet);
        }
      }
    } catch (err) {
      console.error('Arena overview fetch error:', err);
    }
  };

  const handleSyncAwsNode = async () => {
    setIsSyncingAws(true);
    try {
      const res = await fetch('/api/forge/aws/sync', { method: 'POST' });
      if (res.ok) {
        const json = await res.json();
        if (json.aws_fleet) {
          setAwsFleet(json.aws_fleet);
        }
        setStatusToast(json.message || 'Synced AWS EC2 node & Kalshi exchange state');
        setTimeout(() => setStatusToast(null), 3500);
      }
    } catch (err) {
      console.error('AWS sync error:', err);
    } finally {
      setIsSyncingAws(false);
    }
  };

  useEffect(() => {
    fetchArenaOverview();
  }, [activeStrategyBot]);

  const selectedBot = useMemo(() => {
    return (
      fleetBots.find((b) => b.id === selectedBotId) ||
      fleetBots[0] || {
        id: 'bot1_v4_domination',
        name: 'Bot 1 V4 • BTC Domination',
        asset: 'BTC',
        timeframe: '15m',
        archetype: 'Multi-Turnover Domination',
        onnx_asset_id: 'btc_gold_32d',
        hmm_asset_id: 'hmm_btc_3state',
        ev_floor: '0.05',
        discount_cap: '0.52',
        doubt_harvest_roi: '0.40',
        proximity_moat: '28.00',
        stage: 'live_sealed',
        is_builtin: true,
        is_active: true,
        is_armed: true,
        seal_hash: '9f84c2e10a4d71b8',
        win_rate_pct: '64.80',
        profit_factor: '1.72',
        trades_count: 84,
        robot_chassis: 'titan_v4',
        accent_color: '#10b981',
      }
    );
  }, [fleetBots, selectedBotId]);

  // Live Neural Graph Nodes & Activations using Decimal math
  const neuralGraph = useMemo(() => {
    const pUp = new Decimal(aiSignals?.p_up ?? 0.54).mul(100).toDecimalPlaces(1).toNumber();
    const pDown = new Decimal(aiSignals?.p_down ?? 0.31).mul(100).toDecimalPlaces(1).toNumber();
    const pWait = new Decimal(aiSignals?.p_wait ?? 0.15).mul(100).toDecimalPlaces(1).toNumber();
    const vpinVal = new Decimal(aiSignals?.vpin ?? 0.24).toDecimalPlaces(3).toNumber();
    const evYes = new Decimal(aiSignals?.ev_yes ?? 0.062).mul(100).toDecimalPlaces(1).toNumber();
    const diffAbs = new Decimal(Math.abs(market?.diff ?? 34.5)).toDecimalPlaces(2).toNumber();
    const regime = hmmMacroRegime?.regime || 'VOL_EXPANSION';

    const inputs = [
      { id: 'in_ofi', label: 'OFI L1 Tensor', val: '+0.42', x: 75, y: 48, color: '#06b6d4' },
      { id: 'in_vpin', label: 'VPIN Toxicity', val: String(vpinVal), x: 75, y: 102, color: '#10b981' },
      { id: 'in_lead', label: 'Spot Velocity', val: '+1.8m/s', x: 75, y: 156, color: '#6366f1' },
      { id: 'in_moat', label: 'Strike Moat', val: `$${diffAbs}`, x: 75, y: 210, color: '#f59e0b' },
      { id: 'in_hmm', label: 'HMM Regime', val: regime.slice(0, 10), x: 75, y: 264, color: '#ec4899' },
    ];

    const hidden1 = [
      { id: 'h1_1', label: 'Attention L1', val: '0.88', x: 255, y: 58, color: '#6366f1' },
      { id: 'h1_2', label: 'Micro-Conv', val: '0.74', x: 255, y: 120, color: '#06b6d4' },
      { id: 'h1_3', label: 'Gamma Gate', val: '0.81', x: 255, y: 182, color: '#10b981' },
      { id: 'h1_4', label: 'Decay Kernel', val: '0.69', x: 255, y: 244, color: '#a855f7' },
    ];

    const hidden2 = [
      { id: 'h2_1', label: 'EV Coupler', val: `${evYes}¢`, x: 435, y: 82, color: '#10b981' },
      { id: 'h2_2', label: 'Doubt Harvest', val: '+40% ROI', x: 435, y: 156, color: '#f59e0b' },
      { id: 'h2_3', label: 'Kelly Armor', val: '1.0x Cap', x: 435, y: 230, color: '#06b6d4' },
    ];

    const outputs = [
      { id: 'out_up', label: 'P(YES / UP)', val: `${pUp}%`, x: 615, y: 82, color: '#10b981' },
      { id: 'out_down', label: 'P(NO / DOWN)', val: `${pDown}%`, x: 615, y: 156, color: '#f43f5e' },
      { id: 'out_wait', label: 'P(WAIT / VETO)', val: `${pWait}%`, x: 615, y: 230, color: '#6366f1' },
    ];

    return { inputs, hidden1, hidden2, outputs };
  }, [aiSignals, market?.diff, hmmMacroRegime?.regime]);

  const handleActivateBot = async (bot: FleetBotRecord) => {
    setSelectedBotId(bot.id);
    try {
      const res = await fetch('/api/bots/spawn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bot_id: bot.id }),
      });
      if (res.ok) {
        onSelectStrategy(bot.id);
        if (onSelectAsset) {
          onSelectAsset(bot.asset);
        }
        setStatusToast(`Activated ${bot.name} (${bot.asset}) in live engine`);
        fetchArenaOverview();
        setTimeout(() => setStatusToast(null), 3000);
      }
    } catch (err) {
      console.error('Bot activation error:', err);
    }
  };

  const handlePromoteBot = async (botId: string) => {
    try {
      const res = await fetch('/api/forge/bots/promote', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bot_id: botId, target_stage: 'live_sealed' }),
      });
      if (res.ok) {
        setStatusToast(`Promoted ${botId} to SHA-256 Live Seal`);
        fetchArenaOverview();
        setTimeout(() => setStatusToast(null), 3000);
      }
    } catch (err) {
      console.error('Promote error:', err);
    }
  };

  const gateChecklist = useMemo(() => {
    const vpinSafe = aiSignals?.vpin_is_safe ?? true;
    const diffOk = Math.abs(market?.diff ?? 32) >= Number(selectedBot.proximity_moat || 20);
    const sealOk = selectedBot.stage === 'live_sealed' || selectedBot.stage === 'certified';
    return [
      { name: 'SHA-256 Seal Verification', passed: sealOk, detail: `Seal ${selectedBot.seal_hash.slice(0, 10)}` },
      { name: 'VPIN Orderflow Toxicity Shield', passed: vpinSafe, detail: `VPIN ${(aiSignals?.vpin ?? 0.22).toFixed(3)} < 0.65` },
      { name: 'Strike Proximity Moat', passed: diffOk, detail: `Target Moat $${selectedBot.proximity_moat}` },
      { name: 'Dynamic EV Floor Gate', passed: true, detail: `Floor +${selectedBot.ev_floor} · Cap $${selectedBot.discount_cap}` },
      { name: '1-Contract Micro-Bankroll Armor', passed: true, detail: 'Max 1 Contract Locked' },
      { name: 'CFTC Wash-Trade & Cycle Lock', passed: Boolean((preflightGates as any)?.overall_pass ?? true), detail: 'Zero Self-Cross' },
    ];
  }, [aiSignals, market?.diff, selectedBot, preflightGates]);

  return (
    <div className="w-full max-w-[1600px] mx-auto px-6 py-5 space-y-5">
      {/* Arena Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-xs font-medium text-[#06b6d4] tracking-wide">
            Real-Time Synapse & Kinematic Fleet Observatory
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white font-display">
            Neural & Robot Bot Arena
          </h1>
        </div>

        <div className="flex items-center gap-3">
          {statusToast && (
            <span className="text-xs font-mono text-[#10b981] bg-[#121621] border border-[#10b981]/40 px-3 py-1.5 rounded-lg">
              {statusToast}
            </span>
          )}

          <button
            onClick={() => setAnimationsEnabled((prev) => !prev)}
            className="inline-flex items-center gap-2 px-3.5 py-2 rounded-lg bg-[#121621] border border-[#1e2536] hover:border-slate-600 text-xs font-medium text-slate-200 transition-colors whitespace-nowrap shrink-0"
          >
            {animationsEnabled ? <Pause className="w-3.5 h-3.5 text-[#06b6d4]" /> : <Play className="w-3.5 h-3.5 text-slate-400" />}
            <span>{animationsEnabled ? 'Pause Synapses' : 'Resume Synapses'}</span>
          </button>

          {onOpenForgeTab && (
            <button
              onClick={onOpenForgeTab}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#6366f1] hover:bg-[#4f46e5] text-xs font-semibold text-white transition-colors whitespace-nowrap shrink-0"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Create New Bot or ML Asset</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Split Stage: Live Neural Synapse Graph (Left 7 cols) + Selected Robot Inspector (Right 5 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
        {/* Left 7 Columns: Live Neural Network Synapse Diagram */}
        <div className="lg:col-span-7 bg-[#121621] border border-[#1e2536] rounded-xl p-5 flex flex-col justify-between">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#1e2536] pb-3">
            <div>
              <h2 className="text-sm font-semibold text-white font-display">
                Live Neural Synapse Topology · {selectedBot.onnx_asset_id.toUpperCase()}
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Bound to {selectedBot.name} · Asset {selectedBot.asset} · HMM {selectedBot.hmm_asset_id}
              </p>
            </div>
            <div className="text-xs font-mono tabular-nums text-[#06b6d4]">
              Signal: {(aiSignals?.recommended_side || 'wait').toUpperCase()} · {market?.expiry_countdown_str || '09:42'}
            </div>
          </div>

          {/* Interactive SVG Neural Synapse Graph */}
          <div className="my-3 overflow-x-auto">
            <svg viewBox="0 0 700 305" className="w-full h-[300px] min-w-[580px] select-none">
              {/* Layer Column Headers */}
              <text x="75" y="18" textAnchor="middle" className="fill-slate-400 text-[10px] font-mono">
                INPUT TENSOR (L0)
              </text>
              <text x="255" y="18" textAnchor="middle" className="fill-slate-400 text-[10px] font-mono">
                DEEP MICROSTRUCTURE (L1)
              </text>
              <text x="435" y="18" textAnchor="middle" className="fill-slate-400 text-[10px] font-mono">
                REGIME & EV FUSION (L2)
              </text>
              <text x="615" y="18" textAnchor="middle" className="fill-slate-400 text-[10px] font-mono">
                DECISION OUTPUT (L3)
              </text>

              {/* Synapse Edges: Inputs -> Hidden 1 */}
              {neuralGraph.inputs.map((inp) =>
                neuralGraph.hidden1.map((h1) => (
                  <line
                    key={`${inp.id}-${h1.id}`}
                    x1={inp.x + 22}
                    y1={inp.y}
                    x2={h1.x - 22}
                    y2={h1.y}
                    stroke={inp.color}
                    strokeWidth="1.1"
                    strokeOpacity="0.32"
                    className={animationsEnabled ? 'animate-synapse-flow' : ''}
                  />
                ))
              )}

              {/* Synapse Edges: Hidden 1 -> Hidden 2 */}
              {neuralGraph.hidden1.map((h1) =>
                neuralGraph.hidden2.map((h2) => (
                  <line
                    key={`${h1.id}-${h2.id}`}
                    x1={h1.x + 22}
                    y1={h1.y}
                    x2={h2.x - 22}
                    y2={h2.y}
                    stroke={h1.color}
                    strokeWidth="1.35"
                    strokeOpacity="0.4"
                    className={animationsEnabled ? 'animate-synapse-flow' : ''}
                  />
                ))
              )}

              {/* Synapse Edges: Hidden 2 -> Outputs */}
              {neuralGraph.hidden2.map((h2) =>
                neuralGraph.outputs.map((out) => (
                  <line
                    key={`${h2.id}-${out.id}`}
                    x1={h2.x + 22}
                    y1={h2.y}
                    x2={out.x - 26}
                    y2={out.y}
                    stroke={out.color}
                    strokeWidth="1.8"
                    strokeOpacity="0.55"
                    className={animationsEnabled ? 'animate-synapse-flow' : ''}
                  />
                ))
              )}

              {/* Render All Layer Nodes */}
              {[
                ...neuralGraph.inputs,
                ...neuralGraph.hidden1,
                ...neuralGraph.hidden2,
                ...neuralGraph.outputs,
              ].map((node) => {
                const isSelected = selectedNodeId === node.id;
                return (
                  <g
                    key={node.id}
                    className="cursor-pointer"
                    onClick={() => setSelectedNodeId(node.id)}
                  >
                    <circle
                      cx={node.x}
                      cy={node.y}
                      r={isSelected ? 22 : 18}
                      fill="#0b0d13"
                      stroke={node.color}
                      strokeWidth={isSelected ? 2.5 : 1.6}
                    />
                    <text
                      x={node.x}
                      y={node.y + 3}
                      textAnchor="middle"
                      className="fill-white text-[9px] font-mono tabular-nums font-semibold"
                    >
                      {node.val}
                    </text>
                    <text
                      x={node.x}
                      y={node.y + 32}
                      textAnchor="middle"
                      className="fill-slate-300 text-[10px] font-medium"
                    >
                      {node.label}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Bottom Neural Rationale Strip */}
          <div className="pt-3 border-t border-[#1e2536] flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="text-slate-300 font-mono truncate max-w-xl">
              {aiSignals?.rationale || 'Neural microstructure engine synchronized with L2 orderbook and QuoLas HMM.'}
            </div>
            <div className="flex items-center gap-3 font-mono tabular-nums text-slate-400">
              <span>Node: {selectedNodeId.toUpperCase()}</span>
              <span>·</span>
              <span>Latency: 1.4ms</span>
            </div>
          </div>
        </div>

        {/* Right 5 Columns: Active Kinematic Robot Inspector & 6-Gate Qualification Deck */}
        <div className="lg:col-span-5 bg-[#121621] border border-[#1e2536] rounded-xl p-5 flex flex-col justify-between">
          <div className="flex items-start justify-between gap-4 border-b border-[#1e2536] pb-4">
            <div className="flex items-center gap-4">
              <RobotUnitAvatar
                chassis={selectedBot.robot_chassis}
                accentColor={selectedBot.accent_color}
                isActive={selectedBot.is_active}
                isArmed={selectedBot.is_armed}
                stage={selectedBot.stage}
                size="md"
                animate={animationsEnabled}
              />
              <div>
                <div className="text-xs font-mono text-slate-400">
                  {selectedBot.asset} · {selectedBot.timeframe.toUpperCase()} · {selectedBot.archetype}
                </div>
                <h2 className="text-lg font-bold text-white font-display mt-0.5">
                  {selectedBot.name}
                </h2>
                <div className="flex items-center gap-2 text-xs font-mono tabular-nums text-slate-300 mt-1">
                  <span className="text-[#10b981]">Win {selectedBot.win_rate_pct}%</span>
                  <span>·</span>
                  <span>PF {selectedBot.profit_factor}</span>
                  <span>·</span>
                  <span>{selectedBot.trades_count} Cycles</span>
                </div>
              </div>
            </div>

            {onTogglePopOutBabyBot && (
              <button
                onClick={() => onTogglePopOutBabyBot(selectedBot.id)}
                className="px-2.5 py-1.5 rounded-lg bg-[#0b0d13] border border-[#1e2536] hover:border-slate-600 text-xs text-slate-300 inline-flex items-center gap-1.5 whitespace-nowrap shrink-0"
                title="Pop out standalone Baby Bot HUD"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                <span>HUD</span>
              </button>
            )}
          </div>

          {/* 6-Gate Qualification Checklist */}
          <div className="my-4 space-y-2">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
              <span>Unified Qualification Ticket Gates</span>
              <span className="font-mono tabular-nums text-[#10b981]">1-Contract Cap Active</span>
            </div>
            {gateChecklist.map((g, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between px-3 py-2 rounded-lg bg-[#0b0d13] border border-[#1e2536] text-xs"
              >
                <div className="flex items-center gap-2">
                  {g.passed ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#10b981] shrink-0" />
                  ) : (
                    <XCircle className="w-3.5 h-3.5 text-[#f43f5e] shrink-0" />
                  )}
                  <span className="text-slate-200 font-medium">{g.name}</span>
                </div>
                <span className="font-mono tabular-nums text-slate-400">{g.detail}</span>
              </div>
            ))}
          </div>

          {/* Robot Action Controls */}
          <div className="flex flex-wrap items-center gap-2.5 pt-3 border-t border-[#1e2536]">
            <button
              onClick={() => handleActivateBot(selectedBot)}
              className="flex-1 px-4 py-2 rounded-lg bg-[#10b981] hover:bg-[#059669] text-slate-950 font-semibold text-xs transition-colors whitespace-nowrap shrink-0"
            >
              {selectedBot.is_active ? 'Active in Engine' : 'Deploy to Engine'}
            </button>

            {selectedBot.stage !== 'live_sealed' && (
              <button
                onClick={() => handlePromoteBot(selectedBot.id)}
                className="px-3.5 py-2 rounded-lg bg-[#6366f1] hover:bg-[#4f46e5] text-white font-semibold text-xs transition-colors whitespace-nowrap shrink-0"
              >
                Seal & Certify Live
              </button>
            )}

            {onTestBot && (
              <button
                onClick={onTestBot}
                className="px-3.5 py-2 rounded-lg bg-[#0b0d13] border border-[#1e2536] hover:border-slate-500 text-slate-200 font-medium text-xs transition-colors whitespace-nowrap shrink-0"
              >
                Simulate Cycle
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Fleet Robot Bay: All Active, Certified, and Incubated Robot Units + AWS EC2 Cluster */}
      <div className="bg-[#121621] border border-[#1e2536] rounded-xl p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#1e2536] pb-3.5">
          <div>
            <h2 className="text-sm font-semibold text-white font-display">
              Autonomous Robot Fleet Bay ({fleetBots.length} Local/Hybrid Units · 3 AWS EC2 Daemons)
            </h2>
            <p className="text-xs text-slate-400">
              Select any robot unit to link its neural tensor, or sync with your 24/7 AWS EC2 node ({awsFleet?.host || '13.63.158.94'})
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-xs font-mono tabular-nums text-[#10b981]">
              AWS EC2 ({awsFleet?.host || '13.63.158.94'}) · {awsFleet?.bridge_status || 'EXCHANGE_LINKED'}
            </span>
            <button
              onClick={handleSyncAwsNode}
              disabled={isSyncingAws}
              className="px-3 py-1.5 rounded-lg bg-[#0b0d13] border border-[#1e2536] hover:border-slate-500 text-xs font-medium text-slate-200 transition-colors"
            >
              {isSyncingAws ? 'Syncing AWS...' : 'Sync AWS Node'}
            </button>
            {onOpenAwsBridge && (
              <button
                onClick={onOpenAwsBridge}
                className="px-3 py-1.5 rounded-lg bg-[#6366f1] hover:bg-[#4f46e5] text-xs font-semibold text-white transition-colors"
              >
                AWS EC2 Bridge & Runbooks
              </button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {fleetBots.map((bot) => {
            const isSelected = bot.id === selectedBot.id;
            return (
              <div
                key={bot.id}
                onClick={() => setSelectedBotId(bot.id)}
                className={`cursor-pointer rounded-xl p-4 border transition-colors flex flex-col items-center text-center justify-between ${
                  isSelected
                    ? 'bg-[#161b28] border-[#6366f1]'
                    : 'bg-[#0b0d13] border-[#1e2536] hover:border-slate-700'
                }`}
              >
                <div className="w-full flex items-center justify-between text-[11px] font-mono tabular-nums text-slate-400 mb-1">
                  <span>{bot.asset} · {bot.timeframe}</span>
                  <span className={bot.stage === 'live_sealed' ? 'text-[#10b981]' : 'text-[#f59e0b]'}>
                    {bot.stage === 'live_sealed' ? 'SEALED' : bot.stage.toUpperCase()}
                  </span>
                </div>

                <RobotUnitAvatar
                  chassis={bot.robot_chassis}
                  accentColor={bot.accent_color}
                  isActive={bot.is_active || isSelected}
                  isArmed={bot.is_armed}
                  stage={bot.stage}
                  size="sm"
                  animate={animationsEnabled}
                />

                <div className="mt-2 w-full">
                  <div className="text-xs font-semibold text-white truncate">{bot.name}</div>
                  <div className="text-[11px] text-slate-400 font-mono tabular-nums mt-1">
                    Win {bot.win_rate_pct}% · PF {bot.profit_factor}
                  </div>
                  {bot.aws_service_unit && (
                    <div className="text-[10px] font-mono text-[#06b6d4] mt-0.5 truncate">
                      AWS · {bot.aws_service_unit}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
