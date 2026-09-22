import React, { useState } from 'react';
import PerpetualChart from './PerpetualChart';

const PerpetualTerminal: React.FC = () => {
  const [selectedBot, setSelectedBot] = useState('28d-onnx-bot');

  return (
    <div className="flex flex-col h-screen bg-gray-950 text-gray-100 overflow-hidden font-sans w-screen">
      {/* Top Header */}
      <header className="h-12 border-b border-gray-800 flex items-center px-4 bg-gray-900 shadow-sm">
        <h1 className="text-xl font-bold tracking-tight text-white">Kalshi Perpetual Terminal</h1>
      </header>

      {/* Main Content Area */}
      <div className="flex flex-1 overflow-hidden">
        
        {/* Left/Center Panel - Charting */}
        <div className="flex-1 flex flex-col border-r border-gray-800 bg-gray-950 p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-200">Price Chart</h2>
            <div className="text-sm text-gray-400">BTC/USD (Simulated)</div>
          </div>
          <div className="flex-1 border border-gray-800 bg-gray-900 rounded flex items-center justify-center">
            <PerpetualChart />
          </div>
        </div>

        {/* Right Panel - Order Entry & Bot Selector */}
        <div className="w-80 flex flex-col bg-gray-900 p-4">
          <h2 className="text-lg font-semibold text-gray-200 mb-4">Order Entry</h2>
          
          {/* Bot Selector */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-400 mb-2">Select Trading Bot</label>
            <select 
              className="w-full bg-gray-800 border border-gray-700 text-gray-100 rounded px-3 py-2 focus:outline-none focus:border-blue-500"
              value={selectedBot}
              onChange={(e) => setSelectedBot(e.target.value)}
            >
              <option value="28d-onnx-bot">28d ONNX Bot</option>
              <option value="manual">Manual Trading</option>
              <option value="twap-bot">TWAP Execution</option>
            </select>
          </div>

          {/* Order Form Scaffold */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-1">Order Type</label>
              <div className="flex gap-2">
                <button className="flex-1 bg-gray-800 border border-gray-700 rounded py-1 hover:bg-gray-700 transition">Limit</button>
                <button className="flex-1 bg-gray-800 border border-gray-700 rounded py-1 hover:bg-gray-700 transition">Market</button>
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-1">Quantity</label>
              <input type="number" className="w-full bg-gray-800 border border-gray-700 text-gray-100 rounded px-3 py-2" placeholder="0.00" />
            </div>

            <div className="flex gap-2 pt-4">
              <button className="flex-1 bg-green-600 hover:bg-green-700 text-white font-bold py-2 rounded transition">Buy / Long</button>
              <button className="flex-1 bg-red-600 hover:bg-red-700 text-white font-bold py-2 rounded transition">Sell / Short</button>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Panel - Positions and PnL */}
      <div className="h-64 border-t border-gray-800 bg-gray-950 p-4 flex flex-col">
        <h2 className="text-lg font-semibold text-gray-200 mb-4">Positions & PnL</h2>
        <div className="flex-1 overflow-auto border border-gray-800 rounded bg-gray-900">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-800 text-gray-400 sticky top-0">
              <tr>
                <th className="px-4 py-2 font-medium">Symbol</th>
                <th className="px-4 py-2 font-medium">Size</th>
                <th className="px-4 py-2 font-medium">Entry Price</th>
                <th className="px-4 py-2 font-medium">Mark Price</th>
                <th className="px-4 py-2 font-medium">PnL (ROE%)</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-t border-gray-800">
                <td className="px-4 py-3">BTC/USD</td>
                <td className="px-4 py-3 text-green-500">+1.5</td>
                <td className="px-4 py-3">45,000.00</td>
                <td className="px-4 py-3">45,200.50</td>
                <td className="px-4 py-3 text-green-500">+$300.75 (0.66%)</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default PerpetualTerminal;
