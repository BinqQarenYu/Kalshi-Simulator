/**
 * @file TargetChart.tsx
 * @description Real-time interactive Bitcoin spot price trajectory chart matching Kalshi web design:
 * - Time axis smoothly moves/scrolls to the left as live ticks stream in
 * - Proportional vertical Y-axis height with .5 unit price increments (e.g. 77,624.5 to 77,324.0)
 * - Real-time continuous animation ("play") showing fluid UP / DOWN trajectory flow
 * - Collision-proof target strike badge and dedicated X-axis footer
 * - Left-axis strike delta level markers (+ $0, + $1, + $6, + $10, + $30, + $50, + $64)
 * - Active glowing radar beacon on current price head
 * - Color-coded directional aura (Emerald Green when above target strike, Crimson Red/Amber when below)
 * - Dotted threshold guidelines and authentic "⌄ Past | ▼ ▲ ▼" capsule pill.
 */

import React, { useRef, useEffect, useState, useCallback, useMemo } from 'react';
import { ChartPoint, MarketState, TradeTapeItem, WinLossEventReport } from '../types';
import { ChevronDown, Crosshair, Trophy, ArrowUpRight, ArrowDownRight, TrendingUp, TrendingDown } from 'lucide-react';
import { soundFX } from '../utils/audioFX';
import { getAssetMeta, formatAssetDelta } from '../utils/assets';

interface TargetChartProps {
  /** Real-time market state containing target strike, spot price, and calculated deltas */
  market: MarketState;
  /** Historical and live price sequence for dynamic trajectory visualization */
  chart: ChartPoint[];
  /** High-frequency trade events for floating tape indicators */
  tradeTape: TradeTapeItem[];
  /** Recent 15M cycle win/loss reports for the Past dropdown pill */
  winLossReports?: WinLossEventReport[];
  /** Callback when user clicks a price or strike level on chart */
  onSelectPrice?: (priceCents: number) => void;
  /** Callback to open full 15M event reports modal */
  onOpenReports?: () => void;
}

/** Parse HH:MM:SS or ISO string into continuous seconds of the day */
function parseTimeToSeconds(timeStr: string): number {
  if (!timeStr) return 0;
  if (timeStr.includes('T')) {
    const d = new Date(timeStr);
    if (!isNaN(d.getTime())) return d.getTime() / 1000;
  }
  const parts = timeStr.split(':');
  if (parts.length === 3) {
    const h = parseInt(parts[0], 10) || 0;
    const m = parseInt(parts[1], 10) || 0;
    const s = parseFloat(parts[2]) || 0;
    return h * 3600 + m * 60 + s;
  }
  if (parts.length === 2) {
    const m = parseInt(parts[0], 10) || 0;
    const s = parseFloat(parts[1]) || 0;
    return m * 60 + s;
  }
  return 0;
}

/** Format continuous seconds of day back to HH:MM:SS */
function formatSecondsToTime(sec: number): string {
  const totalSecs = Math.floor(sec) % 86400;
  const h = Math.floor(totalSecs / 3600);
  const m = Math.floor((totalSecs % 3600) / 60);
  const s = totalSecs % 60;
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

/** Monotonically unwrap seconds array across midnight boundaries */
function unwrapSeconds(rawSecsArray: number[]): number[] {
  if (rawSecsArray.length === 0) return [];
  const result: number[] = [rawSecsArray[0]];
  let offset = 0;
  for (let i = 1; i < rawSecsArray.length; i++) {
    let s = rawSecsArray[i] + offset;
    if (s < result[i - 1] - 43200) {
      offset += 86400;
      s += 86400;
    }
    result.push(s);
  }
  return result;
}

export const TargetChart: React.FC<TargetChartProps> = React.memo(({
  market,
  chart,
  tradeTape,
  winLossReports = [],
  onSelectPrice,
  onOpenReports,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);
  const crosshairRef = useRef<HTMLDivElement | null>(null);
  const snapDotRef = useRef<HTMLDivElement | null>(null);
  const animFrameRef = useRef<number | null>(null);

  const [selectedTimeframe, setSelectedTimeframe] = useState<'LIVE' | '5M' | '15M' | '1H'>('LIVE');
  const [isPastDropdownOpen, setIsPastDropdownOpen] = useState<boolean>(false);

  const assetMeta = getAssetMeta(market.active_asset);
  const decimals = market.active_asset_decimals ?? assetMeta.decimals;

  // Smooth floating springs for Y-axis bounds & spot price (glides up and down without abrupt teleporting)
  const smoothMinPriceRef = useRef<number | null>(null);
  const smoothMaxPriceRef = useRef<number | null>(null);
  const displayedSpotPriceRef = useRef<number>(market.current_btc_price);
  const initialTimeSecs = chart.length > 0 ? parseTimeToSeconds(chart[chart.length - 1].time) : (Date.now() / 1000) % 86400;
  const lastDataSecsRef = useRef<number>(initialTimeSecs || (Date.now() / 1000) % 86400);
  const lastDataPerfTimeRef = useRef<number>(performance.now());

  // Helper references for coordinate projection in mouse events
  const chartLayoutRef = useRef<{
    minPrice: number;
    maxPrice: number;
    priceRange: number;
    chartStartX: number;
    chartEndX: number;
    points: { x: number; y: number; price: number; time: string; secs: number }[];
    width: number;
    height: number;
    padTop: number;
    padBottom: number;
  }>({
    minPrice: 0,
    maxPrice: 0,
    priceRange: 100,
    chartStartX: 52,
    chartEndX: 500,
    points: [],
    width: 600,
    height: 250,
    padTop: 28,
    padBottom: 42,
  });

  // Dimensions cache to prevent layout thrashing
  const dimensionsRef = useRef<{ width: number; height: number; dpr: number }>({
    width: 600,
    height: 250,
    dpr: window.devicePixelRatio || 1,
  });

  // Synchronize chart timeframe selector with active market timeframe
  useEffect(() => {
    if (market.timeframe === '5m') {
      setSelectedTimeframe('5M');
    } else if (market.timeframe === '15m') {
      setSelectedTimeframe('15M');
    } else if (market.timeframe === '1h') {
      setSelectedTimeframe('1H');
    }
  }, [market.timeframe]);

  // Memoize trajectory points with pre-parsed & unwrapped seconds
  const processedPoints = useMemo<(ChartPoint & { secs: number })[]>(() => {
    const buf = assetMeta.defaultBuffer;
    let baseChart = chart;
    if (selectedTimeframe === 'LIVE') {
      baseChart = chart.slice(-60);
    } else if (selectedTimeframe === '5M') {
      baseChart = chart.slice(-180);
    }
    const raw: ChartPoint[] = baseChart.length >= 2 ? baseChart : [
      { time: '00:00:01', price: market.target_strike - buf * 0.2, target: market.target_strike },
      { time: '00:00:05', price: market.target_strike - buf * 0.4, target: market.target_strike },
      { time: '00:00:10', price: market.target_strike - buf * 0.7, target: market.target_strike },
      { time: '00:00:15', price: market.target_strike - buf * 1.0, target: market.target_strike },
      { time: '00:00:20', price: market.current_btc_price, target: market.target_strike },
    ];
    const rawSecs = raw.map((p) => parseTimeToSeconds(p.time));
    const unwrapped = unwrapSeconds(rawSecs);
    return raw.map((p, i) => ({
      ...p,
      secs: unwrapped[i] ?? parseTimeToSeconds(p.time),
    }));
  }, [chart, market.target_strike, market.current_btc_price, assetMeta.defaultBuffer, selectedTimeframe]);

  // Synchronize wall clock anchor whenever new point data arrives
  useEffect(() => {
    if (processedPoints.length > 0) {
      const latest = processedPoints[processedPoints.length - 1];
      lastDataSecsRef.current = latest.secs;
      lastDataPerfTimeRef.current = performance.now();
    }
  }, [processedPoints]);

  // Track container resize with ResizeObserver
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          dimensionsRef.current = {
            width,
            height,
            dpr: window.devicePixelRatio || 1,
          };
          const canvas = canvasRef.current;
          if (canvas) {
            const dpr = dimensionsRef.current.dpr;
            canvas.width = width * dpr;
            canvas.height = height * dpr;
          }
        }
      }
    });

    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  /**
   * Main Animated Canvas Render Loop (60FPS liquid streaming animation)
   * - Time continuously and seamlessly slides to the left every millisecond
   * - Price head and Y-axis smoothly float/lerp up and down
   */
  useEffect(() => {
    const startTime = performance.now();

    const render = (currentTime: number) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const { width, height, dpr } = dimensionsRef.current;
      if (width <= 0 || height <= 0) {
        animFrameRef.current = requestAnimationFrame(render);
        return;
      }

      // Reset transform and scale for retina/HiDPI
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);

      // 1. Continuous Live Time Tracking (Conveyor belt moves smoothly left at 60 FPS)
      const elapsedSinceData = (currentTime - lastDataPerfTimeRef.current) / 1000.0;
      const clampedElapsed = Math.min(30.0, Math.max(0.0, elapsedSinceData));
      const currentLiveSecs = lastDataSecsRef.current + clampedElapsed;

      let windowSecs = 60;
      if (selectedTimeframe === '5M') windowSecs = 300;
      else if (selectedTimeframe === '15M') windowSecs = 900;
      else if (selectedTimeframe === '1H') windowSecs = 3600;

      const tEnd = currentLiveSecs;
      const tStart = tEnd - windowSecs;

      // 2. Smooth Lerp for Spot Price (glides smoothly up and down without abrupt teleporting)
      const targetSpotPrice = market.current_btc_price;
      if (displayedSpotPriceRef.current === 0 || isNaN(displayedSpotPriceRef.current)) {
        displayedSpotPriceRef.current = targetSpotPrice;
      } else {
        displayedSpotPriceRef.current += (targetSpotPrice - displayedSpotPriceRef.current) * 0.15;
      }
      const currentPrice = displayedSpotPriceRef.current;
      const targetStrike = market.target_strike;
      const isUp = currentPrice >= targetStrike;

      // Chart Padding & Coordinate Bounds
      const padTop = 28;
      const padBottom = 42; // Generous bottom margin for dedicated X-axis time ticker
      const plotHeight = height - padTop - padBottom;
      const chartStartX = 52;
      const chartEndX = width - 85;
      const plotWidth = chartEndX - chartStartX;

      // Continuous time-to-X coordinate mapping (every point smoothly moves left)
      const getX = (secs: number) => {
        const frac = (secs - tStart) / windowSecs;
        return chartStartX + Math.max(0, Math.min(1, frac)) * plotWidth;
      };

      // 3. Proportional Vertical Y-bounds with dynamic unit steps (.5 or fractional)
      const baseBuffer = assetMeta.defaultBuffer;
      let rawMin = Math.min(targetStrike, currentPrice) - baseBuffer;
      let rawMax = Math.max(targetStrike, currentPrice) + baseBuffer;

      for (let i = 0; i < processedPoints.length; i++) {
        const pt = processedPoints[i];
        if (pt.secs >= tStart - 15 && pt.secs <= tEnd + 15) {
          if (pt.price < rawMin) rawMin = pt.price;
          if (pt.price > rawMax) rawMax = pt.price;
        }
      }
      rawMin -= assetMeta.minBuffer;
      rawMax += assetMeta.minBuffer * 1.5;

      const span = rawMax - rawMin;
      let tickStep = 0.5;
      if (decimals >= 4) {
        if (span > 0.02) tickStep = 0.005;
        else if (span > 0.01) tickStep = 0.002;
        else if (span > 0.004) tickStep = 0.001;
        else if (span > 0.002) tickStep = 0.0005;
        else if (span > 0.0008) tickStep = 0.0002;
        else tickStep = 0.0001;
      } else {
        if (span > 300) tickStep = 50.0;
        else if (span > 150) tickStep = 25.0;
        else if (span > 75) tickStep = 10.0;
        else if (span > 30) tickStep = 5.0;
        else if (span > 10) tickStep = 2.5;
        else if (span > 4) tickStep = 1.0;
        else if (span > 1.5) tickStep = 0.5;
        else if (span > 0.6) tickStep = 0.25;
        else if (span > 0.2) tickStep = 0.1;
        else tickStep = 0.05;
      }

      const targetMin = Math.floor(rawMin / tickStep) * tickStep;
      const targetMax = Math.ceil(rawMax / tickStep) * tickStep;

      // Smooth exponential lerp on vertical boundaries to eliminate jitter/snapping
      if (
        smoothMinPriceRef.current === null ||
        smoothMaxPriceRef.current === null ||
        isNaN(smoothMinPriceRef.current) ||
        isNaN(smoothMaxPriceRef.current)
      ) {
        smoothMinPriceRef.current = targetMin;
        smoothMaxPriceRef.current = targetMax;
      } else {
        smoothMinPriceRef.current += (targetMin - smoothMinPriceRef.current) * 0.08;
        smoothMaxPriceRef.current += (targetMax - smoothMaxPriceRef.current) * 0.08;
      }

      const minPrice: number = smoothMinPriceRef.current ?? targetMin;
      const maxPrice: number = smoothMaxPriceRef.current ?? targetMax;
      const priceRange: number = Math.max(0.0001, maxPrice - minPrice);

      // Strictly linear proportional Y coordinate mapping
      const getY = (p: number) => {
        const normalized = (p - minPrice) / priceRange;
        return padTop + (1 - Math.max(0, Math.min(1, normalized))) * plotHeight;
      };

      // 4. Draw Horizontal Proportional Grid Lines & Adaptive Price Labels
      ctx.lineWidth = 1;
      ctx.font = '10px "JetBrains Mono", Inter, sans-serif';
      ctx.textAlign = 'right';

      const numTicks = Math.round((maxPrice - minPrice) / tickStep);
      const stepStride = Math.max(1, Math.floor(numTicks / 5));

      for (let i = 0; i <= numTicks; i += stepStride) {
        const p = minPrice + i * tickStep;
        const y = getY(p);

        if (y >= padTop - 2 && y <= height - padBottom + 2) {
          ctx.strokeStyle = 'rgba(33, 38, 45, 0.85)';
          ctx.beginPath();
          ctx.moveTo(chartStartX, y);
          ctx.lineTo(chartEndX, y);
          ctx.stroke();

          // Format price label with asset decimal precision
          ctx.fillStyle = '#6e7681';
          const formattedPrice = p.toLocaleString('en-US', {
            minimumFractionDigits: decimals >= 4 ? 4 : (tickStep < 1 ? (tickStep < 0.1 ? 2 : 1) : 0),
            maximumFractionDigits: decimals,
          });
          ctx.fillText(`$${formattedPrice}`, width - 8, y + 3.5);
        }
      }

      // 5. Left-Axis Strike Delta Labels (Scaled per Asset Microstructure)
      const deltaOffsets = assetMeta.deltaOffsets;
      ctx.font = 'bold 10px "JetBrains Mono", monospace';
      ctx.textAlign = 'left';

      deltaOffsets.forEach((delta) => {
        const p = targetStrike + delta;
        if (p >= minPrice - assetMeta.minBuffer && p <= maxPrice + assetMeta.minBuffer) {
          const y = getY(p);
          if (y >= padTop - 5 && y <= height - padBottom + 5) {
            let color = '#f7931a'; // + $0 orange baseline
            if (delta > 0) {
              color = delta >= assetMeta.minSpotDiff ? '#00d084' : '#ff7b7b';
            } else if (delta < 0) {
              color = '#ff4d4d';
            }

            ctx.fillStyle = color;
            const labelText = formatAssetDelta(delta, market.active_asset);
            ctx.fillText(labelText, 8, y + 3.5);

            // Red/Green dotted threshold guidelines across chart
            if (Math.abs(delta) === assetMeta.thresholdGuideline) {
              ctx.save();
              ctx.setLineDash([3, 3]);
              ctx.strokeStyle = delta > 0 ? 'rgba(0, 208, 132, 0.7)' : 'rgba(255, 77, 77, 0.7)';
              ctx.lineWidth = 1.2;
              ctx.beginPath();
              ctx.moveTo(chartStartX, y);
              ctx.lineTo(chartEndX, y);
              ctx.stroke();
              ctx.restore();
            }
          }
        }
      });

      // 6. Target Strike Line (K) & Collision-Proof Centered Badge
      const rawTargetY = getY(targetStrike);
      const targetY = Math.max(padTop + 8, Math.min(height - padBottom - 8, rawTargetY));

      ctx.save();
      ctx.setLineDash([5, 4]);
      ctx.strokeStyle = '#4b5563';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(chartStartX, targetY);
      ctx.lineTo(chartEndX, targetY);
      ctx.stroke();
      ctx.restore();

      // Protected Target Strike Badge with dark pill backdrop
      const targetLabel = `${market.target_strike_str} target ︾`;
      ctx.font = 'bold 10px "JetBrains Mono", Inter, sans-serif';
      const textWidth = ctx.measureText(targetLabel).width;
      const pillX = (chartStartX + chartEndX) / 2 - textWidth / 2;
      const pillY = targetY - 6;

      ctx.fillStyle = 'rgba(13, 17, 23, 0.92)';
      ctx.fillRect(pillX - 6, pillY - 10, textWidth + 12, 15);
      ctx.strokeStyle = 'rgba(48, 54, 61, 0.8)';
      ctx.lineWidth = 1;
      ctx.strokeRect(pillX - 6, pillY - 10, textWidth + 12, 15);

      ctx.fillStyle = '#8b949e';
      ctx.textAlign = 'left';
      ctx.fillText(targetLabel, pillX, pillY + 1.5);

      // 7. Trajectory Points Construction with Seamless Continuous Leftward Stream
      const visible = processedPoints.filter((p) => p.secs >= tStart - 15 && p.secs <= tEnd);
      const renderPoints: { x: number; y: number; price: number; secs: number; time: string }[] = [];

      if (visible.length === 0) {
        renderPoints.push({
          x: chartStartX,
          y: getY(currentPrice),
          price: currentPrice,
          secs: tStart,
          time: formatSecondsToTime(tStart),
        });
      } else {
        if (visible[0].secs > tStart) {
          renderPoints.push({
            x: chartStartX,
            y: getY(visible[0].price),
            price: visible[0].price,
            secs: tStart,
            time: formatSecondsToTime(tStart),
          });
        }
        for (const pt of visible) {
          renderPoints.push({
            x: getX(pt.secs),
            y: getY(pt.price),
            price: pt.price,
            secs: pt.secs,
            time: pt.time,
          });
        }
      }

      // Anchor head to live edge at chartEndX
      renderPoints.push({
        x: chartEndX,
        y: getY(currentPrice),
        price: currentPrice,
        secs: tEnd,
        time: formatSecondsToTime(tEnd),
      });

      // Update layout ref for mouse hover projection
      chartLayoutRef.current = {
        minPrice,
        maxPrice,
        priceRange,
        chartStartX,
        chartEndX,
        points: renderPoints,
        width,
        height,
        padTop,
        padBottom,
      };

      // 8. Dynamic Area Gradient Fill (Emerald Green if UP, Coral Red if DOWN)
      const gradient = ctx.createLinearGradient(0, 0, 0, height);
      if (isUp) {
        gradient.addColorStop(0, 'rgba(0, 208, 132, 0.25)');
        gradient.addColorStop(0.7, 'rgba(0, 208, 132, 0.04)');
        gradient.addColorStop(1, 'rgba(0, 208, 132, 0.0)');
      } else {
        gradient.addColorStop(0, 'rgba(247, 147, 26, 0.22)');
        gradient.addColorStop(0.7, 'rgba(247, 147, 26, 0.03)');
        gradient.addColorStop(1, 'rgba(247, 147, 26, 0.0)');
      }

      // Draw Smooth Bezier Area Fill
      ctx.beginPath();
      renderPoints.forEach((pt, idx) => {
        if (idx === 0) {
          ctx.moveTo(pt.x, pt.y);
        } else {
          const prev = renderPoints[idx - 1];
          const cpX = (prev.x + pt.x) / 2;
          ctx.bezierCurveTo(cpX, prev.y, cpX, pt.y, pt.x, pt.y);
        }
      });
      ctx.lineTo(chartEndX, height - padBottom);
      ctx.lineTo(chartStartX, height - padBottom);
      ctx.closePath();
      ctx.fillStyle = gradient;
      ctx.fill();

      // 9. Draw Main Glowing Trajectory Line
      ctx.save();
      ctx.shadowColor = isUp ? 'rgba(0, 208, 132, 0.45)' : 'rgba(247, 147, 26, 0.45)';
      ctx.shadowBlur = 8;
      ctx.strokeStyle = isUp ? '#00d084' : '#f7931a';
      ctx.lineWidth = 2.8;
      ctx.beginPath();
      renderPoints.forEach((pt, idx) => {
        if (idx === 0) {
          ctx.moveTo(pt.x, pt.y);
        } else {
          const prev = renderPoints[idx - 1];
          const cpX = (prev.x + pt.x) / 2;
          ctx.bezierCurveTo(cpX, prev.y, cpX, pt.y, pt.x, pt.y);
        }
      });
      ctx.stroke();
      ctx.restore();

      // 10. Live Animated Radar Beacon on Current Price Head ("Play" Motion)
      const lastX = chartEndX;
      const lastY = getY(currentPrice);
      const elapsed = (currentTime - startTime) / 1000.0;
      const pulsePhase = (elapsed % 1.5) / 1.5; // 0 to 1 cycle every 1.5s
      const pulseRadius = 4 + pulsePhase * 15;
      const pulseAlpha = Math.max(0, 1.0 - pulsePhase);

      // Expanding radar beacon wave
      ctx.strokeStyle = isUp
        ? `rgba(0, 208, 132, ${pulseAlpha * 0.85})`
        : `rgba(247, 147, 26, ${pulseAlpha * 0.85})`;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(lastX, lastY, pulseRadius, 0, Math.PI * 2);
      ctx.stroke();

      // Outer glow circle
      ctx.fillStyle = isUp ? 'rgba(0, 208, 132, 0.35)' : 'rgba(247, 147, 26, 0.35)';
      ctx.beginPath();
      ctx.arc(lastX, lastY, 7, 0, Math.PI * 2);
      ctx.fill();

      // Solid bright inner core
      ctx.fillStyle = isUp ? '#00d084' : '#f7931a';
      ctx.beginPath();
      ctx.arc(lastX, lastY, 4.5, 0, Math.PI * 2);
      ctx.fill();

      // Floating Live Directional Delta Pill on Head
      const diffVal = currentPrice - targetStrike;
      const diffPct = targetStrike > 0 ? (diffVal / targetStrike) * 100.0 : 0.0;
      const diffStr = diffVal >= 0
        ? `▲ +$${diffVal.toFixed(decimals >= 4 ? 4 : 2)}`
        : `▼ -$${Math.abs(diffVal).toFixed(decimals >= 4 ? 4 : 2)}`;
      const tagBg = isUp ? '#00d084' : '#ff4d4d';

      const badgeText = `${diffStr} (${diffPct >= 0 ? '+' : ''}${diffPct.toFixed(3)}%)`;
      ctx.font = 'bold 10px "JetBrains Mono", Inter, sans-serif';
      const badgeWidth = ctx.measureText(badgeText).width;
      const badgeX = lastX + 10;
      const badgeY = Math.max(padTop + 2, Math.min(height - padBottom - 18, lastY - 8));

      ctx.fillStyle = 'rgba(13, 17, 23, 0.90)';
      ctx.fillRect(badgeX - 4, badgeY - 2, badgeWidth + 8, 16);
      ctx.strokeStyle = tagBg;
      ctx.lineWidth = 1;
      ctx.strokeRect(badgeX - 4, badgeY - 2, badgeWidth + 8, 16);

      ctx.fillStyle = tagBg;
      ctx.textAlign = 'left';
      ctx.fillText(badgeText, badgeX, badgeY + 10);

      // 11. Continuous Leftward-Flowing Time Axis (Timestamps glide smoothly to the left)
      ctx.fillStyle = '#6e7681';
      ctx.font = '10px "JetBrains Mono", monospace';
      ctx.textAlign = 'center';

      let timeStepSecs = 15;
      if (windowSecs > 600) timeStepSecs = 120;
      else if (windowSecs > 180) timeStepSecs = 60;
      else if (windowSecs > 90) timeStepSecs = 30;
      else timeStepSecs = 15;

      const firstTickSec = Math.ceil(tStart / timeStepSecs) * timeStepSecs;
      for (let tSec = firstTickSec; tSec <= tEnd; tSec += timeStepSecs) {
        const tickX = getX(tSec);
        if (tickX >= chartStartX && tickX <= chartEndX) {
          // Little tick mark
          ctx.strokeStyle = 'rgba(48, 54, 61, 0.7)';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(tickX, height - padBottom);
          ctx.lineTo(tickX, height - padBottom + 4);
          ctx.stroke();

          // Time text smoothly moving left
          const timeLabel = formatSecondsToTime(tSec);
          ctx.fillText(timeLabel, tickX, height - 12);
        }
      }

      animFrameRef.current = requestAnimationFrame(render);
    };

    animFrameRef.current = requestAnimationFrame(render);

    return () => {
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  }, [processedPoints, market, selectedTimeframe, decimals, assetMeta]);

  /**
   * Handle Mouse Movement across Canvas to calculate nearest snap point.
   */
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const container = containerRef.current;
      const tooltip = tooltipRef.current;
      const crosshair = crosshairRef.current;
      const snapDot = snapDotRef.current;

      if (!container || !tooltip || !crosshair || !snapDot) return;

      const rect = container.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;

      const { chartStartX, chartEndX, points, height, padBottom } =
        chartLayoutRef.current;

      if (!points.length || mouseX < chartStartX - 10 || mouseX > chartEndX + 10) {
        tooltip.style.opacity = '0';
        crosshair.style.opacity = '0';
        snapDot.style.opacity = '0';
        return;
      }

      // Find closest point by X distance
      let closestPt = points[0];
      let minDistance = Math.abs(points[0].x - mouseX);
      for (let i = 1; i < points.length; i++) {
        const d = Math.abs(points[i].x - mouseX);
        if (d < minDistance) {
          minDistance = d;
          closestPt = points[i];
        }
      }

      const snapX = closestPt.x;
      const snapY = closestPt.y;

      const diff = closestPt.price - market.target_strike;
      const diffPct = market.target_strike > 0 ? (diff / market.target_strike) * 100 : 0;

      const timeEl = tooltip.querySelector('.tt-time');
      const priceEl = tooltip.querySelector('.tt-price');
      const diffEl = tooltip.querySelector('.tt-diff');

      if (timeEl) timeEl.textContent = closestPt.time;
      if (priceEl) priceEl.textContent = `$${closestPt.price.toLocaleString('en-US', { minimumFractionDigits: decimals >= 4 ? 4 : 2, maximumFractionDigits: decimals })}`;

      if (diffEl) {
        const sign = (diff ?? 0) >= 0 ? '+' : '';
        const colorClass = (diff ?? 0) >= 0 ? 'text-[#00d084]' : 'text-[#ff4d4d]';
        diffEl.textContent = `${sign}${(diff ?? 0).toFixed(decimals)} (${sign}${(diffPct ?? 0).toFixed(3)}%)`;
        diffEl.className = `tt-diff text-[11px] font-semibold flex items-center gap-1 mt-0.5 ${colorClass}`;
      }

      const tooltipX = Math.min(Math.max(snapX - 60, 20), rect.width - 170);
      const tooltipY = Math.max(snapY - 70, 10);
      tooltip.style.transform = `translate(${tooltipX}px, ${tooltipY}px)`;
      tooltip.style.opacity = '1';

      crosshair.style.transform = `translateX(${snapX}px)`;
      crosshair.style.height = `${height - padBottom}px`;
      crosshair.style.opacity = '1';

      snapDot.style.transform = `translate(${snapX - 4.5}px, ${snapY - 4.5}px)`;
      snapDot.style.opacity = '1';
    },
    [market.target_strike, decimals]
  );

  const handleMouseLeave = useCallback(() => {
    if (tooltipRef.current) tooltipRef.current.style.opacity = '0';
    if (crosshairRef.current) crosshairRef.current.style.opacity = '0';
    if (snapDotRef.current) snapDotRef.current.style.opacity = '0';
  }, []);

  // Compute past 3 outcome arrows from reports or defaults
  const recentOutcomes = React.useMemo(() => {
    if (winLossReports.length >= 3) {
      return winLossReports.slice(0, 3).map((r) => r.outcome === 'win');
    }
    return [false, true, false];
  }, [winLossReports]);

  const isMarketAbove = market.diff >= 0;

  return (
    <div
      ref={containerRef}
      className="relative bg-[#0d1117] border-b border-[#21262d] p-3 sm:p-4 select-none overflow-hidden"
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      {/* Floating Trade Tape Badges on the Left */}
      <div className="absolute left-14 top-4 flex flex-col gap-1 z-10 pointer-events-none">
        {tradeTape.slice(-4).map((t, idx) => {
          const isPos = t.side === 'yes';
          return (
            <span
              key={idx}
              className={`text-[10px] font-extrabold px-1.5 py-0.5 rounded backdrop-blur-sm transition-all animate-fadeIn ${
                isPos ? 'text-[#00d084] bg-[#00d084]/10 border border-[#00d084]/20' : 'text-[#ff4d4d] bg-[#ff4d4d]/10 border border-[#ff4d4d]/20'
              }`}
            >
              {t.val_str}
            </span>
          );
        })}
      </div>

      {/* DOM Crosshair & Snapped Dot Layer */}
      <div
        ref={crosshairRef}
        className="absolute top-[15px] w-px border-l border-dashed border-white/40 pointer-events-none opacity-0 transition-opacity duration-75 z-10"
        style={{ left: 0 }}
      />

      <div
        ref={snapDotRef}
        className="absolute top-0 left-0 w-[9px] h-[9px] bg-white rounded-full border-2 border-[#f7931a] pointer-events-none opacity-0 transition-opacity duration-75 z-20"
      />

      {/* Floating Interactive Tooltip Box */}
      <div
        ref={tooltipRef}
        className="absolute top-0 left-0 z-30 pointer-events-none bg-[#161b22]/95 border border-[#30363d] backdrop-blur-md rounded-xl px-3 py-2 text-xs shadow-2xl opacity-0 transition-opacity duration-75"
        style={{ willChange: 'transform' }}
      >
        <div className="text-[10px] font-mono text-[#8b949e] flex items-center justify-between gap-3">
          <span className="tt-time">00:00:00</span>
          <Crosshair className="h-3 w-3 text-[#f7931a]" />
        </div>
        <div className="tt-price font-bold text-white text-sm font-mono mt-0.5">
          $0.00
        </div>
        <div className="tt-diff text-[11px] font-semibold flex items-center gap-1 mt-0.5">
          +0.00 (0.00%)
        </div>
      </div>

      {/* Main High-DPI Canvas Chart */}
      <div className="h-[250px] w-full cursor-crosshair">
        <canvas
          ref={canvasRef}
          className="h-full w-full block"
        />
      </div>

      {/* Bottom Chart Footer: Authentic Kalshi Capsule Pill & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-2 pt-2 text-xs text-[#8b949e] border-t border-[#21262d]">
        <div className="flex items-center gap-3 relative">
          {/* Authentic Kalshi Capsule Pill Button: "⌄ Past | ▼ ▲ ▼" */}
          <button
            onClick={() => {
              soundFX.playClickSound();
              setIsPastDropdownOpen(!isPastDropdownOpen);
            }}
            className="flex items-center gap-1.5 px-3 py-1 bg-[#1c2128] hover:bg-[#2d333b] text-slate-200 text-xs font-semibold rounded-full border border-[#30363d] shadow-sm transition-all group active:scale-95"
          >
            <ChevronDown className={`h-3.5 w-3.5 transition-transform text-slate-400 group-hover:text-white ${isPastDropdownOpen ? 'rotate-180' : ''}`} />
            <span>Past</span>
            <span className="text-slate-600">|</span>
            <span className="flex items-center gap-1 text-[11px] font-mono">
              {recentOutcomes.map((isWin, idx) => (
                <span
                  key={idx}
                  className={`font-bold transition-transform hover:scale-125 ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}
                >
                  {isWin ? '▲' : '▼'}
                </span>
              ))}
            </span>
          </button>

          {/* Past 15M Cycle Outcomes Dropdown Popover */}
          {isPastDropdownOpen && (
            <div className="absolute left-0 bottom-10 z-40 w-72 bg-[#161b22] border border-[#30363d] rounded-xl p-3 shadow-2xl backdrop-blur-xl animate-fadeIn">
              <div className="flex items-center justify-between pb-2 border-b border-[#21262d] text-xs font-bold text-slate-200">
                <span className="flex items-center gap-1.5">
                  <Trophy className="h-3.5 w-3.5 text-amber-400" />
                  Recent 15M Cycle Results
                </span>
                <span className="text-[10px] text-slate-500 font-mono">ET Timeline</span>
              </div>

              <div className="divide-y divide-[#21262d] py-1 max-h-48 overflow-y-auto font-mono text-xs">
                {winLossReports.length > 0 ? (
                  winLossReports.slice(0, 5).map((r, idx) => (
                    <div key={idx} className="py-1.5 flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        {r.outcome === 'win' ? (
                          <span className="text-emerald-400 flex items-center font-bold">
                            <ArrowUpRight className="h-3.5 w-3.5" /> WIN
                          </span>
                        ) : (
                          <span className="text-rose-400 flex items-center font-bold">
                            <ArrowDownRight className="h-3.5 w-3.5" /> LOSS
                          </span>
                        )}
                        <span className="text-[11px] text-slate-400 uppercase">{r.bot_side}</span>
                      </div>
                      <div className="text-right text-[11px]">
                        <div className={r.pnl >= 0 ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                          {r.pnl >= 0 ? `+$${r.pnl.toFixed(2)}` : `-$${Math.abs(r.pnl).toFixed(2)}`}
                        </div>
                        <div className="text-[10px] text-slate-500">{r.cycle_time || '15M'}</div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="py-2 text-[11px] text-slate-400 text-center">
                    Simulating live 15-minute event sequence...
                  </div>
                )}
              </div>

              {onOpenReports && (
                <button
                  onClick={() => {
                    setIsPastDropdownOpen(false);
                    onOpenReports();
                  }}
                  className="w-full mt-2 py-1 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/30 text-[11px] font-bold rounded-lg transition-colors"
                >
                  View Full Historical Journal & Win/Loss Reports
                </button>
              )}
            </div>
          )}

          {/* Current Dollar Value / Spot Quote Display with live UP/DOWN Arrow */}
          <div className="flex items-center gap-1.5">
            {isMarketAbove ? (
              <TrendingUp className="h-4 w-4 text-emerald-400" />
            ) : (
              <TrendingDown className="h-4 w-4 text-rose-400" />
            )}
            <span className={`font-bold text-xs font-mono ${isMarketAbove ? 'text-emerald-400' : 'text-rose-400'}`}>
              {market.current_btc_price_str || `$${market.current_btc_price.toFixed(decimals)}`}
            </span>
          </div>

          <span className="text-slate-500 text-[11px] hidden sm:inline">
            {market.volume_24h_str} vol
          </span>
        </div>

        {/* Timeframe Range Buttons */}
        <div className="flex items-center gap-1 bg-[#161b22] p-0.5 rounded-lg border border-[#30363d]">
          {(['LIVE', '5M', '15M', '1H'] as const).map((tf) => (
            <button
              key={tf}
              onClick={() => {
                soundFX.playClickSound();
                setSelectedTimeframe(tf);
              }}
              className={`px-2.5 py-0.5 font-bold rounded text-[11px] transition-colors ${
                selectedTimeframe === tf
                  ? 'bg-[#30363d] text-white shadow-sm'
                  : 'text-[#8b949e] hover:text-white'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
});
