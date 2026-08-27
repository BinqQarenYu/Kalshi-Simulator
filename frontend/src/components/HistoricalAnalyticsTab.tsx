import React, { useEffect, useState, useRef } from 'react';
import {
  TrendingUp,
  Award,
  ShieldAlert,
  Activity,
  DollarSign,
  BarChart3,
  Percent,
  RefreshCw,
  Cpu,
  CheckCircle2,
  XCircle,
  Clock,
  Layers
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
}

export const HistoricalAnalyticsTab: React.FC = () => {
  const [metrics, setMetrics] = useState<PortfolioMetrics | null>(null);
  const [equityCurve, setEquityCurve] = useState<EquityPoint[]>([]);
  const [trades, setTrades] = useState<HistoricalTrade[]>([]);
  const [settlements, setSettlements] = useState<HistoricalSettlement[]>([]);
  const [aiPredictions, setAiPredictions] = useState<AIPrediction[]>([]);
  const [activeSubTab, setActiveSubTab] = useState<'journal' | 'settlements' | 'ai'>('journal');
  const [loading, setLoading] = useState<boolean>(true);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const fetchAllData = async () => {
    setLoading(true);
    try {
      const [mRes, eqRes, trRes, stRes, aiRes] = await Promise.all([
        fetch('/api/history/metrics').then(r => r.json()).catch(() => null),
        fetch('/api/history/equity-curve').then(r => r.json()).catch(() => []),
        fetch('/api/history/trades?limit=50').then(r => r.json()).catch(() => []),
        fetch('/api/history/settlements?limit=50').then(r => r.json()).catch(() => []),
        fetch('/api/history/ai-predictions?limit=50').then(r => r.json()).catch(() => []),
      ]);

      if (mRes) setMetrics(mRes);
      if (Array.isArray(eqRes)) setEquityCurve(eqRes);
      if (Array.isArray(trRes)) setTrades(trRes);
      if (Array.isArray(stRes)) setSettlements(stRes);
      if (Array.isArray(aiRes)) setAiPredictions(aiRes);
    } catch (e) {
      console.error('Failed to fetch historical analytics data:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
    const interval = setInterval(fetchAllData, 10000);
    return () => clearInterval(interval);
  }, []);

  // Render Canvas Equity Curve
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    // Background grid
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1;
    for (let x = 0; x < width; x += 80) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = 0; y < height; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    if (equityCurve.length < 2) {
      ctx.fillStyle = '#64748b';
      ctx.font = '14px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('Accumulating real-time equity snapshots...', width / 2, height / 2);
      return;
    }

    const values = equityCurve.map(p => p.equity);
    const minVal = Math.min(...values) * 0.998;
    const maxVal = Math.max(...values) * 1.002;
    const range = maxVal - minVal || 1;

    const getX = (index: number) => (index / (equityCurve.length - 1)) * (width - 40) + 20;
    const getY = (val: number) => height - 30 - ((val - minVal) / range) * (height - 60);

    // Gradient fill under equity line
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, 'rgba(16, 185, 129, 0.25)');
    gradient.addColorStop(1, 'rgba(16, 185, 129, 0.0)');

    ctx.beginPath();
    ctx.moveTo(getX(0), getY(values[0]));
    for (let i = 1; i < values.length; i++) {
      ctx.lineTo(getX(i), getY(values[i]));
    }
    ctx.lineTo(getX(values.length - 1), height - 20);
    ctx.lineTo(getX(0), height - 20);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Equity Line
    ctx.beginPath();
    ctx.moveTo(getX(0), getY(values[0]));
    for (let i = 1; i < values.length; i++) {
      ctx.lineTo(getX(i), getY(values[i]));
    }
    ctx.strokeStyle = '#10b981';
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // Peak Watermark Line
    let peak = values[0];
    ctx.beginPath();
    ctx.moveTo(getX(0), getY(peak));
    for (let i = 1; i < values.length; i++) {
      if (values[i] > peak) peak = values[i];
      ctx.lineTo(getX(i), getY(peak));
    }
    ctx.strokeStyle = 'rgba(59, 130, 246, 0.5)';
    ctx.setLineDash([4, 4]);
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.setLineDash([]);

    // Axes annotations
    ctx.fillStyle = '#94a3b8';
    ctx.font = '11px monospace';
    ctx.textAlign = 'right';
    ctx.fillText(`$${maxVal.toFixed(2)}`, width - 5, 20);
    ctx.fillText(`$${minVal.toFixed(2)}`, width - 5, height - 10);
  }, [equityCurve]);

  return (
    <div className="space-y-6 text-slate-100 p-6 bg-slate-950 rounded-xl border border-slate-800 shadow-2xl">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 pb-4 border-b border-slate-800">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <BarChart3 className="text-emerald-400 w-7 h-7" />
            Institutional Performance Analytics & Trade Journal
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Persisted SQLite WAL Store • Quantitative Edge & Risk Diagnostics
          </p>
        </div>

        <button
          onClick={fetchAllData}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg transition border border-slate-700"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
          Refresh Store
        </button>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-lg">
          <div className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
            <Award className="w-3.5 h-3.5 text-amber-400" /> SHARPE RATIO
          </div>
          <div className="text-xl font-bold text-emerald-400 mt-1 font-mono">
            {metrics ? metrics.sharpe_ratio.toFixed(2) : '--'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Annualized 15m</div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-lg">
          <div className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
            <TrendingUp className="w-3.5 h-3.5 text-emerald-400" /> SORTINO RATIO
          </div>
          <div className="text-xl font-bold text-emerald-400 mt-1 font-mono">
            {metrics ? metrics.sortino_ratio.toFixed(2) : '--'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Downside Semi-Dev</div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-lg">
          <div className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
            <Percent className="w-3.5 h-3.5 text-blue-400" /> WIN RATE
          </div>
          <div className="text-xl font-bold text-white mt-1 font-mono">
            {metrics ? `${metrics.win_rate_pct.toFixed(1)}%` : '--'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            {metrics ? `${metrics.wins}W / ${metrics.losses}L (${metrics.total_trades} total)` : '--'}
          </div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-lg">
          <div className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
            <ShieldAlert className="w-3.5 h-3.5 text-rose-400" /> MAX DRAWDOWN
          </div>
          <div className="text-xl font-bold text-rose-400 mt-1 font-mono">
            {metrics ? `${metrics.max_drawdown_pct.toFixed(2)}%` : '--'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">20% Circuit Breaker Cap</div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-lg">
          <div className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
            <Activity className="w-3.5 h-3.5 text-cyan-400" /> PROFIT FACTOR
          </div>
          <div className="text-xl font-bold text-cyan-400 mt-1 font-mono">
            {metrics ? metrics.profit_factor.toFixed(2) : '--'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            {metrics ? `Payoff: ${metrics.payoff_ratio.toFixed(2)}x` : '--'}
          </div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-lg">
          <div className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
            <DollarSign className="w-3.5 h-3.5 text-emerald-400" /> NET REALIZED P&L
          </div>
          <div className={`text-xl font-bold mt-1 font-mono ${metrics && metrics.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {metrics ? `${metrics.net_pnl >= 0 ? '+' : ''}$${metrics.net_pnl.toFixed(2)}` : '--'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            {metrics ? `ROI: ${metrics.total_roi_pct >= 0 ? '+' : ''}${metrics.total_roi_pct.toFixed(2)}%` : '--'}
          </div>
        </div>
      </div>

      {/* Equity Curve Canvas Section */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-4">
        <div className="flex justify-between items-center mb-3">
          <div className="text-sm font-semibold text-slate-300 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            Cumulative Portfolio Equity & High-Water Mark ($)
          </div>
          <div className="text-xs text-slate-400 flex items-center gap-4">
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block" /> Live Equity
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-0.5 bg-blue-400 inline-block" /> Peak Watermark
            </span>
          </div>
        </div>
        <canvas
          ref={canvasRef}
          width={1000}
          height={240}
          className="w-full h-60 bg-slate-950/60 rounded border border-slate-800"
        />
      </div>

      {/* Sub-Tabs Selector */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
        <button
          onClick={() => setActiveSubTab('journal')}
          className={`px-4 py-2 text-sm font-semibold rounded-lg transition flex items-center gap-2 ${
            activeSubTab === 'journal'
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
          }`}
        >
          <Layers className="w-4 h-4" /> Trade Execution Journal ({trades.length})
        </button>

        <button
          onClick={() => setActiveSubTab('settlements')}
          className={`px-4 py-2 text-sm font-semibold rounded-lg transition flex items-center gap-2 ${
            activeSubTab === 'settlements'
              ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
          }`}
        >
          <Award className="w-4 h-4" /> Contract Settlements ({settlements.length})
        </button>

        <button
          onClick={() => setActiveSubTab('ai')}
          className={`px-4 py-2 text-sm font-semibold rounded-lg transition flex items-center gap-2 ${
            activeSubTab === 'ai'
              ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
          }`}
        >
          <Cpu className="w-4 h-4" /> Stage 1/2 AI Predictions ({aiPredictions.length})
        </button>
      </div>

      {/* Data Tables */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-lg overflow-hidden">
        {activeSubTab === 'journal' && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-800/80 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-700">
                <tr>
                  <th className="py-2.5 px-4">Trade ID</th>
                  <th className="py-2.5 px-3">Time (UTC)</th>
                  <th className="py-2.5 px-3">Ticker</th>
                  <th className="py-2.5 px-3">Side</th>
                  <th className="py-2.5 px-3">Size</th>
                  <th className="py-2.5 px-3">Price</th>
                  <th className="py-2.5 px-3">Notional</th>
                  <th className="py-2.5 px-3">Fees</th>
                  <th className="py-2.5 px-3">Mode</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {trades.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="py-8 text-center text-slate-500 font-sans">
                      No executed trades recorded yet in database.
                    </td>
                  </tr>
                ) : (
                  trades.map(t => (
                    <tr key={t.id} className="hover:bg-slate-800/40 transition">
                      <td className="py-2.5 px-4 font-semibold text-slate-300">{t.trade_id}</td>
                      <td className="py-2.5 px-3 text-slate-400">{t.timestamp_utc.slice(11, 19)}</td>
                      <td className="py-2.5 px-3 text-amber-300">{t.ticker}</td>
                      <td className="py-2.5 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          t.side.toLowerCase() === 'yes' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                        }`}>
                          {t.side.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-white">{t.size}</td>
                      <td className="py-2.5 px-3 text-slate-200">{(t.price * 100).toFixed(1)}¢</td>
                      <td className="py-2.5 px-3 text-slate-200">${t.gross_value.toFixed(2)}</td>
                      <td className="py-2.5 px-3 text-slate-400">${t.fees.toFixed(2)}</td>
                      <td className="py-2.5 px-3 text-slate-400">{t.execution_mode}</td>
                      <td className="py-2.5 px-3 text-emerald-400">{t.status}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {activeSubTab === 'settlements' && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-800/80 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-700">
                <tr>
                  <th className="py-2.5 px-4">Settlement ID</th>
                  <th className="py-2.5 px-3">Time (UTC)</th>
                  <th className="py-2.5 px-3">Ticker</th>
                  <th className="py-2.5 px-3">Side</th>
                  <th className="py-2.5 px-3">Size</th>
                  <th className="py-2.5 px-3">Entry Price</th>
                  <th className="py-2.5 px-3">Outcome</th>
                  <th className="py-2.5 px-3">P&L ($)</th>
                  <th className="py-2.5 px-3">Balance After</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {settlements.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-8 text-center text-slate-500 font-sans">
                      No contract settlements recorded yet in database.
                    </td>
                  </tr>
                ) : (
                  settlements.map(s => (
                    <tr key={s.id} className="hover:bg-slate-800/40 transition">
                      <td className="py-2.5 px-4 font-semibold text-slate-300">{s.settlement_id}</td>
                      <td className="py-2.5 px-3 text-slate-400">{s.timestamp_utc.slice(11, 19)}</td>
                      <td className="py-2.5 px-3 text-amber-300">{s.ticker}</td>
                      <td className="py-2.5 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          s.side.toLowerCase() === 'yes' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'
                        }`}>
                          {s.side.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-white">{s.size}</td>
                      <td className="py-2.5 px-3 text-slate-200">{(s.entry_price * 100).toFixed(1)}¢</td>
                      <td className="py-2.5 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold flex items-center gap-1 w-fit ${
                          s.outcome.toLowerCase() === 'win'
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : 'bg-rose-500/20 text-rose-300'
                        }`}>
                          {s.outcome.toLowerCase() === 'win' ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
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
        )}

        {activeSubTab === 'ai' && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-800/80 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-700">
                <tr>
                  <th className="py-2.5 px-4">Time (UTC)</th>
                  <th className="py-2.5 px-3">Ticker</th>
                  <th className="py-2.5 px-3">P(UP)</th>
                  <th className="py-2.5 px-3">P(DOWN)</th>
                  <th className="py-2.5 px-3">P(WAIT)</th>
                  <th className="py-2.5 px-3">VPIN</th>
                  <th className="py-2.5 px-3">Signal</th>
                  <th className="py-2.5 px-3">Rationale</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {aiPredictions.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-slate-500 font-sans">
                      No AI inferences recorded yet in database.
                    </td>
                  </tr>
                ) : (
                  aiPredictions.map(p => (
                    <tr key={p.id} className="hover:bg-slate-800/40 transition">
                      <td className="py-2.5 px-4 text-slate-400">{p.timestamp_utc.slice(11, 19)}</td>
                      <td className="py-2.5 px-3 text-amber-300">{p.ticker}</td>
                      <td className="py-2.5 px-3 text-emerald-400 font-semibold">{(p.p_up * 100).toFixed(1)}%</td>
                      <td className="py-2.5 px-3 text-rose-400 font-semibold">{(p.p_down * 100).toFixed(1)}%</td>
                      <td className="py-2.5 px-3 text-slate-400">{(p.p_wait * 100).toFixed(1)}%</td>
                      <td className="py-2.5 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          p.vpin <= 0.40
                            ? 'bg-emerald-500/20 text-emerald-300'
                            : p.vpin <= 0.60
                            ? 'bg-amber-500/20 text-amber-300'
                            : 'bg-rose-500/20 text-rose-300'
                        }`}>
                          {p.vpin.toFixed(2)} {p.vpin <= 0.40 ? 'SAFE' : p.vpin <= 0.60 ? 'WARN' : 'TOXIC'}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-bold text-white uppercase">{p.recommended_side}</td>
                      <td className="py-2.5 px-3 text-slate-400 truncate max-w-xs">{p.rationale || '--'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
