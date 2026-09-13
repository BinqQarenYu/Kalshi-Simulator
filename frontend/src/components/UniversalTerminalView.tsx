import React, { useState } from 'react';
import {
  Globe,
  Coins,
  Cpu,
  Layers,
  Shield,
  Zap,
  Activity,
  ArrowRightLeft,
  DollarSign,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Sliders,
  SlidersHorizontal,
  Lock,
  ChevronRight,
  BarChart3,
  ExternalLink,
  Sparkles,
  Award,
  Clock,
  Flame,
  Info,
  X,
} from 'lucide-react';
import { soundFX } from '../utils/audioFX';

interface ExchangeNode {
  id: string;
  name: string;
  category: 'TradFi Binary' | 'Web3 Prediction' | 'Global Derivatives' | 'Grid / Rebalancing';
  currency: string;
  balance: number;
  allocatedPct: number;
  latencyMs: number;
  status: 'CONNECTED' | 'STANDBY' | 'MAINTENANCE';
  protocol: string;
  feeTier: string;
  color: string;
}

interface ArbitrageOpportunity {
  id: string;
  asset: string;
  cycle: string;
  venueA: { name: string; side: 'YES' | 'NO'; price: number };
  venueB: { name: string; side: 'YES' | 'NO'; price: number };
  grossSpreadCents: number;
  netEvPct: number;
  confidence: number;
  recommendedAction: string;
  status: 'SNIPE_READY' | 'NARROWING' | 'LOCKED';
}

const INITIAL_EXCHANGES: ExchangeNode[] = [
  {
    id: 'kalshi',
    name: 'Kalshi (CFTC)',
    category: 'TradFi Binary',
    currency: 'USD',
    balance: 45280.50,
    allocatedPct: 35.2,
    latencyMs: 12.4,
    status: 'CONNECTED',
    protocol: 'RSA 2048-bit Signed REST / 5Hz WS',
    feeTier: 'Maker 0.00% / Taker 7.00% Cap',
    color: '#00bda5',
  },
  {
    id: 'polymarket',
    name: 'Polymarket (Polygon)',
    category: 'Web3 Prediction',
    currency: 'USDC',
    balance: 38450.00,
    allocatedPct: 29.9,
    latencyMs: 18.2,
    status: 'CONNECTED',
    protocol: 'EIP-712 Smart Contract / Pyth Oracle',
    feeTier: '0.00% Gasless Relayer / LP Spread',
    color: '#3b82f6',
  },
  {
    id: 'binance',
    name: 'Binance Derivatives',
    category: 'Global Derivatives',
    currency: 'USDT',
    balance: 28600.25,
    allocatedPct: 22.3,
    latencyMs: 6.1,
    status: 'CONNECTED',
    protocol: 'HMAC-SHA256 / Depth20@100ms WS',
    feeTier: 'Maker 0.02% / Taker 0.04%',
    color: '#f59e0b',
  },
  {
    id: 'bybit',
    name: 'Bybit Linear Perpetuals',
    category: 'Global Derivatives',
    currency: 'USDT',
    balance: 10200.00,
    allocatedPct: 7.9,
    latencyMs: 9.4,
    status: 'STANDBY',
    protocol: 'V5 WebSocket / REST',
    feeTier: 'Maker 0.015% / Taker 0.05%',
    color: '#ec4899',
  },
  {
    id: 'htx',
    name: 'HTX Spot & Options',
    category: 'Global Derivatives',
    currency: 'USDT',
    balance: 4100.00,
    allocatedPct: 3.2,
    latencyMs: 14.8,
    status: 'STANDBY',
    protocol: 'Gzip JSON WebSocket',
    feeTier: 'Tier-1 Institutional',
    color: '#8b5cf6',
  },
  {
    id: 'pionex',
    name: 'Pionex Micro-Rebalancing',
    category: 'Grid / Rebalancing',
    currency: 'USDT',
    balance: 1819.25,
    allocatedPct: 1.5,
    latencyMs: 16.0,
    status: 'STANDBY',
    protocol: 'REST Grid Automation',
    feeTier: '0.05% Fixed Maker/Taker',
    color: '#10b981',
  },
];

const INITIAL_ARBITRAGE: ArbitrageOpportunity[] = [
  {
    id: 'arb-1',
    asset: 'BTC',
    cycle: 'KXBTC15M (5:30 PM ET)',
    venueA: { name: 'Kalshi', side: 'YES', price: 0.48 },
    venueB: { name: 'Polymarket', side: 'YES', price: 0.43 },
    grossSpreadCents: 5.0,
    netEvPct: 11.6,
    confidence: 84.5,
    recommendedAction: 'Buy Polymarket YES @ 43¢ (5¢ Discount vs Kalshi Lead)',
    status: 'SNIPE_READY',
  },
  {
    id: 'arb-2',
    asset: 'GOLD',
    cycle: 'KXGOLD15M (5:30 PM ET)',
    venueA: { name: 'Kalshi', side: 'YES', price: 0.52 },
    venueB: { name: 'Polymarket', side: 'YES', price: 0.47 },
    grossSpreadCents: 5.0,
    netEvPct: 10.6,
    confidence: 81.2,
    recommendedAction: 'Buy Polymarket YES @ 47¢ with Binance PAXG +$2.10 OFI Lead',
    status: 'SNIPE_READY',
  },
  {
    id: 'arb-3',
    asset: 'ETH',
    cycle: 'KXETH15M (5:30 PM ET)',
    venueA: { name: 'Kalshi', side: 'NO', price: 0.49 },
    venueB: { name: 'Binance Fut', side: 'NO', price: 0.46 },
    grossSpreadCents: 3.0,
    netEvPct: 6.5,
    confidence: 76.0,
    recommendedAction: 'Hedged Basis Scalp (Kalshi Discount vs Binance Future Mark)',
    status: 'NARROWING',
  },
];

export const UniversalTerminalView: React.FC = () => {
  const [exchanges, setExchanges] = useState<ExchangeNode[]>(INITIAL_EXCHANGES);
  const [arbitrageList, setArbitrageList] = useState<ArbitrageOpportunity[]>(INITIAL_ARBITRAGE);
  const [selectedAsset, setSelectedAsset] = useState<'BTC' | 'ETH' | 'GOLD' | 'SOL'>('BTC');
  const [executionRoute, setExecutionRoute] = useState<'BEST_VENUE' | 'CROSS_VENUE_ARB' | 'MULTI_VENUE_SPLIT'>('BEST_VENUE');
  const [orderSide, setOrderSide] = useState<'YES' | 'NO'>('YES');
  const [orderContracts, setOrderContracts] = useState<number>(1);
  const [targetDiscountCents, setTargetDiscountCents] = useState<number>(48);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [simulationResult, setSimulationResult] = useState<string | null>(null);
  const [selectedExchangeModal, setSelectedExchangeModal] = useState<ExchangeNode | null>(null);

  const totalPoolBalance = exchanges.reduce((acc, curr) => acc + curr.balance, 0);

  const handleSimulateOmniRoute = (arb: ArbitrageOpportunity) => {
    soundFX.playClickSound();
    setIsSimulating(true);
    setSimulationResult(null);

    setTimeout(() => {
      soundFX.playOrderFillSound();
      setIsSimulating(false);
      setSimulationResult(
        `✅ Successfully dispatched Cross-Venue Smart Route! Routed 1 Contract to ${arb.venueB.name} (${(arb.venueB.price * 100).toFixed(0)}¢) capturing +${arb.grossSpreadCents.toFixed(1)}¢ net edge.`
      );
      setTimeout(() => setSimulationResult(null), 6000);
    }, 900);
  };

  const handleExecuteSlip = () => {
    soundFX.playClickSound();
    setIsSimulating(true);
    setSimulationResult(null);

    setTimeout(() => {
      soundFX.playOrderFillSound();
      setIsSimulating(false);
      setSimulationResult(
        `⚡ Omni-Order Executed: ${selectedAsset} ${orderSide} @ ${targetDiscountCents}¢ across optimal venue router (${executionRoute}). Invariant Micro-Bankroll Guard verified.`
      );
      setTimeout(() => setSimulationResult(null), 5000);
    }, 750);
  };

  return (
    <div className="space-y-6 font-mono text-xs pb-12">
      {/* Top Banner: Global Liquidity & Consolidated Wealth Header */}
      <div className="bg-gradient-to-r from-[#0c121e] via-[#111726] to-[#0c121e] border border-[#26354a] rounded-2xl p-6 shadow-2xl space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-[#212d3e] pb-5">
          <div className="flex items-center gap-3.5">
            <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-blue-500/30 border border-cyan-500/40 flex items-center justify-center shrink-0 shadow-inner">
              <Globe className="w-6 h-6 text-cyan-300 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-lg font-bold text-white uppercase tracking-wider">
                  The Universal Multi-Exchange Quantitative Terminal
                </h1>
                <span className="px-2.5 py-0.5 text-[10px] font-mono bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 rounded-full font-bold">
                  Consolidated Capital Pool v4.0
                </span>
              </div>
              <p className="text-xs text-[#8c9ba5] font-sans mt-0.5">
                Unified multi-exchange routing across TradFi binaries, Web3 prediction CLOBs, and continuous crypto derivatives.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-[10px] uppercase text-[#8c9ba5] font-semibold">Total Capital Pool</div>
              <div className="text-xl font-bold font-mono text-white tracking-tight">
                ${totalPoolBalance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
            </div>
            <button
              onClick={() => {
                soundFX.playClickSound();
                setSimulationResult('🔄 Synchronizing all 6 exchange balances and L2 WebSocket order books...');
                setTimeout(() => setSimulationResult(null), 2500);
              }}
              title="Resync All Exchanges"
              className="p-2 rounded-xl border border-[#26354a] bg-[#162133] hover:bg-[#1f2d45] text-cyan-300 transition-colors shadow-sm cursor-pointer"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* 6-Venue Live Telemetry Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
          {exchanges.map((ex) => (
            <div
              key={ex.id}
              onClick={() => setSelectedExchangeModal(ex)}
              className="bg-[#0b101a] border border-[#1e2a3c] hover:border-cyan-500/40 rounded-xl p-3 space-y-1.5 transition-all cursor-pointer hover:scale-[1.02] shadow-sm"
            >
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold text-white truncate">{ex.name.split(' ')[0]}</span>
                <span
                  className={`w-2 h-2 rounded-full ${
                    ex.status === 'CONNECTED' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
                  }`}
                />
              </div>
              <div className="text-xs font-bold text-slate-200">
                ${ex.balance.toLocaleString('en-US', { maximumFractionDigits: 0 })}
              </div>
              <div className="flex items-center justify-between text-[9px] text-[#8c9ba5] pt-0.5">
                <span>{ex.latencyMs}ms</span>
                <span className="font-bold text-cyan-400">{ex.allocatedPct}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Feedback & Simulation Alert */}
      {simulationResult && (
        <div className="p-3.5 rounded-xl bg-cyan-500/10 border border-cyan-500/40 text-cyan-200 text-xs flex items-center justify-between animate-in fade-in shadow-lg">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-cyan-400 shrink-0" />
            <span>{simulationResult}</span>
          </div>
          <button onClick={() => setSimulationResult(null)} className="text-gray-400 hover:text-white">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Main 2-Column Split: Left = Arbitrage & Multi-Brain | Right = Capital Pool & Execution Slip */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        
        {/* =========================================================================
            LEFT COLUMN (7 cols): Cross-Exchange Arbitrage & Multi-Brain Telemetry
            ========================================================================= */}
        <div className="lg:col-span-7 space-y-6">

          {/* Card 1: Live Cross-Exchange Arbitrage Radar */}
          <div className="bg-[#12161a] border border-[#262d35] rounded-2xl p-5 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-[#21262d] pb-3">
              <div className="flex items-center gap-2.5">
                <ArrowRightLeft className="w-4 h-4 text-emerald-400" />
                <div>
                  <h2 className="text-xs font-bold uppercase tracking-wider text-white">
                    Cross-Exchange Mispricing &amp; Arbitrage Radar
                  </h2>
                  <p className="text-[11px] text-[#8c9ba5] mt-0.5">
                    Live detection of spread differentials and pricing lag across Kalshi, Polymarket, and Binance.
                  </p>
                </div>
              </div>
              <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/15 px-2 py-0.5 rounded border border-emerald-500/30 font-bold">
                SNIPER ARMED
              </span>
            </div>

            <div className="space-y-3">
              {arbitrageList.map((arb) => (
                <div
                  key={arb.id}
                  className="bg-[#161b22] border border-[#30363d] hover:border-emerald-500/40 rounded-xl p-3.5 space-y-2.5 transition-all shadow-sm"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 rounded text-[10px] font-bold">
                        {arb.asset}
                      </span>
                      <span className="text-xs font-bold text-white">{arb.cycle}</span>
                    </div>
                    <div className="flex items-center gap-1.5 font-mono">
                      <span className="text-[10px] text-[#8c9ba5]">Net Edge:</span>
                      <span className="text-xs font-bold text-emerald-400">+{arb.netEvPct}%</span>
                    </div>
                  </div>

                  {/* Pricing Comparison Ladder */}
                  <div className="grid grid-cols-2 gap-2 text-center text-xs font-mono">
                    <div className="bg-[#0e131a] p-2 rounded-lg border border-[#212a36]">
                      <span className="text-[9px] text-[#8c9ba5] block uppercase">{arb.venueA.name}</span>
                      <span className="text-slate-300 font-bold">
                        {arb.venueA.side} @ {(arb.venueA.price * 100).toFixed(0)}¢
                      </span>
                    </div>
                    <div className="bg-[#0e131a] p-2 rounded-lg border border-emerald-500/30">
                      <span className="text-[9px] text-emerald-400 block uppercase font-bold">{arb.venueB.name} (Discount)</span>
                      <span className="text-emerald-300 font-bold">
                        {arb.venueB.side} @ {(arb.venueB.price * 100).toFixed(0)}¢
                      </span>
                    </div>
                  </div>

                  {/* Recommendation & Dispatch Button */}
                  <div className="flex items-center justify-between pt-1">
                    <div className="text-[10px] text-slate-300 flex items-center gap-1.5">
                      <Zap className="w-3 h-3 text-amber-400 shrink-0" />
                      <span>{arb.recommendedAction}</span>
                    </div>
                    <button
                      onClick={() => handleSimulateOmniRoute(arb)}
                      disabled={isSimulating}
                      className="px-3 py-1.5 bg-[#00bda5] hover:bg-[#2dd4bf] text-black font-bold text-[10px] rounded-lg transition-all shadow-md active:scale-95 disabled:opacity-50 cursor-pointer"
                    >
                      {isSimulating ? 'Routing...' : 'Snipe Spread ⚡'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Card 2: Multi-Brain ONNX Fleet Deck */}
          <div className="bg-[#12161a] border border-[#262d35] rounded-2xl p-5 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-[#21262d] pb-3">
              <div className="flex items-center gap-2.5">
                <Cpu className="w-4 h-4 text-cyan-400" />
                <div>
                  <h2 className="text-xs font-bold uppercase tracking-wider text-white">
                    Multi-Brain ONNX Neural Fleet
                  </h2>
                  <p className="text-[11px] text-[#8c9ba5] mt-0.5">
                    Real-time inference matrix powering microsecond cross-exchange decision making.
                  </p>
                </div>
              </div>
              <span className="text-[10px] font-mono text-cyan-300 bg-cyan-500/15 px-2 py-0.5 rounded border border-cyan-500/30">
                SUB-2MS INFERENCE
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* Brain 1 */}
              <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-white">Brain 1: Spot Macro</span>
                  <span className="text-[9px] font-bold text-emerald-400 bg-emerald-500/15 px-1.5 py-0.5 rounded">28-D</span>
                </div>
                <div className="text-[10px] text-gray-400">Binance 5Hz L2 + aggTrade Lead Anchor</div>
                <div className="font-mono text-xs text-cyan-300 font-bold">P(UP): 82.4%</div>
                <div className="text-[9px] text-gray-500">Latency: 1.8ms • Lane 1</div>
              </div>

              {/* Brain 2 */}
              <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-white">Brain 2: CLOB Sniper</span>
                  <span className="text-[9px] font-bold text-emerald-400 bg-emerald-500/15 px-1.5 py-0.5 rounded">28-D</span>
                </div>
                <div className="text-[10px] text-gray-400">Kalshi Inside Touch Momentum</div>
                <div className="font-mono text-xs text-cyan-300 font-bold">P(UP): 79.1%</div>
                <div className="text-[9px] text-gray-500">Latency: 1.2ms • Lane 1</div>
              </div>

              {/* Brain 3 */}
              <div className="bg-amber-950/20 border border-amber-500/40 rounded-xl p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-amber-300">Brain 3: Gold Spacetime</span>
                  <span className="text-[9px] font-bold text-amber-300 bg-amber-500/20 px-1.5 py-0.5 rounded">32-D NEW</span>
                </div>
                <div className="text-[10px] text-gray-300">Gold Orderflow + 4 Spacetime Dimensions</div>
                <div className="font-mono text-xs text-amber-400 font-bold">P(UP): 84.8%</div>
                <div className="text-[9px] text-amber-300/70">Latency: 1.5ms • Tri-Venue</div>
              </div>
            </div>
          </div>
        </div>

        {/* =========================================================================
            RIGHT COLUMN (5 cols): Capital Pool Manager & Omni-Execution Slip
            ========================================================================= */}
        <div className="lg:col-span-5 space-y-6">

          {/* Card 3: Consolidated Capital Pool Manager */}
          <div className="bg-[#12161a] border border-[#262d35] rounded-2xl p-5 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-[#21262d] pb-3">
              <div className="flex items-center gap-2.5">
                <Coins className="w-4 h-4 text-amber-400" />
                <div>
                  <h2 className="text-xs font-bold uppercase tracking-wider text-white">
                    Liquidity Distribution
                  </h2>
                  <p className="text-[11px] text-[#8c9ba5] mt-0.5">
                    Real-time capital balance across all exchange wallets.
                  </p>
                </div>
              </div>
              <span className="text-xs font-bold text-white font-mono">
                ${totalPoolBalance.toLocaleString('en-US', { maximumFractionDigits: 0 })}
              </span>
            </div>

            {/* Distribution Visual Bars */}
            <div className="space-y-2.5">
              {exchanges.map((ex) => (
                <div key={ex.id} className="space-y-1">
                  <div className="flex justify-between text-[11px]">
                    <span className="text-slate-300 font-medium">{ex.name}</span>
                    <span className="font-mono text-gray-400">
                      ${ex.balance.toLocaleString('en-US', { maximumFractionDigits: 2 })} ({ex.allocatedPct}%)
                    </span>
                  </div>
                  <div className="h-2 w-full bg-[#1c232d] rounded-full overflow-hidden">
                    <div
                      style={{ width: `${ex.allocatedPct}%`, backgroundColor: ex.color }}
                      className="h-full rounded-full transition-all duration-500"
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* Anti-Cannibalism Shield Status */}
            <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-3 text-[11px] space-y-1">
              <div className="flex items-center justify-between text-white font-bold">
                <span className="flex items-center gap-1.5">
                  <Shield className="w-3.5 h-3.5 text-cyan-400" />
                  Anti-Wash Trading Shield
                </span>
                <span className="text-emerald-400 text-[10px]">ACTIVE &amp; ENFORCED</span>
              </div>
              <p className="text-[#8c9ba5] text-[10px] leading-tight">
                LiveCoordinator synchronously prevents opposing directional positions (e.g. YES on Kalshi vs NO on Polymarket) across all connected exchange accounts.
              </p>
            </div>
          </div>

          {/* Card 4: Omni-Execution Smart Order Slip */}
          <div className="bg-[#12161a] border border-[#262d35] rounded-2xl p-5 space-y-4 shadow-xl">
            <div className="flex items-center justify-between border-b border-[#21262d] pb-3">
              <div className="flex items-center gap-2.5">
                <SlidersHorizontal className="w-4 h-4 text-purple-400" />
                <div>
                  <h2 className="text-xs font-bold uppercase tracking-wider text-white">
                    Omni-Router Execution Slip
                  </h2>
                  <p className="text-[11px] text-[#8c9ba5] mt-0.5">
                    1-Click multi-exchange order routing with micro-bankroll armor.
                  </p>
                </div>
              </div>
              <span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 text-[10px] font-bold border border-purple-500/30">
                1 CT ARMOR
              </span>
            </div>

            {/* Asset Selector */}
            <div className="space-y-1">
              <label className="text-[10px] uppercase text-[#8c9ba5] font-semibold">Underlying Asset</label>
              <div className="grid grid-cols-4 gap-1.5">
                {(['BTC', 'ETH', 'GOLD', 'SOL'] as const).map((ast) => (
                  <button
                    key={ast}
                    onClick={() => setSelectedAsset(ast)}
                    className={`py-1.5 rounded-lg font-bold text-xs transition-all border ${
                      selectedAsset === ast
                        ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-300 shadow-sm'
                        : 'bg-[#161b22] border-[#262d35] text-gray-400 hover:text-white'
                    }`}
                  >
                    {ast}
                  </button>
                ))}
              </div>
            </div>

            {/* Route Mode Selector */}
            <div className="space-y-1">
              <label className="text-[10px] uppercase text-[#8c9ba5] font-semibold">Routing Logic</label>
              <select
                value={executionRoute}
                onChange={(e) => setExecutionRoute(e.target.value as any)}
                className="w-full bg-[#0a0c10] border border-[#262d35] rounded-lg p-2 text-white text-xs focus:outline-none focus:border-cyan-500 cursor-pointer"
              >
                <option value="BEST_VENUE">BEST_VENUE (Route to Cheapest Spread &amp; Fee)</option>
                <option value="CROSS_VENUE_ARB">CROSS_VENUE_ARB (Simultaneous Dual-Exchange Arbitrage)</option>
                <option value="MULTI_VENUE_SPLIT">MULTI_VENUE_SPLIT (Liquidity Weighted Depth Fill)</option>
              </select>
            </div>

            {/* Side Selection */}
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setOrderSide('YES')}
                className={`py-2 rounded-xl font-bold text-xs transition-all border ${
                  orderSide === 'YES'
                    ? 'bg-emerald-500/20 border-emerald-500/60 text-emerald-300 shadow-md'
                    : 'bg-[#161b22] border-[#262d35] text-gray-400'
                }`}
              >
                BUY YES (Long)
              </button>
              <button
                onClick={() => setOrderSide('NO')}
                className={`py-2 rounded-xl font-bold text-xs transition-all border ${
                  orderSide === 'NO'
                    ? 'bg-rose-500/20 border-rose-500/60 text-rose-300 shadow-md'
                    : 'bg-[#161b22] border-[#262d35] text-gray-400'
                }`}
              >
                BUY NO (Short)
              </button>
            </div>

            {/* Target Price Ceiling Slider */}
            <div className="space-y-1 pt-1">
              <div className="flex justify-between text-[10px] text-[#8c9ba5] font-semibold">
                <span>MAKER DISCOUNT CEILING</span>
                <span className="text-amber-400 font-bold font-mono">{targetDiscountCents}¢ ($0.00 Fee)</span>
              </div>
              <input
                type="range"
                min="20"
                max="55"
                step="1"
                value={targetDiscountCents}
                onChange={(e) => setTargetDiscountCents(parseInt(e.target.value))}
                className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-amber-400"
              />
            </div>

            {/* Execute Dispatch */}
            <button
              onClick={handleExecuteSlip}
              disabled={isSimulating}
              className="w-full py-3 bg-gradient-to-r from-[#00bda5] to-[#2dd4bf] text-black font-extrabold text-xs uppercase tracking-wider rounded-xl transition-all shadow-lg hover:brightness-110 active:scale-95 disabled:opacity-50 cursor-pointer"
            >
              {isSimulating ? 'Routing Across Venues...' : `Dispatch Smart Order (${selectedAsset} ${orderSide} @ ${targetDiscountCents}¢)`}
            </button>
          </div>
        </div>
      </div>

      {/* Exchange Detail Deep Inspection Modal */}
      {selectedExchangeModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in"
          onClick={() => setSelectedExchangeModal(null)}
        >
          <div
            className="bg-[#0f131d] border border-[#28324a] rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl font-mono"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-[#262d35] pb-3">
              <div className="flex items-center gap-2.5">
                <Globe className="w-5 h-5 text-cyan-400" />
                <div>
                  <h3 className="font-bold text-white text-sm">{selectedExchangeModal.name}</h3>
                  <span className="text-[10px] text-gray-400">{selectedExchangeModal.category}</span>
                </div>
              </div>
              <button
                onClick={() => setSelectedExchangeModal(null)}
                className="text-gray-400 hover:text-white p-1 rounded-lg hover:bg-white/5 transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between p-2 bg-[#090c14] rounded-lg border border-white/5">
                <span className="text-gray-400">Currency &amp; Collateral:</span>
                <span className="text-white font-bold">{selectedExchangeModal.currency}</span>
              </div>
              <div className="flex justify-between p-2 bg-[#090c14] rounded-lg border border-white/5">
                <span className="text-gray-400">Live Pool Balance:</span>
                <span className="text-emerald-400 font-bold">${selectedExchangeModal.balance.toFixed(2)}</span>
              </div>
              <div className="flex justify-between p-2 bg-[#090c14] rounded-lg border border-white/5">
                <span className="text-gray-400">API Protocol:</span>
                <span className="text-cyan-300">{selectedExchangeModal.protocol}</span>
              </div>
              <div className="flex justify-between p-2 bg-[#090c14] rounded-lg border border-white/5">
                <span className="text-gray-400">Fee Tier Structure:</span>
                <span className="text-amber-300">{selectedExchangeModal.feeTier}</span>
              </div>
              <div className="flex justify-between p-2 bg-[#090c14] rounded-lg border border-white/5">
                <span className="text-gray-400">WebSocket Ping Latency:</span>
                <span className="text-emerald-300">{selectedExchangeModal.latencyMs}ms</span>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setSelectedExchangeModal(null)}
                className="px-4 py-2 bg-[#1e293b] hover:bg-[#334155] text-white text-xs font-bold rounded-xl transition-colors cursor-pointer"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
