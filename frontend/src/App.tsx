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
import { PortfolioDrawer } from './components/PortfolioDrawer';
import { LiveTradeModal } from './components/LiveTradeModal';
import { HistoricalAnalyticsTab } from './components/HistoricalAnalyticsTab';
import { soundFX } from './utils/audioFX';

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
  } = useKalshiWebSocket();

  const [mainView, setMainView] = useState<'trading' | 'analytics'>('trading');
  const [activeTab, setActiveTab] = useState<'trade_up' | 'trade_down' | 'graph' | 'orderbook' | 'ai'>('orderbook');
  const [liveModal, setLiveModal] = useState<{
    isOpen: boolean;
    ticker: string;
    side: 'yes' | 'no';
    count: number;
    priceDollars: number;
    orderType: 'market' | 'limit';
    action: 'buy' | 'sell';
  }>({
    isOpen: false,
    ticker: '',
    side: 'yes',
    count: 25,
    priceDollars: 0.50,
    orderType: 'limit',
    action: 'buy',
  });

  // Track settlements to trigger win/loss audio chimes automatically
  const prevSettlementsCount = useRef<number>(data.portfolio.settlements.length);
  useEffect(() => {
    if (data.portfolio.settlements.length > prevSettlementsCount.current) {
      const latest = data.portfolio.settlements[0];
      if (latest) {
        if (latest.outcome === 'win') {
          soundFX.playWinSound();
        } else {
          soundFX.playLossSound();
        }
      }
    }
    prevSettlementsCount.current = data.portfolio.settlements.length;
  }, [data.portfolio.settlements]);

  const handlePlaceOrderIntercept = async (
    side: 'yes' | 'no',
    size: number,
    limitPrice?: number,
    orderType: 'market' | 'limit' = 'limit',
    restingOnly: boolean = false
  ) => {
    if (data.settings.mode === 'live') {
      const estPrice = limitPrice || (side === 'yes' ? data.market.best_yes_ask : data.market.best_no_ask) || 0.50;
      setLiveModal({
        isOpen: true,
        ticker: data.market.ticker,
        side,
        count: size,
        priceDollars: estPrice,
        orderType,
        action: 'buy',
      });
      return { success: true, status: 'confirming' };
    }
    return sendOrder(side, size, limitPrice, orderType, restingOnly);
  };

  const handleConfirmLiveTrade = async (dryRun: boolean) => {
    try {
      const res = await fetch('/api/kalshi/orders/live', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: liveModal.ticker,
          side: liveModal.side,
          count: liveModal.count,
          action: liveModal.action,
          order_type: liveModal.orderType,
          limit_price_dollars: liveModal.priceDollars,
          dry_run: dryRun,
          is_demo: true,
        }),
      });
      const resData = await res.json();
      if (resData.success) {
        soundFX.playOrderFillSound();
      } else {
        soundFX.playLossSound();
      }
    } catch (e) {
      soundFX.playLossSound();
    }
  };

  const handleQuickTrade = async (side: 'yes' | 'no') => {
    soundFX.playClickSound();
    const res = await handlePlaceOrderIntercept(side, 25, undefined, 'market');
    if (res?.success && data.settings.mode !== 'live') {
      soundFX.playOrderFillSound();
    }
  };

  const handleSelectPrice = (priceCents: number) => {
    soundFX.playClickSound();
    console.log('Selected price from ladder:', priceCents);
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
        onToggleAI={toggleAIAutoTrade}
        onToggleMode={toggleFeedMode}
        onSelectTimeframe={changeTimeframe}
        onReset={() => {
          soundFX.playClickSound();
          resetPortfolio(10000);
        }}
      />

      {/* View Switcher Bar */}
      <div className="max-w-[1600px] w-full mx-auto px-3 sm:px-5 pt-3 flex items-center gap-3">
        <button
          onClick={() => {
            soundFX.playClickSound();
            setMainView('trading');
          }}
          className={`px-4 py-2 rounded-lg text-sm font-semibold transition flex items-center gap-2 ${
            mainView === 'trading'
              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-lg shadow-emerald-500/10'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent'
          }`}
        >
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          ⚡ Live CLOB Trading Terminal
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
              {/* Price Hero Section */}
              <PriceHero market={data.market} />

              {/* Interactive Target Strike Chart */}
              <TargetChart
                market={data.market}
                chart={data.chart}
                tradeTape={data.trade_tape}
              />

              {/* Market Chance Banner & Tab Selector */}
              <ChanceBanner
                market={data.market}
                activeTab={activeTab}
                onSelectTab={(tab) => {
                  soundFX.playClickSound();
                  setActiveTab(tab);
                }}
                onQuickTrade={handleQuickTrade}
              />

              {/* Tab Views */}
              {activeTab === 'orderbook' || activeTab === 'trade_up' || activeTab === 'trade_down' ? (
                <OrderBookLadder
                  ladder={data.orderbook_ladder}
                  onSelectPrice={handleSelectPrice}
                />
              ) : activeTab === 'ai' ? (
                <div className="p-4">
                  <AIMicrostructureCard signals={data.ai_signals} />
                </div>
              ) : (
                <div className="p-8 text-center text-xs text-[#8b949e]">
                  Dynamic full chart history active in the hero view above.
                </div>
              )}
            </div>

            {/* Portfolio & Active Positions Drawer */}
            <PortfolioDrawer
              portfolio={data.portfolio}
              onClosePosition={closePosition}
              onCancelOrder={cancelOrder}
              onResetCircuitBreaker={resetCircuitBreaker}
            />
          </div>

          {/* Right Column: Order Entry Panel & AI Brain Card (5 cols) */}
          <div className="lg:col-span-5 flex flex-col gap-4">
            {/* Right Execution Widget */}
            <OrderEntryPanel
              market={data.market}
              portfolio={data.portfolio}
              onPlaceOrder={handlePlaceOrderIntercept}
            />

            {/* AI Microstructure & ONNX Inferences */}
            <AIMicrostructureCard signals={data.ai_signals} />
          </div>
        </main>
      )}

      {/* Live Order Safety Confirmation Modal */}
      <LiveTradeModal
        isOpen={liveModal.isOpen}
        ticker={liveModal.ticker}
        side={liveModal.side}
        count={liveModal.count}
        priceDollars={liveModal.priceDollars}
        orderType={liveModal.orderType}
        action={liveModal.action}
        onClose={() => setLiveModal({ ...liveModal, isOpen: false })}
        onConfirm={handleConfirmLiveTrade}
      />
    </div>
  );
}

export default App;

