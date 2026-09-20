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
  const [selectedAsset, setSelectedAsset] = useState<PerpAsset>('BTC');
  const [timeframe, setTimeframe] = useState<string>('5m');
  const [showVolume, setShowVolume] = useState<boolean>(true);
  const [showHeatmap, setShowHeatmap] = useState<boolean>(true);
  const [showEma, setShowEma] = useState<boolean>(true);
  const [showVpin, setShowVpin] = useState<boolean>(false);
  const [activeBotId, setActiveBotId] = useState<string>('dominion_perp');
  const [botConfigs, setBotConfigs] = useState<Record<string, PerpBotConfig>>(DEFAULT_BOTS);
  const [balance, setBalance] = useState<number>(10000.00);

  // Generate initial candle history
  const [candles, setCandles] = useState<PerpCandle[]>(() => {
    const basePrice = DEFAULT_ASSET_PRICES['BTC'];
    const count = 75;
    const now = Math.floor(Date.now() / 1000);
    const interval = 300; // 5 min
    const arr: PerpCandle[] = [];
    let p = basePrice * 0.985;

    for (let i = count; i >= 0; i--) {
      const time = now - i * interval;
      const change = (Math.random() - 0.48) * (basePrice * 0.0035);
      const open = p;
      const close = p + change;
      const high = Math.max(open, close) + Math.random() * (basePrice * 0.0015);
      const low = Math.min(open, close) - Math.random() * (basePrice * 0.0015);
      const volume = Math.floor(Math.random() * 80 + 20);
      const buyRatio = 0.45 + Math.random() * 0.15;
      arr.push({
        time,
        open,
        high,
        low,
        close,
        volume,
        buyVolume: volume * buyRatio,
        sellVolume: volume * (1 - buyRatio),
        vpin: 0.08 + Math.random() * 0.18,
      });
      p = close;
    }
    return arr;
  });

  const [currentPrice, setCurrentPrice] = useState<number>(DEFAULT_ASSET_PRICES['BTC']);
  const [priceChange24h] = useState<number>(2.42);
  const [fundingRate] = useState<number>(0.0001); // 0.010%
  const [nextFundingIn] = useState<string>('03:42:15');

  // Regenerate candles when asset changes
  useEffect(() => {
    const base = DEFAULT_ASSET_PRICES[selectedAsset];
    setCurrentPrice(base);
    const count = 75;
    const now = Math.floor(Date.now() / 1000);
    const interval = 300;
    const arr: PerpCandle[] = [];
    let p = base * 0.985;

    for (let i = count; i >= 0; i--) {
      const time = now - i * interval;
      const change = (Math.random() - 0.48) * (base * 0.004);
      const open = p;
      const close = p + change;
      const high = Math.max(open, close) + Math.random() * (base * 0.002);
      const low = Math.min(open, close) - Math.random() * (base * 0.002);
      const volume = Math.floor(Math.random() * 80 + 20);
      const buyRatio = 0.45 + Math.random() * 0.15;
      arr.push({
        time,
        open,
        high,
        low,
        close,
        volume,
        buyVolume: volume * buyRatio,
        sellVolume: volume * (1 - buyRatio),
        vpin: 0.08 + Math.random() * 0.18,
      });
      p = close;
    }
    setCandles(arr);
  }, [selectedAsset]);

  // Real-time micro-tick price simulation
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentPrice((prev) => {
        const volatility = prev * 0.0002;
        const delta = (Math.random() - 0.495) * volatility;
        const newPrice = Number((prev + delta).toFixed(selectedAsset === 'DOGE' ? 5 : 2));

        setCandles((prevCandles) => {
          if (prevCandles.length === 0) return prevCandles;
          const last = { ...prevCandles[prevCandles.length - 1] };
          last.close = newPrice;
          last.high = Math.max(last.high, newPrice);
          last.low = Math.min(last.low, newPrice);
          last.volume += Math.floor(Math.random() * 2);
          return [...prevCandles.slice(0, -1), last];
        });

        return newPrice;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [selectedAsset]);

  // Positions state
  const [positions, setPositions] = useState<PerpPosition[]>([
    {
      id: 'perp-pos-1',
      asset: 'BTC',
      side: 'long',
      size: 0.05,
      entryPrice: 81150.0,
      markPrice: 81420.5,
      leverage: 5,
      liquidationPrice: 65200.0,
      margin: 811.5,
      unrealizedPnl: 13.52,
      unrealizedPnlPct: 1.66,
      timestamp: '17:15:02 ET',
    },
  ]);

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
      return {
        ...prev,
        [botId]: {
          ...current,
          isArmed: !current.isArmed,
          status: !current.isArmed ? 'active' : 'standby',
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
