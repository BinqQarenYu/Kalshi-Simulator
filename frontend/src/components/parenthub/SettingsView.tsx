import React from 'react';

interface SettingsViewProps {
  onFlattenHalt?: () => Promise<void> | void;
}

export const SettingsView: React.FC<SettingsViewProps> = ({ onFlattenHalt }) => {
  return (
    <div className="space-y-6 max-w-4xl">
      {/* Kalshi API & Execution Routing Section */}
      <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#8c9ba5]">
            Kalshi API & Execution Routing
          </h2>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/20 text-[#d9a752] border border-amber-500/30">
            ACTIVE
          </span>
        </div>

        <div className="grid grid-cols-2 gap-4 text-xs font-mono">
          <div className="space-y-1">
            <label className="text-[#8c9ba5] text-[10px] uppercase font-bold">API Key</label>
            <div className="flex items-center justify-between bg-[#1a2128] border border-[#262d35] rounded-md px-3 py-2 text-xs">
              <span className="text-[#2dd4bf] tracking-wider">KALSHI • L3 • •••••••• b8e2</span>
              <span className="text-emerald-400 text-[10px]">● connected</span>
            </div>
            <div className="text-[10px] text-[#8c9ba5]">Scoped to read + trade only. Zero withdrawal permission.</div>
          </div>

          <div className="space-y-1">
            <label className="text-[#8c9ba5] text-[10px] uppercase font-bold">Account ID</label>
            <input
              readOnly
              value="acct_qx9f2-alpaca-shard-b"
              className="w-full bg-[#1a2128] border border-[#262d35] rounded-md px-3 py-2 text-xs text-white"
            />
            <div className="text-[10px] text-[#8c9ba5]">Per-bot execution routing on promote.</div>
          </div>

          <div className="space-y-1">
            <label className="text-[#8c9ba5] text-[10px] uppercase font-bold">Routing Mode</label>
            <select className="w-full bg-[#1a2128] border border-[#262d35] rounded-md px-3 py-2 text-xs text-white">
              <option>FOK · Fill-or-Kill (default for 5M)</option>
              <option>GTC · Good-Till-Cancel (15M maker ladder)</option>
              <option>IOC · Immediate-or-Cancel (slippage guard)</option>
            </select>
            <div className="text-[10px] text-[#8c9ba5]">Each Baby Bot can override per-cycle.</div>
          </div>

          <div className="space-y-1">
            <label className="text-[#8c9ba5] text-[10px] uppercase font-bold">Slippage Tolerance</label>
            <input
              readOnly
              value="≤ 1.5¢ from mid"
              className="w-full bg-[#1a2128] border border-[#262d35] rounded-md px-3 py-2 text-xs text-white"
            />
            <div className="text-[10px] text-[#8c9ba5]">Reject entry if book top-of-book &lt; 6 contracts.</div>
          </div>
        </div>
      </div>

      {/* Promotion Threshold Gate Section */}
      <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-4">
        <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#8c9ba5]">
          Promotion Threshold · Promote-to-Baby Eligibility
        </h2>
        <div className="p-3 rounded-lg bg-[#f43f5e]/10 border border-[#f43f5e]/30 text-xs text-[#f43f5e] leading-relaxed">
          Promotion is a <b>HARD gate</b>. A Lab candidate becomes an authorized Baby Bot only when all six metrics pass for &ge; 500 paper/isolated-shadow events.
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d]">
            <div className="text-[10px] font-mono text-[#8c9ba5] uppercase">MIN WIN RATE</div>
            <div className="text-xl font-bold font-mono text-[#34d399] mt-1">&ge; 70%</div>
          </div>
          <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d]">
            <div className="text-[10px] font-mono text-[#8c9ba5] uppercase">MIN PROFIT FACTOR</div>
            <div className="text-xl font-bold font-mono text-[#34d399] mt-1">&ge; 1.60</div>
          </div>
          <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d]">
            <div className="text-[10px] font-mono text-[#8c9ba5] uppercase">MAX DRAWDOWN</div>
            <div className="text-xl font-bold font-mono text-[#f43f5e] mt-1">&le; 8%</div>
          </div>
          <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d]">
            <div className="text-[10px] font-mono text-[#8c9ba5] uppercase">MIN EDGE ¢</div>
            <div className="text-xl font-bold font-mono text-[#34d399] mt-1">&ge; +3.5¢</div>
          </div>
          <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d]">
            <div className="text-[10px] font-mono text-[#8c9ba5] uppercase">SHARPE RATIO</div>
            <div className="text-xl font-bold font-mono text-[#34d399] mt-1">&ge; 1.20</div>
          </div>
          <div className="p-3 rounded-lg bg-[#13171c] border border-[#1f262d]">
            <div className="text-[10px] font-mono text-[#8c9ba5] uppercase">PROMO COOLDOWN</div>
            <div className="text-xl font-bold font-mono text-white mt-1">24h</div>
          </div>
        </div>
      </div>

      {/* Per-Bot Defaults Section */}
      <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-4">
        <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#8c9ba5]">
          Per-Bot Micro-Bankroll & Safety Defaults
        </h2>

        <div className="grid grid-cols-2 gap-4 text-xs font-mono">
          <div className="space-y-1">
            <label className="text-[#8c9ba5] text-[10px] uppercase font-bold">Max contracts / event</label>
            <input readOnly value="1 (Hard Institutional Cap)" className="w-full bg-[#1a2128] border border-[#262d35] rounded-md px-3 py-2 text-xs text-amber-300 font-bold" />
          </div>
          <div className="space-y-1">
            <label className="text-[#8c9ba5] text-[10px] uppercase font-bold">Max contracts / session</label>
            <input readOnly value="40" className="w-full bg-[#1a2128] border border-[#262d35] rounded-md px-3 py-2 text-xs text-white" />
          </div>
          <div className="space-y-1">
            <label className="text-[#8c9ba5] text-[10px] uppercase font-bold">Max $ per side</label>
            <input readOnly value="$150" className="w-full bg-[#1a2128] border border-[#262d35] rounded-md px-3 py-2 text-xs text-white" />
          </div>
          <div className="space-y-1">
            <label className="text-[#8c9ba5] text-[10px] uppercase font-bold">Max concurrent Baby Bots</label>
            <input readOnly value="6" className="w-full bg-[#1a2128] border border-[#262d35] rounded-md px-3 py-2 text-xs text-white" />
          </div>
        </div>

        <div className="divide-y divide-[#1f262d] pt-2">
          <div className="py-2.5 flex items-center justify-between">
            <div>
              <div className="text-xs font-semibold text-white">Auto-flatten at T-5s for 5M contracts</div>
              <div className="text-[11px] text-[#8c9ba5]">Required for all Baby Bots. Disables only on lab-tier.</div>
            </div>
            <span className="text-[11px] font-mono font-bold text-[#00bda5] bg-[#00bda5]/15 px-2 py-0.5 rounded border border-[#00bda5]/30">ON</span>
          </div>
          <div className="py-2.5 flex items-center justify-between">
            <div>
              <div className="text-xs font-semibold text-white">Reject entries when book depth &le; 6</div>
              <div className="text-[11px] text-[#8c9ba5]">Skip signal rather than pay excessive slippage.</div>
            </div>
            <span className="text-[11px] font-mono font-bold text-[#00bda5] bg-[#00bda5]/15 px-2 py-0.5 rounded border border-[#00bda5]/30">ON</span>
          </div>
          <div className="py-2.5 flex items-center justify-between">
            <div>
              <div className="text-xs font-semibold text-white">Auto-pause losers (3 consecutive losses)</div>
              <div className="text-[11px] text-[#8c9ba5]">Pauses bot for 15 minutes — does not delete state.</div>
            </div>
            <span className="text-[11px] font-mono font-bold text-[#f43f5e] bg-[#f43f5e]/15 px-2 py-0.5 rounded border border-[#f43f5e]/30">ARMED</span>
          </div>
        </div>
      </div>

      {/* Global Kill-Switch */}
      <div className="bg-[#12161a] border border-[#262d35] rounded-xl p-5 space-y-4">
        <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#f43f5e]">
          Global Kill-Switch
        </h2>
        <div className="p-3 rounded-lg bg-[#f43f5e]/10 border border-[#f43f5e]/30 text-xs text-[#f43f5e] leading-relaxed">
          <b>WARNING.</b> Activating the global kill-switch sends <span className="font-mono bg-[#13171c] px-1.5 py-0.5 rounded text-[#2dd4bf]">FLATTEN_ALL</span> to every active Baby Bot, cancels open resting orders, and revokes session tokens for 60 seconds.
        </div>

        <button
          onClick={onFlattenHalt}
          className="w-full py-3.5 rounded-lg border-2 border-[#d31a38] text-[#f43f5e] font-extrabold text-xs uppercase tracking-wider hover:bg-[#d31a38]/10 transition-all shadow-lg cursor-pointer"
        >
          ★ FLATTEN ALL & HALT — GLOBAL ★
        </button>
      </div>
    </div>
  );
};
