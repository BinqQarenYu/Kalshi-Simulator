import React, { useEffect, useState, useRef } from 'react';
import {
  TrendingUp,
  TrendingDown,
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
  Download,
  FileSpreadsheet,
  Play,
  Loader2,
  FileText,
  CheckSquare,
  Square,
  Crown,
} from 'lucide-react';
import { WinLossEventReport } from '../types';
import {
  PortfolioMetrics,
  EquityPoint,
  HistoricalTrade,
  HistoricalSettlement,
  AIPrediction,
  ForwardValidationStatus,
  SystemFilter,
  SubTabType,
  ITEMS_PER_PAGE,
  formatETDate,
  formatETTime,
} from './analytics/AnalyticsTypes';
import { WinLoss15mSubtab } from './analytics/WinLoss15mSubtab';
import { TradeJournalSubtab } from './analytics/TradeJournalSubtab';
import { SettlementsSubtab } from './analytics/SettlementsSubtab';
import { AIPredictionsSubtab } from './analytics/AIPredictionsSubtab';
import { ValidationGateSubtab } from './analytics/ValidationGateSubtab';

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
  const [winLossReports, setWinLossReports] = useState<WinLossEventReport[]>([]);
  const [validationStatus, setValidationStatus] = useState<ForwardValidationStatus | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<SubTabType>('15m_reports');
  const [loading, setLoading] = useState<boolean>(true);

  // Filter & Pagination States
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [assetFilter, setAssetFilter] = useState<'ALL' | 'BTC' | 'ETH' | 'SOL' | 'DOGE'>('ALL');
  const [timeframeFilter, setTimeframeFilter] = useState<'ALL' | '5M' | '15M'>('ALL');
  const [botFilter, setBotFilter] = useState<'all' | 'macro_onnx' | 'macro_trend_dominion' | 'dominion_2_bot' | '3_step_domination_bot' | 'onnx_ml_bot' | 'live'>('all');
  const [sideFilter, setSideFilter] = useState<'all' | 'yes' | 'no'>('all');
  const [outcomeFilter, setOutcomeFilter] = useState<'all' | 'win' | 'loss' | 'flat'>('all');
  const [page, setPage] = useState<number>(1);

  // Multi-Selection State for Bulk Actions
  const [selectedIds, setSelectedIds] = useState<Set<string | number>>(new Set());

  // Test Bot Trigger State
  const [isTestingBot, setIsTestingBot] = useState<boolean>(false);
  const [testBotType, setTestBotType] = useState<'both' | 'macro_onnx' | 'macro_trend_dominion' | 'dominion_2_bot' | '3_step_domination_bot' | 'onnx_ml_bot'>('both');
  const [testResultMsg, setTestResultMsg] = useState<string | null>(null);

  // Reset Confirmation Modal State
  const [isResetModalOpen, setIsResetModalOpen] = useState<boolean>(false);
  const [resetTarget, setResetTarget] = useState<string>('selected');
  const [resetting, setResetting] = useState<boolean>(false);
  const [resetMessage, setResetMessage] = useState<string | null>(null);

  // Global Export Menu State
  const [isExportMenuOpen, setIsExportMenuOpen] = useState<boolean>(false);

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

      if (selectedSystem === 'macro_onnx') {
        botParam = 'macro_onnx';
        modeParam = '';
      } else if (selectedSystem === 'macro_trend_dominion') {
        botParam = 'macro_trend_dominion';
        modeParam = 'simulated';
      } else if (selectedSystem === 'dominion_2_bot') {
        botParam = 'dominion_2_bot';
        modeParam = 'simulated';
      } else if (selectedSystem === '3_step_domination_bot') {
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
      if (assetFilter !== 'ALL') queryParams.append('asset', assetFilter);
      if (timeframeFilter !== 'ALL') queryParams.append('timeframe', timeframeFilter);
      const qs = queryParams.toString() ? `?${queryParams.toString()}` : '';
      const filterSuffix = `${assetFilter !== 'ALL' ? `&asset=${assetFilter}` : ''}${timeframeFilter !== 'ALL' ? `&timeframe=${timeframeFilter}` : ''}`;

      const [mRes, eqRes, trRes, stRes, aiRes, valRes, wlRes, mAll, mMacroOnnx, mMacro, mDom2, mDom, mOnnx, mLive] = await Promise.all([
        fetch(`/api/history/metrics${qs}`).then((r) => r.json()).catch(() => null),
        fetch(`/api/history/equity-curve${qs ? `${qs}&limit=1000` : '?limit=1000'}`).then((r) => r.json()).catch(() => []),
        fetch(`/api/history/trades${qs ? `${qs}&limit=500` : '?limit=500'}`).then((r) => r.json()).catch(() => []),
        fetch(`/api/history/settlements${qs ? `${qs}&limit=500` : '?limit=500'}`).then((r) => r.json()).catch(() => []),
        fetch(`/api/history/ai-predictions${botParam ? `?bot_type=${botParam}&limit=500${filterSuffix}` : `?limit=500${filterSuffix}`}`).then((r) => r.json()).catch(() => []),
        fetch(`/api/bot/forward-validation-status${qs}`).then((r) => r.json()).catch(() => null),
        fetch(`/api/reports/full${qs ? `?${queryParams.toString()}` : ''}`).then((r) => r.json()).catch(() => null),
        fetch(`/api/history/metrics?bot_type=all${filterSuffix}`).then((r) => r.json()).catch(() => null),
        fetch(`/api/history/metrics?bot_type=macro_onnx${filterSuffix}`).then((r) => r.json()).catch(() => null),
        fetch(`/api/history/metrics?bot_type=macro_trend_dominion&execution_mode=simulated${filterSuffix}`).then((r) => r.json()).catch(() => null),
        fetch(`/api/history/metrics?bot_type=dominion_2_bot&execution_mode=simulated${filterSuffix}`).then((r) => r.json()).catch(() => null),
        fetch(`/api/history/metrics?bot_type=3_step_domination_bot&execution_mode=simulated${filterSuffix}`).then((r) => r.json()).catch(() => null),
        fetch(`/api/history/metrics?bot_type=onnx_ml_bot&execution_mode=simulated${filterSuffix}`).then((r) => r.json()).catch(() => null),
        fetch(`/api/history/metrics?execution_mode=live${filterSuffix}`).then((r) => r.json()).catch(() => null),
      ]);

      if (mRes) setMetrics(mRes);
      if (Array.isArray(eqRes)) setEquityCurve(eqRes);
      if (Array.isArray(trRes)) setTrades(trRes);
      if (Array.isArray(stRes)) setSettlements(stRes);
      if (Array.isArray(aiRes)) setAiPredictions(aiRes);
      if (valRes) setValidationStatus(valRes);
      if (wlRes && Array.isArray(wlRes.reports)) setWinLossReports(wlRes.reports);

      setSystemComparison([
        {
          key: 'all',
          label: 'All Combined',
          sublabel: 'Aggregated Portfolio Overview',
          icon: 'layers',
          metrics: mAll,
        },
        {
          key: 'macro_onnx',
          label: 'Macro ONNX Bot (Champion)',
          sublabel: 'Macro Trend + 15M Retrained ONNX (84.6% WR, PF 6.99)',
          icon: 'cpu',
          metrics: mMacroOnnx || mMacro,
        },
        {
          key: 'macro_trend_dominion',
          label: 'Macro Trend Dominion',
          sublabel: '1-Hour Macro Trend Following (Paper)',
          icon: 'trending-up',
          metrics: mMacro,
        },
        {
          key: 'dominion_2_bot',
          label: 'Dominion 2 Bot',
          sublabel: 'Anti-Pin Asymmetric Scalper (Paper)',
          icon: 'crown',
          metrics: mDom2,
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
  }, [selectedSystem, assetFilter, timeframeFilter]);

  // Reset page & selection when switching tabs or filters
  useEffect(() => {
    setPage(1);
    setSelectedIds(new Set());
  }, [activeSubTab, searchTerm, sideFilter, outcomeFilter, selectedSystem, assetFilter, timeframeFilter]);

  // 1. DELETE Single Item Action
  const handleDeleteSingle = async (type: SubTabType, id: string | number) => {
    try {
      let endpoint = '';
      if (type === '15m_reports') {
        endpoint = `/api/reports/win-loss/${id}`;
      } else if (type === 'journal') {
        endpoint = `/api/history/trades/${id}`;
      } else if (type === 'settlements') {
        endpoint = `/api/history/settlements/${id}`;
      } else if (type === 'ai') {
        endpoint = `/api/history/ai-predictions/${id}`;
      }

      if (!endpoint) return;

      const res = await fetch(endpoint, { method: 'DELETE' });
      if (res.ok) {
        if (type === '15m_reports') {
          setWinLossReports((prev) => prev.filter((r) => r.report_id !== id));
        } else if (type === 'journal') {
          setTrades((prev) => prev.filter((t) => t.id !== id && t.trade_id !== id));
        } else if (type === 'settlements') {
          setSettlements((prev) => prev.filter((s) => s.id !== id && s.settlement_id !== id));
        } else if (type === 'ai') {
          setAiPredictions((prev) => prev.filter((p) => p.id !== id));
        }
        fetchAllData();
      }
    } catch (err) {
      console.error(`Failed to delete record ${id}:`, err);
    }
  };

  // 1. DELETE Batch / Bulk Selected Items Action
  const handleDeleteBatch = async (type: SubTabType) => {
    if (selectedIds.size === 0) return;
    try {
      let table = '';
      if (type === '15m_reports') table = 'win_loss_reports';
      else if (type === 'journal') table = 'trades';
      else if (type === 'settlements') table = 'settlements';
      else if (type === 'ai') table = 'ai_predictions';

      if (!table) return;

      const res = await fetch('/api/history/batch-delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          table,
          ids: Array.from(selectedIds),
        }),
      });

      if (res.ok) {
        setSelectedIds(new Set());
        fetchAllData();
      }
    } catch (err) {
      console.error('Batch delete failed:', err);
    }
  };

  // 2. RESET Execution Handler
  const handleExecuteReset = async () => {
    setResetting(true);
    try {
      let targetParam = resetTarget;
      if (resetTarget === 'selected') {
        targetParam = selectedSystem === 'all' ? 'all' : selectedSystem;
      }
      const res = await fetch(`/api/reports/reset?target=${targetParam}`, {
        method: 'POST',
      });
      const data = await res.json();
      setResetMessage(data.message || 'Ledger reset successfully.');
      setTimeout(() => {
        setIsResetModalOpen(false);
        setResetMessage(null);
        setSelectedIds(new Set());
        fetchAllData();
      }, 1000);
    } catch (e) {
      console.error('Failed to reset reports:', e);
      setResetMessage('Reset request failed. Please try again.');
    } finally {
      setResetting(false);
    }
  };

  // 3. RUN BOT TEST Handler
  const handleRunBotTest = async (overrideType?: 'both' | 'macro_onnx' | 'macro_trend_dominion' | 'dominion_2_bot' | '3_step_domination_bot' | 'onnx_ml_bot') => {
    const targetType = overrideType || testBotType;
    setIsTestingBot(true);
    setTestResultMsg(null);
    try {
      const res = await fetch(`/api/bot/test-trade?bot_type=${targetType}`, { method: 'POST' });
      const data = await res.json();
      if (data?.message) {
        setTestResultMsg(data.message);
      }
      fetchAllData();
    } catch (err) {
      setTestResultMsg(`Error testing bot: ${err}`);
    } finally {
      setIsTestingBot(false);
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
            : selectedSystem === 'dominion_2_bot'
            ? 'Dominion 2 Bot'
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

  // Helper to identify bot types
  const isMacroOnnxBot = (r: WinLossEventReport) =>
    r.bot_type === 'macro_onnx' ||
    r.bot_type === 'macro_onnx_bot' ||
    r.bot_type === 'macro_trend_onnx_fusion' ||
    (r.ai_rationale?.toLowerCase().includes('macro') && r.ai_rationale?.toLowerCase().includes('onnx'));

  const isMacroBot = (r: WinLossEventReport) =>
    !isMacroOnnxBot(r) && (
      r.bot_type === 'macro_trend_dominion' ||
      r.bot_type === 'macro_trend' ||
      r.ai_rationale?.toLowerCase().includes('macro trend')
    );

  const isDom2Bot = (r: WinLossEventReport) =>
    r.bot_type === 'dominion_2_bot' ||
    r.bot_type === 'dominion2' ||
    r.bot_type === 'dominion_v2' ||
    r.ai_rationale?.toLowerCase().includes('dominion 2');

  const isDomBot = (r: WinLossEventReport) =>
    r.bot_type === '3_step_domination_bot' ||
    r.bot_type === 'domination' ||
    (!r.bot_type && r.ai_rationale?.toLowerCase().includes('domination') && !r.ai_rationale?.toLowerCase().includes('dominion 2')) ||
    (!r.bot_type && !r.ai_rationale?.toLowerCase().includes('dominion 2'));

  const isOnnxBot = (r: WinLossEventReport) =>
    r.bot_type === 'onnx_ml_bot' ||
    r.bot_type === 'onnx' ||
    r.bot_type?.includes('onnx') ||
    r.ai_rationale?.toLowerCase().includes('onnx') ||
    r.ai_rationale?.toLowerCase().includes('kelly');

  // Filtering Logic for Tables
  const filteredWinLoss = (winLossReports || []).filter((r) => {
    if (
      searchTerm &&
      !(r.ticker || '').toLowerCase().includes(searchTerm.toLowerCase()) &&
      !(r.report_id || '').toLowerCase().includes(searchTerm.toLowerCase()) &&
      !(r.cycle_time || '').toLowerCase().includes(searchTerm.toLowerCase()) &&
      !(r.bot_type && r.bot_type.toLowerCase().includes(searchTerm.toLowerCase()))
    ) {
      return false;
    }
    if (assetFilter !== 'ALL') {
      const ticker = (r.ticker || '').toUpperCase();
      const rAsset = (r.asset || '').toUpperCase();
      if (rAsset !== assetFilter && !ticker.includes(`KX${assetFilter}`)) return false;
    }
    if (timeframeFilter !== 'ALL') {
      const ticker = (r.ticker || '').toUpperCase();
      const rTf = (r.timeframe || '').toUpperCase();
      if (rTf !== timeframeFilter && !ticker.includes(timeframeFilter)) return false;
    }
    if (botFilter !== 'all') {
      if (botFilter === 'macro_onnx' && !isMacroOnnxBot(r)) return false;
      if (botFilter === 'macro_trend_dominion' && !isMacroBot(r)) return false;
      if (botFilter === 'dominion_2_bot' && !isDom2Bot(r)) return false;
      if (botFilter === '3_step_domination_bot' && !isDomBot(r)) return false;
      if (botFilter === 'onnx_ml_bot' && !isOnnxBot(r)) return false;
      if (botFilter === 'live' && r.execution_mode !== 'live' && r.bot_type !== 'live') return false;
    }
    if (sideFilter !== 'all' && r.bot_side.toLowerCase() !== sideFilter) return false;
    if (outcomeFilter !== 'all') {
      if (outcomeFilter === 'win' && r.outcome !== 'win') return false;
      if (outcomeFilter === 'loss' && r.outcome !== 'loss') return false;
      if (outcomeFilter === 'flat' && !['flat', 'breakeven', 'skip', 'veto'].includes(r.outcome)) return false;
    }
    return true;
  });

  const filteredTrades = trades.filter((t) => {
    if (
      searchTerm &&
      !t.ticker.toLowerCase().includes(searchTerm.toLowerCase()) &&
      !t.trade_id.toLowerCase().includes(searchTerm.toLowerCase())
    ) {
      return false;
    }
    if (assetFilter !== 'ALL' && !t.ticker.toUpperCase().includes(`KX${assetFilter}`)) return false;
    if (timeframeFilter !== 'ALL' && !t.ticker.toUpperCase().includes(timeframeFilter) && t.timeframe?.toUpperCase() !== timeframeFilter) return false;
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
    if (assetFilter !== 'ALL' && !s.ticker.toUpperCase().includes(`KX${assetFilter}`)) return false;
    if (timeframeFilter !== 'ALL' && !s.ticker.toUpperCase().includes(timeframeFilter)) return false;
    if (sideFilter !== 'all' && s.side.toLowerCase() !== sideFilter) return false;
    if (outcomeFilter !== 'all' && s.outcome.toLowerCase() !== outcomeFilter) return false;
    return true;
  });

  const filteredAi = aiPredictions.filter((p) => {
    if (searchTerm && !p.ticker.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    if (assetFilter !== 'ALL' && !p.ticker.toUpperCase().includes(`KX${assetFilter}`)) return false;
    if (sideFilter !== 'all' && p.recommended_side.toLowerCase() !== sideFilter) return false;
    return true;
  });

  // Pagination Helper
  const getPaginatedList = <T,>(list: T[]): { items: T[]; totalPages: number; totalCount: number } => {
    const totalCount = list.length;
    const totalPages = Math.max(1, Math.ceil(totalCount / ITEMS_PER_PAGE));
    const validPage = Math.min(page, totalPages);
    const start = (validPage - 1) * ITEMS_PER_PAGE;
    const items = list.slice(start, start + ITEMS_PER_PAGE);
    return { items, totalPages, totalCount };
  };

  const paginatedWinLoss = getPaginatedList(filteredWinLoss);
  const paginatedTrades = getPaginatedList(filteredTrades);
  const paginatedSettlements = getPaginatedList(filteredSettlements);
  const paginatedAi = getPaginatedList(filteredAi);

  // Toggle Single Selection
  const toggleSelectId = (id: string | number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Toggle Select All Visible Items
  const toggleSelectAllCurrentPage = (currentItems: (string | number)[]) => {
    const allSelected = currentItems.every((id) => selectedIds.has(id));
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allSelected) {
        currentItems.forEach((id) => next.delete(id));
      } else {
        currentItems.forEach((id) => next.add(id));
      }
      return next;
    });
  };

  // Multi-Bot 15M Win/Loss Aggregates for Top Banner
  const calc15mStats = (reps: WinLossEventReport[]) => {
    const safeReps = Array.isArray(reps) ? reps : [];
    const total = safeReps.length;
    const wins = safeReps.filter((r) => r.outcome === 'win').length;
    const losses = safeReps.filter((r) => r.outcome === 'loss').length;
    const winRate = total > 0 ? (wins / total) * 100 : 0;
    const totalPnL = safeReps.reduce((acc, r) => acc + (r.pnl || 0), 0);
    const grossProfits = safeReps.filter((r) => (r.pnl || 0) > 0).reduce((acc, r) => acc + (r.pnl || 0), 0);
    const grossLosses = Math.abs(safeReps.filter((r) => (r.pnl || 0) < 0).reduce((acc, r) => acc + (r.pnl || 0), 0));
    const profitFactor = grossLosses > 0 ? grossProfits / grossLosses : grossProfits > 0 ? 99.9 : 1.0;
    const avgPnL = total > 0 ? totalPnL / total : 0;
    return { total, wins, losses, winRate, totalPnL, profitFactor, avgPnL, grossProfits, grossLosses };
  };

  const dom15mReports = winLossReports.filter(isDomBot);
  const onnx15mReports = winLossReports.filter(isOnnxBot);
  const live15mReports = winLossReports.filter(
    (r) => (r.execution_mode === 'live' || r.bot_type === 'live') && (r.ticker.includes('SEP01') || r.timestamp_utc?.startsWith('2026-09-01'))
  );

  const domStats15m = calc15mStats(dom15mReports);
  const onnxStats15m = calc15mStats(onnx15mReports);
  const liveStats15m = calc15mStats(live15mReports);
  const combinedStats15m = calc15mStats(winLossReports);

  return (
    <div className="space-y-6 text-slate-100 p-3 sm:p-6 bg-slate-950 rounded-2xl border border-slate-800 shadow-2xl">
      {/* --------------------------------------------------------------------------- */}
      {/* 1. Header & Global Toolbar */}
      {/* --------------------------------------------------------------------------- */}
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-400">
              <BarChart3 className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-xl sm:text-2xl font-black tracking-tight text-white flex items-center gap-2">
                <span>Institutional Performance Analytics & Trade Journal</span>
                <span className="px-2 py-0.5 text-[10px] font-mono bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 rounded-full font-bold">
                  UNIFIED REPORTING HUB
                </span>
              </h2>
              <p className="text-xs sm:text-sm text-slate-400 mt-0.5">
                Consolidated 15M Event Reports • Executions Ledger • Settlements • AI Inference • SQLite WAL Sync
              </p>
            </div>
          </div>
        </div>

        {/* Global Action Toolbar */}
        <div className="flex flex-wrap items-center gap-2.5 w-full lg:w-auto">
          {/* Test Bot Trigger with Multi-Bot Selector */}
          <div className="flex items-center bg-slate-900 border border-slate-700 rounded-xl p-0.5 shadow-sm">
            <button
              onClick={() => handleRunBotTest(testBotType)}
              disabled={isTestingBot}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white text-xs sm:text-sm font-bold rounded-lg shadow-md transition-all active:scale-95 disabled:opacity-50"
              title="Execute immediate 15M cycle trade test and record report"
            >
              {isTestingBot ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
              <span>{isTestingBot ? 'Testing...' : '🧪 Run 15M Test'}</span>
            </button>
            <div className="flex items-center px-1 gap-1">
              <button
                onClick={() => {
                  setTestBotType('both');
                  handleRunBotTest('both');
                }}
                className={`px-2 py-1 text-[10px] font-bold rounded-md transition ${
                  testBotType === 'both' ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'
                }`}
                title="Run test trade for Both Domination and ONNX ML bots"
              >
                🚀 Both
              </button>
              <button
                onClick={() => {
                  setTestBotType('macro_onnx');
                  handleRunBotTest('macro_onnx');
                }}
                className={`px-2 py-1 text-[10px] font-bold rounded-md transition ${
                  testBotType === 'macro_onnx' ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-white'
                }`}
                title="Run test trade for Macro ONNX Bot (Champion)"
              >
                🧠 Macro ONNX
              </button>
              <button
                onClick={() => {
                  setTestBotType('macro_trend_dominion');
                  handleRunBotTest('macro_trend_dominion');
                }}
                className={`px-2 py-1 text-[10px] font-bold rounded-md transition ${
                  testBotType === 'macro_trend_dominion' ? 'bg-cyan-600 text-white' : 'text-slate-400 hover:text-white'
                }`}
                title="Run test trade for Macro Trend Dominion"
              >
                📈 Macro Trend
              </button>
              <button
                onClick={() => {
                  setTestBotType('dominion_2_bot');
                  handleRunBotTest('dominion_2_bot');
                }}
                className={`px-2 py-1 text-[10px] font-bold rounded-md transition ${
                  testBotType === 'dominion_2_bot' ? 'bg-emerald-600 text-white' : 'text-slate-400 hover:text-white'
                }`}
                title="Run test trade for Dominion 2 Bot (Anti-Pin Scalper)"
              >
                👑 Dominion 2
              </button>
              <button
                onClick={() => {
                  setTestBotType('3_step_domination_bot');
                  handleRunBotTest('3_step_domination_bot');
                }}
                className={`px-2 py-1 text-[10px] font-bold rounded-md transition ${
                  testBotType === '3_step_domination_bot' ? 'bg-sky-600 text-white' : 'text-slate-400 hover:text-white'
                }`}
                title="Run test trade for 3-Step Domination Bot"
              >
                ⚡ Domination
              </button>
              <button
                onClick={() => {
                  setTestBotType('onnx_ml_bot');
                  handleRunBotTest('onnx_ml_bot');
                }}
                className={`px-2 py-1 text-[10px] font-bold rounded-md transition ${
                  testBotType === 'onnx_ml_bot' ? 'bg-purple-600 text-white' : 'text-slate-400 hover:text-white'
                }`}
                title="Run test trade for ONNX ML Ensemble"
              >
                🧠 ONNX
              </button>
            </div>
          </div>

          {/* Refresh Button */}
          <button
            onClick={fetchAllData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs sm:text-sm font-semibold rounded-xl transition border border-slate-700 shadow-sm"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
            <span>Refresh</span>
          </button>

          {/* Global Export Menu */}
          <div className="relative">
            <button
              onClick={() => setIsExportMenuOpen(!isExportMenuOpen)}
              className="flex items-center gap-1.5 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs sm:text-sm font-semibold rounded-xl transition border border-slate-700 shadow-sm"
            >
              <Download className="w-4 h-4 text-blue-400" />
              <span>Export All</span>
            </button>

            {isExportMenuOpen && (
              <div className="absolute right-0 mt-2 w-64 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl p-2 z-50 animate-in fade-in space-y-1 text-xs font-sans">
                <div className="px-2.5 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                  Download Reports
                </div>
                <a
                  href="/api/reports/executive-summary/export.json"
                  download="kalshi_executive_audit_summary.json"
                  onClick={() => setIsExportMenuOpen(false)}
                  className="flex items-center gap-2 px-2.5 py-2 rounded-lg hover:bg-slate-800 text-slate-200 hover:text-white transition"
                >
                  <FileText className="w-4 h-4 text-emerald-400" />
                  <span>Executive Audit Summary (JSON)</span>
                </a>
                <a
                  href="/api/reports/win-loss/export.csv"
                  download="kalshi_15m_win_loss_reports.csv"
                  onClick={() => setIsExportMenuOpen(false)}
                  className="flex items-center gap-2 px-2.5 py-2 rounded-lg hover:bg-slate-800 text-slate-200 hover:text-white transition"
                >
                  <FileSpreadsheet className="w-4 h-4 text-emerald-400" />
                  <span>15M Event Reports (CSV)</span>
                </a>
                <a
                  href="/api/history/trades/export.csv"
                  download="kalshi_trade_journal.csv"
                  onClick={() => setIsExportMenuOpen(false)}
                  className="flex items-center gap-2 px-2.5 py-2 rounded-lg hover:bg-slate-800 text-slate-200 hover:text-white transition"
                >
                  <FileSpreadsheet className="w-4 h-4 text-blue-400" />
                  <span>Trade Journal (CSV)</span>
                </a>
                <a
                  href="/api/history/settlements/export.csv"
                  download="kalshi_settlements.csv"
                  onClick={() => setIsExportMenuOpen(false)}
                  className="flex items-center gap-2 px-2.5 py-2 rounded-lg hover:bg-slate-800 text-slate-200 hover:text-white transition"
                >
                  <FileSpreadsheet className="w-4 h-4 text-purple-400" />
                  <span>Settlements Ledger (CSV)</span>
                </a>
                <a
                  href="/api/history/ai-predictions/export.csv"
                  download="kalshi_ai_decisions.csv"
                  onClick={() => setIsExportMenuOpen(false)}
                  className="flex items-center gap-2 px-2.5 py-2 rounded-lg hover:bg-slate-800 text-slate-200 hover:text-white transition"
                >
                  <FileSpreadsheet className="w-4 h-4 text-amber-400" />
                  <span>AI Inferences (CSV)</span>
                </a>
              </div>
            )}
          </div>

          {/* Delete / Reset Button */}
          <button
            onClick={() => setIsResetModalOpen(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 hover:text-rose-100 text-xs sm:text-sm font-semibold rounded-xl transition border border-rose-800/60 shadow-sm"
          >
            <Trash2 className="w-4 h-4 text-rose-400" />
            <span>Reset Ledger</span>
          </button>
        </div>
      </div>

      {/* Live Test Feedback Banner */}
      {testResultMsg && (
        <div className="p-3 bg-blue-500/15 border border-blue-500/30 rounded-xl text-xs text-blue-300 flex items-center justify-between gap-2 animate-in fade-in">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-blue-400 shrink-0 animate-pulse" />
            <span className="font-mono">{testResultMsg}</span>
          </div>
          <button onClick={() => setTestResultMsg(null)} className="text-slate-400 hover:text-white text-xs">
            ✕
          </button>
        </div>
      )}

      {/* --------------------------------------------------------------------------- */}
      {/* 2. OVERALL MULTI-SYSTEM EFFICIENCY SUMMARY MATRIX */}
      {/* --------------------------------------------------------------------------- */}
      <div className="bg-slate-900/95 border border-slate-800 rounded-2xl p-4 sm:p-5 shadow-xl space-y-3.5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
              <BarChart3 className="h-4 w-4 text-emerald-400" />
            </div>
            <div>
              <h3 className="text-sm sm:text-base font-extrabold text-white flex items-center gap-2">
                <span>Multi-Bot Profitability & Efficiency Benchmark</span>
                <span className="px-2 py-0.5 text-[10px] font-mono bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 rounded-full font-bold">
                  SIDE-BY-SIDE AUDIT
                </span>
              </h3>
              <p className="text-xs text-slate-400">
                Direct comparative performance across quantitative playbooks, deep neural models, and live fills.
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
                        {item.icon === 'crown' && <Crown className="w-4 h-4 text-emerald-400 shrink-0" />}
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
                      {m && m.total_trades > 0 && m.win_rate_pct != null ? `${m.win_rate_pct.toFixed(1)}%` : '0.0%'}
                    </td>
                    <td className={`py-3 px-3 text-right font-bold text-sm ${
                      m && m.net_pnl > 0 ? 'text-emerald-400' : m && m.net_pnl < 0 ? 'text-rose-400' : 'text-slate-400'
                    }`}>
                      {m && m.net_pnl != null ? `${m.net_pnl >= 0 ? '+' : ''}$${m.net_pnl.toFixed(2)}` : '$0.00'}
                    </td>
                    <td className="py-3 px-3 text-right font-bold text-cyan-400">
                      {m && m.total_trades > 0 && m.profit_factor != null ? m.profit_factor.toFixed(2) : '1.00'}
                    </td>
                    <td className="py-3 px-3 text-right text-emerald-400 font-semibold">
                      {m && m.total_trades > 0 && m.expectancy_per_trade != null ? `${m.expectancy_per_trade >= 0 ? '+' : ''}$${m.expectancy_per_trade.toFixed(2)}` : '$0.00'}
                    </td>
                    <td className="py-3 px-3 text-right text-blue-400">
                      {m && m.total_trades > 0 && m.sharpe_ratio != null ? m.sharpe_ratio.toFixed(2) : '0.00'}
                    </td>
                    <td className="py-3 px-3 text-right text-rose-400">
                      {m && m.total_trades > 0 && m.max_drawdown_pct != null ? `${m.max_drawdown_pct.toFixed(2)}%` : '0.00%'}
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

      {/* --------------------------------------------------------------------------- */}
      {/* 3. Bot & System Isolated Drilldown Selector */}
      {/* --------------------------------------------------------------------------- */}
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
            onClick={() => setSelectedSystem('macro_onnx')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition ${
              selectedSystem === 'macro_onnx'
                ? 'bg-purple-500/20 text-purple-300 shadow-sm border border-purple-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Cpu className="w-3.5 h-3.5 text-purple-400" />
            Macro ONNX Bot (Champ)
          </button>

          <button
            onClick={() => setSelectedSystem('macro_trend_dominion')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition ${
              selectedSystem === 'macro_trend_dominion'
                ? 'bg-cyan-500/20 text-cyan-300 shadow-sm border border-cyan-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <TrendingUp className="w-3.5 h-3.5 text-cyan-400" />
            Macro Trend Dominion (Paper)
          </button>

          <button
            onClick={() => setSelectedSystem('dominion_2_bot')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition ${
              selectedSystem === 'dominion_2_bot'
                ? 'bg-emerald-500/20 text-emerald-300 shadow-sm border border-emerald-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Crown className="w-3.5 h-3.5 text-emerald-400" />
            Dominion 2 Bot (Paper)
          </button>

          <button
            onClick={() => setSelectedSystem('3_step_domination_bot')}
            className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition ${
              selectedSystem === '3_step_domination_bot'
                ? 'bg-amber-500/20 text-amber-300 shadow-sm border border-amber-500/40'
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

      {/* 3B. Multi-Asset & Multi-Timeframe Institutional Filter */}
      <div className="bg-slate-900/90 border border-slate-800 p-3 rounded-xl flex flex-wrap items-center justify-between gap-3 font-mono">
        <div className="flex items-center gap-3">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[#8c9ba5]">Asset Class:</span>
          <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
            {(['ALL', 'BTC', 'ETH', 'SOL', 'DOGE'] as const).map((a) => (
              <button
                key={a}
                onClick={() => setAssetFilter(a)}
                className={`px-3 py-1 rounded text-xs font-bold transition ${
                  assetFilter === a
                    ? 'bg-emerald-500 text-black shadow-sm font-black'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {a}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[#8c9ba5]">Cycle Horizon:</span>
          <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
            {(['ALL', '5M', '15M'] as const).map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframeFilter(tf)}
                className={`px-3 py-1 rounded text-xs font-bold transition ${
                  timeframeFilter === tf
                    ? 'bg-amber-500 text-black shadow-sm font-black'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* --------------------------------------------------------------------------- */}
      {/* 4. KPI Cards Grid */}
      {/* --------------------------------------------------------------------------- */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-xl shadow-sm">
          <div className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5 uppercase">
            <Award className="w-3.5 h-3.5 text-amber-400" /> SHARPE RATIO
          </div>
          <div className="text-lg sm:text-xl font-bold text-emerald-400 mt-1 font-mono">
            {metrics?.sharpe_ratio != null ? metrics.sharpe_ratio.toFixed(2) : '--'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">365-Day 15M Annualized</div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-xl shadow-sm">
          <div className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5 uppercase">
            <TrendingUp className="w-3.5 h-3.5 text-emerald-400" /> SORTINO RATIO
          </div>
          <div className="text-lg sm:text-xl font-bold text-emerald-400 mt-1 font-mono">
            {metrics?.sortino_ratio != null ? metrics.sortino_ratio.toFixed(2) : '--'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Downside Risk Guard</div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-xl shadow-sm">
          <div className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5 uppercase">
            <Percent className="w-3.5 h-3.5 text-blue-400" /> WIN RATE
          </div>
          <div className="text-lg sm:text-xl font-bold text-white mt-1 font-mono">
            {metrics?.win_rate_pct != null ? `${metrics.win_rate_pct.toFixed(1)}%` : '--'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            {metrics ? `${metrics.wins ?? 0}W / ${metrics.losses ?? 0}L (${metrics.total_trades ?? 0} cycles)` : '--'}
          </div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-xl shadow-sm">
          <div className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5 uppercase">
            <ShieldAlert className="w-3.5 h-3.5 text-rose-400" /> MAX DRAWDOWN
          </div>
          <div className="text-lg sm:text-xl font-bold text-rose-400 mt-1 font-mono">
            {metrics?.max_drawdown_pct != null ? `${metrics.max_drawdown_pct.toFixed(2)}%` : '--'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">15% Gate Threshold</div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-xl shadow-sm">
          <div className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5 uppercase">
            <Activity className="w-3.5 h-3.5 text-cyan-400" /> PROFIT FACTOR
          </div>
          <div className="text-lg sm:text-xl font-bold text-cyan-400 mt-1 font-mono">
            {metrics?.profit_factor != null ? metrics.profit_factor.toFixed(2) : '--'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            {metrics?.payoff_ratio != null ? `Payoff: ${metrics.payoff_ratio.toFixed(2)}x` : '--'}
          </div>
        </div>

        <div className="bg-slate-900/90 border border-slate-800 p-3.5 rounded-xl shadow-sm">
          <div className="text-[11px] font-semibold text-slate-400 flex items-center gap-1.5 uppercase">
            <DollarSign className="w-3.5 h-3.5 text-emerald-400" /> NET REALIZED P&L
          </div>
          <div
            className={`text-lg sm:text-xl font-bold mt-1 font-mono ${
              metrics && (metrics.net_pnl ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'
            }`}
          >
            {metrics?.net_pnl != null ? `${metrics.net_pnl >= 0 ? '+' : ''}$${metrics.net_pnl.toFixed(2)}` : '--'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            {metrics?.total_roi_pct != null ? `ROI: ${metrics.total_roi_pct >= 0 ? '+' : ''}${metrics.total_roi_pct.toFixed(1)}%` : '--'}
          </div>
        </div>
      </div>

      {/* --------------------------------------------------------------------------- */}
      {/* 5. HiDPI Canvas Equity Curve Section */}
      {/* --------------------------------------------------------------------------- */}
      <div ref={containerRef} className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-sm">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 mb-3">
          <div className="text-xs sm:text-sm font-semibold text-slate-200 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            Cumulative Portfolio Equity & High-Water Mark ($) •{' '}
            <span className="text-emerald-400 font-mono">
              {selectedSystem === 'all'
                ? 'All Combined'
                : selectedSystem === 'dominion_2_bot'
                ? 'Dominion 2 Bot'
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

      {/* --------------------------------------------------------------------------- */}
      {/* 6. Consolidated Sub-Tabs Selector */}
      {/* --------------------------------------------------------------------------- */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="flex flex-wrap items-center gap-2">
          {/* 15M Win/Loss Event Reports Tab */}
          <button
            onClick={() => setActiveSubTab('15m_reports')}
            className={`px-3.5 py-2 text-xs sm:text-sm font-bold rounded-xl transition flex items-center gap-2 ${
              activeSubTab === '15m_reports'
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800 border border-transparent'
            }`}
          >
            <Award className="w-4 h-4 text-emerald-400" />
            <span>15M Win/Loss Reports</span>
            <span className="px-1.5 py-0.2 text-[10px] font-mono bg-emerald-500/20 border border-emerald-500/30 rounded-full text-emerald-300">
              {winLossReports.length}
            </span>
          </button>

          {/* Trade Journal Tab */}
          <button
            onClick={() => setActiveSubTab('journal')}
            className={`px-3.5 py-2 text-xs sm:text-sm font-bold rounded-xl transition flex items-center gap-2 ${
              activeSubTab === 'journal'
                ? 'bg-blue-500/20 text-blue-300 border border-blue-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800 border border-transparent'
            }`}
          >
            <Layers className="w-4 h-4 text-blue-400" />
            <span>Trade Journal</span>
            <span className="px-1.5 py-0.2 text-[10px] font-mono bg-blue-500/20 border border-blue-500/30 rounded-full text-blue-300">
              {trades.length}
            </span>
          </button>

          {/* Settlements Tab */}
          <button
            onClick={() => setActiveSubTab('settlements')}
            className={`px-3.5 py-2 text-xs sm:text-sm font-bold rounded-xl transition flex items-center gap-2 ${
              activeSubTab === 'settlements'
                ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800 border border-transparent'
            }`}
          >
            <CheckCircle2 className="w-4 h-4 text-purple-400" />
            <span>Settlements</span>
            <span className="px-1.5 py-0.2 text-[10px] font-mono bg-purple-500/20 border border-purple-500/30 rounded-full text-purple-300">
              {settlements.length}
            </span>
          </button>

          {/* AI Decisions Tab */}
          <button
            onClick={() => setActiveSubTab('ai')}
            className={`px-3.5 py-2 text-xs sm:text-sm font-bold rounded-xl transition flex items-center gap-2 ${
              activeSubTab === 'ai'
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800 border border-transparent'
            }`}
          >
            <Cpu className="w-4 h-4 text-amber-400" />
            <span>AI Decisions</span>
            <span className="px-1.5 py-0.2 text-[10px] font-mono bg-amber-500/20 border border-amber-500/30 rounded-full text-amber-300">
              {aiPredictions.length}
            </span>
          </button>

          {/* Forward Validation Tab */}
          <button
            onClick={() => setActiveSubTab('validation')}
            className={`px-3.5 py-2 text-xs sm:text-sm font-bold rounded-xl transition flex items-center gap-2 ${
              activeSubTab === 'validation'
                ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800 border border-transparent'
            }`}
          >
            <ShieldCheck className="w-4 h-4 text-indigo-400" />
            <span>100-Cycle Forward Validation</span>
          </button>
        </div>

        {/* Sub-Tab Action Controls (Export, Reset, Delete Selected) */}
        <div className="flex items-center gap-2">
          {/* Delete Selected Button */}
          {selectedIds.size > 0 && activeSubTab !== 'validation' && (
            <button
              onClick={() => handleDeleteBatch(activeSubTab)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold rounded-lg shadow-sm transition animate-in fade-in"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Delete Selected ({selectedIds.size})</span>
            </button>
          )}

          {/* Sub-Tab Dedicated CSV Export */}
          {activeSubTab === '15m_reports' && (
            <a
              href="/api/reports/win-loss/export.csv"
              download="kalshi_15m_win_loss_reports.csv"
              className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition"
            >
              <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400" />
              <span>CSV</span>
            </a>
          )}
          {activeSubTab === 'journal' && (
            <a
              href="/api/history/trades/export.csv"
              download="kalshi_trade_journal.csv"
              className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition"
            >
              <FileSpreadsheet className="w-3.5 h-3.5 text-blue-400" />
              <span>CSV</span>
            </a>
          )}
          {activeSubTab === 'settlements' && (
            <a
              href="/api/history/settlements/export.csv"
              download="kalshi_settlements.csv"
              className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition"
            >
              <FileSpreadsheet className="w-3.5 h-3.5 text-purple-400" />
              <span>CSV</span>
            </a>
          )}
          {activeSubTab === 'ai' && (
            <a
              href="/api/history/ai-predictions/export.csv"
              download="kalshi_ai_decisions.csv"
              className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition"
            >
              <FileSpreadsheet className="w-3.5 h-3.5 text-amber-400" />
              <span>CSV</span>
            </a>
          )}

          {/* Sub-Tab Dedicated JSON Export */}
          {activeSubTab === '15m_reports' && (
            <a
              href="/api/reports/win-loss/export.json"
              download="kalshi_15m_win_loss_reports.json"
              className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition"
            >
              <Download className="w-3.5 h-3.5 text-blue-400" />
              <span>JSON</span>
            </a>
          )}
          {activeSubTab === 'journal' && (
            <a
              href="/api/history/trades/export.json"
              download="kalshi_trade_journal.json"
              className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition"
            >
              <Download className="w-3.5 h-3.5 text-blue-400" />
              <span>JSON</span>
            </a>
          )}
          {activeSubTab === 'settlements' && (
            <a
              href="/api/history/settlements/export.json"
              download="kalshi_settlements.json"
              className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition"
            >
              <Download className="w-3.5 h-3.5 text-purple-400" />
              <span>JSON</span>
            </a>
          )}
          {activeSubTab === 'ai' && (
            <a
              href="/api/history/ai-predictions/export.json"
              download="kalshi_ai_decisions.json"
              className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white text-xs font-semibold rounded-lg transition"
            >
              <Download className="w-3.5 h-3.5 text-amber-400" />
              <span>JSON</span>
            </a>
          )}

          {/* Reset Current Tab */}
          <button
            onClick={() => {
              setResetTarget(activeSubTab === '15m_reports' ? '15m_reports' : activeSubTab === 'journal' ? 'trades' : activeSubTab === 'settlements' ? 'settlements' : activeSubTab === 'ai' ? 'ai' : 'selected');
              setIsResetModalOpen(true);
            }}
            className="flex items-center gap-1 px-3 py-1.5 bg-rose-950/30 hover:bg-rose-900/50 border border-rose-800/40 text-rose-300 hover:text-white text-xs font-semibold rounded-lg transition"
            title="Reset active table"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Reset View</span>
          </button>
        </div>
      </div>

      {/* --------------------------------------------------------------------------- */}
      {/* 7. Search & Filter Bar (for tabular views) */}
      {/* --------------------------------------------------------------------------- */}
      {activeSubTab !== 'validation' && (
        <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900/70 p-3 rounded-xl border border-slate-800 text-xs">
          <div className="flex items-center gap-2 flex-1 min-w-[200px] max-w-md">
            <Search className="w-4 h-4 text-slate-500" />
            <input
              type="text"
              placeholder={`Search ${activeSubTab === '15m_reports' ? '15M reports (ticker, cycle, ID)...' : 'ticker, ID...'}`}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 w-full"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Bot System Filter (for 15M reports) */}
            {activeSubTab === '15m_reports' && (
              <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
                <span className="text-[10px] text-slate-500 px-1 font-semibold uppercase">Bot:</span>
                {[
                  { id: 'all', label: 'All Bots' },
                  { id: 'macro_onnx', label: '🧠 Macro ONNX' },
                  { id: 'macro_trend_dominion', label: '📈 Macro Trend' },
                  { id: 'dominion_2_bot', label: '👑 Dominion 2' },
                  { id: '3_step_domination_bot', label: '⚡ Domination' },
                  { id: 'onnx_ml_bot', label: '🔬 ONNX ML' },
                  { id: 'live', label: '🔴 Live' },
                ].map((b) => (
                  <button
                    key={b.id}
                    onClick={() => setBotFilter(b.id as any)}
                    className={`px-2 py-0.5 rounded-md font-bold text-[10px] transition ${
                      botFilter === b.id ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    {b.label}
                  </button>
                ))}
              </div>
            )}

            {/* Side Filter */}
            <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
              <span className="text-[10px] text-slate-500 px-1 font-semibold uppercase">Side:</span>
              {(['all', 'yes', 'no'] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setSideFilter(s)}
                  className={`px-2 py-0.5 rounded-md font-bold uppercase text-[10px] transition ${
                    sideFilter === s ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>

            {/* Outcome Filter */}
            {(activeSubTab === '15m_reports' || activeSubTab === 'settlements') && (
              <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
                <span className="text-[10px] text-slate-500 px-1 font-semibold uppercase">Outcome:</span>
                {(['all', 'win', 'loss'] as const).map((o) => (
                  <button
                    key={o}
                    onClick={() => setOutcomeFilter(o)}
                    className={`px-2 py-0.5 rounded-md font-bold uppercase text-[10px] transition ${
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

      {/* --------------------------------------------------------------------------- */}
      {/* 8. Active Sub-Tab Content */}
      {/* --------------------------------------------------------------------------- */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        {/* SUBTAB 1: 15-Minute Event Win/Loss Reports */}
        {activeSubTab === '15m_reports' && (
          <WinLoss15mSubtab
            domStats15m={domStats15m}
            onnxStats15m={onnxStats15m}
            combinedStats15m={combinedStats15m}
            liveStats15m={liveStats15m}
            paginatedWinLoss={paginatedWinLoss}
            selectedIds={selectedIds}
            toggleSelectId={toggleSelectId}
            toggleSelectAllCurrentPage={toggleSelectAllCurrentPage}
            handleDeleteSingle={handleDeleteSingle}
            page={page}
            setPage={setPage}
            isMacroOnnxBot={isMacroOnnxBot}
            isMacroBot={isMacroBot}
            isDom2Bot={isDom2Bot}
            isDomBot={isDomBot}
            isOnnxBot={isOnnxBot}
          />
        )}

        {/* SUBTAB 2: Trade Execution Journal */}
        {activeSubTab === 'journal' && (
          <TradeJournalSubtab
            paginatedTrades={paginatedTrades}
            selectedIds={selectedIds}
            toggleSelectId={toggleSelectId}
            toggleSelectAllCurrentPage={toggleSelectAllCurrentPage}
            handleDeleteSingle={handleDeleteSingle}
            page={page}
            setPage={setPage}
          />
        )}

        {/* SUBTAB 3: Contract Settlements Ledger */}
        {activeSubTab === 'settlements' && (
          <SettlementsSubtab
            paginatedSettlements={paginatedSettlements}
            selectedIds={selectedIds}
            toggleSelectId={toggleSelectId}
            toggleSelectAllCurrentPage={toggleSelectAllCurrentPage}
            handleDeleteSingle={handleDeleteSingle}
            page={page}
            setPage={setPage}
          />
        )}

        {/* SUBTAB 4: AI & Quantitative Signal Audit */}
        {activeSubTab === 'ai' && (
          <AIPredictionsSubtab
            paginatedAi={paginatedAi}
            selectedIds={selectedIds}
            toggleSelectId={toggleSelectId}
            toggleSelectAllCurrentPage={toggleSelectAllCurrentPage}
            handleDeleteSingle={handleDeleteSingle}
            page={page}
            setPage={setPage}
          />
        )}

        {/* SUBTAB 5: Forward Validation & 5-Gate Institutional Audit */}
        {activeSubTab === 'validation' && (
          <ValidationGateSubtab validationStatus={validationStatus} />
        )}
      </div>

      {/* --------------------------------------------------------------------------- */}
      {/* 9. Reset Confirmation Modal */}
      {/* --------------------------------------------------------------------------- */}
      {isResetModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-rose-500/20 text-rose-400 rounded-xl border border-rose-500/30">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Reset Historical Reports & Ledger</h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Clear historical records and recalculate efficiency metrics.
                </p>
              </div>
            </div>

            <div className="space-y-2 bg-slate-950/80 p-3.5 rounded-xl border border-slate-800 text-xs">
              <div className="text-slate-300 font-semibold mb-1">Select Target Scope to Reset:</div>

              <label className="flex items-center gap-2.5 cursor-pointer p-2 rounded-lg hover:bg-slate-800/50">
                <input
                  type="radio"
                  name="resetTarget"
                  checked={resetTarget === '15m_reports'}
                  onChange={() => setResetTarget('15m_reports')}
                  className="text-emerald-500 focus:ring-emerald-500"
                />
                <span className="text-slate-200">
                  Reset <strong className="text-emerald-400">15-Minute Event Reports</strong> only
                </span>
              </label>

              <label className="flex items-center gap-2.5 cursor-pointer p-2 rounded-lg hover:bg-slate-800/50">
                <input
                  type="radio"
                  name="resetTarget"
                  checked={resetTarget === 'trades'}
                  onChange={() => setResetTarget('trades')}
                  className="text-blue-500 focus:ring-blue-500"
                />
                <span className="text-slate-200">
                  Reset <strong className="text-blue-400">Trade Journal Executions</strong> only
                </span>
              </label>

              <label className="flex items-center gap-2.5 cursor-pointer p-2 rounded-lg hover:bg-slate-800/50">
                <input
                  type="radio"
                  name="resetTarget"
                  checked={resetTarget === 'settlements'}
                  onChange={() => setResetTarget('settlements')}
                  className="text-purple-500 focus:ring-purple-500"
                />
                <span className="text-slate-200">
                  Reset <strong className="text-purple-400">Settlements History</strong> only
                </span>
              </label>

              <label className="flex items-center gap-2.5 cursor-pointer p-2 rounded-lg hover:bg-slate-800/50">
                <input
                  type="radio"
                  name="resetTarget"
                  checked={resetTarget === 'selected'}
                  onChange={() => setResetTarget('selected')}
                  className="text-amber-500 focus:ring-amber-500"
                />
                <span className="text-slate-200">
                  Reset <strong className="text-amber-400">{selectedSystem === 'all' ? 'All Systems' : selectedSystem}</strong> only
                </span>
              </label>

              <label className="flex items-center gap-2.5 cursor-pointer p-2 rounded-lg hover:bg-slate-800/50">
                <input
                  type="radio"
                  name="resetTarget"
                  checked={resetTarget === 'all'}
                  onChange={() => setResetTarget('all')}
                  className="text-rose-500 focus:ring-rose-500"
                />
                <span className="text-slate-200">
                  Reset <strong className="text-rose-400">Complete Ledger Globally</strong> (Factory Wipe)
                </span>
              </label>
            </div>

            {resetMessage && (
              <div className="p-2.5 rounded-xl bg-slate-800 text-xs text-emerald-400 text-center font-mono border border-slate-700">
                {resetMessage}
              </div>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setIsResetModalOpen(false)}
                disabled={resetting}
                className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-xl transition"
              >
                Cancel
              </button>
              <button
                onClick={handleExecuteReset}
                disabled={resetting}
                className="px-4 py-2 text-xs font-semibold text-white bg-rose-600 hover:bg-rose-500 rounded-xl transition flex items-center gap-1.5 shadow-md disabled:opacity-50"
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

export default HistoricalAnalyticsTab;
