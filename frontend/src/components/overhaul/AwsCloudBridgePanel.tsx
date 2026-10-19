import React, { useState } from 'react';
import {
  Cloud,
  Copy,
  Check,
  RefreshCw,
  Server,
  Terminal,
  UploadCloud,
  Activity,
} from 'lucide-react';
import { RobotUnitAvatar } from './RobotUnitAvatar';

interface AwsCloudBridgePanelProps {
  awsFleet: any;
  onnxAssets: any[];
  hmmAssets: any[];
  onRefresh: () => Promise<void>;
  onNotify: (msg: string) => void;
}

export const AwsCloudBridgePanel: React.FC<AwsCloudBridgePanelProps> = ({
  awsFleet,
  onnxAssets,
  hmmAssets,
  onRefresh,
  onNotify,
}) => {
  const fleet = awsFleet || {
    host: '13.63.158.94',
    port: 8000,
    ssh_user: 'ec2-user',
    remote_root: '/home/ec2-user/kalshi-bot',
    ssh_key_path: 'kalshi_aws_key.pem',
    region: 'eu-north-1 (AWS EC2 Production)',
    integration_mode: 'hybrid_exchange_and_http',
    bridge_status: 'EXCHANGE_LINKED',
    direct_http_reachable: false,
    exchange_account_linked: true,
    sync_count: 1,
    daemons: [],
    remote_telemetry: {
      live_balance_dollars: '24.85',
      available_margin_dollars: '24.85',
      active_positions_count: 0,
      batch_trades_completed: 4,
      batch_trades_target: 6,
      last_synced_ticker: 'KXBTC15M-LIVE',
      note: 'Synced via Shared Kalshi Exchange Account & AWS Fleet Registry',
    },
  };

  const [host, setHost] = useState<string>(fleet.host || '13.63.158.94');
  const [port, setPort] = useState<number>(fleet.port || 8000);
  const [sshUser, setSshUser] = useState<string>(fleet.ssh_user || 'ec2-user');
  const [remoteRoot, setRemoteRoot] = useState<string>(
    fleet.remote_root || '/home/ec2-user/kalshi-bot'
  );
  const [integrationMode, setIntegrationMode] = useState<string>(
    fleet.integration_mode || 'hybrid_exchange_and_http'
  );

  const [targetUnit, setTargetUnit] = useState<string>('all');
  const [selectedOnnx, setSelectedOnnx] = useState<string>('btc_gold_32d');
  const [selectedHmm, setSelectedHmm] = useState<string>('hmm_btc_3state');
  const [stagedRunbook, setStagedRunbook] = useState<string | null>(null);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [isPushing, setIsPushing] = useState<boolean>(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard?.writeText(text);
    setCopiedId(id);
    onNotify('Copied command to clipboard');
    setTimeout(() => setCopiedId(null), 2500);
  };

  const handleSyncAwsNow = async () => {
    setIsSyncing(true);
    try {
      const res = await fetch('/api/forge/aws/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (res.ok) {
        const json = await res.json();
        onNotify(json.message || 'Synced AWS EC2 node & Kalshi exchange state');
        await onRefresh();
      }
    } catch (err) {
      console.error('AWS sync failed:', err);
    } finally {
      setIsSyncing(false);
    }
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSyncing(true);
    try {
      const res = await fetch('/api/forge/aws/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          host,
          port: Number(port),
          ssh_user: sshUser,
          remote_root: remoteRoot,
          integration_mode: integrationMode,
        }),
      });
      if (res.ok) {
        const json = await res.json();
        onNotify(json.message || 'Saved AWS EC2 bridge settings');
        await onRefresh();
      }
    } catch (err) {
      console.error('AWS config update error:', err);
    } finally {
      setIsSyncing(false);
    }
  };

  const handleStageModelPush = async () => {
    setIsPushing(true);
    try {
      const res = await fetch('/api/forge/aws/push-models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_unit: targetUnit,
          onnx_asset_id: selectedOnnx,
          hmm_asset_id: selectedHmm,
        }),
      });
      if (res.ok) {
        const json = await res.json();
        setStagedRunbook(json.runbook_command || null);
        onNotify(json.message || 'Staged ONNX & HMM models for AWS EC2');
        await onRefresh();
      }
    } catch (err) {
      console.error('AWS model push error:', err);
    } finally {
      setIsPushing(false);
    }
  };

  const sshTunnelCmd = `ssh -i ${fleet.ssh_key_path || 'kalshi_aws_key.pem'} -N -L 8000:127.0.0.1:8000 ${sshUser}@${host}`;
  const systemdStatusCmd = `ssh -i ${fleet.ssh_key_path || 'kalshi_aws_key.pem'} ${sshUser}@${host} "sudo systemctl status kalshi-bot kalshi-btc-bot kalshi-eth-bot --no-pager"`;
  const rule6RestartCmd =
    stagedRunbook ||
    `scp -i ${fleet.ssh_key_path || 'kalshi_aws_key.pem'} models/*.onnx models/*.pkl ${sshUser}@${host}:${remoteRoot}/models/ && ssh -i ${fleet.ssh_key_path || 'kalshi_aws_key.pem'} ${sshUser}@${host} "sudo systemctl restart kalshi-bot kalshi-btc-bot kalshi-eth-bot"`;

  const daemons: any[] = fleet.daemons || [];

  return (
    <div className="space-y-5">
      {/* Top AWS EC2 Node Overview Banner */}
      <div className="bg-[#121621] border border-[#1e2536] rounded-xl p-5 flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-xs font-mono tabular-nums text-[#10b981]">
            <Cloud className="w-4 h-4" />
            <span>AWS EC2 PRODUCTION NODE</span>
            <span aria-hidden="true">·</span>
            <span>{fleet.host}:{fleet.port}</span>
            <span aria-hidden="true">·</span>
            <span>{fleet.bridge_status}</span>
          </div>
          <h2 className="text-lg font-bold text-white font-display">
            24/7 Cloud Trading Daemons & Command Deck Integration
          </h2>
          <p className="text-xs text-slate-400">
            {fleet.remote_telemetry?.note}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-5">
          <div className="text-right font-mono tabular-nums">
            <div className="text-[11px] text-slate-400">Kalshi Live Exchange Balance</div>
            <div className="text-base font-bold text-[#10b981]">
              ${fleet.remote_telemetry?.live_balance_dollars || '24.85'}
            </div>
          </div>

          <div className="text-right font-mono tabular-nums">
            <div className="text-[11px] text-slate-400">6-Trade Supervisor Batch</div>
            <div className="text-base font-bold text-white">
              {fleet.remote_telemetry?.batch_trades_completed ?? 4} / {fleet.remote_telemetry?.batch_trades_target ?? 6} Cycles
            </div>
          </div>

          <button
            onClick={handleSyncAwsNow}
            disabled={isSyncing}
            className="px-4 py-2.5 rounded-lg bg-[#6366f1] hover:bg-[#4f46e5] text-white font-semibold text-xs flex items-center gap-2 transition-colors whitespace-nowrap shrink-0"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin' : ''}`} />
            {isSyncing ? 'Probing AWS EC2...' : 'Probe & Sync AWS Node'}
          </button>
        </div>
      </div>

      {/* 3 Production Systemd Services Running on AWS EC2 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {daemons.map((d: any) => {
          const chassis =
            d.asset === 'ETH'
              ? 'valkyrie_eth'
              : d.asset === 'BTC'
              ? 'titan_v4'
              : 'atlas_macro';
          const accent =
            d.asset === 'ETH'
              ? '#06b6d4'
              : d.asset === 'BTC'
              ? '#10b981'
              : '#f59e0b';

          return (
            <div
              key={d.unit}
              className="bg-[#121621] border border-[#1e2536] rounded-xl p-5 flex flex-col justify-between space-y-4"
            >
              <div className="flex items-start justify-between gap-3 border-b border-[#1e2536] pb-3">
                <div>
                  <div className="text-xs font-mono tabular-nums text-[#10b981]">
                    {d.unit} · {d.status} ({d.sub_state})
                  </div>
                  <h3 className="text-sm font-bold text-white font-display mt-0.5">
                    {d.name}
                  </h3>
                </div>
                <RobotUnitAvatar
                  chassis={chassis}
                  accentColor={accent}
                  isActive={true}
                  isArmed={true}
                  stage="live_sealed"
                  size="sm"
                />
              </div>

              <div className="space-y-2 text-xs">
                <div className="flex items-center justify-between font-mono tabular-nums">
                  <span className="text-slate-400">Asset & Mode</span>
                  <span className="text-white">
                    {d.asset} · {d.mode}
                  </span>
                </div>
                <div className="flex items-center justify-between font-mono tabular-nums">
                  <span className="text-slate-400">Resources</span>
                  <span className="text-slate-200">
                    {d.memory_mb} MB RAM · {d.cpu_pct}% CPU · {d.tasks_count}/{d.tasks_limit} Tasks
                  </span>
                </div>
                <div className="flex items-center justify-between font-mono tabular-nums">
                  <span className="text-slate-400">ONNX Brain</span>
                  <span className="text-[#06b6d4]">{d.onnx_model}</span>
                </div>
                <div className="flex items-center justify-between font-mono tabular-nums">
                  <span className="text-slate-400">HMM Regime</span>
                  <span className="text-slate-200">{d.hmm_model}</span>
                </div>
                <div className="flex items-center justify-between font-mono tabular-nums">
                  <span className="text-slate-400">SHA-256 Seal</span>
                  <span className="text-[#10b981]">{d.seal_hash}</span>
                </div>
              </div>

              <div className="pt-2 border-t border-[#1e2536] space-y-1.5">
                <div className="text-[11px] text-slate-400">
                  {d.armor_summary}
                </div>
                <div className="text-[11px] font-mono text-slate-500 truncate" title={d.entrypoint}>
                  {d.entrypoint}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Bottom 2-Column Section: How Integration Works + Model Push & Bridge Settings */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left 7 Cols: 3 Real Integration Pathways & Copyable Runbooks */}
        <div className="lg:col-span-7 bg-[#121621] border border-[#1e2536] rounded-xl p-5 space-y-4">
          <div className="border-b border-[#1e2536] pb-3">
            <h3 className="text-base font-bold text-white font-display">
              How Your AWS EC2 Bot Integrates With This Command Deck
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Three production pathways link your 24/7 AWS EC2 node ({fleet.host}) with this dashboard
            </p>
          </div>

          <div className="space-y-3.5">
            {/* Pathway 1 */}
            <div className="p-3.5 rounded-lg bg-[#0b0d13] border border-[#1e2536] space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-white">
                  01. Shared Kalshi Production Exchange Sync (Zero-Firewall Default)
                </span>
                <span className="text-xs font-mono text-[#10b981]">ACTIVE</span>
              </div>
              <p className="text-xs text-slate-400">
                Both your AWS EC2 daemons (<code className="font-mono text-slate-200">kalshi-btc-bot</code> and <code className="font-mono text-slate-200">kalshi-eth-bot</code>) and this Command Deck authenticate against the same Kalshi Exchange account (<code className="font-mono text-slate-200">PROD_REST_BASE</code>). Every live order, position, and 15M settlement executed on AWS automatically populates your Analytics KPIs and Live Portfolio.
              </p>
            </div>

            {/* Pathway 2 */}
            <div className="p-3.5 rounded-lg bg-[#0b0d13] border border-[#1e2536] space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-white">
                  02. SSH Tunnel or Direct Port 8000 Telemetry Stream
                </span>
                <button
                  onClick={() => handleCopy('tunnel', sshTunnelCmd)}
                  className="text-xs font-mono text-[#06b6d4] hover:text-white flex items-center gap-1"
                >
                  {copiedId === 'tunnel' ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  {copiedId === 'tunnel' ? 'Copied' : 'Copy SSH Tunnel'}
                </button>
              </div>
              <p className="text-xs text-slate-400">
                Your AWS <code className="font-mono text-slate-200">kalshi-bot.service</code> runs <code className="font-mono text-slate-200">aws_headless_daemon.py</code> on port <code className="font-mono text-slate-200">8000</code>. Forward port 8000 over SSH or open your EC2 Security Group IP so clicking <strong>Probe & Sync AWS Node</strong> pulls live <code className="font-mono text-slate-200">/api/state</code> memory directly:
              </p>
              <div className="p-2.5 rounded bg-[#121621] border border-[#1e2536] font-mono text-[11px] text-slate-300 overflow-x-auto">
                {sshTunnelCmd}
              </div>
            </div>

            {/* Pathway 3 */}
            <div className="p-3.5 rounded-lg bg-[#0b0d13] border border-[#1e2536] space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-white">
                  03. Forge-to-AWS Model Deployment & Rule 6 Cache Invalidation
                </span>
                <button
                  onClick={() => handleCopy('restart', rule6RestartCmd)}
                  className="text-xs font-mono text-[#10b981] hover:text-white flex items-center gap-1"
                >
                  {copiedId === 'restart' ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  {copiedId === 'restart' ? 'Copied' : 'Copy Deploy Command'}
                </button>
              </div>
              <p className="text-xs text-slate-400">
                Train new BTC/ETH ONNX or HMM brains in this Forge, then push the artifacts to <code className="font-mono text-slate-200">{sshUser}@{host}:{remoteRoot}/models/</code> and forcefully restart all 3 systemd daemons (Rule 6 Protocol):
              </p>
              <div className="p-2.5 rounded bg-[#121621] border border-[#1e2536] font-mono text-[11px] text-[#10b981] overflow-x-auto">
                {rule6RestartCmd}
              </div>
            </div>
          </div>
        </div>

        {/* Right 5 Cols: Stage ONNX/HMM Push to AWS + Configure Bridge Endpoint */}
        <div className="lg:col-span-5 space-y-5">
          {/* Stage Model Push to AWS EC2 */}
          <div className="bg-[#121621] border border-[#1e2536] rounded-xl p-5 space-y-4">
            <div className="border-b border-[#1e2536] pb-3">
              <h3 className="text-sm font-bold text-white font-display flex items-center gap-2">
                <UploadCloud className="w-4 h-4 text-[#10b981]" />
                Stage Forged Brains for AWS EC2 Deployment
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Bind trained ONNX & HMM models to your AWS systemd fleet and issue a fresh SHA-256 deployment seal
              </p>
            </div>

            <div className="grid grid-cols-1 gap-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Target AWS Systemd Unit</label>
                <select
                  value={targetUnit}
                  onChange={(e) => setTargetUnit(e.target.value)}
                  className="w-full bg-[#0b0d13] border border-[#1e2536] rounded-lg px-3 py-2 text-xs text-white"
                >
                  <option value="all">All 3 AWS Daemons (kalshi-bot + btc + eth)</option>
                  <option value="kalshi-btc-bot.service">kalshi-btc-bot.service (BTC Live Taker)</option>
                  <option value="kalshi-eth-bot.service">kalshi-eth-bot.service (ETH Live Taker)</option>
                  <option value="kalshi-bot.service">kalshi-bot.service (Quolas Monolith)</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-slate-400 mb-1">ONNX Brain Asset</label>
                  <select
                    value={selectedOnnx}
                    onChange={(e) => setSelectedOnnx(e.target.value)}
                    className="w-full bg-[#0b0d13] border border-[#1e2536] rounded-lg px-3 py-2 text-xs text-white font-mono"
                  >
                    {onnxAssets.map((a: any) => (
                      <option key={a.id} value={a.id}>
                        {a.id} ({a.validation_accuracy}%)
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs text-slate-400 mb-1">HMM Regime Brain</label>
                  <select
                    value={selectedHmm}
                    onChange={(e) => setSelectedHmm(e.target.value)}
                    className="w-full bg-[#0b0d13] border border-[#1e2536] rounded-lg px-3 py-2 text-xs text-white font-mono"
                  >
                    {hmmAssets.map((h: any) => (
                      <option key={h.id} value={h.id}>
                        {h.id} ({h.active_regime})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <button
                onClick={handleStageModelPush}
                disabled={isPushing}
                className="w-full py-2.5 px-4 rounded-lg bg-[#10b981] hover:bg-[#059669] text-slate-950 font-semibold text-xs flex items-center justify-center gap-2 transition-colors"
              >
                <UploadCloud className="w-4 h-4" />
                {isPushing ? 'Staging AWS Bundle...' : 'Stage Models & Generate AWS Restart Runbook'}
              </button>
            </div>
          </div>

          {/* Configure AWS EC2 Host & Bridge Parameters */}
          <form
            onSubmit={handleSaveConfig}
            className="bg-[#121621] border border-[#1e2536] rounded-xl p-5 space-y-3.5"
          >
            <div className="border-b border-[#1e2536] pb-2.5 flex items-center justify-between">
              <h3 className="text-sm font-bold text-white font-display flex items-center gap-2">
                <Server className="w-4 h-4 text-[#6366f1]" />
                AWS EC2 Endpoint Configuration
              </h3>
              <button
                type="button"
                onClick={() => handleCopy('status_cmd', systemdStatusCmd)}
                className="text-[11px] font-mono text-slate-400 hover:text-white flex items-center gap-1"
              >
                <Terminal className="w-3 h-3" />
                Copy Health Check
              </button>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <label className="block text-xs text-slate-400 mb-1">EC2 Public IP / Host</label>
                <input
                  type="text"
                  value={host}
                  onChange={(e) => setHost(e.target.value)}
                  className="w-full bg-[#0b0d13] border border-[#1e2536] rounded-lg px-3 py-1.5 text-xs font-mono text-white"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">WebCLOB Port</label>
                <input
                  type="number"
                  value={port}
                  onChange={(e) => setPort(Number(e.target.value))}
                  className="w-full bg-[#0b0d13] border border-[#1e2536] rounded-lg px-3 py-1.5 text-xs font-mono text-white"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">SSH User</label>
                <input
                  type="text"
                  value={sshUser}
                  onChange={(e) => setSshUser(e.target.value)}
                  className="w-full bg-[#0b0d13] border border-[#1e2536] rounded-lg px-3 py-1.5 text-xs font-mono text-white"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Integration Mode</label>
                <select
                  value={integrationMode}
                  onChange={(e) => setIntegrationMode(e.target.value)}
                  className="w-full bg-[#0b0d13] border border-[#1e2536] rounded-lg px-3 py-1.5 text-xs text-white"
                >
                  <option value="hybrid_exchange_and_http">Hybrid (Exchange + HTTP)</option>
                  <option value="kalshi_exchange_sync">Shared Kalshi Exchange Only</option>
                  <option value="direct_http">Direct HTTP (:8000)</option>
                  <option value="webhook_push">Inbound Heartbeat Webhook</option>
                </select>
              </div>
            </div>

            <button
              type="submit"
              disabled={isSyncing}
              className="w-full py-2 px-4 rounded-lg bg-[#1e2536] hover:bg-slate-700 text-white font-semibold text-xs transition-colors"
            >
              Save AWS Bridge Settings
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
