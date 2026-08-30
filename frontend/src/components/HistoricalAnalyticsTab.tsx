import React, { useEffect, useState, useRef } from 'react';
import {
  TrendingUp,
  Award,
  ShieldAlert,
  ShieldCheck,
  Activity,
  DollarSign,
  BarChart3,
  Percent,
  RefreshCw,
  Cpu,
  CheckCircle2,
  XCircle,
  Layers,
  Lock,
  Search,
  ChevronLeft,
  ChevronRight,
  Trash2,
  AlertTriangle,
  Bot,
  Zap,
  Radio,
} from 'lucide-react';

interface PortfolioMetrics {
  total_trades: number;
  wins: number;
  losses: number;
  win_rate_pct: number;
  gross_profit: number;
  gross_loss: number;
  profit_factor: number;
  total_fees_paid: number;
  total_realized_pnl: number;
  net_pnl: number;
  total_roi_pct: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  avg_trade_pnl: number;
  avg_win: number;
  avg_loss: number;
  payoff_ratio: number;
  expectancy_per_trade: number;
  current_equity: number;
  current_balance: number;
}

interface EquityPoint {
  id: number;
  timestamp_utc: string;
  timestamp_epoch_ms: number;
  balance: number;
  equity: number;
  realized_pnl: number;
  unrealized_pnl: number;
  drawdown_pct: number;
  win_rate: number;
  total_trades: number;
  bot_type?: string;
  execution_mode?: string;
}

interface HistoricalTrade {
  id: number;
  trade_id: string;
  timestamp_utc: string;
  timestamp_epoch_ms: number;
  ticker: string;
  timeframe: string;
  side: string;
  size: number;
  price: number;
  gross_value: number;
  fees: number;
  vpin: number | null;
  kelly_fraction: number | null;
  bot_type?: string;
  execution_mode: string;
  status: string;
}

interface HistoricalSettlement {
  id: number;
  settlement_id: string;
  timestamp_utc: string;
  timestamp_epoch_ms: number;
  ticker: string;
  side: string;
  size: number;
  entry_price: number;
  settlement_price: number;
  outcome: string;
  pnl: number;
  balance_after: number;
  bot_type?: string;
  execution_mode?: string;
}

interface AIPrediction {
  id: number;
  timestamp_utc: string;
  timestamp_epoch_ms: number;
  ticker: string;
  p_up: number;
  p_down: number;
  p_wait: number;
  vpin: number;
  ev_yes: number;
  ev_no: number;
  recommended_side: string;
  rationale: string | null;
  bot_type?: string;
}

interface GateItem {
  name: string;
  passed: boolean;
  current: string;
  threshold: string;
}

interface ForwardValidationStatus {
  forward_testing: {
    total_cycles_completed: number;
    target_cycles: number;
    progress_pct: number;
    wins: number;
    losses: number;
    win_rate_pct: number;
    net_pnl: number;
    total_fees_paid: number;
    expectancy_per_trade: number;
    profit_factor: number;
    max_drawdown_pct: number;
    sharpe_ratio: number;
  };
  gates: {
    gate_1_positive_expectancy: GateItem;
    gate_2_profit_factor: GateItem;
    gate_3_max_drawdown: GateItem;
    gate_4_100_cycle_sample: GateItem;
    gate_5_integrity_audit: GateItem;
  };
  real_money_readiness: {
    is_ready_for_real_money: boolean;
    micro_capital_cap: {
      max_contracts_per_trade: number;
      max_risk_per_trade_dollars: number;
      daily_max_loss_circuit_breaker: number;
    };
    live_account?: {
      balance_dollars: number;
      available_margin: number;
      positions_count: number;
    } | null;
  };
  timestamp: string;
}

type SystemFilter = 'all' | '3_step_domination_bot' | 'onnx_ml_bot' | 'live';

function formatETTime(val: string | number | null | undefined): string {
  if (!val) return '--';
  try {
    const d = typeof val === 'number' ? new Date(val) : new Date(val);
    if (isNaN(d.getTime())) return String(val);
    return (
      d.toLocaleTimeString('en-US', {
        timeZone: 'America/New_York',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true,
      }) + ' ET'
    );
  } catch {
    return String(val);
  }
}

function formatETDate(val: string | number | null | undefined): string {
  if (!val) return '';
  try {
    const d = typeof val === 'number' ? new Date(val) : new Date(val);
    if (isNaN(d.getTime())) return '';
    return d.toLocaleDateString('en-US', {
      timeZone: 'America/New_York',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return '';
  }
}

const ITEMS_PER_PAGE = 15;

export interface SystemComparisonItem {
  key: SystemFilter;
  label: string;
  sublabel: string;
  icon: string;
  metrics: PortfolioMetrics | null;
}

export const HistoricalAnalyticsTab: React.FC = () => {
  const [selectedSystem, setSelectedSystem] = useState<SystemFilter>('all');
  const [metrics, setMetrics] = useState<PortfolioMetrics | null>(null);
  const [systemComparison, setSystemComparison] = useState<SystemComparisonItem[]>([]);
  const [equityCurve, setEquityCurve] = useState<EquityPoint[]>([]);
  const [trades, setTrades] = useState<HistoricalTrade[]>([]);
  const [settlements, setSettlements] = useState<HistoricalSettlement[]>([]);
  const [aiPredictions, setAiPredictions] = useState<AIPrediction[]>([]);
  const [validationStatus, setValidationStatus] = useState<ForwardValidationStatus | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<'journal' | 'settlements' | 'ai' | 'validation'>('journal');
  const [loading, setLoading] = useState<boolean>(true);

  // Filter & Pagination States
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [sideFilter, setSideFilter] = useState<'all' | 'yes' | 'no'>('all');
  const [outcomeFilter, setOutcomeFilter] = useState<'all' | 'win' | 'loss' | 'flat'>('all');
  const [page, setPage] = useState<number>(1);

  // Reset Confirmation Modal State
  const [isResetModalOpen, setIsResetModalOpen] = useState<boolean>(false);
  const [resetTarget, setResetTarget] = useState<'selected' | 'all'>('selected');
  const [resetting, setResetting] = useState<boolean>(false);
  const [resetMessage, setResetMessage] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [dimensions, setDimensions] = useState({ width: 900, height: 240 });

  // Measure container for Retina canvas
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      if (entries[0]) {
        const { width } = entries[0].contentRect;
        if (width > 250) {
          setDimensions({ width, height: 240 });
        }
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const fetchAllData = async () => {
    setLoading(true);
    try {
      let botParam = '';
      let modeParam = '';

      if (selectedSystem === '3_step_domination_bot') {
        botParam = '3_step_domination_bot';
        modeParam = 'simulated';
      } else if (selectedSystem === 'onnx_ml_bot') {
        botParam = 'onnx_ml_bot';
        modeParam = 'simulated';
      } else if (selectedSystem === 'live') {
        modeParam = 'live';
      }

      const queryParams = new URLSearchParams();
      if (botParam) queryParams.append('bot_type', botParam);
      if (modeParam) queryParams.append('execution_mode', modeParam);
      const qs = queryParams.toString() ? `?${queryParams.toString()}` : '';

      const [mRes, eqRes, trRes, stRes, aiRes, valRes, mAll, mDom, mOnnx, mLive] = await Promise.all([
        fetch(`/api/history/metrics${qs}`).then((r) => r.json()).catch(() => null),
        fetch(`/api/history/equity-curve${qs ? `${qs}&limit=1000` : '?limit=1000'}`).then((r) => r.json()).catch(() => []),
        fetch(`/api/history/trades${qs ? `${qs}&limit=500` : '?limit=500'}`).then((r) => r.json()).catch(() => []),
        fetch(`/api/history/settlements${qs ? `${qs}&limit=500` : '?limit=500'}`).then((r) => r.json()).catch(() => []),
        fetch(`/api/history/ai-predictions${botParam ? `?bot_type=${botParam}&limit=500` : '?limit=500'}`).then((r) => r.json()).catch(() => []),
        fetch(`/api/bot/forward-validation-status${qs}`).then((r) => r.json()).catch(() => null),
        fetch('/api/history/metrics?bot_type=all').then((r) => r.json()).catch(() => null),
        fetch('/api/history/metrics?bot_type=3_step_domination_bot&execution_mode=simulated').then((r) => r.json()).catch(() => null),
        fetch('/api/history/metrics?bot_type=onnx_ml_bot&execution_mode=simulated').then((r) => r.json()).catch(() => null),
        fetch('/api/history/metrics?execution_mode=live').then((r) => r.json()).catch(() => null),
      ]);

      if (mRes) setMetrics(mRes);
      if (Array.isArray(eqRes)) setEquityCurve(eqRes);
      if (Array.isArray(trRes)) setTrades(trRes);
      if (Array.isArray(stRes)) setSettlements(stRes);
      if (Array.isArray(aiRes)) setAiPredictions(aiRes);
      if (valRes) setValidationStatus(valRes);

      setSystemComparison([
        {
          key: 'all',
          label: 'All Combined',
          sublabel: 'Aggregated Portfolio Overview',
          icon: 'layers',
          metrics: mAll,
        },
        {
          key: '3_step_domination_bot',
          label: '3-Step Domination Bot',
          sublabel: 'L3 Order Flow & Momentum Scalper (Paper)',
          icon: 'zap',
          metrics: mDom,
        },
        {
          key: 'onnx_ml_bot',
          label: 'ONNX ML Ensemble',
          sublabel: 'Deep Learning Stage 1/2 Model (Paper)',
          icon: 'cpu',
          metrics: mOnnx,
        },
        {
          key: 'live',
          label: 'Live Trading',
          sublabel: 'Real-Money Kalshi Execution & Fills',
          icon: 'radio',
          metrics: mLive,
        },
      ]);
    } catch (e) {
      console.error('Failed to fetch historical analytics data:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
    const interval = setInterval(fetchAllData, 8000);
    return () => clearInterval(interval);
  }, [selectedSystem]);

  // Reset page when switching tabs or filters
  useEffect(() => {
    setPage(1);
  }, [activeSubTab, searchTerm, sideFilter, outcomeFilter, selectedSystem]);

  // Handle Manual Reset
  const handleExecuteReset = async () => {
    setResetting(true);
    try {
      const target = resetTarget === 'all' ? 'all' : selectedSystem;
      const res = await fetch(`/api/reports/reset?target=${target}`, {
        method: 'POST',
      });
      const data = await res.json();
      setResetMessage(data.message || 'Ledger reset successfully.');
      setTimeout(() => {
        setIsResetModalOpen(false);
        setResetMessage(null);
        fetchAllData();
      }, 1200);
    } catch (e) {
      console.error('Failed to reset reports:', e);
      setResetMessage('Reset request failed. Please try again.');
    } finally {
      setResetting(false);
    }
  };

  // HiDPI Retina Canvas Equity Curve Renderer
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = dimensions.width;
    const h = dimensions.height;

    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    // Background grid lines
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1;
    for (let x = 0; x < w; x += 90) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y < h; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    if (equityCurve.length === 0) {
      ctx.fillStyle = '#64748b';
      ctx.font = '13px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(
        `Accumulating real-time equity snapshots for ${
          selectedSystem === 'all'
            ? 'all systems'
            : selectedSystem === '3_step_domination_bot'
            ? '3-Step Domination Bot'
            : selectedSystem === 'onnx_ml_bot'
            ? 'ONNX ML Bot'
            : 'Live Trading'
        }...`,
        w / 2,
        h / 2
      );
      return;
    }

    // Build equity point series
    const points =
      equityCurve.length === 1
        ? [{ ...equityCurve[0], equity: equityCurve[0].equity }, { ...equityCurve[0], equity: equityCurve[0].equity }]
        : equityCurve;

    const values = points.map((p) => p.equity);
    const minVal = Math.min(...values) * 0.998;
    const maxVal = Math.max(...values) * 1.002;
    const range = maxVal - minVal || 1.0;

    const getX = (index: number) => (index / (points.length - 1)) * (w - 70) + 20;
    const getY = (val: number) => h - 30 - ((val - minVal) / range) * (h - 60);

    // Gradient fill under live equity line
    const gradient = ctx.createLinearGradient(0, 0, 0, h);
    gradient.addColorStop(0, 'rgba(16, 185, 129, 0.28)');
    gradient.addColorStop(1, 'rgba(16, 185, 129, 0.0)');

    ctx.beginPath();
    ctx.moveTo(getX(0), getY(values[0]));
    for (let i = 1; i < values.length; i++) {
      ctx.lineTo(getX(i), getY(values[i]));
    }
    ctx.lineTo(getX(values.length - 1), h - 20);
    ctx.lineTo(getX(0), h - 20);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // High-Water Mark Peak Line
    let peak = values[0];
    ctx.beginPath();
    ctx.moveTo(getX(0), getY(peak));
    for (let i = 1; i < values.length; i++) {
      if (values[i] > peak) peak = values[i];
      ctx.lineTo(getX(i), getY(peak));
    }
    ctx.strokeStyle = 'rgba(59, 130, 246, 0.65)';
    ctx.setLineDash([4, 4]);
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.setLineDash([]);

    // Live Equity Line
    ctx.beginPath();
    ctx.moveTo(getX(0), getY(values[0]));
    for (let i = 1; i < values.length; i++) {
      ctx.lineTo(getX(i), getY(values[i]));
    }
    ctx.strokeStyle = '#10b981';
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // End point indicator
    const lastX = getX(values.length - 1);
    const lastY = getY(values[values.length - 1]);
    ctx.beginPath();
    ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
    ctx.fillStyle = '#10b981';
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Annotations & Y-Axis Labels
    ctx.fillStyle = '#94a3b8';
    ctx.font = '11px monospace';
    ctx.textAlign = 'right';
    ctx.fillText(`$${maxVal.toFixed(2)}`, w - 8, 20);
    ctx.fillText(`$${minVal.toFixed(2)}`, w - 8, h - 10);
  }, [equityCurve, dimensions, selectedSystem]);

  // Filtering Logic for Tables
  const filteredTrades = trades.filter((t) => {
    if (
      searchTerm &&
      !t.ticker.toLowerCase().includes(searchTerm.toLowerCase()) &&
      !t.trade_id.toLowerCase().includes(searchTerm.toLowerCase())
    ) {
      return false;
    }
    if (sideFilter !== 'all' && t.side.toLowerCase() !== sideFilter) return false;
    return true;
  });

  const filteredSettlements = settlements.filter((s) => {
    if (
      searchTerm &&
      !s.ticker.toLowerCase().includes(searchTerm.toLowerCase()) &&
      !s.settlement_id.toLowerCase().includes(searchTerm.toLowerCase())
    ) {
      return false;
    }
    if (sideFilter !== 'all' && s.side.toLowerCase() !== sideFilter) return false;
    if (outcomeFilter !== 'all' && s.outcome.toLowerCase() !== outcomeFilter) return false;
    return true;
  });

  const filteredAi = aiPredictions.filter((p) => {
    if (searchTerm && !p.ticker.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    if (sideFilter !== 'all' && p.recommended_side.toLowerCase() !== sideFilter) return false;
    return true;
  });

  // Pagination Slice
  const getPaginatedList = <T,>(list: T[]): { items: T[]; totalPages: number; totalCount: number } => {
    const totalCount = list.length;
    const totalPages = Math.max(1, Math.ceil(totalCount / ITEMS_PER_PAGE));
    const validPage = Math.min(page, totalPages);
    const start = (validPage - 1) * ITEMS_PER_PAGE;
    const items = list.slice(start, start + ITEMS_PER_PAGE);
    return { items, totalPages, totalCount };
  };

  const paginatedTrades = getPaginatedList(filteredTrades);
  const paginatedSettlements = getPaginatedList(filteredSettlements);
  const paginatedAi = getPaginatedList(filteredAi);

  return (
    <div className="space-y-6 text-slate-100 p-4 sm:p-6 bg-slate-950 rounded-xl border border-slate-800 shadow-2xl">
      {/* Header & Controls */}
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4 pb-4 border-b border-slate-800">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
            <BarChart3 className="text-emerald-400 w-6 h-6 sm:w-7 sm:h-7" />
            Institutional Performance Analytics & Trade Journal
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Isolated Bot Metrics • SQLite WAL Time-Series Store • Continuous 24/7 Crypto Annualization
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 w-full lg:w-auto">
          {/* Refresh Button */}
          <button
            onClick={fetchAllData}
            disabled={loading}
            className="flex items-center gap-2 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs sm:text-sm font-semibold rounded-lg transition border border-slate-700 shadow-sm"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
            Refresh Store
          </button>

          {/* Delete / Reset Button */}
          <button
            onClick={() => setIsResetModalOpen(true)}
            className="flex items-center gap-2 px-3.5 py-2 bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 hover:text-rose-100 text-xs sm:text-sm font-semibold rounded-lg transition border border-rose-800/60 shadow-sm"
          >
            <Trash2 className="w-4 h-4 text-rose-400" />
            Reset Ledger
          </button>
        </div>
      </div>

      {/* OVERALL SYSTEM EFFICIENCY SUMMARY MATRIX */}
      <div className="bg-slate-900/95 border border-slate-800 rounded-2xl p-4 sm:p-5 shadow-xl space-y-3.5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
              <BarChart3 className="h-4 w-4 text-emerald-400" />
            </div>
            <div>
              <h3 className="text-sm sm:text-base font-extrabold text-white flex items-center gap-2">
                <span>Overall System Efficiency & Profitability Summary</span>
                <span className="px-2 py-0.5 text-[10px] font-mono bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 rounded-full font-bold">
                  MULTI-BOT LIVE COMPARISON
                </span>
              </h3>
              <p className="text-xs text-slate-400">
                Direct side-by-side comparison across all trading algorithms, models, and real capital execution.
              </p>
            </div>
          </div>
          <div className="text-[11px] text-slate-400 font-mono flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>SQLite WAL Sync Active</span>
          </div>
        </div>

        {/* Efficiency Summary Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px] font-bold tracking-wider">
                <th className="py-2.5 px-3">System / Strategy</th>
                <th className="py-2.5 px-3">Execution Mode</th>
                <th className="py-2.5 px-3 text-center">Trades (W/L)</th>
                <th className="py-2.5 px-3 text-right">Win Rate %</th>
                <th className="py-2.5 px-3 text-right">Net Realized P&L</th>
                <th className="py-2.5 px-3 text-right">Profit Factor</th>
                <th className="py-2.5 px-3 text-right">Expectancy / Trade</th>
                <th className="py-2.5 px-3 text-right">Sharpe Ratio</th>
                <th className="py-2.5 px-3 text-right">Max Drawdown</th>
                <th className="py-2.5 px-3 text-center">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {systemComparison.map((item) => {
                const m = item.metrics;
                const isSelected = selectedSystem === item.key;
                const isMostProfitable = item.key === '3_step_domination_bot' && m && m.net_pnl > 0;

                return (
                  <tr
                    key={item.key}
                    onClick={() => setSelectedSystem(item.key)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? 'bg-emerald-500/10 border-l-2 border-emerald-400'
                        : 'hover:bg-slate-800/50'
                    }`}
                  >
                    <td className="py-3 px-3 font-sans">
                      <div className="flex items-center gap-2">
                        {item.icon === 'zap' && <Zap className="w-4 h-4 text-amber-400 shrink-0" />}
                        {item.icon === 'cpu' && <Cpu className="w-4 h-4 text-purple-400 shrink-0" />}
                        {item.icon === 'radio' && <Radio className="w-4 h-4 text-rose-400 shrink-0 animate-pulse" />}
                        {item.icon === 'layers' && <Layers className="w-4 h-4 text-blue-400 shrink-0" />}
                        <div>
                          <div className="font-bold text-white flex items-center gap-1.5">
                            <span>{item.label}</span>
                            {isMostProfitable && (
                              <span className="px-1.5 py-0.2 text-[9px] font-bold bg-amber-400/20 text-amber-300 border border-amber-400/40 rounded-full">
                                🏆 HIGHEST PROFIT
                              </span>
                            )}
                          </div>
                          <div className="text-[10px] text-slate-400 font-normal">{item.sublabel}</div>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-3 font-sans">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        item.key === 'live'
                          ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                          : 'bg-blue-500/20 text-blue-300 border border-blue-500/40'
                      }`}>
                        {item.key === 'live' ? 'REAL MONEY' : 'PAPER SIM'}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-center text-slate-200">
                      {m ? `${m.total_trades} (${m.wins}W / ${m.losses}L)` : '--'}
                    </td>
                    <td className="py-3 px-3 text-right font-bold text-white">
                      {m && m.total_trades > 0 ? `${m.win_rate_pct.toFixed(1)}%` : '0.0%'}
                    </td>
                    <td className={`py-3 px-3 text-right font-bold text-sm ${
                      m && m.net_pnl > 0 ? 'text-emerald-400' : m && m.net_pnl < 0 ? 'text-rose-400' : 'text-slate-400'
                    }`}>
                      {m ? `${m.net_pnl >= 0 ? '+' : ''}$${m.net_pnl.toFixed(2)}` : '$0.00'}
                    </td>
                    <td className="py-3 px-3 text-right font-bold text-cyan-400">
                      {m && m.total_trades > 0 ? m.profit_factor.toFixed(2) : '1.00'}
                    </td>
                    <td className="py-3 px-3 text-right text-emerald-400 font-semibold">
                      {m && m.total_trades > 0 ? `${m.expectancy_per_trade >= 0 ? '+' : ''}$${m.expectancy_per_trade.toFixed(2)}` : '$0.00'}
                    </td>
                    <td className="py-3 px-3 text-right text-blue-400">
                      {m && m.total_trades > 0 ? m.sharpe_ratio.toFixed(2) : '0.00'}
                    </td>
                    <td className="py-3 px-3 text-right text-rose-400">
                      {m && m.total_trades > 0 ? `${m.max_drawdown_pct.toFixed(2)}%` : '0.00%'}
                    </td>
                    <td className="py-3 px-3 text-center font-sans">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedSystem(item.key);
                        }}
                        className={`px-2.5 py-1 text-[11px] font-bold rounded-lg transition ${
                          isSelected
                            ? 'bg-emerald-500 text-black font-extrabold shadow-sm'
                            : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                        }`}
                      >
                        {isSelected ? 'Active View' : 'Isolate Bot'}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Bot & System Filter Selector */}
      <div className="bg-slate-900/90 border border-slate-800 p-3 rounded-xl flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Active Isolated Drilldown:</span>
        </div>

        <div className="flex flex-wrap items-center gap-1.5 bg-slate-950 p-1 rounded-lg border border-slate-800">
          <button
            onClick={() => setSelectedSystem('all')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition ${
              selectedSystem === 'all'
                ? 'bg-slate-800 text-white shadow-sm border border-slate-700'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Layers className="w-3.5 h-3.5 text-blue-400" />
            All Combined
          </button>

          <button
            onClick={() => setSelectedSystem('3_step_domination_bot')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition ${
              selectedSystem === '3_step_domination_bot'
                ? 'bg-emerald-500/20 text-emerald-300 shadow-sm border border-emerald-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            3-Step Domination (Paper)
          </button>

          <button
            onClick={() => setSelectedSystem('onnx_ml_bot')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition ${
              selectedSystem === 'onnx_ml_bot'
                ? 'bg-purple-500/20 text-purple-300 shadow-sm border border-purple-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Cpu className="w-3.5 h-3.5 text-purple-400" />
            ONNX ML Ensemble (Paper)
          </button>

          <button
            onClick={() => setSelectedSystem('live')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition ${
              selectedSystem === 'live'
                ? 'bg-rose-500/20 text-rose-300 shadow-sm border border-rose-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Radio className="w-3.5 h-3.5 text-rose-400 animate-pulse" />
            Live Trading (Real Capital)
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-xl shadow-sm">
          <div className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5 uppercase">
            <Award className="w-3.5 h-3.5 text-amber-400" /> SHARPE RATIO
          </div>
          <div className="text-lg sm:text-xl font-bold text-emerald-400 mt-1 font-mono">
            {metrics ? metrics.sharpe_ratio.toFixed(2) : '--'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">365-Day 15M Annualized</div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-xl shadow-sm">
          <div className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5 uppercase">
            <TrendingUp className="w-3.5 h-3.5 text-emerald-400" /> SORTINO RATIO
          </div>
          <div className="text-lg sm:text-xl font-bold text-emerald-400 mt-1 font-mono">
            {metrics ? metrics.sortino_ratio.toFixed(2) : '--'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Downside Risk Guard</div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-xl shadow-sm">
          <div className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5 uppercase">
            <Percent className="w-3.5 h-3.5 text-blue-400" /> WIN RATE
          </div>
          <div className="text-lg sm:text-xl font-bold text-white mt-1 font-mono">
            {metrics ? `${metrics.win_rate_pct.toFixed(1)}%` : '--'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            {metrics ? `${metrics.wins}W / ${metrics.losses}L (${metrics.total_trades} cycles)` : '--'}
          </div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-xl shadow-sm">
          <div className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5 uppercase">
            <ShieldAlert className="w-3.5 h-3.5 text-rose-400" /> MAX DRAWDOWN
          </div>
          <div className="text-lg sm:text-xl font-bold text-rose-400 mt-1 font-mono">
            {metrics ? `${metrics.max_drawdown_pct.toFixed(2)}%` : '--'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">15% Gate Threshold</div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-xl shadow-sm">
          <div className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5 uppercase">
            <Activity className="w-3.5 h-3.5 text-cyan-400" /> PROFIT FACTOR
          </div>
          <div className="text-lg sm:text-xl font-bold text-cyan-400 mt-1 font-mono">
            {metrics ? metrics.profit_factor.toFixed(2) : '--'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            {metrics ? `Payoff: ${metrics.payoff_ratio.toFixed(2)}x` : '--'}
          </div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-xl shadow-sm">
          <div className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5 uppercase">
            <DollarSign className="w-3.5 h-3.5 text-emerald-400" /> NET REALIZED P&L
          </div>
          <div
            className={`text-lg sm:text-xl font-bold mt-1 font-mono ${
              metrics && metrics.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'
            }`}
          >
            {metrics ? `${metrics.net_pnl >= 0 ? '+' : ''}$${metrics.net_pnl.toFixed(2)}` : '--'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            {metrics ? `ROI: ${metrics.total_roi_pct >= 0 ? '+' : ''}${metrics.total_roi_pct.toFixed(1)}%` : '--'}
          </div>
        </div>
      </div>

      {/* HiDPI Canvas Equity Curve Section */}
      <div ref={containerRef} className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-sm">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 mb-3">
          <div className="text-xs sm:text-sm font-semibold text-slate-200 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            Cumulative Portfolio Equity & High-Water Mark ($) •{' '}
            <span className="text-emerald-400 font-mono">
              {selectedSystem === 'all'
                ? 'All Combined'
                : selectedSystem === '3_step_domination_bot'
                ? '3-Step Domination Bot'
                : selectedSystem === 'onnx_ml_bot'
                ? 'ONNX ML Bot'
                : 'Live Real Capital'}
            </span>
          </div>
          <div className="text-xs text-slate-400 flex items-center gap-4">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block" /> Live Equity
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-blue-400 inline-block" /> Peak Watermark
            </span>
          </div>
        </div>
        <canvas
          ref={canvasRef}
          style={{ width: `${dimensions.width}px`, height: '240px' }}
          className="w-full h-60 bg-slate-950/70 rounded-lg border border-slate-800/80 block"
        />
      </div>

      {/* Sub-Tabs Selector */}
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-800 pb-2">
        <button
          onClick={() => setActiveSubTab('journal')}
          className={`px-3.5 py-2 text-xs sm:text-sm font-semibold rounded-lg transition flex items-center gap-2 ${
            activeSubTab === 'journal'
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
          }`}
        >
          <Layers className="w-4 h-4" /> Trade Journal ({trades.length})
        </button>

        <button
          onClick={() => setActiveSubTab('settlements')}
          className={`px-3.5 py-2 text-xs sm:text-sm font-semibold rounded-lg transition flex items-center gap-2 ${
            activeSubTab === 'settlements'
              ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
          }`}
        >
          <Award className="w-4 h-4" /> Settlements ({settlements.length})
        </button>

        <button
          onClick={() => setActiveSubTab('ai')}
          className={`px-3.5 py-2 text-xs sm:text-sm font-semibold rounded-lg transition flex items-center gap-2 ${
            activeSubTab === 'ai'
              ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
          }`}
        >
          <Cpu className="w-4 h-4" /> AI Decisions ({aiPredictions.length})
        </button>

        <button
          onClick={() => setActiveSubTab('validation')}
          className={`px-3.5 py-2 text-xs sm:text-sm font-semibold rounded-lg transition flex items-center gap-2 ${
            activeSubTab === 'validation'
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
          }`}
        >
          <ShieldCheck className="w-4 h-4" /> 100-Cycle Forward Validation Gate
        </button>
      </div>

      {/* Filter & Search Bar */}
      {activeSubTab !== 'validation' && (
        <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900/60 p-3 rounded-lg border border-slate-800 text-xs">
          <div className="flex items-center gap-2 flex-1 min-w-[200px] max-w-md">
            <Search className="w-4 h-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search ticker, trade ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-md px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 w-full"
            />
          </div>

          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-md border border-slate-800">
              <span className="text-[10px] text-slate-500 px-1 font-semibold uppercase">Side:</span>
              {(['all', 'yes', 'no'] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setSideFilter(s)}
                  className={`px-2 py-0.5 rounded font-bold uppercase text-[10px] transition ${
                    sideFilter === s ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>

            {activeSubTab === 'settlements' && (
              <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-md border border-slate-800">
                <span className="text-[10px] text-slate-500 px-1 font-semibold uppercase">Outcome:</span>
                {(['all', 'win', 'loss'] as const).map((o) => (
                  <button
                    key={o}
                    onClick={() => setOutcomeFilter(o)}
                    className={`px-2 py-0.5 rounded font-bold uppercase text-[10px] transition ${
                      outcomeFilter === o ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    {o}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tables Section */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        {/* Trade Execution Journal */}
        {activeSubTab === 'journal' && (
          <div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-800/80 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-700">
                  <tr>
                    <th className="py-3 px-4">Trade ID</th>
                    <th className="py-3 px-3">Date & Time (ET)</th>
                    <th className="py-3 px-3">Ticker</th>
                    <th className="py-3 px-3">Side</th>
                    <th className="py-3 px-3">Size</th>
                    <th className="py-3 px-3">Price</th>
                    <th className="py-3 px-3">Notional</th>
                    <th className="py-3 px-3">Bot / Mode</th>
                    <th className="py-3 px-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {paginatedTrades.items.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="py-8 text-center text-slate-500 font-sans">
                        No trade executions matching current filter criteria.
                      </td>
                    </tr>
                  ) : (
                    paginatedTrades.items.map((t) => (
                      <tr key={t.id} className="hover:bg-slate-800/40 transition">
                        <td className="py-2.5 px-4 font-semibold text-slate-300">{t.trade_id}</td>
                        <td className="py-2.5 px-3 text-slate-300">
                          <span className="text-slate-500 mr-1.5">
                            {formatETDate(t.timestamp_epoch_ms || t.timestamp_utc)}
                          </span>
                          {formatETTime(t.timestamp_epoch_ms || t.timestamp_utc)}
                        </td>
                        <td className="py-2.5 px-3 text-amber-300 font-bold">{t.ticker}</td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              t.side.toLowerCase() === 'yes'
                                ? 'bg-emerald-500/20 text-emerald-300'
                                : 'bg-rose-500/20 text-rose-300'
                            }`}
                          >
                            {t.side.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-white font-bold">{t.size}</td>
                        <td className="py-2.5 px-3 text-slate-200">{(t.price * 100).toFixed(1)}¢</td>
                        <td className="py-2.5 px-3 text-slate-200">${t.gross_value.toFixed(2)}</td>
                        <td className="py-2.5 px-3">
                          <span className="px-2 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300 border border-slate-700">
                            {t.bot_type ? t.bot_type.replace('_bot', '') : t.execution_mode}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-emerald-400 font-semibold">{t.status}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            {paginatedTrades.totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800 bg-slate-950/60 text-xs">
                <span className="text-slate-400">
                  Showing {(page - 1) * ITEMS_PER_PAGE + 1} -{' '}
                  {Math.min(page * ITEMS_PER_PAGE, paginatedTrades.totalCount)} of {paginatedTrades.totalCount} trades
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="p-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="text-slate-300 font-mono">
                    Page {page} of {paginatedTrades.totalPages}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(paginatedTrades.totalPages, p + 1))}
                    disabled={page === paginatedTrades.totalPages}
                    className="p-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Contract Settlements */}
        {activeSubTab === 'settlements' && (
          <div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-800/80 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-700">
                  <tr>
                    <th className="py-3 px-4">Settlement ID</th>
                    <th className="py-3 px-3">Date & Time (ET)</th>
                    <th className="py-3 px-3">Ticker</th>
                    <th className="py-3 px-3">Side</th>
                    <th className="py-3 px-3">Size</th>
                    <th className="py-3 px-3">Entry Price</th>
                    <th className="py-3 px-3">Outcome</th>
                    <th className="py-3 px-3">Realized P&L</th>
                    <th className="py-3 px-3">Balance After</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {paginatedSettlements.items.length === 0 ? (
                    <tr>
                      <td colSpan={9} className="py-8 text-center text-slate-500 font-sans">
                        No settlements matching current filter criteria.
                      </td>
                    </tr>
                  ) : (
                    paginatedSettlements.items.map((s) => (
                      <tr key={s.id} className="hover:bg-slate-800/40 transition">
                        <td className="py-2.5 px-4 font-semibold text-slate-300">{s.settlement_id}</td>
                        <td className="py-2.5 px-3 text-slate-300">
                          <span className="text-slate-500 mr-1.5">
                            {formatETDate(s.timestamp_epoch_ms || s.timestamp_utc)}
                          </span>
                          {formatETTime(s.timestamp_epoch_ms || s.timestamp_utc)}
                        </td>
                        <td className="py-2.5 px-3 text-amber-300 font-bold">{s.ticker}</td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              s.side.toLowerCase() === 'yes'
                                ? 'bg-emerald-500/20 text-emerald-300'
                                : 'bg-rose-500/20 text-rose-300'
                            }`}
                          >
                            {s.side.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-white font-bold">{s.size}</td>
                        <td className="py-2.5 px-3 text-slate-200">{(s.entry_price * 100).toFixed(1)}¢</td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold flex items-center gap-1 w-fit ${
                              s.outcome.toLowerCase() === 'win'
                                ? 'bg-emerald-500/20 text-emerald-300'
                                : s.outcome.toLowerCase() === 'loss'
                                ? 'bg-rose-500/20 text-rose-300'
                                : 'bg-slate-500/20 text-slate-300'
                            }`}
                          >
                            {s.outcome.toLowerCase() === 'win' ? (
                              <CheckCircle2 className="w-3 h-3" />
                            ) : s.outcome.toLowerCase() === 'loss' ? (
                              <XCircle className="w-3 h-3" />
                            ) : null}
                            {s.outcome.toUpperCase()}
                          </span>
                        </td>
                        <td className={`py-2.5 px-3 font-bold ${s.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {s.pnl >= 0 ? '+' : ''}${s.pnl.toFixed(2)}
                        </td>
                        <td className="py-2.5 px-3 text-slate-300 font-semibold">${s.balance_after.toFixed(2)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {paginatedSettlements.totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800 bg-slate-950/60 text-xs">
                <span className="text-slate-400">
                  Showing {(page - 1) * ITEMS_PER_PAGE + 1} -{' '}
                  {Math.min(page * ITEMS_PER_PAGE, paginatedSettlements.totalCount)} of{' '}
                  {paginatedSettlements.totalCount} settlements
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="p-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="text-slate-300 font-mono">
                    Page {page} of {paginatedSettlements.totalPages}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(paginatedSettlements.totalPages, p + 1))}
                    disabled={page === paginatedSettlements.totalPages}
                    className="p-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* AI Inferences */}
        {activeSubTab === 'ai' && (
          <div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead className="bg-slate-800/80 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-700">
                  <tr>
                    <th className="py-3 px-4">Date & Time (ET)</th>
                    <th className="py-3 px-3">Ticker</th>
                    <th className="py-3 px-3">P(UP)</th>
                    <th className="py-3 px-3">P(DOWN)</th>
                    <th className="py-3 px-3">P(WAIT)</th>
                    <th className="py-3 px-3">VPIN Toxicity</th>
                    <th className="py-3 px-3">Decision Signal</th>
                    <th className="py-3 px-3">Playbook Rationale</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {paginatedAi.items.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-slate-500 font-sans">
                        No AI predictions matching current criteria.
                      </td>
                    </tr>
                  ) : (
                    paginatedAi.items.map((p) => (
                      <tr key={p.id} className="hover:bg-slate-800/40 transition">
                        <td className="py-2.5 px-4 text-slate-300">
                          <span className="text-slate-500 mr-1.5">
                            {formatETDate(p.timestamp_epoch_ms || p.timestamp_utc)}
                          </span>
                          {formatETTime(p.timestamp_epoch_ms || p.timestamp_utc)}
                        </td>
                        <td className="py-2.5 px-3 text-amber-300 font-bold">{p.ticker}</td>
                        <td className="py-2.5 px-3 text-emerald-400 font-bold">{(p.p_up * 100).toFixed(1)}%</td>
                        <td className="py-2.5 px-3 text-rose-400 font-bold">{(p.p_down * 100).toFixed(1)}%</td>
                        <td className="py-2.5 px-3 text-slate-400">{(p.p_wait * 100).toFixed(1)}%</td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              p.vpin <= 0.35
                                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                : p.vpin <= 0.65
                                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                                : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                            }`}
                          >
                            {p.vpin.toFixed(2)} {p.vpin <= 0.35 ? 'SAFE' : p.vpin <= 0.65 ? 'WARN' : 'TOXIC'}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-bold text-white uppercase">{p.recommended_side}</td>
                        <td className="py-2.5 px-3 text-slate-400 truncate max-w-sm">{p.rationale || '--'}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {paginatedAi.totalPages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800 bg-slate-950/60 text-xs">
                <span className="text-slate-400">
                  Showing {(page - 1) * ITEMS_PER_PAGE + 1} -{' '}
                  {Math.min(page * ITEMS_PER_PAGE, paginatedAi.totalCount)} of {paginatedAi.totalCount} inferences
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="p-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="text-slate-300 font-mono">
                    Page {page} of {paginatedAi.totalPages}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(paginatedAi.totalPages, p + 1))}
                    disabled={page === paginatedAi.totalPages}
                    className="p-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 100-Cycle Forward Validation Gate */}
        {activeSubTab === 'validation' && (
          <div className="p-5 flex flex-col gap-6">
            {/* Top Readiness Banner */}
            <div
              className={`p-4 rounded-xl border flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 ${
                validationStatus?.real_money_readiness.is_ready_for_real_money
                  ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
                  : 'bg-amber-950/30 border-amber-500/30 text-amber-300'
              }`}
            >
              <div className="flex items-center gap-3">
                {validationStatus?.real_money_readiness.is_ready_for_real_money ? (
                  <div className="p-2.5 bg-emerald-500/20 rounded-lg text-emerald-400 border border-emerald-500/30">
                    <CheckCircle2 className="w-6 h-6" />
                  </div>
                ) : (
                  <div className="p-2.5 bg-amber-500/20 rounded-lg text-amber-400 border border-amber-500/30">
                    <Lock className="w-6 h-6" />
                  </div>
                )}
                <div>
                  <h3 className="text-base font-bold text-white">
                    {validationStatus?.real_money_readiness.is_ready_for_real_money
                      ? 'REAL-MONEY READY: All 5 Validation Gates Passed'
                      : 'FORWARD VALIDATION IN PROGRESS (Phase 2)'}
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {validationStatus?.real_money_readiness.is_ready_for_real_money
                      ? 'Statistical expectancy, profit factor, drawdown, and integrity gates verified under live exchange friction.'
                      : 'Executing continuous 15-minute expiration forward cycles before real capital deployment.'}
                  </p>
                </div>
              </div>

              <div className="text-right flex flex-col sm:items-end">
                <span className="text-[10px] uppercase font-bold text-slate-400">100-Cycle Gate Progress</span>
                <span className="text-lg font-mono font-extrabold text-white">
                  {validationStatus?.forward_testing.total_cycles_completed ?? 0} /{' '}
                  {validationStatus?.forward_testing.target_cycles ?? 100} Cycles
                </span>
                <span className="text-xs font-mono text-amber-400">
                  {validationStatus?.forward_testing.progress_pct ?? 0}% Complete
                </span>
              </div>
            </div>

            {/* Progress Bar */}
            <div>
              <div className="flex justify-between text-xs font-semibold text-slate-400 mb-1.5">
                <span>Forward Sample Progress</span>
                <span>{validationStatus?.forward_testing.progress_pct ?? 0}%</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-amber-500 to-emerald-500 h-2.5 rounded-full transition-all duration-500"
                  style={{ width: `${validationStatus?.forward_testing.progress_pct ?? 0}%` }}
                />
              </div>
            </div>

            {/* 5 Validation Gates Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {validationStatus?.gates &&
                Object.entries(validationStatus.gates).map(([key, gate]) => (
                  <div
                    key={key}
                    className={`p-4 rounded-xl border ${
                      gate.passed ? 'bg-emerald-950/20 border-emerald-500/30' : 'bg-slate-900 border-slate-800'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-300">{gate.name}</span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-extrabold uppercase ${
                          gate.passed ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'
                        }`}
                      >
                        {gate.passed ? 'PASSED' : 'PENDING'}
                      </span>
                    </div>
                    <div className="mt-3 flex items-baseline justify-between font-mono">
                      <div>
                        <div className="text-[10px] text-slate-500 uppercase">Current Value</div>
                        <div className="text-base font-bold text-white mt-0.5">{gate.current}</div>
                      </div>
                      <div className="text-right">
                        <div className="text-[10px] text-slate-500 uppercase">Threshold</div>
                        <div className="text-xs font-semibold text-slate-400 mt-0.5">{gate.threshold}</div>
                      </div>
                    </div>
                  </div>
                ))}
            </div>

            {/* Phase 3 Micro-Capital Safeguards Summary */}
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300 mb-3 flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-amber-400" />
                <span>Phase 3 Micro-Capital Live Safeguards</span>
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono">
                <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                  <div className="text-[#8b949e] text-[10px] uppercase">Single-Contract Sizing Cap</div>
                  <div className="text-emerald-400 font-bold text-sm mt-0.5">
                    Max {validationStatus?.real_money_readiness.micro_capital_cap.max_contracts_per_trade ?? 2} Contracts
                    ($1.50 Max Risk)
                  </div>
                </div>
                <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                  <div className="text-[#8b949e] text-[10px] uppercase">Daily Circuit Breaker</div>
                  <div className="text-rose-400 font-bold text-sm mt-0.5">
                    -${validationStatus?.real_money_readiness.micro_capital_cap.daily_max_loss_circuit_breaker ?? 10.0} Max
                    Loss Kill
                  </div>
                </div>
                <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800">
                  <div className="text-[#8b949e] text-[10px] uppercase">Live Exchange Bankroll</div>
                  <div className="text-blue-400 font-bold text-sm mt-0.5">
                    ${(validationStatus?.real_money_readiness.live_account?.balance_dollars ?? 0.3).toFixed(2)} Available
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Manual Reset Confirmation Modal */}
      {isResetModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-rose-500/20 text-rose-400 rounded-lg border border-rose-500/30">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Reset Historical Reports</h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Clear win/loss records and recalculate efficiency metrics.
                </p>
              </div>
            </div>

            <div className="space-y-2 bg-slate-950/80 p-3.5 rounded-lg border border-slate-800 text-xs">
              <div className="text-slate-300 font-semibold mb-1">Select Reset Scope:</div>
              
              <label className="flex items-center gap-2.5 cursor-pointer p-2 rounded hover:bg-slate-800/50">
                <input
                  type="radio"
                  name="resetTarget"
                  checked={resetTarget === 'selected'}
                  onChange={() => setResetTarget('selected')}
                  className="text-emerald-500 focus:ring-emerald-500"
                />
                <span className="text-slate-200">
                  Reset <strong className="text-emerald-400">{selectedSystem === 'all' ? 'All Systems' : selectedSystem}</strong> only
                </span>
              </label>

              <label className="flex items-center gap-2.5 cursor-pointer p-2 rounded hover:bg-slate-800/50">
                <input
                  type="radio"
                  name="resetTarget"
                  checked={resetTarget === 'all'}
                  onChange={() => setResetTarget('all')}
                  className="text-rose-500 focus:ring-rose-500"
                />
                <span className="text-slate-200">
                  Reset <strong className="text-rose-400">All History Globally</strong> (Complete Wipe)
                </span>
              </label>
            </div>

            {resetMessage && (
              <div className="p-2.5 rounded bg-slate-800 text-xs text-emerald-400 text-center font-mono border border-slate-700">
                {resetMessage}
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setIsResetModalOpen(false)}
                disabled={resetting}
                className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-lg transition"
              >
                Cancel
              </button>
              <button
                onClick={handleExecuteReset}
                disabled={resetting}
                className="px-4 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-500 rounded-lg transition flex items-center gap-1.5 shadow-md disabled:opacity-50"
              >
                {resetting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Trash2 className="w-3.5 h-3.5" />}
                Confirm Reset
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
