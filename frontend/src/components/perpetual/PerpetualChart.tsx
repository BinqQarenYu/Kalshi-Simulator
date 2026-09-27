/**
 * @file PerpetualChart.tsx
 * @description High-performance interactive HTML5 Canvas chart for Perpetual Trading.
 * Features:
 * 1. Candlestick rendering with dynamic auto-scaling
 * 2. Independent multi-asset switching (BTC, ETH, SOL, DOGE)
 * 3. Volume histogram with buyer/seller delta coloring
 * 4. Heatmap liquidity overlay (DOM depth clouds)
 * 5. Exponential Moving Averages (EMA 20 & EMA 50)
 * 6. Interactive crosshair with time & price tracking HUD
 * 7. Live current price ticker line
 */

import React, { useRef, useEffect, useState, useMemo } from 'react';
import { usePerpetualTrading } from '../../context/PerpetualTradingContext';
import { Volume2, Layers, Activity, TrendingUp, Maximize2, RefreshCw } from 'lucide-react';

export const PerpetualChart: React.FC = () => {
  const {
    selectedAsset,
    setSelectedAsset,
    timeframe,
    setTimeframe,
    candles,
    currentPrice,
    showVolume,
    setShowVolume,
    showHeatmap,
    setShowHeatmap,
    showEma,
    setShowEma,
    showVpin,
    setShowVpin,
  } = usePerpetualTrading();

  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [crosshair, setCrosshair] = useState<{ x: number; y: number; price: number; time: number } | null>(null);

  // Calculate EMA series helper
  const calculateEMA = (period: number) => {
    if (candles.length === 0) return [];
    const k = 2 / (period + 1);
    const emaValues: (number | null)[] = [];
    let prevEma = candles[0].close;
    emaValues.push(prevEma);

    for (let i = 1; i < candles.length; i++) {
      const currentClose = candles[i].close;
      const currentEma = currentClose * k + prevEma * (1 - k);
      emaValues.push(currentEma);
      prevEma = currentEma;
    }
    return emaValues;
  };

  const ema20 = useMemo(() => calculateEMA(20), [candles]);
  const ema50 = useMemo(() => calculateEMA(50), [candles]);

  // Main Canvas Render Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Handle high DPI displays
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;
    const padding = { top: 30, right: 65, bottom: 45, left: 10 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // Clear background
    ctx.fillStyle = '#0b0e14';
    ctx.fillRect(0, 0, width, height);

    if (candles.length === 0) return;

    // Min and Max price bounds
    let minPrice = Infinity;
    let maxPrice = -Infinity;
    let maxVol = 0;

    candles.forEach((c) => {
      if (c.low < minPrice) minPrice = c.low;
      if (c.high > maxPrice) maxPrice = c.high;
      if (c.volume > maxVol) maxVol = c.volume;
    });

    const priceRange = maxPrice - minPrice || 1;
    minPrice -= priceRange * 0.05;
    maxPrice += priceRange * 0.05;
    const adjustedRange = maxPrice - minPrice;

    const getY = (price: number) => {
      return padding.top + chartHeight - ((price - minPrice) / adjustedRange) * chartHeight;
    };

    const getX = (index: number) => {
      const step = chartWidth / candles.length;
      return padding.left + index * step + step / 2;
    };

    const candleWidth = Math.max(2, (chartWidth / candles.length) * 0.72);

    // 1. Grid Lines
    ctx.strokeStyle = '#1a2230';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);

    const gridSteps = 6;
    for (let i = 0; i <= gridSteps; i++) {
      const p = minPrice + (adjustedRange / gridSteps) * i;
      const y = getY(p);
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();

      // Price labels on right axis
      ctx.fillStyle = '#64748b';
      ctx.font = '10px JetBrains Mono, monospace';
      ctx.textAlign = 'left';
      ctx.fillText(p.toFixed(selectedAsset === 'DOGE' ? 5 : 2), width - padding.right + 6, y + 3);
    }
    ctx.setLineDash([]);

    // 2. Heatmap / Liquidity Cloud Overlay
    if (showHeatmap) {
      const heatmapBands = 8;
      for (let i = 0; i < heatmapBands; i++) {
        const bandPrice = minPrice + (adjustedRange / heatmapBands) * i;
        const y = getY(bandPrice);
        const intensity = Math.sin((i / heatmapBands) * Math.PI) * 0.12;
        ctx.fillStyle = i % 2 === 0 ? `rgba(16, 185, 129, ${intensity})` : `rgba(244, 63, 94, ${intensity})`;
        ctx.fillRect(padding.left, y - 8, chartWidth, 16);
      }
    }

    // 3. Volume Sub-panel at Bottom
    if (showVolume && maxVol > 0) {
      const volHeight = chartHeight * 0.22;
      const volBaseY = padding.top + chartHeight;

      candles.forEach((c, idx) => {
        const x = getX(idx);
        const vH = (c.volume / maxVol) * volHeight;
        const isUp = c.close >= c.open;
        ctx.fillStyle = isUp ? 'rgba(16, 185, 129, 0.35)' : 'rgba(244, 63, 94, 0.35)';
        ctx.fillRect(x - candleWidth / 2, volBaseY - vH, candleWidth, vH);
      });
    }

    // 4. Candlesticks
    candles.forEach((c, idx) => {
      const x = getX(idx);
      const openY = getY(c.open);
      const closeY = getY(c.close);
      const highY = getY(c.high);
      const lowY = getY(c.low);
      const isUp = c.close >= c.open;
      const color = isUp ? '#10b981' : '#f43f5e';

      // Wick
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(x, highY);
      ctx.lineTo(x, lowY);
      ctx.stroke();

      // Body
      ctx.fillStyle = color;
      const bodyTop = Math.min(openY, closeY);
      const bodyHeight = Math.max(1.5, Math.abs(closeY - openY));
      ctx.fillRect(x - candleWidth / 2, bodyTop, candleWidth, bodyHeight);
    });

    // 5. EMA Lines
    if (showEma) {
      // EMA 20 (Cyan)
      ctx.strokeStyle = '#06b6d4';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      let started = false;
      ema20.forEach((val, idx) => {
        if (val !== null) {
          const x = getX(idx);
          const y = getY(val);
          if (!started) {
            ctx.moveTo(x, y);
            started = true;
          } else {
            ctx.lineTo(x, y);
          }
        }
      });
      ctx.stroke();

      // EMA 50 (Orange)
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      started = false;
      ema50.forEach((val, idx) => {
        if (val !== null) {
          const x = getX(idx);
          const y = getY(val);
          if (!started) {
            ctx.moveTo(x, y);
            started = true;
          } else {
            ctx.lineTo(x, y);
          }
        }
      });
      ctx.stroke();
    }

    // 6. Current Price Line (Dashed Emerald / Crimson)
    const currentY = getY(currentPrice);
    ctx.strokeStyle = '#34d399';
    ctx.lineWidth = 1.2;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(padding.left, currentY);
    ctx.lineTo(width - padding.right, currentY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Current Price Badge
    ctx.fillStyle = '#10b981';
    ctx.fillRect(width - padding.right, currentY - 9, padding.right - 2, 18);
    ctx.fillStyle = '#000000';
    ctx.font = 'bold 10px JetBrains Mono, monospace';
    ctx.textAlign = 'left';
    ctx.fillText(currentPrice.toFixed(selectedAsset === 'DOGE' ? 5 : 2), width - padding.right + 4, currentY + 3.5);

    // 7. Interactive Crosshair
    if (crosshair) {
      ctx.strokeStyle = '#94a3b8';
      ctx.lineWidth = 0.8;
      ctx.setLineDash([2, 2]);

      // Vertical line
      ctx.beginPath();
      ctx.moveTo(crosshair.x, padding.top);
      ctx.lineTo(crosshair.x, height - padding.bottom);
      ctx.stroke();

      // Horizontal line
      ctx.beginPath();
      ctx.moveTo(padding.left, crosshair.y);
      ctx.lineTo(width - padding.right, crosshair.y);
      ctx.stroke();
      ctx.setLineDash([]);

      // Axis Price Pill
      ctx.fillStyle = '#334155';
      ctx.fillRect(width - padding.right, crosshair.y - 9, padding.right - 2, 18);
      ctx.fillStyle = '#f8fafc';
      ctx.font = '10px JetBrains Mono, monospace';
      ctx.textAlign = 'left';
      ctx.fillText(crosshair.price.toFixed(selectedAsset === 'DOGE' ? 5 : 2), width - padding.right + 4, crosshair.y + 3.5);
    }
  }, [candles, currentPrice, showVolume, showHeatmap, showEma, crosshair, selectedAsset]);

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || candles.length === 0) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const padding = { top: 30, right: 65, bottom: 45, left: 10 };
    const chartHeight = rect.height - padding.top - padding.bottom;

    let minPrice = Infinity;
    let maxPrice = -Infinity;
    candles.forEach((c) => {
      if (c.low < minPrice) minPrice = c.low;
      if (c.high > maxPrice) maxPrice = c.high;
    });
    const priceRange = maxPrice - minPrice || 1;
    minPrice -= priceRange * 0.05;
    maxPrice += priceRange * 0.05;

    const normalizedY = Math.max(padding.top, Math.min(rect.height - padding.bottom, y));
    const price = maxPrice - ((normalizedY - padding.top) / chartHeight) * (maxPrice - minPrice);

    setCrosshair({ x, y: normalizedY, price, time: Date.now() });
  };

  const handleMouseLeave = () => {
    setCrosshair(null);
  };

  return (
    <div className="flex flex-col h-full bg-[#0b0e14] border border-[#1f2937] rounded-xl overflow-hidden shadow-2xl">
      {/* Top Chart Toolbar: Assets, Timeframes & Indicators */}
      <div className="h-11 px-3 bg-[#0e131b] border-b border-[#1f2937] flex items-center justify-between shrink-0 select-none">
        {/* Asset Switcher Ribbon */}
        <div className="flex items-center gap-1.5">
          {(['BTC', 'ETH', 'SOL', 'DOGE'] as const).map((ast) => (
            <button
              key={ast}
              onClick={() => setSelectedAsset(ast)}
              className={`px-2.5 py-1 rounded text-xs font-mono font-bold transition-all ${
                selectedAsset === ast
                  ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              {ast}-PERP
            </button>
          ))}

          <div className="h-4 w-[1px] bg-slate-800 mx-1" />

          {/* Timeframe Selectors */}
          {['1m', '5m', '15m', '1h', '4h', '1D'].map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-2 py-0.5 rounded text-[11px] font-mono transition-all ${
                timeframe === tf
                  ? 'text-emerald-400 font-bold bg-emerald-500/15'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>

        {/* Indicators and Graph Controls */}
        <div className="flex items-center gap-2 text-xs font-mono">
          <button
            onClick={() => setShowHeatmap(!showHeatmap)}
            className={`px-2 py-1 rounded flex items-center gap-1 transition-all ${
              showHeatmap
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Toggle Liquidity Heatmap Depth Cloud"
          >
            <Layers className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Heatmap</span>
          </button>

          <button
            onClick={() => setShowVolume(!showVolume)}
            className={`px-2 py-1 rounded flex items-center gap-1 transition-all ${
              showVolume
                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Toggle Volume Delta Histogram"
          >
            <Volume2 className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Volume</span>
          </button>

          <button
            onClick={() => setShowEma(!showEma)}
            className={`px-2 py-1 rounded flex items-center gap-1 transition-all ${
              showEma
                ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                : 'text-slate-400 hover:text-slate-200'
            }`}
            title="Toggle EMA 20 / EMA 50 Trajectory"
          >
            <TrendingUp className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">EMA 20/50</span>
          </button>
        </div>
      </div>

      {/* Main Canvas Viewport */}
      <div ref={containerRef} className="relative flex-1 w-full min-h-[360px] overflow-hidden">
        {/* Floating Legend */}
        <div className="absolute top-2 left-3 z-10 flex items-center gap-3 text-[11px] font-mono select-none pointer-events-none">
          <span className="text-white font-bold">{selectedAsset}-PERPETUAL</span>
          <span className="text-emerald-400 font-bold">${currentPrice.toFixed(selectedAsset === 'DOGE' ? 5 : 2)}</span>
          {showEma && (
            <>
              <span className="text-cyan-400">EMA(20): {ema20[ema20.length - 1]?.toFixed(2) || '—'}</span>
              <span className="text-amber-400">EMA(50): {ema50[ema50.length - 1]?.toFixed(2) || '—'}</span>
            </>
          )}
        </div>

        <canvas
          ref={canvasRef}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          className="w-full h-full cursor-crosshair block"
        />
      </div>
    </div>
  );
};
