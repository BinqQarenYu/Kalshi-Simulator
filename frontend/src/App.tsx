/**
 * @file App.tsx
 * @description Main Application component uniting the Two-Tier Architecture:
 * 1. The Factory / Parent Hub (Lab, Benchmarking Matrix, Journal, Analytics, Settings)
 * 2. The Standalone Baby Bot Console (distraction-free execution on 5M and 15M cycles)
 */

import React, { useState, useEffect, useRef } from 'react';
import { useKalshiWebSocket } from './hooks/useKalshiWebSocket';
import { ParentHub } from './components/ParentHub';
import { BabyBotConsole } from './components/BabyBotConsole';
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
    resyncMemory,
    resetCircuitBreaker,
    triggerKillSwitch,
    selectStrategyBot,
    testBotTrade,
    updateDominationDiscountPrice,
    selectAsset,
  } = useKalshiWebSocket();

  const [tradingMode, setTradingMode] = useState<'paper' | 'live'>(
    data.settings?.mode === 'live' ? 'live' : 'paper'
  );
  const [isPoppedOutBabyBot, setIsPoppedOutBabyBot] = useState(false);
  const [isLoadingAudit, setIsLoadingAudit] = useState<boolean>(false);

  // Synchronize trading mode when backend reports live mode
  useEffect(() => {
    if (data.settings?.mode) {
      setTradingMode(data.settings.mode === 'live' ? 'live' : 'paper');
    }
  }, [data.settings?.mode]);

  const isLive = tradingMode === 'live';

  // Detect if current window is running as standalone Baby Bot pop-out
  const isStandaloneBabyBot =
    typeof window !== 'undefined' &&
    (window.location.search.includes('view=baby-bot') || window.name === 'BabyBot');

  // Support URL bot parameter or fallback to server active strategy
  const urlBotParam = typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('bot') : null;
  const [standaloneBotId, setStandaloneBotId] = useState<string>(
    urlBotParam || data.settings?.active_strategy_bot || '3_step_domination_bot'
  );

  useEffect(() => {
    if (data.settings?.active_strategy_bot && !urlBotParam) {
      setStandaloneBotId(data.settings.active_strategy_bot);
    }
  }, [data.settings?.active_strategy_bot, urlBotParam]);

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

  const handleTogglePopOutBabyBot = (botId?: string) => {
    if (!isPoppedOutBabyBot) {
      const queryParam = botId ? `&bot=${encodeURIComponent(botId)}` : '';
      const popout = window.open(
        `/?view=baby-bot${queryParam}`,
        'BabyBot',
        'width=480,height=760,menubar=no,toolbar=no,location=no,status=no'
      );
      if (popout) {
        setIsPoppedOutBabyBot(true);
        popout.onbeforeunload = () => setIsPoppedOutBabyBot(false);
      }
    } else {
      setIsPoppedOutBabyBot(false);
    }
  };

  // Compute consecutive losses from verified settlements
  const consecutiveLosses = (data.portfolio?.settlements || [])
    .slice(0, 3)
    .filter((s) => s.outcome === 'loss').length;

  // 1. STANDALONE BABY BOT CONSOLE (Frameless Pop-Out View)
  if (isStandaloneBabyBot) {
    return (
      <div className="min-h-screen w-screen bg-[#0c0f12] flex items-center justify-center p-3">
        <BabyBotConsole
          market={data.market}
          aiSignals={data.ai_signals}
          livePortfolio={data.live_portfolio}
          activePosition={data.portfolio?.positions?.[0]}
          tradingMode={tradingMode}
          timeframe={data.market?.timeframe || '15m'}
          isPoppedOut={true}
          onTogglePopOut={() => window.close()}
          onFlattenHalt={handleKillSwitch}
          onQuickTrade={handleQuickTrade}
          reportsCount={Array.isArray(data.win_loss_reports) ? data.win_loss_reports.length : 0}
          consecutiveLosses={consecutiveLosses}
          selectedBotId={standaloneBotId}
          onSelectBot={(botId) => {
            setStandaloneBotId(botId);
            selectStrategyBot(botId);
            if (typeof window !== 'undefined' && window.history) {
              const url = new URL(window.location.href);
              url.searchParams.set('bot', botId);
              window.history.replaceState({}, '', url.toString());
            }
          }}
          dualOnnxTelemetry={data.dual_onnx_telemetry}
          preflightGates={data.preflight_gates}
          macroDominionTelemetry={data.macro_trend_dominion_telemetry}
          hmmMacroRegime={data.hmm_macro_regime}
          sealOfExcellence={data.seal_of_excellence}
          onOpenReports={() => {
            if (window.opener) {
              try {
                window.opener.focus();
              } catch {}
            } else {
              window.open('/', '_blank');
            }
          }}
        />
      </div>
    );
  }

  // 2. THE PARENT HUB (Factory / Lab Multi-Column Architecture)
  return (
    <ParentHub
      market={data.market}
      ladder={data.orderbook_ladder}
      aiSignals={data.ai_signals}
      livePortfolio={data.live_portfolio}
      portfolio={data.portfolio}
      activePosition={data.portfolio?.positions?.[0]}
      tradeTape={data.trade_tape}
      chartPoints={data.chart}
      reports={data.win_loss_reports}
      integrityStatus={data.integrity_status}
      complianceStatus={data.compliance_status}
      systemResources={data.system_resources}
      continuousTraining={data.continuous_training}
      tradingMode={tradingMode}
      timeframe={data.settings?.timeframe || data.market?.timeframe || '15m'}
      activeStrategyBot={data.settings?.active_strategy_bot || '3_step_domination_bot'}
      onSelectStrategy={selectStrategyBot}
      onSelectAsset={selectAsset}
      onSelectTimeframe={changeTimeframe}
      onSelectTradingMode={(m) => setTradingMode(m)}
      onQuickTrade={handleQuickTrade}
      onFlattenHalt={handleKillSwitch}
      onRunAuditNow={handleRunAuditNow}
      onTestBot={!isLive ? handleTestBot : undefined}
      isPoppedOutBabyBot={isPoppedOutBabyBot}
      onTogglePopOutBabyBot={handleTogglePopOutBabyBot}
      consecutiveLosses={consecutiveLosses}
      onClosePosition={closePosition}
      onCancelOrder={cancelOrder}
      onResetCircuitBreaker={resetCircuitBreaker}
      onResyncMemory={resyncMemory}
      dualOnnxTelemetry={data.dual_onnx_telemetry}
      preflightGates={data.preflight_gates}
      macroDominionTelemetry={data.macro_trend_dominion_telemetry}
      hmmMacroRegime={data.hmm_macro_regime}
      sealOfExcellence={data.seal_of_excellence}
      botAuditStatus={data.bot_audit_status}
    />
  );
}

export default App;
