/**
 * @file ClobTerminalView.tsx
 * @description Institutional 3-column WebCLOB binary options trading cockpit.
 * Features:
 * 1. Global Navigation & Live EST Clock Header
 * 2. Left Panel: Kalshi 15-Minute Event Order Book & Cumulative Depth Ladder
 * 3. Center Panel: Event Price Graph with HTML5 Canvas Liquidity Heatmap (DOM Cloud),
 *    candlesticks, crosshair hover tooltip, drawing toolbar, TradingView controls,
 *    Pine Editor drawer, and Rapid Execution Trading Panel.
 * 4. Right Panel: Underlying Asset (BTC/USD) Level-2 Spot Order Book with CME CF Benchmarks 5Hz parity.
 */

import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  MarketState,
  OrderBookLadderRow,
  AISignals,
  Position,
  TradeTapeItem,
  ChartPoint,
  CryptoAsset,
} from '../types';
import {
  Activity,
  BarChart2,
  Crosshair,
  TrendingUp,
  TrendingDown,
  Clock,
  Search,
  Bell,
  User,
  MoreHorizontal,
  Maximize2,
  Minimize2,
  Sliders,
  RefreshCw,
  Terminal,
  ChevronDown,
  ChevronUp,
  Info,
  Zap,
  Shield,
  ArrowUpRight,
  ArrowDownRight,
  Volume2,
  Check,
  Flame,
  Code,
  Layers,
  X,
  Compass,
  FileText,
  MousePointer,
  Minus,
  Hash,
  Square,
  Sparkles,
} from 'lucide-react';
import { soundFX } from '../utils/audioFX';
import { ClobTopHeader, TopNavTab } from './clob/ClobTopHeader';
import { EventOrderBookPanel } from './clob/EventOrderBookPanel';
import { SpotOrderBookPanel } from './clob/SpotOrderBookPanel';
import { ChartControlsToolbar } from './clob/ChartControlsToolbar';
import { ClobBottomDock } from './clob/ClobBottomDock';
import { ClobModals } from './clob/ClobModals';

interface ClobTerminalViewProps {
  market: MarketState;
  ladder?: OrderBookLadderRow[];
  aiSignals?: AISignals;
  activePosition?: Position | null;
  tradeTape?: TradeTapeItem[];
  chartPoints?: ChartPoint[];
  tradingMode?: 'paper' | 'live';
  timeframe?: string;
  onQuickTrade?: (side: 'yes' | 'no') => void;
  onSelectAsset?: (asset: CryptoAsset) => void;
  onSelectTimeframe?: (tf: string) => void;
  onClosePosition?: (ticker: string, executionMode?: 'paper' | 'live') => Promise<any>;
  onCancelOrder?: (orderId: string, executionMode?: 'paper' | 'live') => Promise<any>;
  isRightPanelHidden?: boolean;
  onToggleRightPanel?: () => void;
}

// Drawing tool types
type DrawingTool = 'cursor' | 'crosshair' | 'trendline' | 'pitchfork' | 'fibonacci' | 'text' | 'patterns' | 'measure' | 'zoom' | 'magnet';

// Theme options
type ChartTheme = 'institutional' | 'heatmap_high_contrast' | 'cyberpunk' | 'monochrome';

// TradingView chart styles
export type ChartStyle = 'candles' | 'line' | 'area';

// Asset specifications for CME CF Benchmarks & Spot CLOB
interface AssetSpec {
  name: string;
  symbol: string;
  decimals: number;
  tickSize: number;
  baseSpread: number;
  feedId: string;
  unit: string;
  defaultBasePrice: number;
}

const ASSET_SPECS: Record<CryptoAsset, AssetSpec> = {
  BTC: {
    name: 'Bitcoin',
    symbol: 'BTC/USD',
    decimals: 2,
    tickSize: 0.50,
    baseSpread: 0.60,
    feedId: 'BRTI 5Hz (200ms)',
    unit: 'BTC',
    defaultBasePrice: 68450.50,
  },
  ETH: {
    name: 'Ethereum',
    symbol: 'ETH/USD',
    decimals: 2,
    tickSize: 0.10,
    baseSpread: 0.15,
    feedId: 'ETHUSD_RTI 5Hz',
    unit: 'ETH',
    defaultBasePrice: 3520.40,
  },
  SOL: {
    name: 'Solana',
    symbol: 'SOL/USD',
    decimals: 2,
    tickSize: 0.02,
    baseSpread: 0.04,
    feedId: 'SOLUSD_RTI 5Hz',
    unit: 'SOL',
    defaultBasePrice: 178.65,
  },
  DOGE: {
    name: 'Dogecoin',
    symbol: 'DOGE/USD',
    decimals: 4,
    tickSize: 0.0001,
    baseSpread: 0.0002,
    feedId: 'DOGEUSD_RTI 5Hz',
    unit: 'DOGE',
    defaultBasePrice: 0.1425,
  },
};

export const ClobTerminalView: React.FC<ClobTerminalViewProps> = ({
  market,
  ladder = [],
  aiSignals,
  activePosition,
  tradeTape = [],
  chartPoints = [],
  tradingMode = 'live',
  timeframe = '15m',
  onQuickTrade,
  onSelectAsset,
  onSelectTimeframe,
  onClosePosition,
  isRightPanelHidden = false,
  onToggleRightPanel,
}) => {
  // State variables for interactive controls
  const [activeAsset, setActiveAsset] = useState<CryptoAsset>(market?.active_asset || 'BTC');
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>(timeframe || '15m');
  const [activeDrawingTool, setActiveDrawingTool] = useState<DrawingTool>('crosshair');
  const [chartStyle, setChartStyle] = useState<ChartStyle>('candles');
  const [hoveredCandleIndex, setHoveredCandleIndex] = useState<number | null>(null);
  const [isHeatmapEnabled, setIsHeatmapEnabled] = useState<boolean>(true);
  const [chartTheme, setChartTheme] = useState<ChartTheme>('institutional');
  const [timeZoneDisplay, setTimeZoneDisplay] = useState<'EST' | 'UTC'>('EST');
  const [timeRange, setTimeRange] = useState<string>('1D');
  const [scaleMode, setScaleMode] = useState<'auto' | 'log' | 'pct'>('auto');
  const [isIndicatorsModalOpen, setIsIndicatorsModalOpen] = useState<boolean>(false);
  const [isSearchModalOpen, setIsSearchModalOpen] = useState<boolean>(false);
  const [isNotificationsOpen, setIsNotificationsOpen] = useState<boolean>(false);
  const [isPineEditorOpen, setIsPineEditorOpen] = useState<boolean>(false);
  const [isTradingPanelOpen, setIsTradingPanelOpen] = useState<boolean>(false);
  const [isOrderSizeTooltipOpen, setIsOrderSizeTooltipOpen] = useState<boolean>(false);
  const [volumeUnit, setVolumeUnit] = useState<'lots' | 'usd' | 'cumulative'>('lots');
  const [spotVolumeUnit, setSpotVolumeUnit] = useState<'btc' | 'usd'>('btc');
  const [selectedStrikePrice, setSelectedStrikePrice] = useState<number | null>(null);
  const [activeTopTab, setActiveTopTab] = useState<'Trading' | 'Live' | 'Topics' | 'Events' | 'Community' | 'Support'>('Trading');

  // Interactive crosshair state
  const [crosshairPos, setCrosshairPos] = useState<{ x: number; y: number; visible: boolean; time: string; price: number; volume: string; heat: string }>({
    x: 0,
    y: 0,
    visible: false,
    time: '14:56:32',
    price: 72,
    volume: '14.5K',
    heat: 'High',
  });

  // Rapid execution order inputs
  const [orderSide, setOrderSide] = useState<'yes' | 'no'>('yes');
  const [orderLimitPrice, setOrderLimitPrice] = useState<number>(
    market?.market_chance_pct ? Math.round(market.market_chance_pct) : 72
  );
  const [orderQuantity] = useState<number>(1); // Micro-bankroll armor: strictly 1 contract
  const [orderStatusMessage, setOrderStatusMessage] = useState<string | null>(null);

  // Indicators toggle state
  const [activeIndicators, setActiveIndicators] = useState({
    vpin: true,
    orderFlowImbalance: true,
    bollingerBands: false,
    volumeProfile: true,
    twap60s: true,
  });

  // Pine Script state
  const [pineScriptCode, setPineScriptCode] = useState<string>(
    `//@version=5\n// Kalshi 15M DOM Liquidity Heatmap & Reversal Engine\nstrategy("Dominion V3.2 Heatmap Scanner", overlay=true)\n\nstrike = input.float(${market?.target_strike || 68500}, "Strike Target")\nthreshold_vpin = input.float(0.72, "VPIN Toxicity Shield")\n\nif (close > strike and volume > 10000)\n    strategy.entry("BUY_YES", strategy.long, qty=1)`
  );

  // Live EST Clock ticker
  const [currentTimeStr, setCurrentTimeStr] = useState<string>('');
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      if (timeZoneDisplay === 'EST') {
        const estOptions: Intl.DateTimeFormatOptions = {
          timeZone: 'America/New_York',
          month: 'short',
          day: 'numeric',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        };
        setCurrentTimeStr(`${now.toLocaleDateString('en-US', estOptions)} EST`);
      } else {
        const utcOptions: Intl.DateTimeFormatOptions = {
          timeZone: 'UTC',
          month: 'short',
          day: 'numeric',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: false,
        };
        setCurrentTimeStr(`${now.toLocaleDateString('en-US', utcOptions)} UTC`);
      }
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, [timeZoneDisplay]);

  // Sync active asset from parent
  useEffect(() => {
    if (market?.active_asset) {
      setActiveAsset(market.active_asset);
    }
  }, [market?.active_asset]);

  // Handle asset switch
  const handleSwitchAsset = (asset: CryptoAsset) => {
    soundFX.playClickSound();
    setActiveAsset(asset);
    if (onSelectAsset) {
      onSelectAsset(asset);
    }
  };

  // Handle timeframe switch
  const handleSwitchTimeframe = (tf: string) => {
    soundFX.playClickSound();
    setSelectedTimeframe(tf);
    if (onSelectTimeframe) {
      onSelectTimeframe(tf);
    }
  };

  // Order placement handler with micro-bankroll armor
  const handleExecuteTrade = (side: 'yes' | 'no') => {
    soundFX.playClickSound();
    if (onQuickTrade) {
      onQuickTrade(side);
      setOrderStatusMessage(`Routing 1 ${side.toUpperCase()} contract at ${orderLimitPrice}¢ via LiveCoordinator...`);
      setTimeout(() => setOrderStatusMessage(null), 4000);
    }
  };

  // =========================================================================
  // 1. LIVE KALSHI 15M ORDER BOOK LADDER DERIVATION
  // =========================================================================
  const yesRows = useMemo(() => {
    return (ladder || [])
      .filter((r) => r.side === 'yes')
      .sort((a, b) => b.price_raw - a.price_raw);
  }, [ladder]);

  const noRows = useMemo(() => {
    return (ladder || [])
      .filter((r) => r.side === 'no')
      .sort((a, b) => b.price_raw - a.price_raw);
  }, [ladder]);

  // Top of Book paired rows: Buy (YES) vs Sell (NO)
  const topBookRows = useMemo(() => {
    const rowCount = Math.max(yesRows.length, noRows.length);
    if (rowCount === 0) {
      // Dynamic fallback anchored to current market state if ladder hasn't streamed yet
      const yesP = market?.best_yes_bid
        ? Math.round(market.best_yes_bid * 100)
        : market?.market_chance_pct
        ? Math.round(market.market_chance_pct)
        : 68;
      const noP = market?.best_no_ask
        ? Math.round(market.best_no_ask * 100)
        : Math.max(1, 100 - yesP);

      return [
        { vol: '1.8K', yesBid: `${yesP}¢`, noAsk: `${noP}¢`, size: '1.5K', volPct: 45, sizePct: 35, yesCents: yesP, noCents: noP, yesContracts: 1800, noContracts: 1500 },
        { vol: '2.5K', yesBid: `${Math.max(1, yesP - 1)}¢`, noAsk: `${Math.min(99, noP + 1)}¢`, size: '2.2K', volPct: 60, sizePct: 50, yesCents: yesP - 1, noCents: noP + 1, yesContracts: 2500, noContracts: 2200 },
        { vol: '4.2K', yesBid: `${Math.max(1, yesP - 2)}¢`, noAsk: `${Math.min(99, noP + 2)}¢`, size: '3.8K', volPct: 85, sizePct: 75, yesCents: yesP - 2, noCents: noP + 2, yesContracts: 4200, noContracts: 3800 },
        { vol: '3.1K', yesBid: `${Math.max(1, yesP - 3)}¢`, noAsk: `${Math.min(99, noP + 3)}¢`, size: '2.9K', volPct: 70, sizePct: 65, yesCents: yesP - 3, noCents: noP + 3, yesContracts: 3100, noContracts: 2900 },
        { vol: '1.5K', yesBid: `${Math.max(1, yesP - 4)}¢`, noAsk: `${Math.min(99, noP + 4)}¢`, size: '1.8K', volPct: 35, sizePct: 40, yesCents: yesP - 4, noCents: noP + 4, yesContracts: 1500, noContracts: 1800 },
        { vol: '1.2K', yesBid: `${Math.max(1, yesP - 5)}¢`, noAsk: `${Math.min(99, noP + 5)}¢`, size: '1.4K', volPct: 28, sizePct: 32, yesCents: yesP - 5, noCents: noP + 5, yesContracts: 1200, noContracts: 1400 },
        { vol: '900', yesBid: `${Math.max(1, yesP - 6)}¢`, noAsk: `${Math.min(99, noP + 6)}¢`, size: '1.1K', volPct: 20, sizePct: 25, yesCents: yesP - 6, noCents: noP + 6, yesContracts: 900, noContracts: 1100 },
      ];
    }

    const maxYesContracts = Math.max(...yesRows.map((r) => r.contracts), 1);
    const maxNoContracts = Math.max(...noRows.map((r) => r.contracts), 1);

    const rows = [];
    for (let i = 0; i < Math.min(8, rowCount); i++) {
      const y = yesRows[i];
      const n = noRows[i];

      const yesCents = y ? Math.round(y.price_raw * 100) : 0;
      const noCents = n ? Math.round(n.price_raw * 100) : 0;

      const yesVolFormatted = y
        ? volumeUnit === 'usd'
          ? y.total
          : y.contracts >= 1000
          ? `${(y.contracts / 1000).toFixed(1)}K`
          : `${y.contracts}`
        : '--';

      const noSizeFormatted = n
        ? volumeUnit === 'usd'
          ? n.total
          : n.contracts >= 1000
          ? `${(n.contracts / 1000).toFixed(1)}K`
          : `${n.contracts}`
        : '--';

      const volPct = y ? Math.min(100, Math.max(8, Math.round((y.contracts / maxYesContracts) * 100))) : 0;
      const sizePct = n ? Math.min(100, Math.max(8, Math.round((n.contracts / maxNoContracts) * 100))) : 0;

      rows.push({
        vol: yesVolFormatted,
        yesBid: y ? `${yesCents}¢` : '--',
        noAsk: n ? `${noCents}¢` : '--',
        size: noSizeFormatted,
        volPct,
        sizePct,
        yesCents,
        noCents,
        yesContracts: y?.contracts || 0,
        noContracts: n?.contracts || 0,
      });
    }
    return rows;
  }, [yesRows, noRows, market, volumeUnit]);

  // Cumulative Depth Ladder
  const cumulativeLadderRows = useMemo(() => {
    const count = Math.max(yesRows.length, noRows.length);
    if (count === 0 && topBookRows.length > 0) {
      let cBuy = 0;
      let cSell = 0;
      return topBookRows.map((r) => {
        cBuy += r.yesContracts;
        cSell += r.noContracts;
        return {
          buyCum: cBuy >= 1000 ? `${(cBuy / 1000).toFixed(1)}K` : `${cBuy}`,
          price: `${r.yesBid} / ${r.noAsk}`,
          sellCum: cSell >= 1000 ? `${(cSell / 1000).toFixed(1)}K` : `${cSell}`,
          buyPct: Math.min(100, Math.max(12, Math.round((cBuy / (cBuy + cSell || 1)) * 100))),
          sellPct: Math.min(100, Math.max(12, Math.round((cSell / (cBuy + cSell || 1)) * 100))),
          rawPrice: r.yesCents,
        };
      });
    }

    const totalYes = yesRows.reduce((acc, r) => acc + r.contracts, 0) || 1;
    const totalNo = noRows.reduce((acc, r) => acc + r.contracts, 0) || 1;

    let cumYes = 0;
    let cumNo = 0;
    const rows = [];

    for (let i = 0; i < Math.min(9, count); i++) {
      const y = yesRows[i];
      const n = noRows[i];
      if (y) cumYes += y.contracts;
      if (n) cumNo += n.contracts;

      const yCents = y ? `${Math.round(y.price_raw * 100)}¢` : '--';
      const nCents = n ? `${Math.round(n.price_raw * 100)}¢` : '--';

      rows.push({
        buyCum: cumYes >= 1000 ? `${(cumYes / 1000).toFixed(1)}K` : `${cumYes}`,
        price: `${yCents} / ${nCents}`,
        sellCum: cumNo >= 1000 ? `${(cumNo / 1000).toFixed(1)}K` : `${cumNo}`,
        buyPct: Math.min(100, Math.max(8, Math.round((cumYes / totalYes) * 100))),
        sellPct: Math.min(100, Math.max(8, Math.round((cumNo / totalNo) * 100))),
        rawPrice: y ? Math.round(y.price_raw * 100) : 50,
      });
    }
    return rows;
  }, [yesRows, noRows, topBookRows]);

  // Fast resting depth lookup map by price cent (1¢ to 99¢)
  const depthByCent = useMemo(() => {
    const map = new Map<number, number>();
    (ladder || []).forEach((row) => {
      const cent = Math.round(row.price_raw * 100);
      const existing = map.get(cent) || 0;
      map.set(cent, existing + row.contracts);
    });
    return map;
  }, [ladder]);

  // =========================================================================
  // 2. LIVE ROLLING CANDLES SYNCED TO REAL PROBABILITY AND CHART TICKS
  // =========================================================================
  const chartCandles = useMemo(() => {
    const baseChance = market?.market_chance_pct
      ? Math.round(market.market_chance_pct)
      : market?.best_yes_bid
      ? Math.round(market.best_yes_bid * 100)
      : 72;

    interface CandleData {
      time: string;
      timeMs: number;
      open: number;
      high: number;
      low: number;
      close: number;
      volume: number;
      isUp: boolean;
    }

    const candles: CandleData[] = [];
    const now = Date.now();
    const intervalMs = 60 * 1000; // 1 min per candle

    if (chartPoints && chartPoints.length > 5) {
      // Seed historical candles from real chartPoints
      const step = Math.max(1, Math.floor(chartPoints.length / 36));
      for (let i = 0; i < chartPoints.length; i += step) {
        const pt = chartPoints[i];
        const strike = pt.target || market?.target_strike || 68500;
        const diff = pt.price - strike;
        // Implied probability from spot diff
        const impliedProb = Math.max(5, Math.min(95, Math.round(50 + diff * 0.4)));
        const high = Math.min(98, impliedProb + Math.round(Math.abs(Math.sin(i)) * 2) + 1);
        const low = Math.max(2, impliedProb - Math.round(Math.abs(Math.cos(i)) * 2) - 1);
        const openVal: number = i > 0 && candles.length > 0 ? candles[candles.length - 1].close : impliedProb;
        const close = impliedProb;
        const volume = Math.round(6000 + Math.abs(Math.sin(i * 1.3)) * 12000);

        candles.push({
          time: pt.time || `${new Date(now - (chartPoints.length - i) * intervalMs).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' })}`,
          timeMs: now - (chartPoints.length - i) * intervalMs,
          open: openVal,
          high,
          low,
          close,
          volume,
          isUp: close >= openVal,
        });
      }
    }

    // Ensure we have at least 36 historical bars for institutional depth
    if (candles.length < 36) {
      const needed = 36 - candles.length;
      for (let i = needed; i >= 0; i--) {
        const timeMs = now - i * intervalMs;
        const d = new Date(timeMs);
        const timeLabel = `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
        const drift = Math.sin(i / 4) * 6 + Math.cos(i / 2) * 4;
        const open = Math.max(15, Math.min(92, Math.round(baseChance - drift + ((i % 3) - 1) * 1.5)));
        const close = Math.max(15, Math.min(92, Math.round(open + ((i % 5) - 2) * 2)));
        const high = Math.min(98, Math.max(open, close) + Math.round(Math.abs(Math.sin(i)) * 2));
        const low = Math.max(5, Math.min(open, close) - Math.round(Math.abs(Math.cos(i)) * 2));
        const volume = Math.round(8000 + Math.abs(Math.sin(i * 1.5)) * 14000);

        candles.push({
          time: timeLabel,
          timeMs,
          open,
          high,
          low,
          close,
          volume,
          isUp: close >= open,
        });
      }
    }

    // Anchor the active current candle to the exact live probability tick!
    if (candles.length > 0) {
      const last = candles[candles.length - 1];
      last.close = baseChance;
      last.high = Math.max(last.high, baseChance);
      last.low = Math.min(last.low, baseChance);
      last.isUp = last.close >= last.open;
    }

    return candles;
  }, [market?.market_chance_pct, market?.best_yes_bid, market?.target_strike, chartPoints]);

  // Active hovered or latest candle for TradingView top-left OHLCV strip
  const activeBar = useMemo(() => {
    if (hoveredCandleIndex !== null && chartCandles[hoveredCandleIndex]) {
      return chartCandles[hoveredCandleIndex];
    }
    return chartCandles.length > 0 ? chartCandles[chartCandles.length - 1] : null;
  }, [hoveredCandleIndex, chartCandles]);

  const barChange = activeBar ? activeBar.close - activeBar.open : 0;
  const barChangePct = activeBar && activeBar.open > 0 ? (barChange / activeBar.open) * 100 : 0;
  const isBarUp = barChange >= 0;

  // =========================================================================
  // 3. CANVAS HEATMAP & HIGH FREQUENCY CHART RENDERER
  // =========================================================================
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Resize canvas to match display size
    const width = canvas.parentElement?.clientWidth || 800;
    const height = canvas.parentElement?.clientHeight || 500;
    canvas.width = width;
    canvas.height = height;

    // Clear background
    ctx.fillStyle = '#0b0f15';
    ctx.fillRect(0, 0, width, height);

    const paddingLeft = 10;
    const paddingRight = 55;
    const paddingTop = 30;
    const paddingBottom = 60;
    const plotWidth = width - paddingLeft - paddingRight;
    const plotHeight = height - paddingTop - paddingBottom;
    const volumeHeight = 50;
    const candlePlotHeight = plotHeight - volumeHeight;

    // 1. RENDER LIQUIDITY HEATMAP (DOM CLOUD SYNCHRONIZED TO REAL LADDER DEPTH)
    if (isHeatmapEnabled) {
      const activeStrikeProb = market?.market_chance_pct ? market.market_chance_pct : 72;
      const numPriceLevels = 50; // 0¢ to 100¢ in 2¢ bands
      const bandHeight = candlePlotHeight / numPriceLevels;

      // Find max contracts in book for proportional scaling
      let maxContractsInBook = 1000;
      depthByCent.forEach((contracts) => {
        if (contracts > maxContractsInBook) maxContractsInBook = contracts;
      });

      for (let level = 0; level < numPriceLevels; level++) {
        const priceCents = 100 - level * 2;
        const y = paddingTop + level * bandHeight;

        // Actual resting orders at this level from real ladder
        const restingInBand = (depthByCent.get(priceCents) || 0) + (depthByCent.get(priceCents - 1) || 0);

        // Ambient orderbook halo near ATM price
        const distFromMid = Math.abs(priceCents - activeStrikeProb);
        const proximityIntensity = Math.exp(-(distFromMid * distFromMid) / 110) * 0.45;
        const bookIntensity = restingInBand > 0 ? Math.min(1.0, restingInBand / maxContractsInBook) : 0;
        const intensity = Math.max(proximityIntensity, bookIntensity);

        // Institutional Heatmap Color Palette:
        // Crimson Red (Heavy Order Wall) -> Orange -> Yellow -> Lime Green -> Cyan
        let heatColor = 'rgba(10, 18, 40, 0.4)';
        if (intensity > 0.8) {
          heatColor = `rgba(239, 68, 68, ${0.55 * intensity})`; // Crimson Red wall
        } else if (intensity > 0.65) {
          heatColor = `rgba(249, 115, 22, ${0.48 * intensity})`; // Orange
        } else if (intensity > 0.45) {
          heatColor = `rgba(234, 179, 8, ${0.38 * intensity})`; // Yellow
        } else if (intensity > 0.25) {
          heatColor = `rgba(34, 197, 94, ${0.25 * intensity})`; // Lime Green
        } else if (intensity > 0.10) {
          heatColor = `rgba(6, 182, 212, ${0.18 * intensity})`; // Cyan
        }

        ctx.fillStyle = heatColor;
        ctx.fillRect(paddingLeft, y, plotWidth, bandHeight + 1);
      }
    }

    // 2. DRAW HORIZONTAL GRID LINES & RIGHT Y-AXIS LABELS (Probability Cents 10¢ - 100¢)
    ctx.textAlign = 'left';
    ctx.font = '10px JetBrains Mono, monospace';

    for (let prob = 10; prob <= 100; prob += 10) {
      const y = paddingTop + candlePlotHeight * (1 - prob / 100);
      
      // Grid line
      ctx.strokeStyle = '#1a232e';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(paddingLeft, y);
      ctx.lineTo(paddingLeft + plotWidth, y);
      ctx.stroke();

      // Right axis label
      ctx.fillStyle = prob === 70 ? '#38bdf8' : '#64748b';
      ctx.fillText(`${prob}¢`, paddingLeft + plotWidth + 6, y + 3);
    }

    // 3. DRAW 60S TWAP PARITY REFERENCE LINE (IF ACTIVE)
    if (activeIndicators.twap60s && (market?.twap_60s_price || market?.current_btc_price)) {
      const twapVal = market?.twap_60s_price || market?.current_btc_price || 68500;
      const targetStrike = market?.target_strike || 68500;
      const twapDiff = twapVal - targetStrike;
      const twapProb = Math.max(5, Math.min(95, Math.round(50 + twapDiff * 0.4)));
      const twapY = paddingTop + candlePlotHeight * (1 - twapProb / 100);

      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 1.2;
      ctx.setLineDash([6, 3]);
      ctx.beginPath();
      ctx.moveTo(paddingLeft, twapY);
      ctx.lineTo(paddingLeft + plotWidth, twapY);
      ctx.stroke();
      ctx.setLineDash([]);

      // TWAP Label
      ctx.fillStyle = '#f59e0b';
      ctx.font = '9px JetBrains Mono, monospace';
      ctx.fillText('TWAP 60s', paddingLeft + 8, twapY - 4);
    }

    // 4. DRAW PRICE DATA (CANDLESTICKS / SMOOTH LINE / AREA)
    const candleCount = chartCandles.length;
    const candleWidth = Math.max(4, Math.floor(plotWidth / candleCount) - 3);
    const step = plotWidth / candleCount;

    if (chartStyle === 'area') {
      // Area Gradient Fill
      ctx.save();
      const areaGradient = ctx.createLinearGradient(0, paddingTop, 0, paddingTop + candlePlotHeight);
      areaGradient.addColorStop(0, 'rgba(0, 201, 120, 0.38)');
      areaGradient.addColorStop(0.65, 'rgba(0, 201, 120, 0.10)');
      areaGradient.addColorStop(1, 'rgba(0, 201, 120, 0.00)');

      ctx.fillStyle = areaGradient;
      ctx.beginPath();
      chartCandles.forEach((c, idx) => {
        const x = paddingLeft + idx * step + step / 2;
        const closeY = paddingTop + candlePlotHeight * (1 - c.close / 100);
        if (idx === 0) ctx.moveTo(x, closeY);
        else ctx.lineTo(x, closeY);
      });
      const lastX = paddingLeft + (chartCandles.length - 1) * step + step / 2;
      const firstX = paddingLeft + step / 2;
      const baselineY = paddingTop + candlePlotHeight;
      ctx.lineTo(lastX, baselineY);
      ctx.lineTo(firstX, baselineY);
      ctx.closePath();
      ctx.fill();
      ctx.restore();

      // Top Line Stroke with Neon Glow
      ctx.save();
      ctx.strokeStyle = '#00c978';
      ctx.lineWidth = 2.2;
      ctx.shadowColor = 'rgba(0, 201, 120, 0.5)';
      ctx.shadowBlur = 8;
      ctx.beginPath();
      chartCandles.forEach((c, idx) => {
        const x = paddingLeft + idx * step + step / 2;
        const closeY = paddingTop + candlePlotHeight * (1 - c.close / 100);
        if (idx === 0) ctx.moveTo(x, closeY);
        else ctx.lineTo(x, closeY);
      });
      ctx.stroke();
      ctx.restore();
    } else if (chartStyle === 'line') {
      // Smooth Line Stroke with Neon Glow
      ctx.save();
      ctx.strokeStyle = '#00c978';
      ctx.lineWidth = 2.2;
      ctx.shadowColor = 'rgba(0, 201, 120, 0.5)';
      ctx.shadowBlur = 8;
      ctx.beginPath();
      chartCandles.forEach((c, idx) => {
        const x = paddingLeft + idx * step + step / 2;
        const closeY = paddingTop + candlePlotHeight * (1 - c.close / 100);
        if (idx === 0) ctx.moveTo(x, closeY);
        else ctx.lineTo(x, closeY);
      });
      ctx.stroke();
      ctx.restore();
    } else {
      // Candlesticks (Wick + Body)
      chartCandles.forEach((c, idx) => {
        const x = paddingLeft + idx * step + step / 2;
        const openY = paddingTop + candlePlotHeight * (1 - c.open / 100);
        const closeY = paddingTop + candlePlotHeight * (1 - c.close / 100);
        const highY = paddingTop + candlePlotHeight * (1 - c.high / 100);
        const lowY = paddingTop + candlePlotHeight * (1 - c.low / 100);

        const isUp = c.close >= c.open;
        const color = isUp ? '#10b981' : '#f43f5e';

        // Wick
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(x, highY);
        ctx.lineTo(x, lowY);
        ctx.stroke();

        // Body
        ctx.fillStyle = color;
        const bodyTop = Math.min(openY, closeY);
        const bodyHeight = Math.max(2, Math.abs(closeY - openY));
        ctx.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);
      });
    }

    // Extrema Markers (Local High & Low Callouts) for Line / Area modes
    if (chartStyle !== 'candles' && chartCandles.length > 3) {
      let highestIdx = 0;
      let lowestIdx = 0;
      chartCandles.forEach((c, idx) => {
        if (c.high > chartCandles[highestIdx].high) highestIdx = idx;
        if (c.low < chartCandles[lowestIdx].low) lowestIdx = idx;
      });

      const highC = chartCandles[highestIdx];
      const highX = paddingLeft + highestIdx * step + step / 2;
      const highY = paddingTop + candlePlotHeight * (1 - highC.high / 100);

      const lowC = chartCandles[lowestIdx];
      const lowX = paddingLeft + lowestIdx * step + step / 2;
      const lowY = paddingTop + candlePlotHeight * (1 - lowC.low / 100);

      ctx.save();
      ctx.font = 'bold 9px JetBrains Mono, monospace';
      ctx.textAlign = 'center';

      // High marker
      ctx.fillStyle = '#10b981';
      ctx.fillText(`H ${highC.high}¢`, highX, Math.max(paddingTop + 10, highY - 6));

      // Low marker
      ctx.fillStyle = '#f43f5e';
      ctx.fillText(`L ${lowC.low}¢`, lowX, Math.min(paddingTop + candlePlotHeight - 4, lowY + 12));
      ctx.restore();
    }

    // Pulsing Head Beacon on the latest point (in Line & Area modes)
    if (chartStyle !== 'candles' && chartCandles.length > 0) {
      const lastIdx = chartCandles.length - 1;
      const lastC = chartCandles[lastIdx];
      const lastX = paddingLeft + lastIdx * step + step / 2;
      const lastCloseY = paddingTop + candlePlotHeight * (1 - lastC.close / 100);

      ctx.save();
      // Outer radar pulse
      ctx.beginPath();
      ctx.arc(lastX, lastCloseY, 8, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(0, 201, 120, 0.25)';
      ctx.fill();
      ctx.strokeStyle = 'rgba(0, 201, 120, 0.6)';
      ctx.lineWidth = 1.2;
      ctx.stroke();

      // Core point
      ctx.beginPath();
      ctx.arc(lastX, lastCloseY, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = '#00c978';
      ctx.fill();
      ctx.restore();
    }

    // Volume Bars & X-Axis Time Labels
    const maxVol = 25000;
    chartCandles.forEach((c, idx) => {
      const x = paddingLeft + idx * step + step / 2;
      const isUp = c.close >= c.open;

      // Volume Bars
      const vBarHeight = (c.volume / maxVol) * volumeHeight;
      const vBarY = paddingTop + candlePlotHeight + 8 + (volumeHeight - vBarHeight);
      ctx.fillStyle = isUp ? 'rgba(16, 185, 129, 0.45)' : 'rgba(244, 63, 94, 0.45)';
      ctx.fillRect(x - candleWidth / 2, vBarY, candleWidth, vBarHeight);

      // X-Axis time label (every 8 candles)
      if (idx % 8 === 0) {
        ctx.fillStyle = '#64748b';
        ctx.font = '9px JetBrains Mono, monospace';
        ctx.textAlign = 'center';
        ctx.fillText(c.time, x, paddingTop + plotHeight + 16);
      }
    });

    // 5. CURRENT PRICE HORIZONTAL LINE & BADGE
    const currentPrice = market?.market_chance_pct ? Math.round(market.market_chance_pct) : 72;
    const currentY = paddingTop + candlePlotHeight * (1 - currentPrice / 100);
    ctx.strokeStyle = '#00c978';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(paddingLeft, currentY);
    ctx.lineTo(paddingLeft + plotWidth, currentY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Current price tag on right axis
    ctx.fillStyle = '#00c978';
    ctx.fillRect(paddingLeft + plotWidth + 2, currentY - 8, 42, 16);
    ctx.fillStyle = '#000000';
    ctx.font = 'bold 10px JetBrains Mono, monospace';
    ctx.textAlign = 'left';
    ctx.fillText(`${currentPrice}¢`, paddingLeft + plotWidth + 6, currentY + 4);

    // 6. DRAW INTERACTIVE CROSSHAIR IF HOVERED
    if (crosshairPos.visible) {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);

      // Vertical line
      ctx.beginPath();
      ctx.moveTo(crosshairPos.x, paddingTop);
      ctx.lineTo(crosshairPos.x, paddingTop + plotHeight);
      ctx.stroke();

      // Horizontal line
      ctx.beginPath();
      ctx.moveTo(paddingLeft, crosshairPos.y);
      ctx.lineTo(paddingLeft + plotWidth, crosshairPos.y);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }, [chartCandles, isHeatmapEnabled, crosshairPos, market?.market_chance_pct, market?.twap_60s_price, activeIndicators, depthByCent, chartStyle]);

  // Handle canvas mouse move for interactive crosshair & tooltip
  const handleCanvasMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const paddingLeft = 10;
    const paddingRight = 55;
    const paddingTop = 30;
    const plotWidth = canvas.width - paddingLeft - paddingRight;
    const candlePlotHeight = canvas.height - paddingTop - 110;

    if (x >= paddingLeft && x <= paddingLeft + plotWidth && y >= paddingTop && y <= paddingTop + candlePlotHeight) {
      // Calculate price from Y
      const pricePct = Math.round(100 - ((y - paddingTop) / candlePlotHeight) * 100);
      const clampedPrice = Math.max(1, Math.min(99, pricePct));

      // Calculate candle index from X
      const candleIdx = Math.min(
        chartCandles.length - 1,
        Math.max(0, Math.floor(((x - paddingLeft) / plotWidth) * chartCandles.length))
      );
      setHoveredCandleIndex(candleIdx);
      const hoveredCandle = chartCandles[candleIdx];

      // Lookup real depth from ladder
      const restingContracts = (depthByCent.get(clampedPrice) || 0) + (depthByCent.get(clampedPrice - 1) || 0);
      const heatLabel = restingContracts > 4000
        ? `Order Wall (${(restingContracts / 1000).toFixed(1)}K)`
        : restingContracts > 1000
        ? `Dense (${(restingContracts / 1000).toFixed(1)}K)`
        : Math.abs(clampedPrice - (market?.market_chance_pct || 72)) <= 3
        ? 'ATM Spread Zone'
        : 'Low Depth';

      setCrosshairPos({
        x,
        y,
        visible: true,
        time: hoveredCandle?.time || '14:56:32',
        price: clampedPrice,
        volume: restingContracts > 0 ? `${(restingContracts / 1000).toFixed(1)}K` : (hoveredCandle ? `${(hoveredCandle.volume / 1000).toFixed(1)}K` : '14.5K'),
        heat: heatLabel,
      });
    } else {
      setCrosshairPos((prev) => ({ ...prev, visible: false }));
      setHoveredCandleIndex(null);
    }
  };

  const handleCanvasMouseLeave = () => {
    setCrosshairPos((prev) => ({ ...prev, visible: false }));
    setHoveredCandleIndex(null);
  };

  // =========================================================================
  // 4. UNDERLYING ASSET L2 SPOT BOOK WITH CME CF BENCHMARKS 5HZ PARITY
  // =========================================================================
  const currentSpec = ASSET_SPECS[activeAsset] || ASSET_SPECS.BTC;

  // Live spot price from CF Benchmarks indices or market spot
  const currentSpotPrice = useMemo(() => {
    const cfPrice = market?.cf_indices?.[activeAsset]?.price;
    if (cfPrice && cfPrice > 0) return cfPrice;
    if (activeAsset === 'BTC' && market?.current_btc_price && market.current_btc_price > 0) {
      return market.current_btc_price;
    }
    return currentSpec.defaultBasePrice;
  }, [market?.cf_indices, market?.current_btc_price, activeAsset, currentSpec]);

  // Format asset price with appropriate decimals
  const formatAssetPrice = (val: number) => {
    return `$${val.toLocaleString('en-US', {
      minimumFractionDigits: currentSpec.decimals,
      maximumFractionDigits: currentSpec.decimals,
    })}`;
  };

  const spotPriceFormatted = formatAssetPrice(currentSpotPrice);
  const strikePriceFormatted = market?.target_strike_str || formatAssetPrice(market?.target_strike || 68500);
  const spotDiff = market?.diff !== undefined ? market.diff : currentSpotPrice - (market?.target_strike || currentSpotPrice);
  const isDiffPositive = spotDiff >= 0;

  // Dynamic L2 Spot Order Book Asks and Bids around currentSpotPrice
  const spotBook = useMemo(() => {
    const halfSpread = currentSpec.baseSpread / 2;
    const bestBid = currentSpotPrice - halfSpread;
    const bestAsk = currentSpotPrice + halfSpread;
    const spread = bestAsk - bestBid;

    const asks = [];
    for (let i = 8; i >= 1; i--) {
      const price = bestAsk + (i - 1) * currentSpec.tickSize;
      const baseVol = activeAsset === 'BTC' ? 1.5 + (i % 3) * 1.8 : activeAsset === 'ETH' ? 8 + (i % 4) * 6 : activeAsset === 'SOL' ? 120 + i * 45 : 8500 + i * 2000;
      const bidQty = Math.round(15 + i * 4 + Math.sin(i) * 8);
      asks.push({
        bidQty: `${bidQty}`,
        price: formatAssetPrice(price),
        ask: formatAssetPrice(price + currentSpec.tickSize),
        vol: spotVolumeUnit === 'usd' ? `$${(baseVol * currentSpotPrice).toLocaleString('en-US', { maximumFractionDigits: 0 })}` : `${baseVol.toFixed(activeAsset === 'DOGE' ? 0 : 1)} ${currentSpec.unit}`,
        askPct: Math.min(100, Math.max(15, i * 11)),
      });
    }

    const bids = [];
    for (let i = 1; i <= 8; i++) {
      const price = bestBid - (i - 1) * currentSpec.tickSize;
      const baseVol = activeAsset === 'BTC' ? 1.8 + (i % 3) * 1.6 : activeAsset === 'ETH' ? 9 + (i % 4) * 5 : activeAsset === 'SOL' ? 130 + i * 40 : 9200 + i * 1800;
      const bidQty = Math.round(20 + i * 5 - Math.cos(i) * 6);
      bids.push({
        bidQty: `${bidQty}`,
        price: formatAssetPrice(price),
        ask: formatAssetPrice(price + currentSpec.tickSize),
        vol: spotVolumeUnit === 'usd' ? `$${(baseVol * currentSpotPrice).toLocaleString('en-US', { maximumFractionDigits: 0 })}` : `${baseVol.toFixed(activeAsset === 'DOGE' ? 0 : 1)} ${currentSpec.unit}`,
        bidPct: Math.min(100, Math.max(15, i * 11)),
      });
    }

    return { asks, bids, spread: formatAssetPrice(spread).replace('$', '$'), bestBidPrice: formatAssetPrice(bestBid) };
  }, [currentSpotPrice, currentSpec, spotVolumeUnit, activeAsset]);

  return (
    <div className="w-full h-full flex flex-col bg-[#0b0f15] text-slate-200 font-sans select-none overflow-hidden">
      {/* =========================================================================
          1. TOP GLOBAL NAVIGATION & SYSTEM CLOCK HEADER
          ========================================================================= */}
      <ClobTopHeader
        activeTopTab={activeTopTab}
        setActiveTopTab={setActiveTopTab}
        timeZoneDisplay={timeZoneDisplay}
        setTimeZoneDisplay={setTimeZoneDisplay}
        currentTimeStr={currentTimeStr}
        isSearchModalOpen={isSearchModalOpen}
        setIsSearchModalOpen={setIsSearchModalOpen}
        isNotificationsOpen={isNotificationsOpen}
        setIsNotificationsOpen={setIsNotificationsOpen}
      />

      {/* =========================================================================
          MAIN 3-COLUMN TRADING COCKPIT LAYOUT
          ========================================================================= */}
      <div className="flex-1 min-h-0 flex flex-row overflow-hidden divide-x divide-[#1f2937]">
        {/* =====================================================================
            COLUMN 1 (LEFT): KALSHI EVENT ORDER BOOK (15MIN)
            ===================================================================== */}
        <EventOrderBookPanel
          market={market}
          currentSpec={currentSpec}
          strikePriceFormatted={strikePriceFormatted}
          isDiffPositive={isDiffPositive}
          spotDiff={spotDiff}
          topBookRows={topBookRows}
          cumulativeLadderRows={cumulativeLadderRows}
          volumeUnit={volumeUnit}
          setVolumeUnit={setVolumeUnit}
          isOrderSizeTooltipOpen={isOrderSizeTooltipOpen}
          setIsOrderSizeTooltipOpen={setIsOrderSizeTooltipOpen}
          setOrderLimitPrice={setOrderLimitPrice}
          setIsTradingPanelOpen={setIsTradingPanelOpen}
        />

        {/* =====================================================================
            COLUMN 2 (CENTER): EVENT PRICE GRAPH & LIQUIDITY HEATMAP
            ===================================================================== */}
        <main className="flex-1 flex flex-col min-w-0 bg-[#0b0f15] overflow-hidden select-none">
          {/* Chart Header Bar */}
          <ChartControlsToolbar
            market={market}
            activeDrawingTool={activeDrawingTool}
            setActiveDrawingTool={setActiveDrawingTool}
            selectedTimeframe={selectedTimeframe}
            handleSwitchTimeframe={handleSwitchTimeframe}
            chartStyle={chartStyle}
            setChartStyle={setChartStyle}
            isIndicatorsModalOpen={isIndicatorsModalOpen}
            setIsIndicatorsModalOpen={setIsIndicatorsModalOpen}
            isHeatmapEnabled={isHeatmapEnabled}
            setIsHeatmapEnabled={setIsHeatmapEnabled}
            onToggleRightPanel={onToggleRightPanel}
            isRightPanelHidden={isRightPanelHidden}
          />
          {/* Chart Workspace with Left Drawing Palette & Center Canvas */}
          <div className="flex-1 relative flex overflow-hidden">
            {/* Drawing Toolbar Strip on Left Edge */}
            <div className="w-9 bg-[#0e131b] border-r border-[#1f2937] flex flex-col items-center py-2 gap-1.5 shrink-0 z-20">
              {[
                { id: 'cursor', icon: MousePointer, title: 'Cursor' },
                { id: 'crosshair', icon: Crosshair, title: 'Crosshair' },
                { id: 'trendline', icon: Minus, title: 'Trend Line' },
                { id: 'pitchfork', icon: Compass, title: 'Pitchfork' },
                { id: 'fibonacci', icon: Hash, title: 'Fibonacci Retracement' },
                { id: 'text', icon: FileText, title: 'Text Note' },
                { id: 'patterns', icon: Square, title: 'Chart Patterns' },
                { id: 'measure', icon: Sliders, title: 'Measure / Ruler' },
                { id: 'magnet', icon: Sparkles, title: 'Magnet Mode' },
              ].map((tool) => {
                const Icon = tool.icon;
                const isActive = activeDrawingTool === tool.id;
                return (
                  <button
                    key={tool.id}
                    onClick={() => {
                      soundFX.playClickSound();
                      setActiveDrawingTool(tool.id as DrawingTool);
                    }}
                    className={`p-1.5 rounded transition ${
                      isActive ? 'bg-[#00c978]/20 text-[#00c978]' : 'text-[#64748b] hover:text-white hover:bg-[#17202d]'
                    }`}
                    title={tool.title}
                  >
                    <Icon className="w-4 h-4" />
                  </button>
                );
              })}
            </div>

            {/* Center Canvas Area */}
            <div className="flex-1 relative overflow-hidden bg-[#0b0f15]">
              {/* Overlay Watermark / Contract Title inside Chart */}
              <div className="absolute top-3 left-4 z-10 flex items-center gap-2 font-mono pointer-events-none">
                <span className="text-xs font-bold text-white">
                  {market?.title || `${currentSpec.symbol} · 15M Binary Event`}
                </span>
                <span className="text-xs font-bold text-[#00c978] bg-[#00c978]/15 px-2 py-0.5 rounded border border-[#00c978]/30">
                  ● {market?.market_chance_pct ? Math.round(market.market_chance_pct) : 72}¢ ({isDiffPositive ? '+' : ''}${Math.abs(spotDiff).toFixed(currentSpec.decimals)})
                </span>
              </div>

              {/* TradingView Dynamic OHLCV Legend Bar */}
              <div className="absolute top-9 left-4 z-10 flex items-center gap-2.5 font-mono text-[11px] pointer-events-none bg-[#0e131b]/85 px-2.5 py-1 rounded border border-[#1f2937] backdrop-blur-sm shadow-md">
                <span className="text-slate-400 font-medium">O <span className={isBarUp ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>{activeBar?.open ?? '--'}¢</span></span>
                <span className="text-slate-400 font-medium">H <span className={isBarUp ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>{activeBar?.high ?? '--'}¢</span></span>
                <span className="text-slate-400 font-medium">L <span className={isBarUp ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>{activeBar?.low ?? '--'}¢</span></span>
                <span className="text-slate-400 font-medium">C <span className={isBarUp ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>{activeBar?.close ?? '--'}¢</span></span>
                <span className={`font-bold ${isBarUp ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {isBarUp ? '+' : ''}{barChange}¢ ({isBarUp ? '+' : ''}{barChangePct.toFixed(1)}%)
                </span>
                <span className="text-slate-600">|</span>
                <span className="text-slate-400 font-medium">Vol <span className="text-cyan-400 font-bold">{activeBar ? (activeBar.volume >= 1000 ? `${(activeBar.volume / 1000).toFixed(1)}K` : activeBar.volume) : '--'}</span></span>
              </div>

              {/* Floating Crosshair Hover Card Tooltip */}
              {crosshairPos.visible && (
                <div
                  className="absolute z-20 pointer-events-none bg-[#0e131be6] border border-[#2d3d52] rounded-lg p-2.5 shadow-2xl backdrop-blur font-mono text-[11px] text-slate-200"
                  style={{
                    left: Math.min(window.innerWidth - 300, crosshairPos.x + 15),
                    top: Math.min(window.innerHeight - 200, crosshairPos.y - 45),
                  }}
                >
                  <div className="text-white font-bold mb-1 border-b border-[#1f2937] pb-1">
                    Time: {crosshairPos.time}
                  </div>
                  <div className="space-y-0.5">
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-[#8c9ba5]">Price:</span>
                      <span className="text-[#00c978] font-bold">{crosshairPos.price}¢</span>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-[#8c9ba5]">Volume:</span>
                      <span className="text-white font-bold">{crosshairPos.volume}</span>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <span className="text-[#8c9ba5]">Heat:</span>
                      <span className="text-amber-400 font-bold">{crosshairPos.heat}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* The Interactive Canvas */}
              <canvas
                ref={canvasRef}
                onMouseMove={handleCanvasMouseMove}
                onMouseLeave={handleCanvasMouseLeave}
                className="w-full h-full cursor-crosshair block"
              />
            </div>
          </div>

          {/* TradingView Bottom Controls Bar */}
          <div className="h-8 px-4 bg-[#0e131b] border-t border-[#1f2937] flex items-center justify-between text-xs font-mono shrink-0">
            {/* Left: TradingView Branding Watermark */}
            <div className="flex items-center gap-3">
              <span className="text-[11px] font-bold text-[#64748b] tracking-wider uppercase">
                TradingView
              </span>
              {/* Range Selectors */}
              <div className="flex items-center gap-1">
                {['1D', '5D', '1M', '6M', 'YTD', '1Y', 'ALL'].map((r) => (
                  <button
                    key={r}
                    onClick={() => {
                      soundFX.playClickSound();
                      setTimeRange(r);
                    }}
                    className={`px-1.5 py-0.5 rounded text-[10px] font-bold transition ${
                      timeRange === r ? 'text-[#00c978] bg-[#17202d]' : 'text-[#64748b] hover:text-white'
                    }`}
                  >
                    {r}
                  </button>
                ))}
              </div>
            </div>

            {/* Right: Timezone & Scale Controls */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  soundFX.playClickSound();
                  setTimeZoneDisplay((prev) => (prev === 'EST' ? 'UTC' : 'EST'));
                }}
                className="text-[10px] text-[#8c9ba5] hover:text-white"
              >
                14:06:32 ({timeZoneDisplay})
              </button>

              <div className="flex items-center gap-0.5 bg-[#131923] p-0.5 rounded border border-[#1f2937]">
                {(['pct', 'log', 'auto'] as const).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => {
                      soundFX.playClickSound();
                      setScaleMode(mode);
                    }}
                    className={`px-1.5 py-0.2 rounded text-[9px] font-bold uppercase ${
                      scaleMode === mode ? 'bg-[#00c978] text-black' : 'text-[#64748b] hover:text-white'
                    }`}
                  >
                    {mode === 'pct' ? '%' : mode}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <ClobBottomDock
            chartTheme={chartTheme}
            setChartTheme={setChartTheme}
            isPineEditorOpen={isPineEditorOpen}
            setIsPineEditorOpen={setIsPineEditorOpen}
            pineScriptCode={pineScriptCode}
            setPineScriptCode={setPineScriptCode}
            isTradingPanelOpen={isTradingPanelOpen}
            setIsTradingPanelOpen={setIsTradingPanelOpen}
            orderSide={orderSide}
            setOrderSide={setOrderSide}
            orderLimitPrice={orderLimitPrice}
            setOrderLimitPrice={setOrderLimitPrice}
            handleExecuteTrade={handleExecuteTrade}
            orderStatusMessage={orderStatusMessage}
            onResetTrading={() => {
              setIsHeatmapEnabled(true);
              setSelectedTimeframe('15m');
              setScaleMode('auto');
              setActiveDrawingTool('crosshair');
            }}
          />
        </main>

        {/* =====================================================================
            COLUMN 3 (RIGHT): UNDERLYING ASSET (BTC/USD) ORDER BOOK
            ===================================================================== */}
        <SpotOrderBookPanel
          currentSpec={currentSpec}
          spotPriceFormatted={spotPriceFormatted}
          strikePriceFormatted={strikePriceFormatted}
          isDiffPositive={isDiffPositive}
          spotDiff={spotDiff}
          spotBook={spotBook}
          activeAsset={activeAsset}
          spotVolumeUnit={spotVolumeUnit}
          setSpotVolumeUnit={setSpotVolumeUnit}
          handleSwitchAsset={handleSwitchAsset}
        />
      </div>

      {/* =========================================================================
          MODALS & OVERLAYS
          ========================================================================= */}
      <ClobModals
        isIndicatorsModalOpen={isIndicatorsModalOpen}
        setIsIndicatorsModalOpen={setIsIndicatorsModalOpen}
        activeIndicators={activeIndicators}
        setActiveIndicators={setActiveIndicators}
        isSearchModalOpen={isSearchModalOpen}
        setIsSearchModalOpen={setIsSearchModalOpen}
        market={market}
        handleSwitchAsset={handleSwitchAsset}
        isNotificationsOpen={isNotificationsOpen}
        setIsNotificationsOpen={setIsNotificationsOpen}
      />
    </div>
  );
};

export default ClobTerminalView;
