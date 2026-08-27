/**
 * @file TargetChart.tsx
 * @description Real-time interactive Bitcoin spot price trajectory chart with Kalshi target strike line,
 * dynamic Bezier curve interpolation, live floating trade tape badges, and interactive hover crosshairs.
 */

import React, { useRef, useEffect, useState, useCallback } from 'react';
import { ChartPoint, MarketState, TradeTapeItem } from '../types';
import { Eye, ChevronDown, Crosshair } from 'lucide-react';

interface TargetChartProps {
  /** Real-time market state containing target strike, spot price, and calculated deltas */
  market: MarketState;
  /** Historical and live price sequence for dynamic trajectory visualization */
  chart: ChartPoint[];
  /** High-frequency trade events for floating tape indicators */
  tradeTape: TradeTapeItem[];
}

interface HoverData {
  /** Screen X coordinate of the cursor / snapped point */
  x: number;
  /** Screen Y coordinate of the snapped price level */
  y: number;
  /** Snapped Bitcoin spot price */
  price: number;
  /** Formatted time string */
  time: string;
  /** Dollar difference from target strike (Price - Strike) */
  diff: number;
  /** Percentage difference from target strike */
  diffPct: number;
}

export const TargetChart: React.FC<TargetChartProps> = ({
  market,
  chart,
  tradeTape,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [selectedTimeframe, setSelectedTimeframe] = useState<'LIVE' | '5M' | '15M' | '1H'>('LIVE');
  const [hoverData, setHoverData] = useState<HoverData | null>(null);

  // Helper references for coordinate projection in mouse events
  const chartLayoutRef = useRef<{
    minPrice: number;
    maxPrice: number;
    priceRange: number;
    chartStartX: number;
    chartEndX: number;
    stepX: number;
    points: ChartPoint[];
    width: number;
    height: number;
  }>({
    minPrice: 0,
    maxPrice: 0,
    priceRange: 100,
    chartStartX: 50,
    chartEndX: 500,
    stepX: 10,
    points: [],
    width: 600,
    height: 220,
  });

  /**
   * Main Canvas Render Loop
   */
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Handle high-DPI displays (retina screens)
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;

    // Clear background
    ctx.clearRect(0, 0, width, height);

    // Calculate Y scale based on target strike and price points
    const targetStrike = market.target_strike;
    const currentPrice = market.current_btc_price;

    let minPrice = Math.min(targetStrike, currentPrice) - 30;
    let maxPrice = Math.max(targetStrike, currentPrice) + 20;

    if (chart.length > 0) {
      const prices = chart.map((c) => c.price);
      minPrice = Math.min(minPrice, ...prices) - 15;
      maxPrice = Math.max(maxPrice, ...prices) + 15;
    }

    const priceRange = maxPrice - minPrice || 100;
    const getY = (price: number) => {
      const normalized = (price - minPrice) / priceRange;
      return height - 40 - normalized * (height - 80);
    };

    // 1. Draw horizontal grid lines and prices on right axis
    ctx.strokeStyle = '#1e2430';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#6b7280';
    ctx.font = '10px Inter, sans-serif';
    ctx.textAlign = 'right';

    const gridSteps = 4;
    for (let i = 0; i <= gridSteps; i++) {
      const p = minPrice + (priceRange / gridSteps) * i;
      const y = getY(p);
      ctx.beginPath();
      ctx.moveTo(40, y);
      ctx.lineTo(width - 70, y);
      ctx.stroke();
      ctx.fillText(`$${p.toFixed(2)}`, width - 10, y + 3);
    }

    // 2. Draw Target Strike Line (Dotted Amber Line matching Kalshi UI)
    const targetY = getY(targetStrike);
    ctx.save();
    ctx.setLineDash([5, 4]);
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(40, targetY);
    ctx.lineTo(width - 80, targetY);
    ctx.stroke();
    ctx.restore();

    // Target Strike Label tag
    ctx.fillStyle = '#f59e0b';
    ctx.font = 'bold 11px Inter, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(`${market.target_strike_str} target ︽`, width / 2 - 50, targetY - 6);

    // 3. Trajectory Points & Interpolation
    const points = chart.length >= 2 ? chart : [
      { time: '00:00:01', price: targetStrike - 10, target: targetStrike },
      { time: '00:00:05', price: targetStrike - 50, target: targetStrike },
      { time: '00:00:10', price: targetStrike - 120, target: targetStrike },
      { time: '00:00:15', price: targetStrike - 160, target: targetStrike },
      { time: '00:00:20', price: currentPrice, target: targetStrike },
    ];

    const chartStartX = 50;
    const chartEndX = width - 80;
    const stepX = (chartEndX - chartStartX) / (points.length - 1 || 1);

    // Store layout details for hover interaction
    chartLayoutRef.current = {
      minPrice,
      maxPrice,
      priceRange,
      chartStartX,
      chartEndX,
      stepX,
      points,
      width,
      height,
    };

    // Gradient fill under the curve
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, 'rgba(247, 147, 26, 0.22)');
    gradient.addColorStop(0.7, 'rgba(247, 147, 26, 0.04)');
    gradient.addColorStop(1, 'rgba(247, 147, 26, 0.0)');

    ctx.beginPath();
    points.forEach((pt, idx) => {
      const x = chartStartX + idx * stepX;
      const y = getY(pt.price);
      if (idx === 0) {
        ctx.moveTo(x, y);
      } else {
        const prevX = chartStartX + (idx - 1) * stepX;
        const prevY = getY(points[idx - 1].price);
        const cpX = (prevX + x) / 2;
        ctx.bezierCurveTo(cpX, prevY, cpX, y, x, y);
      }
    });

    // Close path for area fill
    ctx.lineTo(chartEndX, height - 35);
    ctx.lineTo(chartStartX, height - 35);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw main trajectory line
    ctx.beginPath();
    points.forEach((pt, idx) => {
      const x = chartStartX + idx * stepX;
      const y = getY(pt.price);
      if (idx === 0) {
        ctx.moveTo(x, y);
      } else {
        const prevX = chartStartX + (idx - 1) * stepX;
        const prevY = getY(points[idx - 1].price);
        const cpX = (prevX + x) / 2;
        ctx.bezierCurveTo(cpX, prevY, cpX, y, x, y);
      }
    });
    ctx.strokeStyle = '#f7931a';
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // 4. Draw Current Price Head Dot & Live Label
    const lastX = chartEndX;
    const lastY = getY(currentPrice);

    // Glowing outer ring
    ctx.fillStyle = 'rgba(247, 147, 26, 0.3)';
    ctx.beginPath();
    ctx.arc(lastX, lastY, 7, 0, Math.PI * 2);
    ctx.fill();

    // Inner solid dot
    ctx.fillStyle = '#f7931a';
    ctx.beginPath();
    ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
    ctx.fill();

    // Live Percentage Tag at head
    ctx.fillStyle = market.diff >= 0 ? '#00d084' : '#ff4d4d';
    ctx.font = 'bold 10px Inter, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(`${market.diff_pct.toFixed(3)}%`, lastX + 10, lastY + 3);

    // 5. Draw Hover Crosshair and Snapped Highlight if user is hovering
    if (hoverData) {
      ctx.save();
      // Vertical crosshair guide line
      ctx.setLineDash([3, 3]);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(hoverData.x, 20);
      ctx.lineTo(hoverData.x, height - 35);
      ctx.stroke();

      // Snapped circle on the trajectory
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(hoverData.x, hoverData.y, 4.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = '#f7931a';
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.restore();
    }
  }, [chart, market, hoverData]);

  /**
   * Handle Mouse Movement across Canvas to calculate nearest snap point
   */
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas) return;

      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;

      const { chartStartX, chartEndX, stepX, points, minPrice, priceRange, height } =
        chartLayoutRef.current;

      if (!points.length || mouseX < chartStartX - 10 || mouseX > chartEndX + 10) {
        setHoverData(null);
        return;
      }

      // Find closest index
      const relativeX = mouseX - chartStartX;
      const index = Math.max(0, Math.min(points.length - 1, Math.round(relativeX / (stepX || 1))));
      const snappedPt = points[index];

      if (!snappedPt) {
        setHoverData(null);
        return;
      }

      const snapX = chartStartX + index * stepX;
      const normalized = (snappedPt.price - minPrice) / priceRange;
      const snapY = height - 40 - normalized * (height - 80);

      const diff = snappedPt.price - market.target_strike;
      const diffPct = (diff / market.target_strike) * 100;

      setHoverData({
        x: snapX,
        y: snapY,
        price: snappedPt.price,
        time: snappedPt.time,
        diff,
        diffPct,
      });
    },
    [market.target_strike]
  );

  const handleMouseLeave = useCallback(() => {
    setHoverData(null);
  }, []);

  return (
    <div ref={containerRef} className="relative bg-[#0d1117] border-b border-[#21262d] p-4 select-none">
      {/* Floating Trade Tape Badges on the Left */}
      <div className="absolute left-4 top-8 flex flex-col gap-1 z-10 pointer-events-none">
        {tradeTape.slice(-6).map((t, idx) => {
          const isPos = t.side === 'yes';
          return (
            <span
              key={idx}
              className={`text-[11px] font-extrabold px-1.5 py-0.5 rounded backdrop-blur-sm transition-all animate-fadeIn ${
                isPos ? 'text-[#00d084] bg-[#00d084]/10' : 'text-[#ff4d4d] bg-[#ff4d4d]/10'
              }`}
            >
              {t.val_str}
            </span>
          );
        })}
      </div>

      {/* Floating Interactive Hover Tooltip Box */}
      {hoverData && (
        <div
          className="absolute z-20 pointer-events-none bg-[#161b22]/95 border border-[#30363d] backdrop-blur-md rounded-xl px-3 py-2 text-xs shadow-2xl transition-all duration-75"
          style={{
            left: `${Math.min(Math.max(hoverData.x - 60, 20), (containerRef.current?.clientWidth || 500) - 160)}px`,
            top: `${Math.max(hoverData.y - 65, 10)}px`,
          }}
        >
          <div className="text-[10px] font-mono text-[#8b949e] flex items-center justify-between gap-3">
            <span>{hoverData.time}</span>
            <Crosshair className="h-3 w-3 text-[#f7931a]" />
          </div>
          <div className="font-bold text-white text-sm font-mono mt-0.5">
            ${hoverData.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className={`text-[11px] font-semibold flex items-center gap-1 mt-0.5 ${
            hoverData.diff >= 0 ? 'text-[#00d084]' : 'text-[#ff4d4d]'
          }`}>
            <span>{hoverData.diff >= 0 ? '+' : ''}${hoverData.diff.toFixed(2)}</span>
            <span>({hoverData.diff >= 0 ? '+' : ''}{hoverData.diffPct.toFixed(3)}%)</span>
          </div>
        </div>
      )}

      {/* Main Interactive Canvas Chart */}
      <div className="h-[220px] w-full cursor-crosshair">
        <canvas
          ref={canvasRef}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          className="h-full w-full block"
        />
      </div>

      {/* Bottom Chart Footer: Past View Toggle, Volume & Timeframe Buttons */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-2 text-xs text-[#8b949e] border-t border-[#21262d]">
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-1 hover:text-white font-medium">
            <Eye className="h-3.5 w-3.5" />
            <span>Past</span>
            <ChevronDown className="h-3 w-3" />
          </button>
          <span className="font-semibold text-gray-300">
            {market.volume_24h_str} vol
          </span>
        </div>

        {/* Range Buttons */}
        <div className="flex items-center gap-1 bg-[#161b22] p-0.5 rounded-lg border border-[#30363d]">
          {(['LIVE', '5M', '15M', '1H'] as const).map((tf) => (
            <button
              key={tf}
              onClick={() => setSelectedTimeframe(tf)}
              className={`px-2.5 py-0.5 font-bold rounded text-[11px] transition-colors ${
                selectedTimeframe === tf
                  ? 'bg-[#30363d] text-white'
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
};
