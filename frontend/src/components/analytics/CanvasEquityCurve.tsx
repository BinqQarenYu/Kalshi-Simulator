import React, { useEffect, useRef, useState } from 'react';
import { TrendingUp } from 'lucide-react';
import { EquityPoint, SystemFilter } from './AnalyticsTypes';

interface CanvasEquityCurveProps {
  equityCurve: EquityPoint[];
  selectedSystem: SystemFilter;
}

export const CanvasEquityCurve: React.FC<CanvasEquityCurveProps> = ({
  equityCurve,
  selectedSystem,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [dimensions, setDimensions] = useState({ width: 900, height: 240 });

  // Measure container for Retina canvas
  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      if (entries[0]) {
        const { width } = entries[0].contentRect;
        if (width > 250) {
          setDimensions({ width, height: 240 });
        }
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // HiDPI Retina Canvas Equity Curve Renderer
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = dimensions.width;
    const h = dimensions.height;

    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    // Background grid lines
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1;
    for (let x = 0; x < w; x += 90) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y < h; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    if (equityCurve.length === 0) {
      ctx.fillStyle = '#64748b';
      ctx.font = '13px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(
        `Accumulating real-time equity snapshots for ${
          selectedSystem === 'all'
            ? 'all systems'
            : selectedSystem === 'dominion_2_bot'
            ? 'Dominion 2 Bot'
            : selectedSystem === '3_step_domination_bot'
            ? '3-Step Domination Bot'
            : selectedSystem === 'onnx_ml_bot'
            ? 'ONNX ML Bot'
            : 'Live Trading'
        }...`,
        w / 2,
        h / 2
      );
      return;
    }

    // Build equity point series
    const points =
      equityCurve.length === 1
        ? [{ ...equityCurve[0], equity: equityCurve[0].equity }, { ...equityCurve[0], equity: equityCurve[0].equity }]
        : equityCurve;

    const values = points.map((p) => p.equity);
    const minVal = Math.min(...values) * 0.998;
    const maxVal = Math.max(...values) * 1.002;
    const range = maxVal - minVal || 1.0;

    const getX = (index: number) => (index / (points.length - 1)) * (w - 70) + 20;
    const getY = (val: number) => h - 30 - ((val - minVal) / range) * (h - 60);

    // Gradient fill under live equity line
    const gradient = ctx.createLinearGradient(0, 0, 0, h);
    gradient.addColorStop(0, 'rgba(16, 185, 129, 0.28)');
    gradient.addColorStop(1, 'rgba(16, 185, 129, 0.0)');

    ctx.beginPath();
    ctx.moveTo(getX(0), getY(values[0]));
    for (let i = 1; i < values.length; i++) {
      ctx.lineTo(getX(i), getY(values[i]));
    }
    ctx.lineTo(getX(values.length - 1), h - 20);
    ctx.lineTo(getX(0), h - 20);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // High-Water Mark Peak Line
    let peak = values[0];
    ctx.beginPath();
    ctx.moveTo(getX(0), getY(peak));
    for (let i = 1; i < values.length; i++) {
      if (values[i] > peak) peak = values[i];
      ctx.lineTo(getX(i), getY(peak));
    }
    ctx.strokeStyle = 'rgba(59, 130, 246, 0.65)';
    ctx.setLineDash([4, 4]);
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.setLineDash([]);

    // Live Equity Line
    ctx.beginPath();
    ctx.moveTo(getX(0), getY(values[0]));
    for (let i = 1; i < values.length; i++) {
      ctx.lineTo(getX(i), getY(values[i]));
    }
    ctx.strokeStyle = '#10b981';
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // End point indicator
    const lastX = getX(values.length - 1);
    const lastY = getY(values[values.length - 1]);
    ctx.beginPath();
    ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
    ctx.fillStyle = '#10b981';
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Annotations & Y-Axis Labels
    ctx.fillStyle = '#94a3b8';
    ctx.font = '11px monospace';
    ctx.textAlign = 'right';
    ctx.fillText(`$${maxVal.toFixed(2)}`, w - 8, 20);
    ctx.fillText(`$${minVal.toFixed(2)}`, w - 8, h - 10);
  }, [equityCurve, dimensions, selectedSystem]);

  return (
    <div ref={containerRef} className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-sm">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 mb-3">
        <div className="text-xs sm:text-sm font-semibold text-slate-200 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-emerald-400" />
          Cumulative Portfolio Equity & High-Water Mark ($) •{' '}
          <span className="text-emerald-400 font-mono">
            {selectedSystem === 'all'
              ? 'All Combined'
              : selectedSystem === 'dominion_2_bot'
              ? 'Dominion 2 Bot'
              : selectedSystem === '3_step_domination_bot'
              ? '3-Step Domination Bot'
              : selectedSystem === 'onnx_ml_bot'
              ? 'ONNX ML Bot'
              : 'Live Real Capital'}
          </span>
        </div>
        <div className="text-xs text-slate-400 flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 inline-block" /> Live Equity
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-0.5 bg-blue-400 inline-block" /> Peak Watermark
          </span>
        </div>
      </div>
      <canvas
        ref={canvasRef}
        style={{ width: `${dimensions.width}px`, height: '240px' }}
        className="w-full h-60 bg-slate-950/70 rounded-lg border border-slate-800/80 block"
      />
    </div>
  );
};
