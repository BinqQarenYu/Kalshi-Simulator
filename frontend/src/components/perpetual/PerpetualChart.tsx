import React, { useRef, useEffect, useState, useMemo } from 'react';
import { usePerpetualTrading } from '../../context/PerpetualTradingContext';
import { Volume2, Layers, TrendingUp } from 'lucide-react';
import { createChart, IChartApi, ISeriesApi, Time, LineStyle, CrosshairMode, ColorType, CandlestickSeries, HistogramSeries, LineSeries } from 'lightweight-charts';

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
  } = usePerpetualTrading();

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<IChartApi | null>(null);
  
  const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const ema20SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ema50SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  // Initialize the chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#0b0e14' },
        textColor: '#64748b',
      },
      grid: {
        vertLines: { color: '#1a2230', style: LineStyle.Dashed },
        horzLines: { color: '#1a2230', style: LineStyle.Dashed },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: {
          color: '#94a3b8',
          width: 1,
          style: LineStyle.Dotted,
          labelBackgroundColor: '#334155',
        },
        horzLine: {
          color: '#94a3b8',
          width: 1,
          style: LineStyle.Dotted,
          labelBackgroundColor: '#334155',
        },
      },
      rightPriceScale: {
        borderColor: '#1f2937',
      },
      timeScale: {
        borderColor: '#1f2937',
        timeVisible: true,
      },
    });

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#10b981',
      downColor: '#f43f5e',
      borderVisible: false,
      wickUpColor: '#10b981',
      wickDownColor: '#f43f5e',
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: {
        type: 'volume',
      },
      priceScaleId: '', // overlay
    });

    chart.priceScale('').applyOptions({
      scaleMargins: {
        top: 0.78,
        bottom: 0,
      },
    });

    const ema20Series = chart.addSeries(LineSeries, {
      color: '#06b6d4',
      lineWidth: 2,
      crosshairMarkerVisible: false,
    });

    const ema50Series = chart.addSeries(LineSeries, {
      color: '#f59e0b',
      lineWidth: 2,
      crosshairMarkerVisible: false,
    });

    chartInstanceRef.current = chart;
    candlestickSeriesRef.current = candlestickSeries;
    volumeSeriesRef.current = volumeSeries;
    ema20SeriesRef.current = ema20Series;
    ema50SeriesRef.current = ema50Series;

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    };

    window.addEventListener('resize', handleResize);
    handleResize();

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, []);

  // Compute EMA helper
  const calculateEMA = (period: number) => {
    if (candles.length === 0) return [];
    const k = 2 / (period + 1);
    const emaData: { time: Time; value: number }[] = [];
    let prevEma = candles[0].close;

    emaData.push({ time: candles[0].time as Time, value: prevEma });

    for (let i = 1; i < candles.length; i++) {
      const c = candles[i];
      const currentEma = c.close * k + prevEma * (1 - k);
      emaData.push({ time: c.time as Time, value: currentEma });
      prevEma = currentEma;
    }
    return emaData;
  };

  // Sync data whenever candles change
  useEffect(() => {
    if (!candlestickSeriesRef.current || !volumeSeriesRef.current || candles.length === 0) return;

    // Candlesticks
    const cData = candles.map(c => ({
      time: c.time as Time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));
    candlestickSeriesRef.current.setData(cData);

    // Volume
    if (showVolume) {
      const vData = candles.map(c => ({
        time: c.time as Time,
        value: c.volume,
        color: c.close >= c.open ? 'rgba(16, 185, 129, 0.4)' : 'rgba(244, 63, 94, 0.4)',
      }));
      volumeSeriesRef.current.setData(vData);
    } else {
      volumeSeriesRef.current.setData([]);
    }

    // EMA
    if (showEma && ema20SeriesRef.current && ema50SeriesRef.current) {
      ema20SeriesRef.current.setData(calculateEMA(20));
      ema50SeriesRef.current.setData(calculateEMA(50));
    } else {
      ema20SeriesRef.current?.setData([]);
      ema50SeriesRef.current?.setData([]);
    }
    
  }, [candles, showVolume, showEma]);

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

      {/* Main Lightweight Charts Viewport */}
      <div className="relative flex-1 w-full min-h-[360px] overflow-hidden">
        {/* Floating Legend */}
        <div className="absolute top-2 left-3 z-10 flex flex-col gap-1 text-[11px] font-mono select-none pointer-events-none">
          <div className="flex items-center gap-3">
            <span className="text-white font-bold">{selectedAsset}-PERPETUAL</span>
            <span className="text-emerald-400 font-bold">${currentPrice.toFixed(selectedAsset === 'DOGE' ? 5 : 2)}</span>
          </div>
          {showEma && (
            <div className="flex items-center gap-3 mt-1">
              <span className="text-cyan-400">EMA(20)</span>
              <span className="text-amber-400">EMA(50)</span>
            </div>
          )}
        </div>
        
        {/* Container for Lightweight Charts */}
        <div ref={chartContainerRef} className="w-full h-full" />
      </div>
    </div>
  );
};
