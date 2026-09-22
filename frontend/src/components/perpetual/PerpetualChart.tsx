import React, { useEffect, useRef } from 'react';

// Mock data generator
const generateMockData = (numCandles: number) => {
  const data = [];
  let currentPrice = 50000;
  for (let i = 0; i < numCandles; i++) {
    const open = currentPrice;
    const high = open + Math.random() * 500;
    const low = open - Math.random() * 500;
    const close = low + Math.random() * (high - low);
    
    // Simple EMA and ATR mock values
    const ema = close * 1.002;
    const atrLower = close - 300;
    const atrUpper = close + 300;

    data.push({ open, high, low, close, ema, atrLower, atrUpper });
    currentPrice = close;
  }
  return data;
};

const PerpetualChart: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const data = useRef(generateMockData(100)).current;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Make canvas responsive to its display size
    const rect = canvas.parentElement?.getBoundingClientRect();
    if (rect) {
      canvas.width = rect.width;
      canvas.height = rect.height;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Dark mode background
    ctx.fillStyle = '#111827'; // Tailwind gray-900
    ctx.fillRect(0, 0, width, height);

    const padding = 20;
    const candleWidth = (width - padding * 2) / data.length;
    const maxPrice = Math.max(...data.map(d => Math.max(d.high, d.ema, d.atrUpper)));
    const minPrice = Math.min(...data.map(d => Math.min(d.low, d.ema, d.atrLower)));
    
    const scaleY = (price: number) => {
      return height - padding - ((price - minPrice) / (maxPrice - minPrice)) * (height - padding * 2);
    };

    // Draw EMA
    ctx.beginPath();
    ctx.strokeStyle = '#3b82f6'; // blue-500
    ctx.lineWidth = 2;
    data.forEach((d, i) => {
      const x = padding + i * candleWidth + candleWidth / 2;
      const y = scaleY(d.ema);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Draw ATR Bounds
    ctx.beginPath();
    ctx.strokeStyle = '#8b5cf6'; // violet-500
    ctx.lineWidth = 1;
    ctx.setLineDash([5, 5]);
    data.forEach((d, i) => {
      const x = padding + i * candleWidth + candleWidth / 2;
      const y = scaleY(d.atrUpper);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    ctx.beginPath();
    data.forEach((d, i) => {
      const x = padding + i * candleWidth + candleWidth / 2;
      const y = scaleY(d.atrLower);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.setLineDash([]); // Reset

    // Draw Candlesticks
    data.forEach((d, i) => {
      const x = padding + i * candleWidth;
      const centerX = x + candleWidth / 2;
      const yOpen = scaleY(d.open);
      const yClose = scaleY(d.close);
      const yHigh = scaleY(d.high);
      const yLow = scaleY(d.low);

      const isBullish = d.close >= d.open;
      const color = isBullish ? '#10b981' : '#ef4444'; // emerald-500 : red-500

      ctx.strokeStyle = color;
      ctx.fillStyle = color;

      // Wick
      ctx.beginPath();
      ctx.moveTo(centerX, yHigh);
      ctx.lineTo(centerX, yLow);
      ctx.stroke();

      // Body
      const bodyTop = Math.min(yOpen, yClose);
      const bodyHeight = Math.max(Math.abs(yOpen - yClose), 1);
      ctx.fillRect(x + 1, bodyTop, candleWidth - 2, bodyHeight);
    });

  }, [data]);

  return (
    <div className="w-full h-full relative bg-gray-900 rounded overflow-hidden">
      <canvas 
        ref={canvasRef} 
        className="block w-full h-full"
      />
      <div className="absolute top-2 left-2 flex gap-4 text-xs font-mono bg-gray-900/80 p-1 rounded">
        <span className="text-blue-500">■ EMA (Macro Shield)</span>
        <span className="text-violet-500 border-b border-dashed border-violet-500">ATR Bounds (Exit Manager)</span>
      </div>
    </div>
  );
};

export default PerpetualChart;
