/**
 * @file App.tsx
 * @description Main Application component uniting Header, Price Hero, Target Strike Chart,
 * L2 CLOB Depth Ladder, 1-Click Execution Panel, ONNX Microstructure AI Card, and Audio FX.
 */

import React, { useState, useEffect, useRef } from 'react';
import { useKalshiWebSocket } from './hooks/useKalshiWebSocket';
import { Header } from './components/Header';
import { PriceHero } from './components/PriceHero';
import { TargetChart } from './components/TargetChart';
import { ChanceBanner } from './components/ChanceBanner';
import { OrderBookLadder } from './components/OrderBookLadder';
import { OrderEntryPanel } from './components/OrderEntryPanel';
import { AIMicrostructureCard } from './components/AIMicrostructureCard';
import { LiveGuardrailsCard } from './components/LiveGuardrailsCard';
import { PortfolioDrawer } from './components/PortfolioDrawer';
import { HistoricalAnalyticsTab } from './components/HistoricalAnalyticsTab';
import { TradeTape } from './components/TradeTape';
import { GuardianStationModal, GuardianTab } from './components/GuardianStationModal';
import { soundFX } from './utils/audioFX';
import { AlertOctagon, Play } from 'lucide-react';

export function App() {
  const {
    data,
    isConnected,
    sendOrder,
    cancelOrder,
    closePosition,
    toggleAIAutoTrade,
    toggleFeedMode,
    changeTimeframe,
    resetPortfolio,
    resetCircuitBreaker,
    triggerKillSwitch,
    selectStrategyBot,
    testBotTrade,
    updateDominationDiscountPrice,
    selectAsset,
  } = useKalshiWebSocket();

  const [mainView, setMainView] = useState<'trading' | 'analytics'>('trading');
  const [tradingMode, setTradingMode] = useState<'paper' | 'live'>(
    data.settings?.mode === 'live' ? 'live' : 'paper'
  );
  const [activeTab, setActiveTab] = useState<'orderbook' | 'tape' | 'positions'>('orderbook');
  const [rightDeckTab, setRightDeckTab] = useState<'brain' | 'guardrails'>('brain');
  const [guardianStationTab, setGuardianStationTab] = useState<GuardianTab | null>(null);
  const [isLoadingAudit, setIsLoadingAudit] = useState<boolean>(false);

  // Synchronize trading mode when backend reports live mode
  useEffect(() => {
    if (data.settings?.mode) {
      setTradingMode(data.settings.mode === 'live' ? 'live' : 'paper');
    }
  }, [data.settings?.mode]);

  const isLive = tradingMode === 'live';
  const isKillSwitchTripped = data.portfolio?.circuit_breaker_tripped ?? false;

  // Track settlements to trigger win/loss audio chimes automatically
  const prevSettlementsCount = useRef<number>((data.portfolio?.settlements || []).length);
  useEffect(() => {
    const count = (data.portfolio?.settlements || []).length;
    if (count > prevSettlementsCount.current) {
      const latest = (data.portfolio?.settlements || [])[0];
      if (latest) {
        if (latest.outcome === 'win') {
          soundFX.playWinSound();
        } else {
          soundFX.playLossSound();
        }
      }
    }
    prevSettlementsCount.current = count;
  }, [data.portfolio?.settlements]);

  const handlePlaceOrderIntercept = async (
    side: 'yes' | 'no',
    size: number,
    limitPrice?: number,
    orderType: 'market' | 'limit' = 'limit',
    restingOnly: boolean = false
  ) => {
    const res = await sendOrder(side, size, limitPrice, orderType, restingOnly, tradingMode);
    if (res?.success) {
      soundFX.playOrderFillSound();
    } else {
      soundFX.playLossSound();
    }
    return res;
  };

  const handleQuickTrade = async (side: 'yes' | 'no') => {
    soundFX.playClickSound();
    const res = await sendOrder(side, isLive ? 1 : 10, undefined, 'market', false, tradingMode);
    if (res?.success) {
      soundFX.playOrderFillSound();
    } else {
      soundFX.playLossSound();
    }
  };

  const handleSelectPrice = (priceCents: number) => {
    soundFX.playClickSound();
    console.log('Selected price from ladder:', priceCents);
  };

  const handleTestBot = async () => {
    soundFX.playClickSound();
    const res = await testBotTrade();
    if (res?.success) {
      if (res?.report?.outcome === 'win') {
        soundFX.playWinSound();
      } else {
        soundFX.playOrderFillSound();
      }
    }
    return res;
  };

  const handleKillSwitch = async () => {
    soundFX.playLossSound();
    await triggerKillSwitch();
  };

  const handleResumeTrading = async () => {
    soundFX.playClickSound();
    await resetCircuitBreaker();
  };

  const handleRunAuditNow = async () => {
    setIsLoadingAudit(true);
    try {
      const res = await fetch('http://localhost:8000/api/integrity/audit-now', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (res.ok) {
        soundFX.playClickSound();
      }
    } catch (err) {
      console.error('Audit trigger error:', err);
    } finally {
      setIsLoadingAudit(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0b0e14] text-[#f3f4f6] flex flex-col">
      {/* Top Header */}
      <Header
        market={data.market}
        isConnected={isConnected}
        aiAutoTrade={data.settings.ai_auto_trade}
        timeframe={data.settings.timeframe}
        mode={data.settings.mode}
        tradingMode={tradingMode}
        activeStrategyBot={data.settings?.active_strategy_bot || '3_step_domination_bot'}
        onSelectStrategy={selectStrategyBot}
        onSelectAsset={selectAsset}
        mainView={mainView}
        onSelectMainView={(v) => setMainView(v)}
        isKillSwitchTripped={isKillSwitchTripped}
        livePortfolio={data.live_portfolio}
        memoryProfile={data.memory_profile}
        reportsCount={Array.isArray(data.win_loss_reports) ? data.win_loss_reports.length : 0}
        integrityStatus={data.integrity_status}
        complianceStatus={data.compliance_status}
        botAuditStatus={data.bot_audit_status}
        systemResources={data.system_resources}
        onToggleAI={toggleAIAutoTrade}
        onToggleMode={toggleFeedMode}
        onSelectTradingMode={(m) => setTradingMode(m)}
        onSelectTimeframe={changeTimeframe}
        onKillSwitch={handleKillSwitch}
        onResumeTrading={handleResumeTrading}
        onReset={() => {
          soundFX.playClickSound();
          resetPortfolio(15);
        }}
        onOpenReports={() => {
          soundFX.playClickSound();
          setGuardianStationTab('reports');
        }}
        onOpenIntegrity={() => {
          soundFX.playClickSound();
          setGuardianStationTab('integrity');
        }}
        onOpenCompliance={() => {
          soundFX.playClickSound();
          setGuardianStationTab('compliance');
        }}
        onOpenSystemResources={() => {
          soundFX.playClickSound();
          setGuardianStationTab('resources');
        }}
        onTestBot={!isLive ? handleTestBot : undefined}
      />

      {/* Live Trading Top Banner when in Live Mode */}
      {isLive && (
        <div className="bg-rose-950/30 border-b border-rose-500/30 px-4 py-2">
          <div className="max-w-[1600px] w-full mx-auto flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2.5">
              <span className="flex h-2.5 w-2.5 rounded-full bg-rose-500 animate-ping" />
              <span className="font-extrabold uppercase tracking-wider text-rose-300">
                🔴 LIVE REAL-MONEY TRADING ACTIVE
              </span>
              <span className="text-[#8b949e] hidden sm:inline">|</span>
              <span className="text-[#8b949e] hidden sm:inline font-mono">
                Environment: {data.live_portfolio?.environment?.toUpperCase() || 'LIVE PROD'}
              </span>
              <span className="text-[#8b949e] hidden md:inline font-mono">
                | Cash: ${(Number(data.live_portfolio?.balance_dollars ?? 0.30) || 0.30).toFixed(2)}
              </span>
              <span className="text-[#8b949e] hidden md:inline font-mono">
                | Single-Trade Cap: 1 Contract / Asset ($1.00 Max Risk)
              </span>
            </div>

            <div className="flex items-center gap-2">
              {isKillSwitchTripped ? (
                <button
                  onClick={handleResumeTrading}
                  className="flex items-center gap-1.5 px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded-lg transition-all text-[11px]"
                >
                  <Play className="h-3 w-3 fill-current" />
                  <span>Resume Trading</span>
                </button>
              ) : (
                <button
                  onClick={handleKillSwitch}
                  className="flex items-center gap-1.5 px-3 py-1 bg-red-600 hover:bg-red-500 text-white font-bold rounded-lg transition-all text-[11px] animate-pulse"
                >
                  <AlertOctagon className="h-3 w-3 fill-current" />
                  <span>Stop / Kill Switch</span>
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Small Notification if Live Balance is Depleted / All Bets Frozen */}
      {isLive && (Number(data.live_portfolio?.balance_dollars ?? 0.0) || 0.0) <= 0.05 && (
        <div className="bg-amber-500/15 border-b border-amber-500/30 px-4 py-2 animate-in fade-in">
          <div className="max-w-[1600px] w-full mx-auto flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2 text-amber-300">
              <span className="text-sm">⚠️</span>
              <span className="font-bold">Live Balance Depleted (${(Number(data.live_portfolio?.balance_dollars ?? 0.0) || 0.0).toFixed(2)}):</span>
              <span className="text-amber-200/90">All live bets are frozen. Please load assets into your Kalshi account to resume.</span>
            </div>
            <a
              href="https://kalshi.com"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 px-3 py-1 bg-amber-400 hover:bg-amber-300 text-black text-[11px] font-extrabold rounded-lg transition-colors shadow-sm"
            >
              <span>Deposit on Kalshi</span>
              <span className="text-xs">↗</span>
            </a>
          </div>
        </div>
      )}

      {/* View Switcher Bar */}
      <div className="max-w-[1600px] w-full mx-auto px-3 sm:px-5 pt-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              soundFX.playClickSound();
              setMainView('trading');
            }}
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition flex items-center gap-2 ${
              mainView === 'trading'
                ? isLive
                  ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40 shadow-lg shadow-rose-500/10'
                  : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-lg shadow-emerald-500/10'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
            }`}
          >
            <span className={`w-2 h-2 rounded-full animate-pulse ${isLive ? 'bg-rose-400' : 'bg-emerald-400'}`} />
            {isLive ? '🔴 Live CLOB Execution Terminal' : '⚡ Paper CLOB Trading Terminal'}
          </button>

          <button
            onClick={() => {
              soundFX.playClickSound();
              setMainView('analytics');
            }}
            className={`px-4 py-2 rounded-lg text-sm font-semibold transition flex items-center gap-2 ${
              mainView === 'analytics'
                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40 shadow-lg shadow-blue-500/10'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
            }`}
          >
            📊 Performance Analytics & Historical Journal
          </button>
        </div>

        {/* Quick 15M Win/Loss Reports button on banner */}
        <button
          onClick={() => {
            soundFX.playClickSound();
            setGuardianStationTab('reports');
          }}
          className={`hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-xl transition-all shadow-sm font-bold text-xs ${
            isLive
              ? 'bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/40 text-rose-400 hover:text-rose-300 shadow-rose-500/10'
              : 'bg-[#161b22] hover:bg-[#21262d] border border-emerald-500/30 text-emerald-400 hover:text-emerald-300'
          }`}
        >
          {isLive ? (
            <>
              <span className="flex h-2 w-2 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
              </span>
              <span>🔴 Live Event Reports</span>
              {Array.isArray(data.win_loss_reports) && (
                <span className="px-1.5 py-0.2 text-[10px] font-mono bg-rose-500/20 border border-rose-500/40 rounded-full text-rose-300">
                  {data.win_loss_reports.filter((r) => r.execution_mode === 'live').length}
                </span>
              )}
            </>
          ) : (
            <>
              <span>🏆 15M Event Win/Loss Reports</span>
              {Array.isArray(data.win_loss_reports) && data.win_loss_reports.length > 0 && (
                <span className="px-1.5 py-0.2 text-[10px] font-mono bg-emerald-500/20 border border-emerald-500/40 rounded-full">
                  {data.win_loss_reports.length}
                </span>
              )}
            </>
          )}
        </button>
      </div>

      {mainView === 'analytics' ? (
        <div className="flex-1 max-w-[1600px] w-full mx-auto p-3 sm:p-5">
          <HistoricalAnalyticsTab />
        </div>
      ) : (
        /* Main Trading Arena Layout */
        <main className="flex-1 max-w-[1600px] w-full mx-auto p-3 sm:p-5 grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Left Column: Price Hero, Target Chart, Tabs & L2 Book (7 cols) */}
          <div className="lg:col-span-7 flex flex-col gap-4">
            <div className="bg-[#111620] border border-[#21262d] rounded-2xl overflow-hidden shadow-xl">
              {/* Compact Price Hero Section */}
              <PriceHero market={data.market} />

              {/* Interactive Target Strike Chart (60 FPS Conveyor) */}
              <TargetChart
                market={data.market}
                chart={data.chart}
                tradeTape={data.trade_tape}
                winLossReports={data.win_loss_reports}
                onSelectPrice={handleSelectPrice}
                onOpenReports={() => {
                  soundFX.playClickSound();
                  setGuardianStationTab('reports');
                }}
              />

              {/* Market Chance Banner & Tab Selector */}
              <ChanceBanner
                market={data.market}
                activeTab={activeTab as any}
                tradingMode={tradingMode}
                onSelectTab={(tab) => {
                  soundFX.playClickSound();
                  setActiveTab(tab as any);
                }}
                onQuickTrade={handleQuickTrade}
              />

              {/* Lower Deck Tab Views */}
              {activeTab === 'orderbook' ? (
                <OrderBookLadder
                  ladder={data.orderbook_ladder}
                  onSelectPrice={handleSelectPrice}
                />
              ) : activeTab === 'tape' ? (
                <TradeTape tradeTape={data.trade_tape} />
              ) : (
                <div className="p-2 sm:p-4">
                  <PortfolioDrawer
                    portfolio={data.portfolio}
                    livePortfolio={data.live_portfolio}
                    tradingMode={tradingMode}
                    onClosePosition={closePosition}
                    onCancelOrder={cancelOrder}
                    onResetCircuitBreaker={resetCircuitBreaker}
                  />
                </div>
              )}
            </div>

            {/* Persistent Portfolio Ledger when viewing CLOB or Tape */}
            {activeTab !== 'positions' && (
              <PortfolioDrawer
                portfolio={data.portfolio}
                livePortfolio={data.live_portfolio}
                tradingMode={tradingMode}
                onClosePosition={closePosition}
                onCancelOrder={cancelOrder}
                onResetCircuitBreaker={resetCircuitBreaker}
              />
            )}
          </div>

          {/* Right Column: Order Entry Panel & Intelligence Deck (5 cols) */}
          <div className="lg:col-span-5 flex flex-col gap-4">
            {/* 1-Click Execution Widget (Micro-Sizing Cap, Limit Sniper) */}
            <OrderEntryPanel
              market={data.market}
              portfolio={data.portfolio}
              livePortfolio={data.live_portfolio}
              tradingMode={tradingMode}
              onPlaceOrder={handlePlaceOrderIntercept}
            />

            {/* Right Side Intelligence Deck Switcher */}
            <div className="flex items-center bg-[#161b22] p-1 rounded-xl border border-[#21262d] text-xs font-bold shadow-md">
              <button
                onClick={() => {
                  soundFX.playClickSound();
                  setRightDeckTab('brain');
                }}
                className={`flex-1 py-1.5 px-3 rounded-lg transition-all flex items-center justify-center gap-2 ${
                  rightDeckTab === 'brain'
                    ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40 shadow-sm'
                    : 'text-[#8b949e] hover:text-white border border-transparent'
                }`}
              >
                <span>🧠 3-Step Dominion Brain</span>
              </button>
              <button
                onClick={() => {
                  soundFX.playClickSound();
                  setRightDeckTab('guardrails');
                }}
                className={`flex-1 py-1.5 px-3 rounded-lg transition-all flex items-center justify-center gap-2 ${
                  rightDeckTab === 'guardrails'
                    ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40 shadow-sm'
                    : 'text-[#8b949e] hover:text-white border border-transparent'
                }`}
              >
                <span>🛡️ Live Risk & Guardrails</span>
              </button>
            </div>

            {/* Right Intelligence Deck Body */}
            {rightDeckTab === 'brain' ? (
              <AIMicrostructureCard 
                signals={data.ai_signals} 
                activeAsset={data.market.active_asset}
                onSelectStrategy={selectStrategyBot}
                onTestBot={!isLive ? handleTestBot : undefined}
                onOpenReports={() => {
                  soundFX.playClickSound();
                  setGuardianStationTab('reports');
                }}
                dominationDiscountPrice={data.settings?.domination_discount_price ?? data.ai_signals?.discount_limit_price ?? 0.48}
                onUpdateDiscountPrice={updateDominationDiscountPrice}
              />
            ) : (
              <LiveGuardrailsCard
                livePortfolio={data.live_portfolio}
                integrityStatus={data.integrity_status}
                complianceStatus={data.compliance_status}
                isKillSwitchTripped={isKillSwitchTripped}
                onKillSwitch={handleKillSwitch}
                onResumeTrading={handleResumeTrading}
              />
            )}
          </div>
        </main>
      )}

      {/* Consolidated Terminal Guardian Station Modal */}
      <GuardianStationModal
        isOpen={guardianStationTab !== null}
        onClose={() => setGuardianStationTab(null)}
        activeTab={guardianStationTab || 'reports'}
        onSelectTab={(tab) => setGuardianStationTab(tab)}
        reports={data.win_loss_reports}
        onTestBot={!isLive ? handleTestBot : undefined}
        isLiveMode={isLive}
        integrityStatus={data.integrity_status}
        onRunAuditNow={handleRunAuditNow}
        isLoadingAudit={isLoadingAudit}
        complianceStatus={data.compliance_status}
        systemResources={data.system_resources}
      />
    </div>
  );
}

export default App;



