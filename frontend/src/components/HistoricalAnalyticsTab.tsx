import React, { useEffect, useState } from 'react';
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
  SystemComparisonItem,
} from './analytics/AnalyticsTypes';
import { WinLoss15mSubtab } from './analytics/WinLoss15mSubtab';
import { TradeJournalSubtab } from './analytics/TradeJournalSubtab';
import { SettlementsSubtab } from './analytics/SettlementsSubtab';
import { AIPredictionsSubtab } from './analytics/AIPredictionsSubtab';
import { ValidationGateSubtab } from './analytics/ValidationGateSubtab';
import { CanvasEquityCurve } from './analytics/CanvasEquityCurve';
import { ResetConfirmationModal } from './analytics/ResetConfirmationModal';
import { MultiBotEfficiencyTable } from './analytics/MultiBotEfficiencyTable';
import { AnalyticsKpiCards } from './analytics/AnalyticsKpiCards';
import { AnalyticsFilterBar } from './analytics/AnalyticsFilterBar';
import { AnalyticsHeaderToolbar } from './analytics/AnalyticsHeaderToolbar';
import { AnalyticsSubTabSelector } from './analytics/AnalyticsSubTabSelector';
import { BotSystemFilterSelector } from './analytics/BotSystemFilterSelector';

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
      {/* 1. Header & Global Toolbar */}
      <AnalyticsHeaderToolbar
        handleRunBotTest={handleRunBotTest}
        isTestingBot={isTestingBot}
        testBotType={testBotType}
        setTestBotType={setTestBotType}
        fetchAllData={fetchAllData}
        loading={loading}
        isExportMenuOpen={isExportMenuOpen}
        setIsExportMenuOpen={setIsExportMenuOpen}
        setIsResetModalOpen={setIsResetModalOpen}
        testResultMsg={testResultMsg}
        setTestResultMsg={setTestResultMsg}
      />

      {/* 2. OVERALL MULTI-SYSTEM EFFICIENCY SUMMARY MATRIX */}
      <MultiBotEfficiencyTable
        systemComparison={systemComparison}
        selectedSystem={selectedSystem}
        setSelectedSystem={setSelectedSystem}
      />

      {/* 3. Bot & System Isolated Drilldown Selector & Multi-Asset Filter */}
      <BotSystemFilterSelector
        selectedSystem={selectedSystem}
        setSelectedSystem={setSelectedSystem}
        assetFilter={assetFilter}
        setAssetFilter={setAssetFilter}
        timeframeFilter={timeframeFilter}
        setTimeframeFilter={setTimeframeFilter}
      />

      {/* 4. KPI Cards Grid */}
      <AnalyticsKpiCards metrics={metrics} />

      {/* 5. HiDPI Canvas Equity Curve Section */}
      <CanvasEquityCurve equityCurve={equityCurve} selectedSystem={selectedSystem} />

      {/* 6. Consolidated Sub-Tabs Selector & Toolbar */}
      <AnalyticsSubTabSelector
        activeSubTab={activeSubTab}
        setActiveSubTab={setActiveSubTab}
        winLossReports={winLossReports}
        trades={trades}
        settlements={settlements}
        aiPredictions={aiPredictions}
        selectedIds={selectedIds}
        handleDeleteBatch={handleDeleteBatch}
        setResetTarget={setResetTarget}
        setIsResetModalOpen={setIsResetModalOpen}
      />

      {/* 7. Search & Filter Bar */}
      <AnalyticsFilterBar
        activeSubTab={activeSubTab}
        searchTerm={searchTerm}
        setSearchTerm={setSearchTerm}
        botFilter={botFilter}
        setBotFilter={setBotFilter}
        sideFilter={sideFilter}
        setSideFilter={setSideFilter}
        outcomeFilter={outcomeFilter}
        setOutcomeFilter={setOutcomeFilter}
      />

      {/* 8. Active Sub-Tab Content */}
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

      {/* 9. Reset Confirmation Modal */}
      <ResetConfirmationModal
        isOpen={isResetModalOpen}
        onClose={() => setIsResetModalOpen(false)}
        resetTarget={resetTarget}
        setResetTarget={setResetTarget}
        selectedSystem={selectedSystem}
        resetting={resetting}
        resetMessage={resetMessage}
        onConfirmReset={handleExecuteReset}
      />
    </div>
  );
};

export default HistoricalAnalyticsTab;
