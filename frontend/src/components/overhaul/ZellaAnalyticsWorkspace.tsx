import React, { useMemo, useState } from 'react';
import Decimal from 'decimal.js';
import {
  RefreshCw,
  Rocket,
  SlidersHorizontal,
  TrendingUp,
  TrendingDown,
  ShieldCheck,
  Info,
} from 'lucide-react';
import { CryptoAsset, LivePortfolioState, MarketState } from '../../types';

interface ZellaAnalyticsWorkspaceProps {
  market: MarketState;
  portfolio?: {
    balance: number;
    equity: number;
    realized_pnl: number;
    unrealized_pnl: number;
    win_rate: number;
    total_trades: number;
    wins: number;
    losses: number;
    positions: any[];
    settlements: any[];
  };
  livePortfolio?: LivePortfolioState | null;
  reports?: any[];
  tradingMode: 'paper' | 'live';
  onResyncMemory?: () => void;
  onRunAuditNow?: () => void;
  onSelectAsset?: (asset: CryptoAsset) => void;
}

interface NormalizedTrade {
  id: string;
  ticker: string;
  asset: 'BTC' | 'ETH';
  outcome: 'win' | 'loss' | 'breakeven';
  pnl: Decimal;
  timestamp: string;
  dateLabel: string;
  cycleLabel: string;
  botId: string;
  isLive: boolean;
}

export const ZellaAnalyticsWorkspace: React.FC<ZellaAnalyticsWorkspaceProps> = ({
  market,
  portfolio,
  livePortfolio,
  reports = [],
  tradingMode,
  onResyncMemory,
  onRunAuditNow,
  onSelectAsset,
}) => {
  const [unitMode, setUnitMode] = useState<'dollar' | 'pct'>('dollar');
  const [assetFilter, setAssetFilter] = useState<'ALL' | 'BTC' | 'ETH'>('ALL');
  const [accountFilter, setAccountFilter] = useState<'ALL' | 'LIVE' | 'PAPER'>('ALL');
  const [windowLimit, setWindowLimit] = useState<number>(60);
  const [hoveredPointIdx, setHoveredPointIdx] = useState<number | null>(null);
  const [hoveredBarIdx, setHoveredBarIdx] = useState<number | null>(null);

  // Normalize settlements & win_loss_reports using strict Decimal math
  const normalizedTrades = useMemo<NormalizedTrade[]>(() => {
    const rawList: any[] = [];
    if (Array.isArray(reports) && reports.length > 0) {
      rawList.push(...reports);
    }
    if (Array.isArray(portfolio?.settlements)) {
      for (const s of portfolio!.settlements) {
        if (!rawList.some((r) => r.report_id && r.report_id === s.report_id)) {
          rawList.push(s);
        }
      }
    }

    const mapped: NormalizedTrade[] = rawList.map((item, idx) => {
      const ticker = String(item.ticker || market?.ticker || 'KXBTC15M');
      const isEth =
        String(item.asset || '').toUpperCase() === 'ETH' ||
        ticker.toUpperCase().includes('ETH');
      const rawPnl = item.pnl ?? item.realized_pnl ?? item.net_pnl ?? 0;
      let pnlDec = new Decimal(0);
      try {
        pnlDec = new Decimal(String(rawPnl));
      } catch {
        pnlDec = new Decimal(0);
      }

      const rawOutcome = String(item.outcome || '').toLowerCase();
      let outcome: 'win' | 'loss' | 'breakeven' = 'breakeven';
      if (rawOutcome === 'win' || pnlDec.gt(0)) {
        outcome = 'win';
      } else if (rawOutcome === 'loss' || pnlDec.lt(0)) {
        outcome = 'loss';
      }

      const ts = String(item.timestamp || item.settled_at || new Date().toISOString());
      const datePart = ts.slice(5, 10).replace('-', '/') || `10/${String((idx % 19) + 1).padStart(2, '0')}`;
      const timePart = ts.slice(11, 16) || `${String((idx % 12) + 8).padStart(2, '0')}:${idx % 2 === 0 ? '15' : '45'}`;
      const modeStr = String(item.execution_mode || item.mode || 'live').toLowerCase();

      return {
        id: String(item.report_id || item.id || `tr_${idx}`),
        ticker,
        asset: isEth ? 'ETH' : 'BTC',
        outcome,
        pnl: pnlDec,
        timestamp: ts,
        dateLabel: datePart,
        cycleLabel: `${datePart} ${timePart}`,
        botId: String(item.bot_type || item.strategy_id || 'bot1_v4_domination'),
        isLive: modeStr === 'live',
      };
    });

    // Filter by asset & account
    const filtered = mapped.filter((t) => {
      if (assetFilter !== 'ALL' && t.asset !== assetFilter) return false;
      if (accountFilter === 'LIVE' && !t.isLive) return false;
      if (accountFilter === 'PAPER' && t.isLive) return false;
      return true;
    });

    // Chronological order (oldest -> newest) for cumulative curve
    return filtered.slice(0, windowLimit).reverse();
  }, [reports, portfolio?.settlements, market?.ticker, assetFilter, accountFilter, windowLimit]);

  // Compute all KPI metrics with strict Decimal.js math
  const metrics = useMemo(() => {
    const totalCount = normalizedTrades.length;
    let netPnl = new Decimal(0);
    let grossProfit = new Decimal(0);
    let grossLoss = new Decimal(0);
    let wins = 0;
    let losses = 0;
    let breakevens = 0;

    const cycleBuckets = new Map<string, Decimal>();
    const cumulativeSeries: { label: string; cumPnl: number; tradePnl: number; ticker: string }[] = [];
    let runningPnl = new Decimal(0);
    let peakPnl = new Decimal(0);
    let maxDrawdown = new Decimal(0);

    for (const t of normalizedTrades) {
      netPnl = netPnl.plus(t.pnl);
      runningPnl = runningPnl.plus(t.pnl);
      if (runningPnl.gt(peakPnl)) {
        peakPnl = runningPnl;
      }
      const dd = peakPnl.minus(runningPnl);
      if (dd.gt(maxDrawdown)) {
        maxDrawdown = dd;
      }

      if (t.outcome === 'win') {
        wins += 1;
        if (t.pnl.gt(0)) grossProfit = grossProfit.plus(t.pnl);
      } else if (t.outcome === 'loss') {
        losses += 1;
        if (t.pnl.lt(0)) grossLoss = grossLoss.plus(t.pnl.abs());
      } else {
        breakevens += 1;
      }

      const prevBucket = cycleBuckets.get(t.cycleLabel) || new Decimal(0);
      cycleBuckets.set(t.cycleLabel, prevBucket.plus(t.pnl));

      cumulativeSeries.push({
        label: t.cycleLabel,
        cumPnl: runningPnl.toDecimalPlaces(2).toNumber(),
        tradePnl: t.pnl.toDecimalPlaces(2).toNumber(),
        ticker: t.ticker,
      });
    }

    const winRatePct =
      totalCount > 0
        ? new Decimal(wins).div(totalCount).mul(100).toDecimalPlaces(2)
        : new Decimal(0);

    const profitFactor = grossLoss.gt(0)
      ? grossProfit.div(grossLoss).toDecimalPlaces(2)
      : grossProfit.gt(0)
      ? new Decimal('2.50')
      : new Decimal('1.00');

    const avgWin = wins > 0 ? grossProfit.div(wins).toDecimalPlaces(2) : new Decimal(0);
    const avgLoss = losses > 0 ? grossLoss.div(losses).toDecimalPlaces(2) : new Decimal(0);
    const avgWinLossRatio = avgLoss.gt(0)
      ? avgWin.div(avgLoss).toDecimalPlaces(2)
      : avgWin.gt(0)
      ? new Decimal('1.85')
      : new Decimal('1.00');

    let cycleWins = 0;
    let cycleLosses = 0;
    let cycleFlat = 0;
    const barSeries: { label: string; pnl: number }[] = [];

    for (const [label, bucketPnl] of cycleBuckets.entries()) {
      if (bucketPnl.gt(0)) cycleWins += 1;
      else if (bucketPnl.lt(0)) cycleLosses += 1;
      else cycleFlat += 1;
      barSeries.push({ label, pnl: bucketPnl.toDecimalPlaces(2).toNumber() });
    }

    const totalCycles = cycleWins + cycleLosses + cycleFlat;
    const cycleWinPct =
      totalCycles > 0
        ? new Decimal(cycleWins).div(totalCycles).mul(100).toDecimalPlaces(2)
        : winRatePct;

    // 6-Axis Radar vertices (0 to 100 scale)
    const winAxis = Decimal.min(100, Decimal.max(20, winRatePct.mul('1.25'))).toNumber();
    const pfAxis = Decimal.min(100, Decimal.max(20, profitFactor.mul(42))).toNumber();
    const awlAxis = Decimal.min(100, Decimal.max(20, avgWinLossRatio.mul(45))).toNumber();
    const ddRatio = peakPnl.gt(0)
      ? Decimal.max(0, new Decimal(100).minus(maxDrawdown.div(Decimal.max(peakPnl, new Decimal(1))).mul(60)))
      : new Decimal(74);
    const ddAxis = Decimal.min(100, Decimal.max(25, ddRatio)).toNumber();
    const recoveryAxis = maxDrawdown.gt(0)
      ? Decimal.min(100, Decimal.max(25, netPnl.abs().div(maxDrawdown).mul(38))).toNumber()
      : 78;
    const consistencyAxis = Decimal.min(100, Decimal.max(30, cycleWinPct.mul('1.2'))).toNumber();

    const compositeScore = new Decimal(
      (winAxis + pfAxis + awlAxis + ddAxis + recoveryAxis + consistencyAxis) / 6
    ).toDecimalPlaces(2);

    return {
      totalCount,
      netPnl,
      wins,
      losses,
      breakevens,
      winRatePct,
      profitFactor,
      avgWin,
      avgLoss,
      avgWinLossRatio,
      cycleWins,
      cycleLosses,
      cycleFlat,
      cycleWinPct,
      cumulativeSeries,
      barSeries: barSeries.slice(-24),
      radarAxes: [
        { label: 'Win %', value: winAxis },
        { label: 'Profit factor', value: pfAxis },
        { label: 'Avg win/loss', value: awlAxis },
        { label: 'Recovery factor', value: recoveryAxis },
        { label: 'Max drawdown', value: ddAxis },
        { label: 'Consistency', value: consistencyAxis },
      ],
      compositeScore,
    };
  }, [normalizedTrades]);

  // SVG Radar Geometry helper
  const radarGeometry = useMemo(() => {
    const cx = 170;
    const cy = 135;
    const maxR = 88;
    const angles = [-90, -30, 30, 90, 150, 210].map((deg) => (deg * Math.PI) / 180);

    const rings = [0.25, 0.5, 0.75, 1.0].map((scale) => {
      const pts = angles
        .map((a) => `${(cx + Math.cos(a) * maxR * scale).toFixed(1)},${(cy + Math.sin(a) * maxR * scale).toFixed(1)}`)
        .join(' ');
      return pts;
    });

    const dataCoords = metrics.radarAxes.map((axis, i) => {
      const r = (axis.value / 100) * maxR;
      const x = cx + Math.cos(angles[i]) * r;
      const y = cy + Math.sin(angles[i]) * r;
      const lx = cx + Math.cos(angles[i]) * (maxR + 28);
      const ly = cy + Math.sin(angles[i]) * (maxR + 20);
      return { x, y, lx, ly, label: axis.label, value: axis.value };
    });

    const polygonPoints = dataCoords.map((d) => `${d.x.toFixed(1)},${d.y.toFixed(1)}`).join(' ');
    return { cx, cy, maxR, angles, rings, dataCoords, polygonPoints };
  }, [metrics.radarAxes]);

  // SVG Area Chart Geometry helper
  const areaChartGeometry = useMemo(() => {
    const pts = metrics.cumulativeSeries;
    const width = 520;
    const height = 220;
    const padL = 52;
    const padR = 16;
    const padT = 18;
    const padB = 28;
    const plotW = width - padL - padR;
    const plotH = height - padT - padB;

    if (pts.length === 0) {
      return { width, height, padL, padT, plotW, plotH, linePath: '', areaPath: '', zeroY: padT + plotH / 2, coords: [], yTicks: [0, 5, 10] };
    }

    const values = pts.map((p) => p.cumPnl);
    const minVal = Math.min(0, ...values);
    const maxVal = Math.max(1, ...values);
    const span = Math.max(0.5, maxVal - minVal);

    const toY = (v: number) => padT + plotH - ((v - minVal) / span) * plotH;
    const zeroY = toY(0);

    const coords = pts.map((p, i) => {
      const x = padL + (pts.length === 1 ? plotW / 2 : (i / (pts.length - 1)) * plotW);
      const y = toY(p.cumPnl);
      return { x, y, ...p };
    });

    const linePath = coords
      .map((c, i) => `${i === 0 ? 'M' : 'L'} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`)
      .join(' ');
    const areaPath = `${linePath} L ${coords[coords.length - 1].x.toFixed(1)} ${zeroY.toFixed(1)} L ${coords[0].x.toFixed(1)} ${zeroY.toFixed(1)} Z`;

    const step = span / 4;
    const yTicks = [minVal, minVal + step, minVal + step * 2, minVal + step * 3, maxVal];

    return { width, height, padL, padT, plotW, plotH, linePath, areaPath, zeroY, coords, yTicks };
  }, [metrics.cumulativeSeries]);

  const winArcDash = useMemo(() => {
    const pct = Math.max(0, Math.min(100, metrics.winRatePct.toNumber()));
    const arcLen = 125.6; // pi * r (r=40)
    return `${((pct / 100) * arcLen).toFixed(1)} ${arcLen}`;
  }, [metrics.winRatePct]);

  const cycleArcDash = useMemo(() => {
    const pct = Math.max(0, Math.min(100, metrics.cycleWinPct.toNumber()));
    const arcLen = 125.6;
    return `${((pct / 100) * arcLen).toFixed(1)} ${arcLen}`;
  }, [metrics.cycleWinPct]);

  const pfRingDash = useMemo(() => {
    const pf = metrics.profitFactor.toNumber();
    const ratio = Math.max(0.1, Math.min(0.92, pf / (pf + 1)));
    const circum = 2 * Math.PI * 24;
    return `${(ratio * circum).toFixed(1)} ${circum.toFixed(1)}`;
  }, [metrics.profitFactor]);

  const avgWinBarPct = useMemo(() => {
    const w = metrics.avgWin.toNumber();
    const l = metrics.avgLoss.toNumber();
    if (w + l <= 0) return 60;
    return Math.max(15, Math.min(85, Math.round((w / (w + l)) * 100)));
  }, [metrics.avgWin, metrics.avgLoss]);

  const isPositiveNet = metrics.netPnl.gte(0);
  const startingCap = tradingMode === 'live' ? new Decimal(25) : new Decimal(100);
  const netDisplay =
    unitMode === 'dollar'
      ? `${isPositiveNet ? '' : '-'}$${metrics.netPnl.abs().toFixed(2)}`
      : `${isPositiveNet ? '+' : '-'}${metrics.netPnl.abs().div(startingCap).mul(100).toFixed(2)}%`;

  return (
    <div className="w-full max-w-[1600px] mx-auto px-6 py-5 space-y-5">
      {/* Top Header & Filter Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-xs font-medium text-[#6366f1] tracking-wide">Tracking</div>
          <h1 className="text-2xl font-bold tracking-tight text-white font-display">Dashboard</h1>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* Dollar / % Segmented Toggle */}
          <div className="flex items-center bg-[#121621] border border-[#1e2536] rounded-lg p-1">
            <button
              onClick={() => setUnitMode('dollar')}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors whitespace-nowrap shrink-0 ${
                unitMode === 'dollar'
                  ? 'bg-[#1e2536] text-white'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Dollar
            </button>
            <button
              onClick={() => setUnitMode('pct')}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors whitespace-nowrap shrink-0 ${
                unitMode === 'pct'
                  ? 'bg-[#1e2536] text-white'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Return %
            </button>
          </div>

          {/* Asset Selector */}
          <div className="flex items-center bg-[#121621] border border-[#1e2536] rounded-lg p-1">
            {(['ALL', 'BTC', 'ETH'] as const).map((asset) => (
              <button
                key={asset}
                onClick={() => {
                  setAssetFilter(asset);
                  if (asset !== 'ALL' && onSelectAsset) {
                    onSelectAsset(asset);
                  }
                }}
                className={`px-3 py-1 text-xs font-medium rounded-md transition-colors whitespace-nowrap shrink-0 ${
                  assetFilter === asset
                    ? 'bg-[#6366f1] text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {asset === 'ALL' ? 'All Assets' : asset}
              </button>
            ))}
          </div>

          {/* Cycle Window Selector */}
          <select
            value={windowLimit}
            onChange={(e) => setWindowLimit(Number(e.target.value))}
            aria-label="Cycle Window"
            className="bg-[#121621] border border-[#1e2536] text-xs font-medium text-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:border-[#6366f1]"
          >
            <option value={25}>Last 25 Trades</option>
            <option value={60}>Last 60 Trades</option>
            <option value={150}>All Recorded Cycles</option>
          </select>

          {/* Account Mode Filter */}
          <select
            value={accountFilter}
            onChange={(e) => setAccountFilter(e.target.value as 'ALL' | 'LIVE' | 'PAPER')}
            aria-label="Execution Account Filter"
            className="bg-[#121621] border border-[#1e2536] text-xs font-medium text-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:border-[#6366f1]"
          >
            <option value="ALL">All accounts</option>
            <option value="LIVE">Live Kalshi Seal</option>
            <option value="PAPER">Paper Incubator</option>
          </select>
        </div>
      </div>

      {/* Sub-Toolbar: Last Sync & Primary Action */}
      <div className="flex flex-wrap items-center justify-between gap-4 pt-1">
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span>Last telemetry sync:</span>
          <span className="font-mono tabular-nums text-slate-300">
            {market?.ticker || 'KXBTC15M'} · Spot {market?.current_btc_price_str || '$78,900.00'}
          </span>
          <button
            onClick={onResyncMemory}
            className="text-[#818cf8] hover:text-[#a5b4fc] underline underline-offset-4 font-medium ml-1 transition-colors whitespace-nowrap shrink-0"
          >
            Resync
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onRunAuditNow}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#6366f1] hover:bg-[#4f46e5] text-white text-xs font-semibold transition-colors shadow-sm whitespace-nowrap shrink-0"
          >
            <Rocket className="w-3.5 h-3.5" />
            <span>Audit & Sync Fleet</span>
          </button>
        </div>
      </div>

      {/* 5-Card Top KPI Strip (TradeZella Layout) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Card 1: Net P&L */}
        <div className="bg-[#121621] border border-[#1e2536] rounded-xl p-5 flex flex-col justify-between min-h-[118px]">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <span>Net P&L</span>
            <Info className="w-3.5 h-3.5 text-slate-500" />
            <span className="font-mono tabular-nums text-slate-500 ml-1">{metrics.totalCount}</span>
          </div>
          <div
            className={`text-2xl font-bold font-mono tabular-nums tracking-tight mt-2 ${
              isPositiveNet ? 'text-[#10b981]' : 'text-[#f43f5e]'
            }`}
          >
            {netDisplay}
          </div>
          <div className="text-[11px] text-slate-400 font-mono tabular-nums mt-1">
            {livePortfolio?.balance_dollars
              ? `Live Cash: $${Number(livePortfolio.balance_dollars).toFixed(2)}`
              : `Sim Equity: $${Number(portfolio?.equity ?? 100).toFixed(2)}`}
          </div>
        </div>

        {/* Card 2: Trade Win % */}
        <div className="bg-[#121621] border border-[#1e2536] rounded-xl p-5 flex items-center justify-between min-h-[118px]">
          <div>
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <span>Trade win %</span>
              <Info className="w-3.5 h-3.5 text-slate-500" />
            </div>
            <div className="text-2xl font-bold font-mono tabular-nums text-white mt-2">
              {metrics.winRatePct.toFixed(2)}%
            </div>
          </div>

          <div className="flex flex-col items-center">
            <svg width="96" height="54" viewBox="0 0 96 54" className="overflow-visible">
              <path
                d="M 8 46 A 40 40 0 0 1 88 46"
                fill="none"
                stroke="#f43f5e"
                strokeWidth="7"
                strokeLinecap="round"
              />
              <path
                d="M 8 46 A 40 40 0 0 1 88 46"
                fill="none"
                stroke="#10b981"
                strokeWidth="7"
                strokeLinecap="round"
                strokeDasharray={winArcDash}
              />
            </svg>
            <div className="flex items-center gap-2.5 text-[11px] font-mono tabular-nums -mt-1">
              <span className="text-[#10b981]">{metrics.wins}W</span>
              <span className="text-slate-500">·</span>
              <span className="text-[#6366f1]">{metrics.breakevens}B</span>
              <span className="text-slate-500">·</span>
              <span className="text-[#f43f5e]">{metrics.losses}L</span>
            </div>
          </div>
        </div>

        {/* Card 3: Profit Factor */}
        <div className="bg-[#121621] border border-[#1e2536] rounded-xl p-5 flex items-center justify-between min-h-[118px]">
          <div>
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <span>Profit factor</span>
              <Info className="w-3.5 h-3.5 text-slate-500" />
            </div>
            <div className="text-2xl font-bold font-mono tabular-nums text-white mt-2">
              {metrics.profitFactor.toFixed(2)}
            </div>
          </div>

          <svg width="64" height="64" viewBox="0 0 64 64">
            <circle
              cx="32"
              cy="32"
              r="24"
              fill="none"
              stroke="#f43f5e"
              strokeWidth="6"
            />
            <circle
              cx="32"
              cy="32"
              r="24"
              fill="none"
              stroke="#10b981"
              strokeWidth="6"
              strokeDasharray={pfRingDash}
              strokeLinecap="round"
              transform="rotate(-90 32 32)"
            />
          </svg>
        </div>

        {/* Card 4: Cycle Win % */}
        <div className="bg-[#121621] border border-[#1e2536] rounded-xl p-5 flex items-center justify-between min-h-[118px]">
          <div>
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <span>Cycle win %</span>
              <Info className="w-3.5 h-3.5 text-slate-500" />
            </div>
            <div className="text-2xl font-bold font-mono tabular-nums text-white mt-2">
              {metrics.cycleWinPct.toFixed(2)}%
            </div>
          </div>

          <div className="flex flex-col items-center">
            <svg width="96" height="54" viewBox="0 0 96 54" className="overflow-visible">
              <path
                d="M 8 46 A 40 40 0 0 1 88 46"
                fill="none"
                stroke="#f43f5e"
                strokeWidth="7"
                strokeLinecap="round"
              />
              <path
                d="M 8 46 A 40 40 0 0 1 88 46"
                fill="none"
                stroke="#10b981"
                strokeWidth="7"
                strokeLinecap="round"
                strokeDasharray={cycleArcDash}
              />
            </svg>
            <div className="flex items-center gap-2.5 text-[11px] font-mono tabular-nums -mt-1">
              <span className="text-[#10b981]">{metrics.cycleWins}</span>
              <span className="text-slate-500">·</span>
              <span className="text-[#6366f1]">{metrics.cycleFlat}</span>
              <span className="text-slate-500">·</span>
              <span className="text-[#f43f5e]">{metrics.cycleLosses}</span>
            </div>
          </div>
        </div>

        {/* Card 5: Avg Win/Loss Trade */}
        <div className="bg-[#121621] border border-[#1e2536] rounded-xl p-5 flex flex-col justify-between min-h-[118px]">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <span>Avg win/loss trade</span>
            <Info className="w-3.5 h-3.5 text-slate-500" />
          </div>

          <div className="flex items-center gap-4 mt-2">
            <div className="text-2xl font-bold font-mono tabular-nums text-white shrink-0">
              {metrics.avgWinLossRatio.toFixed(2)}
            </div>
            <div className="flex-1">
              <div className="h-2.5 w-full rounded-full bg-[#f43f5e] overflow-hidden flex">
                <div
                  className="h-full bg-[#10b981]"
                  style={{ width: `${avgWinBarPct}%` }}
                />
              </div>
              <div className="flex items-center justify-between text-xs font-mono tabular-nums mt-1.5">
                <span className="text-[#10b981]">+${metrics.avgWin.toFixed(2)}</span>
                <span className="text-[#f43f5e]">-${metrics.avgLoss.toFixed(2)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 3-Column Bottom Analytics Row: Radar Score + Cumulative P&L + Cycle Net P&L Bars */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Column 1: Zella-style 6-Axis Radar / Spider Chart */}
        <div className="bg-[#121621] border border-[#1e2536] rounded-xl p-5 flex flex-col justify-between">
          <div className="flex items-center justify-between border-b border-[#1e2536] pb-3">
            <div className="flex items-center gap-1.5">
              <h2 className="text-sm font-semibold text-white font-display">Quant Edge Score</h2>
              <Info className="w-3.5 h-3.5 text-slate-500" />
            </div>
            <span className="text-xs font-mono tabular-nums text-slate-400">6-Pillar Telemetry</span>
          </div>

          <div className="flex items-center justify-center my-2">
            <svg width="340" height="265" viewBox="0 0 340 265" className="select-none">
              {/* Polygonal Grid Rings */}
              {radarGeometry.rings.map((pts, idx) => (
                <polygon
                  key={idx}
                  points={pts}
                  fill="none"
                  stroke="#1e2536"
                  strokeWidth="1"
                />
              ))}

              {/* Radial Axes */}
              {radarGeometry.dataCoords.map((d, idx) => {
                const angle = radarGeometry.angles[idx];
                const ex = radarGeometry.cx + Math.cos(angle) * radarGeometry.maxR;
                const ey = radarGeometry.cy + Math.sin(angle) * radarGeometry.maxR;
                return (
                  <line
                    key={idx}
                    x1={radarGeometry.cx}
                    y1={radarGeometry.cy}
                    x2={ex}
                    y2={ey}
                    stroke="#1e2536"
                    strokeWidth="1"
                  />
                );
              })}

              {/* Filled Score Polygon */}
              <polygon
                points={radarGeometry.polygonPoints}
                fill="rgba(99, 102, 241, 0.28)"
                stroke="#818cf8"
                strokeWidth="2"
              />

              {/* Vertex Points & Axis Labels */}
              {radarGeometry.dataCoords.map((d, idx) => (
                <g key={idx}>
                  <circle
                    cx={d.x}
                    cy={d.y}
                    r="3.5"
                    fill="#121621"
                    stroke="#a5b4fc"
                    strokeWidth="2"
                  />
                  <text
                    x={d.lx}
                    y={d.ly}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    className="fill-slate-300 text-[11px] font-medium"
                  >
                    {d.label}
                  </text>
                </g>
              ))}
            </svg>
          </div>

          <div className="pt-3 border-t border-[#1e2536] flex items-end justify-between gap-6">
            <div>
              <div className="text-xs text-slate-400">Your Edge Score</div>
              <div className="text-2xl font-bold font-mono tabular-nums text-white mt-0.5">
                {metrics.compositeScore.toFixed(2)}
              </div>
            </div>

            <div className="flex-1 pb-1">
              <div className="relative h-2 w-full rounded-full bg-gradient-to-r from-[#f43f5e] via-[#f59e0b] to-[#10b981]">
                <div
                  className="absolute -top-1 w-4 h-4 rounded-full bg-[#f59e0b] border-2 border-[#121621] shadow"
                  style={{
                    left: `calc(${Math.max(0, Math.min(100, metrics.compositeScore.toNumber()))}% - 8px)`,
                  }}
                />
              </div>
              <div className="flex justify-between text-[10px] font-mono tabular-nums text-slate-400 mt-1.5">
                <span>0</span>
                <span>20</span>
                <span>40</span>
                <span>60</span>
                <span>80</span>
                <span>100</span>
              </div>
            </div>
          </div>
        </div>

        {/* Column 2: Cumulative Net P&L Area Chart */}
        <div className="bg-[#121621] border border-[#1e2536] rounded-xl p-5 flex flex-col justify-between">
          <div className="flex items-center justify-between border-b border-[#1e2536] pb-3">
            <div className="flex items-center gap-1.5">
              <h2 className="text-sm font-semibold text-white font-display">
                Cumulative net P&L
              </h2>
              <Info className="w-3.5 h-3.5 text-slate-500" />
            </div>
            {hoveredPointIdx !== null && areaChartGeometry.coords[hoveredPointIdx] ? (
              <span className="text-xs font-mono tabular-nums text-[#10b981]">
                {areaChartGeometry.coords[hoveredPointIdx].label} · $
                {areaChartGeometry.coords[hoveredPointIdx].cumPnl.toFixed(2)}
              </span>
            ) : (
              <span className="text-xs font-mono tabular-nums text-slate-400">
                Realized Trajectory
              </span>
            )}
          </div>

          <div className="my-auto pt-3">
            <svg
              viewBox={`0 0 ${areaChartGeometry.width} ${areaChartGeometry.height}`}
              className="w-full h-[250px] overflow-visible"
              onMouseLeave={() => setHoveredPointIdx(null)}
            >
              <defs>
                <linearGradient id="zellaCumGreen" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity="0.45" />
                  <stop offset="100%" stopColor="#10b981" stopOpacity="0.02" />
                </linearGradient>
              </defs>

              {/* Horizontal Grid Lines & Y Labels */}
              {areaChartGeometry.yTicks.map((val, idx) => {
                const minVal = areaChartGeometry.yTicks[0];
                const maxVal = areaChartGeometry.yTicks[areaChartGeometry.yTicks.length - 1];
                const span = Math.max(0.5, maxVal - minVal);
                const y =
                  areaChartGeometry.padT +
                  areaChartGeometry.plotH -
                  ((val - minVal) / span) * areaChartGeometry.plotH;
                return (
                  <g key={idx}>
                    <line
                      x1={areaChartGeometry.padL}
                      y1={y}
                      x2={areaChartGeometry.width - 16}
                      y2={y}
                      stroke="#1e2536"
                      strokeDasharray="3 3"
                    />
                    <text
                      x={areaChartGeometry.padL - 8}
                      y={y}
                      textAnchor="end"
                      dominantBaseline="middle"
                      className="fill-slate-400 text-[10px] font-mono tabular-nums"
                    >
                      ${val.toFixed(2)}
                    </text>
                  </g>
                );
              })}

              {/* Area & Stroke */}
              {areaChartGeometry.areaPath && (
                <path d={areaChartGeometry.areaPath} fill="url(#zellaCumGreen)" />
              )}
              {areaChartGeometry.linePath && (
                <path
                  d={areaChartGeometry.linePath}
                  fill="none"
                  stroke="#10b981"
                  strokeWidth="2"
                />
              )}

              {/* Interactive Hover Targets */}
              {areaChartGeometry.coords.map((c, idx) => (
                <g key={idx}>
                  <circle
                    cx={c.x}
                    cy={c.y}
                    r={hoveredPointIdx === idx ? 4.5 : 2.5}
                    className="fill-[#10b981] cursor-pointer transition-transform"
                    onMouseEnter={() => setHoveredPointIdx(idx)}
                  />
                </g>
              ))}

              {/* X-Axis Labels */}
              {areaChartGeometry.coords
                .filter((_, idx, arr) => idx === 0 || idx === Math.floor(arr.length / 2) || idx === arr.length - 1)
                .map((c, idx) => (
                  <text
                    key={idx}
                    x={c.x}
                    y={areaChartGeometry.height - 6}
                    textAnchor="middle"
                    className="fill-slate-400 text-[10px] font-mono tabular-nums"
                  >
                    {c.label}
                  </text>
                ))}
            </svg>
          </div>
        </div>

        {/* Column 3: Net Cycle / Daily P&L Bar Chart */}
        <div className="bg-[#121621] border border-[#1e2536] rounded-xl p-5 flex flex-col justify-between">
          <div className="flex items-center justify-between border-b border-[#1e2536] pb-3">
            <div className="flex items-center gap-1.5">
              <h2 className="text-sm font-semibold text-white font-display">
                Net cycle P&L
              </h2>
              <Info className="w-3.5 h-3.5 text-slate-500" />
            </div>
            {hoveredBarIdx !== null && metrics.barSeries[hoveredBarIdx] ? (
              <span
                className={`text-xs font-mono tabular-nums ${
                  metrics.barSeries[hoveredBarIdx].pnl >= 0 ? 'text-[#10b981]' : 'text-[#f43f5e]'
                }`}
              >
                {metrics.barSeries[hoveredBarIdx].label} · $
                {metrics.barSeries[hoveredBarIdx].pnl.toFixed(2)}
              </span>
            ) : (
              <span className="text-xs font-mono tabular-nums text-slate-400">
                15M / Cycle Settlement Bars
              </span>
            )}
          </div>

          <div className="my-auto pt-3">
            {(() => {
              const bars = metrics.barSeries;
              const width = 520;
              const height = 220;
              const padL = 48;
              const padR = 12;
              const padT = 18;
              const padB = 28;
              const plotW = width - padL - padR;
              const plotH = height - padT - padB;
              const maxAbs = Math.max(0.5, ...bars.map((b) => Math.abs(b.pnl)));
              const midY = padT + plotH / 2;
              const barSlotW = bars.length > 0 ? plotW / bars.length : plotW;
              const barW = Math.max(5, Math.min(18, barSlotW * 0.62));

              return (
                <svg
                  viewBox={`0 0 ${width} ${height}`}
                  className="w-full h-[250px] overflow-visible"
                  onMouseLeave={() => setHoveredBarIdx(null)}
                >
                  {[-maxAbs, -maxAbs / 2, 0, maxAbs / 2, maxAbs].map((v, i) => {
                    const y = midY - (v / maxAbs) * (plotH / 2);
                    return (
                      <g key={i}>
                        <line
                          x1={padL}
                          y1={y}
                          x2={width - padR}
                          y2={y}
                          stroke="#1e2536"
                          strokeDasharray={v === 0 ? undefined : '3 3'}
                        />
                        <text
                          x={padL - 8}
                          y={y}
                          textAnchor="end"
                          dominantBaseline="middle"
                          className="fill-slate-400 text-[10px] font-mono tabular-nums"
                        >
                          ${v.toFixed(2)}
                        </text>
                      </g>
                    );
                  })}

                  {bars.map((b, idx) => {
                    const x = padL + idx * barSlotW + (barSlotW - barW) / 2;
                    const barH = Math.max(3, (Math.abs(b.pnl) / maxAbs) * (plotH / 2));
                    const y = b.pnl >= 0 ? midY - barH : midY;
                    return (
                      <rect
                        key={idx}
                        x={x}
                        y={y}
                        width={barW}
                        height={barH}
                        rx="2"
                        fill={b.pnl >= 0 ? '#10b981' : '#f43f5e'}
                        className="cursor-pointer transition-opacity hover:opacity-80"
                        onMouseEnter={() => setHoveredBarIdx(idx)}
                      />
                    );
                  })}

                  {bars
                    .filter((_, idx, arr) => idx === 0 || idx === Math.floor(arr.length / 2) || idx === arr.length - 1)
                    .map((b, idx, arr) => {
                      const origIdx = bars.indexOf(b);
                      const x = padL + origIdx * barSlotW + barSlotW / 2;
                      return (
                        <text
                          key={idx}
                          x={x}
                          y={height - 6}
                          textAnchor="middle"
                          className="fill-slate-400 text-[10px] font-mono tabular-nums"
                        >
                          {b.label}
                        </text>
                      );
                    })}
                </svg>
              );
            })()}
          </div>
        </div>
      </div>
    </div>
  );
};
