/**
 * @file PerpetualTradingContext.tsx
 * @description Dedicated Context for Perpetual Trading within Kalshi Simulator.
 * Provides independent state management:
 * 1. Multi-asset selection (BTC-PERP, ETH-PERP, SOL-PERP, DOGE-PERP)
 * 2. Independent OHLCV candlestick generation with live price updates
 * 3. Technical indicators (Volume, Heatmap, EMA 20/50, VPIN, Bollinger)
 * 4. Bot deployment selection & dynamic parameter state
 * 5. Manual order placement ticket (Leverage 1x-50x, Market/Limit, Long/Short)
 * 6. Isolated perpetual positions & live unrealized PnL
 */

import React, { createContext, useContext, useState, useEffect, useMemo, useCallback } from 'react';
import { useKalshiWebSocket } from '../hooks/useKalshiWebSocket';

export type PerpAsset = 'BTC' | 'ETH' | 'SOL' | 'DOGE';

export interface PerpCandle {
  time: number; // Unix timestamp in seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  buyVolume: number;
  sellVolume: number;
  vpin: number;
}

export interface PerpPosition {
  id: string;
  asset: PerpAsset;
  side: 'long' | 'short';
  size: number;
  entryPrice: number;
  markPrice: number;
  leverage: number;
  liquidationPrice: number;
  margin: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
  timestamp: string;
}

export interface PerpBotConfig {
  id: string;
  name: string;
  strategyType: string;
  leverage: number;
  minConfidence: number;
  takeProfitPct: number;
  stopLossPct: number;
  trailingStopPct: number;
  dynamicMoat: number;
  vpinToxicThreshold: number;
  isArmed: boolean;
  status: 'active' | 'standby' | 'quarantine';
  signals: {
    conviction: number;
    recommendedSide: 'long' | 'short' | 'neutral';
    rationale: string;
    vpin: number;
  };
}

export interface PerpetualContextType {
  selectedAsset: PerpAsset;
  setSelectedAsset: (asset: PerpAsset) => void;
  timeframe: string;
  setTimeframe: (tf: string) => void;
  candles: PerpCandle[];
  currentPrice: number;
  priceChange24h: number;
  fundingRate: number;
  nextFundingIn: string;
  // Chart indicators
  showVolume: boolean;
  setShowVolume: (val: boolean) => void;
  showHeatmap: boolean;
  setShowHeatmap: (val: boolean) => void;
  showEma: boolean;
  setShowEma: (val: boolean) => void;
  showVpin: boolean;
  setShowVpin: (val: boolean) => void;
  // Bot management
  activeBotId: string;
  setActiveBotId: (botId: string) => void;
  botConfigs: Record<string, PerpBotConfig>;
  updateBotParam: (botId: string, param: keyof PerpBotConfig, value: any) => void;
  toggleArmBot: (botId: string) => void;
  // Positions & Manual Trading
  positions: PerpPosition[];
  openPosition: (side: 'long' | 'short', size: number, leverage: number, orderType?: 'market' | 'limit', limitPrice?: number) => void;
  closePosition: (positionId: string) => void;
  balance: number;
}

const DEFAULT_ASSET_PRICES: Record<PerpAsset, number> = {
  BTC: 81420.50,
  ETH: 2165.20,
  SOL: 132.80,
  DOGE: 0.0915,
};

const DEFAULT_BOTS: Record<string, PerpBotConfig> = {
  'dominion_perp': {
    id: 'dominion_perp',
    name: '3-Step Dominion Perp',
    strategyType: 'Momentum Breakout & Trend Scalp',
    leverage: 5,
    minConfidence: 68,
    takeProfitPct: 3.5,
    stopLossPct: 1.5,
    trailingStopPct: 0.8,
    dynamicMoat: 25.0,
    vpinToxicThreshold: 0.60,
    isArmed: true,
    status: 'active',
    signals: {
      conviction: 78.4,
      recommendedSide: 'long',
      rationale: 'Breakout above 15m VWAP anchor with surging spot delta and zero toxic VPIN.',
      vpin: 0.14,
    },
  },
  'macro_trend_perp': {
    id: 'macro_trend_perp',
    name: 'Macro Trend Dominion Perp',
    strategyType: 'HMM Multi-Regime Swing Arbitrage',
    leverage: 3,
    minConfidence: 72,
    takeProfitPct: 6.0,
    stopLossPct: 2.0,
    trailingStopPct: 1.2,
    dynamicMoat: 40.0,
    vpinToxicThreshold: 0.55,
    isArmed: false,
    status: 'standby',
    signals: {
      conviction: 64.2,
      recommendedSide: 'neutral',
      rationale: 'HMM Regime: RANGE_ACCUMULATION. Preserving capital until dynamic expansion.',
      vpin: 0.22,
    },
  },
  'dual_onnx_perp': {
    id: 'dual_onnx_perp',
    name: 'Dual-ONNX Micro Perp',
    strategyType: 'Neural Microstructure High-Frequency Scalp',
    leverage: 10,
    minConfidence: 80,
    takeProfitPct: 1.8,
    stopLossPct: 0.9,
    trailingStopPct: 0.4,
    dynamicMoat: 15.0,
    vpinToxicThreshold: 0.50,
    isArmed: true,
    status: 'active',
    signals: {
      conviction: 82.5,
      recommendedSide: 'long',
      rationale: 'Brain 1 Spot Conviction + Brain 2 CLOB Acceleration alignment confirmed.',
      vpin: 0.11,
    },
  },
};

const PerpetualTradingContext = createContext<PerpetualContextType | null>(null);

export const PerpetualTradingProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { data: kalshiData } = useKalshiWebSocket();
  const [selectedAsset, setSelectedAsset] = useState<PerpAsset>('BTC');
  const [timeframe, setTimeframe] = useState<string>('5m');
  const [showVolume, setShowVolume] = useState<boolean>(true);
  const [showHeatmap, setShowHeatmap] = useState<boolean>(true);
  const [showEma, setShowEma] = useState<boolean>(true);
  const [showVpin, setShowVpin] = useState<boolean>(false);
  const [activeBotId, setActiveBotId] = useState<string>('dominion_perp');
  const [botConfigs, setBotConfigs] = useState<Record<string, PerpBotConfig>>(DEFAULT_BOTS);
  const [balance, setBalance] = useState<number>(10.00);

  // Generate initial candle history
  const [candles, setCandles] = useState<PerpCandle[]>([]);

  const [currentPrice, setCurrentPrice] = useState<number>(DEFAULT_ASSET_PRICES['BTC']);
  const [priceChange24h] = useState<number>(2.42);
  const [fundingRate] = useState<number>(0.0001); // 0.010%
  const [nextFundingIn] = useState<string>('03:42:15');

  // Helper to get seconds from timeframe string
  const getIntervalSeconds = (tf: string) => {
    switch (tf) {
      case '1m': return 60;
      case '5m': return 300;
      case '15m': return 900;
      case '1h': return 3600;
      case '4h': return 14400;
      case '1D': return 86400;
      default: return 300;
    }
  };

  // Fetch real historical candles when asset or timeframe changes
  useEffect(() => {
    // Binance intervals: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
    const binanceInterval = timeframe === '1D' ? '1d' : timeframe;
    const symbol = selectedAsset + 'USDT';
    
    fetch(`https://api.binance.com/api/v3/klines?symbol=${symbol}&interval=${binanceInterval}&limit=75`)
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          const arr: PerpCandle[] = data.map((kline: any) => ({
            time: Math.floor(kline[0] / 1000),
            open: parseFloat(kline[1]),
            high: parseFloat(kline[2]),
            low: parseFloat(kline[3]),
            close: parseFloat(kline[4]),
            volume: parseFloat(kline[5]),
            buyVolume: parseFloat(kline[9]),
            sellVolume: parseFloat(kline[5]) - parseFloat(kline[9]),
            vpin: 0.12, // VPIN requires tick-level orderbook data, defaulting safely
          }));
          setCandles(arr);
          if (arr.length > 0) {
            setCurrentPrice(arr[arr.length - 1].close);
          }
        }
      })
      .catch(err => console.error("Failed to fetch historical klines", err));
  }, [selectedAsset, timeframe]);

  // Real-time tick updates driven by actual Backend State / WebSocket
  useEffect(() => {
    const dataAny = kalshiData as any;
    const interval = getIntervalSeconds(timeframe);
    const now = Math.floor(Date.now() / 1000);

    if (selectedAsset === 'BTC' && dataAny?.market?.current_btc_price) {
      const newPrice = Number(dataAny.market.current_btc_price);
      setCurrentPrice(newPrice);
      
      setCandles((prevCandles) => {
        if (prevCandles.length === 0) return prevCandles;
        const last = { ...prevCandles[prevCandles.length - 1] };
        
        if (now >= last.time + interval) {
          // Time to roll over to a new candle
          const newCandle: PerpCandle = {
            time: last.time + interval,
            open: last.close,
            high: Math.max(last.close, newPrice),
            low: Math.min(last.close, newPrice),
            close: newPrice,
            volume: 1,
            buyVolume: newPrice >= last.close ? 1 : 0,
            sellVolume: newPrice < last.close ? 1 : 0,
            vpin: last.vpin,
          };
          return [...prevCandles.slice(1), newCandle];
        } else {
          // Update current candle
          if (last.close !== newPrice) {
            last.close = newPrice;
            last.high = Math.max(last.high, newPrice);
            last.low = Math.min(last.low, newPrice);
            last.volume += 1;
            if (newPrice >= last.close) last.buyVolume += 1;
            else last.sellVolume += 1;
            return [...prevCandles.slice(0, -1), last];
          }
          return prevCandles;
        }
      });
    } else {
      // Fallback for non-BTC assets (or if WS disconnected), using a real API tick
      const timer = setInterval(() => {
        const symbol = selectedAsset + 'USDT';
        fetch(`https://api.binance.com/api/v3/ticker/price?symbol=${symbol}`)
          .then(res => res.json())
          .then(data => {
            if (data && data.price) {
              const newPrice = Number(parseFloat(data.price).toFixed(selectedAsset === 'DOGE' ? 5 : 2));
              const currentNow = Math.floor(Date.now() / 1000);
              
              setCurrentPrice(newPrice);
              
              setCandles((prevCandles) => {
                if (prevCandles.length === 0) return prevCandles;
                const last = { ...prevCandles[prevCandles.length - 1] };
                
                if (currentNow >= last.time + interval) {
                  // Roll over
                  const newCandle: PerpCandle = {
                    time: last.time + interval,
                    open: last.close,
                    high: Math.max(last.close, newPrice),
                    low: Math.min(last.close, newPrice),
                    close: newPrice,
                    volume: 1,
                    buyVolume: newPrice >= last.close ? 1 : 0,
                    sellVolume: newPrice < last.close ? 1 : 0,
                    vpin: last.vpin,
                  };
                  return [...prevCandles.slice(1), newCandle];
                } else {
                  if (last.close !== newPrice) {
                    last.close = newPrice;
                    last.high = Math.max(last.high, newPrice);
                    last.low = Math.min(last.low, newPrice);
                    last.volume += 1;
                    if (newPrice >= last.close) last.buyVolume += 1;
                    else last.sellVolume += 1;
                    return [...prevCandles.slice(0, -1), last];
                  }
                  return prevCandles;
                }
              });
            }
          })
          .catch(() => {});
      }, 5000);
      return () => clearInterval(timer);
    }
  }, [selectedAsset, timeframe, (kalshiData as any)?.market?.current_btc_price]);

  // Real-time AI signals update from Backend WebSocket
  useEffect(() => {
    const dataAny = kalshiData as any;
    if (dataAny?.ai_signals) {
      setBotConfigs((prev) => {
        const current = prev[activeBotId];
        if (!current) return prev;
        
        const pUp = dataAny.ai_signals.p_up * 100;
        const pDown = dataAny.ai_signals.p_down * 100;
        let side: 'long' | 'short' | 'neutral' = 'neutral';
        let conviction = 50;

        if (pUp > pDown) {
          side = 'long';
          conviction = pUp;
        } else if (pDown > pUp) {
          side = 'short';
          conviction = pDown;
        }

        if (
          current.signals.recommendedSide === side &&
          current.signals.conviction === conviction &&
          current.signals.vpin === dataAny.ai_signals.vpin
        ) {
          return prev;
        }

        return {
          ...prev,
          [activeBotId]: {
            ...current,
            signals: {
              ...current.signals,
              recommendedSide: side,
              conviction,
              vpin: dataAny.ai_signals.vpin || 0,
              rationale: dataAny.ai_signals.rationale || 'Live neural inference active.',
            }
          }
        };
      });
    }
  }, [activeBotId, kalshiData]);

  // Periodic positions polling (since websocket might not emit positions fast enough)
  useEffect(() => {
    const timer = setInterval(() => {
      fetch('/api/perpetuals/positions')
        .then(res => res.json())
        .then(data => {
          if (data.positions && Array.isArray(data.positions)) {
            setPositions(prev => {
              const newPositions = data.positions.map((p: any) => ({
                id: p.id,
                asset: 'BTC',
                side: p.side as 'long' | 'short',
                size: p.size,
                leverage: p.leverage || 10,
                entryPrice: p.entry_price,
                liquidationPrice: p.side === 'long' 
                  ? p.entry_price * (1 - 1/p.leverage)
                  : p.entry_price * (1 + 1/p.leverage),
                unrealizedPnl: 0,
                unrealizedPnlPct: 0,
                botId: p.bot_id
              }));
              
              // Only update if changed (basic length check for simulation UI)
              if (newPositions.length !== prev.length) {
                return newPositions;
              }
              return prev;
            });
          }
        })
        .catch(() => {});
    }, 2000);
    return () => clearInterval(timer);
  }, []);

  // Positions state
  const [positions, setPositions] = useState<PerpPosition[]>([]);

  // Recalculate position mark prices and PnL on price tick
  useEffect(() => {
    setPositions((prev) =>
      prev.map((pos) => {
        if (pos.asset === selectedAsset) {
          const diff = pos.side === 'long' ? currentPrice - pos.entryPrice : pos.entryPrice - currentPrice;
          const uPnl = Number((diff * pos.size).toFixed(2));
          const uPnlPct = Number(((uPnl / pos.margin) * 100).toFixed(2));
          return {
            ...pos,
            markPrice: currentPrice,
            unrealizedPnl: uPnl,
            unrealizedPnlPct: uPnlPct,
          };
        }
        return pos;
      })
    );
  }, [currentPrice, selectedAsset]);

  // Fetch initial bots and positions from backend
  useEffect(() => {
    fetch('/api/perpetuals/bots')
      .then(res => res.json())
      .then(data => {
        if (data.bots && Array.isArray(data.bots)) {
          const newConfigs: Record<string, PerpBotConfig> = {};
          data.bots.forEach((b: any) => {
            newConfigs[b.id] = {
              id: b.id,
              name: b.name || 'Unknown Bot',
              strategyType: b.strategyType || 'UNKNOWN',
              leverage: b.leverage || 10,
              minConfidence: b.min_confidence || 75,
              takeProfitPct: b.take_profit_pct || 5.0,
              stopLossPct: b.stop_loss_pct || 2.0,
              trailingStopPct: b.trailing_stop_pct || 1.0,
              dynamicMoat: b.dynamic_moat || 15.0,
              vpinToxicThreshold: b.vpin_toxic_threshold || 0.25,
              isArmed: b.is_armed || false,
              status: b.is_armed ? 'active' : 'standby',
              signals: {
                recommendedSide: 'neutral',
                conviction: 50,
                vpin: 0.12,
                rationale: 'Awaiting first neural sweep...',
              }
            };
          });
          setBotConfigs(prev => ({ ...prev, ...newConfigs }));
        }
      })
      .catch(err => console.error("Failed to fetch perp bots:", err));

    fetch('/api/perpetuals/positions')
      .then(res => res.json())
      .then(data => {
        if (data.positions && Array.isArray(data.positions)) {
          // Map backend position to frontend PerpPosition
          const mappedPositions: PerpPosition[] = data.positions.map((p: any) => ({
            id: p.id,
            asset: 'BTC',
            side: p.side as 'long' | 'short',
            size: p.size,
            leverage: p.leverage || 10,
            entryPrice: p.entry_price,
            liquidationPrice: p.side === 'long' 
              ? p.entry_price * (1 - 1/p.leverage)
              : p.entry_price * (1 + 1/p.leverage),
            unrealizedPnl: 0,
            unrealizedPnlPct: 0,
            botId: p.bot_id
          }));
          setPositions(mappedPositions);
        }
      })
      .catch(err => console.error("Failed to fetch perp positions:", err));
  }, []);

  const updateBotParam = useCallback((botId: string, param: keyof PerpBotConfig, value: any) => {
    setBotConfigs((prev) => ({
      ...prev,
      [botId]: {
        ...prev[botId],
        [param]: value,
      },
    }));
  }, []);

  const toggleArmBot = useCallback((botId: string) => {
    setBotConfigs((prev) => {
      const current = prev[botId];
      if (!current) return prev;
      
      const newIsArmed = !current.isArmed;
      
      // Fire and forget to backend
      fetch('/api/perpetuals/bot/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bot_id: botId, is_armed: newIsArmed })
      }).catch(err => console.error("Failed to arm bot on backend:", err));

      return {
        ...prev,
        [botId]: {
          ...current,
          isArmed: newIsArmed,
          status: newIsArmed ? 'active' : 'standby',
        },
      };
    });
  }, []);

  const openPosition = useCallback(
    async (side: 'long' | 'short', size: number, leverage: number, orderType: 'market' | 'limit' = 'market', limitPrice?: number) => {
      const entry = orderType === 'limit' && limitPrice ? limitPrice : currentPrice;
      const notional = size * entry;
      const margin = notional / leverage;

      if (margin > balance) {
        alert('Insufficient margin to open perpetual position!');
        return;
      }

      setBalance((b) => b - margin);

      const liqBuffer = entry * (1 / leverage) * 0.9;
      const liqPrice = side === 'long' ? entry - liqBuffer : entry + liqBuffer;

      const fallbackId = `perp-${Date.now()}`;
      const newPos: PerpPosition = {
        id: fallbackId,
        asset: selectedAsset,
        side,
        size,
        entryPrice: entry,
        markPrice: currentPrice,
        leverage,
        liquidationPrice: Math.max(0, Number(liqPrice.toFixed(2))),
        margin: Number(margin.toFixed(2)),
        unrealizedPnl: 0,
        unrealizedPnlPct: 0,
        timestamp: new Date().toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour12: false }) + ' ET',
      };

      setPositions((prev) => [newPos, ...prev]);

      try {
        const res = await fetch('/api/perpetuals/order', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            asset: selectedAsset,
            side,
            order_type: orderType,
            size,
            leverage,
            price: limitPrice,
            bot_id: activeBotId,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.position && data.position.id) {
            setPositions((prev) =>
              prev.map((p) => (p.id === fallbackId ? { ...p, id: data.position.id } : p))
            );
          }
        }
      } catch (err) {
        // Optimistic offline execution continues seamlessly
      }
    },
    [activeBotId, balance, currentPrice, selectedAsset]
  );

  const closePosition = useCallback(async (positionId: string) => {
    setPositions((prev) => {
      const target = prev.find((p) => p.id === positionId);
      if (target) {
        setBalance((b) => b + target.margin + target.unrealizedPnl);
      }
      return prev.filter((p) => p.id !== positionId);
    });

    try {
      await fetch('/api/perpetuals/position/close', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ position_id: positionId }),
      });
    } catch (err) {
      // Offline fallback
    }
  }, []);

  const value = useMemo(
    () => ({
      selectedAsset,
      setSelectedAsset,
      timeframe,
      setTimeframe,
      candles,
      currentPrice,
      priceChange24h,
      fundingRate,
      nextFundingIn,
      showVolume,
      setShowVolume,
      showHeatmap,
      setShowHeatmap,
      showEma,
      setShowEma,
      showVpin,
      setShowVpin,
      activeBotId,
      setActiveBotId,
      botConfigs,
      updateBotParam,
      toggleArmBot,
      positions,
      openPosition,
      closePosition,
      balance,
    }),
    [
      selectedAsset,
      timeframe,
      candles,
      currentPrice,
      priceChange24h,
      fundingRate,
      nextFundingIn,
      showVolume,
      showHeatmap,
      showEma,
      showVpin,
      activeBotId,
      botConfigs,
      updateBotParam,
      toggleArmBot,
      positions,
      openPosition,
      closePosition,
      balance,
    ]
  );

  return <PerpetualTradingContext.Provider value={value}>{children}</PerpetualTradingContext.Provider>;
};

export const usePerpetualTrading = (): PerpetualContextType => {
  const ctx = useContext(PerpetualTradingContext);
  if (!ctx) {
    throw new Error('usePerpetualTrading must be used within PerpetualTradingProvider');
  }
  return ctx;
};
