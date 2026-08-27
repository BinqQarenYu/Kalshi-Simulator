/**
 * @file Header.tsx
 * @description Top navigation bar with Bitcoin symbol, active market timeframe selector (5m, 15m, 1h),
 * Feed Mode switcher (Mock Sim vs Live Kalshi), AI Copilot switch, audio FX toggle, and connection status.
 */

import React, { useState } from 'react';
import { MarketState } from '../types';
import { Bot, RefreshCw, Radio, Share2, ArrowDownToLine, MessageSquare, Volume2, VolumeX, Activity } from 'lucide-react';
import { soundFX } from '../utils/audioFX';

interface HeaderProps {
  market: MarketState;
  isConnected: boolean;
  aiAutoTrade: boolean;
  timeframe: string;
  mode?: 'mock' | 'live';
  onToggleAI: (enabled: boolean) => void;
  onToggleMode?: (mode: 'mock' | 'live') => void;
  onSelectTimeframe: (tf: string) => void;
  onReset: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  market,
  isConnected,
  aiAutoTrade,
  timeframe,
  mode = 'mock',
  onToggleAI,
  onToggleMode,
  onSelectTimeframe,
  onReset,
}) => {
  const [isMuted, setIsMuted] = useState<boolean>(soundFX.muted);

  const handleToggleSound = () => {
    const muted = soundFX.toggleMute();
    setIsMuted(muted);
    if (!muted) {
      soundFX.playClickSound();
    }
  };

  return (
    <header className="border-b border-[#21262d] bg-[#0d1117] px-4 py-3 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Left: BTC Symbol + Title + Live Subtitle */}
        <div className="flex items-center gap-3.5">
          {/* Bitcoin Orange Icon */}
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-[#f7931a] to-[#e67e00] shadow-lg shadow-[#f7931a]/20">
            <span className="text-2xl font-bold text-white leading-none">₿</span>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-[#8b949e]">
                BTC / {timeframe.toUpperCase()}
              </span>
              <div className="flex gap-1 bg-[#161b22] p-0.5 rounded-lg border border-[#30363d]">
                {['5m', '15m', '1h'].map((tf) => (
                  <button
                    key={tf}
                    onClick={() => {
                      soundFX.playClickSound();
                      onSelectTimeframe(tf);
                    }}
                    className={`px-2 py-0.5 text-[11px] font-semibold rounded-md transition-all ${
                      timeframe === tf
                        ? 'bg-[#f7931a] text-black shadow-sm font-bold'
                        : 'text-[#8b949e] hover:text-white'
                    }`}
                  >
                    {tf.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2.5 mt-0.5">
              <h1 className="text-xl font-bold text-white tracking-tight">{market.title}</h1>
              <div className="flex items-center gap-1.5 text-xs text-[#8b949e]">
                <span>August 26, 4:45 - 5:00 PM GMT+3</span>
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-red-500/10 text-red-400 font-bold text-[10px]">
                  <span className="h-1.5 w-1.5 rounded-full bg-red-500 animate-ping" />
                  LIVE
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Actions, Feed Mode, AI Copilot Toggle, Sound FX & Connection Status */}
        <div className="flex items-center gap-3">
          {/* Feed Mode Switcher (Mock Sim vs Live Kalshi) */}
          <div className="flex items-center bg-[#161b22] p-0.5 rounded-lg border border-[#30363d] text-xs font-semibold">
            <button
              onClick={() => {
                soundFX.playClickSound();
                onToggleMode?.('mock');
              }}
              className={`px-2.5 py-1 rounded-md transition-all ${
                mode === 'mock'
                  ? 'bg-[#30363d] text-white font-bold'
                  : 'text-[#8b949e] hover:text-white'
              }`}
            >
              Mock Sim
            </button>
            <button
              onClick={() => {
                soundFX.playClickSound();
                onToggleMode?.('live');
              }}
              className={`px-2.5 py-1 rounded-md transition-all flex items-center gap-1 ${
                mode === 'live'
                  ? 'bg-[#00d084]/20 text-[#00d084] font-bold border border-[#00d084]/40'
                  : 'text-[#8b949e] hover:text-white'
              }`}
            >
              <Activity className="h-3 w-3" />
              <span>Kalshi Live</span>
            </button>
          </div>

          {/* AI Auto-Trade Toggle Pill */}
          <button
            onClick={() => {
              soundFX.playClickSound();
              onToggleAI(!aiAutoTrade);
            }}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold border transition-all ${
              aiAutoTrade
                ? 'bg-[#00d084]/15 border-[#00d084]/50 text-[#00d084] shadow-sm shadow-[#00d084]/20'
                : 'bg-[#161b22] border-[#30363d] text-[#8b949e] hover:text-white'
            }`}
          >
            <Bot className={`h-4 w-4 ${aiAutoTrade ? 'text-[#00d084] animate-bounce' : ''}`} />
            <span>AI Auto-Trade: {aiAutoTrade ? 'ON' : 'OFF'}</span>
          </button>

          {/* Audio SoundFX Toggle Button */}
          <button
            onClick={handleToggleSound}
            className={`p-2 rounded-xl border transition-all ${
              isMuted
                ? 'bg-[#161b22] border-[#30363d] text-[#8b949e] hover:text-white'
                : 'bg-[#f7931a]/15 border-[#f7931a]/40 text-[#f7931a]'
            }`}
            title={isMuted ? 'Unmute Sound Effects' : 'Mute Sound Effects'}
          >
            {isMuted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
          </button>

          {/* Quick Header Tool Icons */}
          <div className="hidden md:flex items-center gap-1 bg-[#161b22] border border-[#30363d] rounded-full px-2 py-1 text-[#8b949e]">
            <button className="p-1 hover:text-white transition-colors" title="Stats">
              <span className="text-[11px] font-bold">37K</span>
            </button>
            <button className="p-1 hover:text-white transition-colors" title="Share">
              <Share2 className="h-3.5 w-3.5" />
            </button>
            <button className="p-1 hover:text-white transition-colors" title="Export">
              <ArrowDownToLine className="h-3.5 w-3.5" />
            </button>
            <button className="p-1 hover:text-white transition-colors flex items-center gap-1" title="Live Chat">
              <MessageSquare className="h-3.5 w-3.5" />
              <span className="text-[11px]">Live chat</span>
            </button>
          </div>

          {/* Reset Capital Button */}
          <button
            onClick={onReset}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-[#8b949e] hover:text-white bg-[#161b22] border border-[#30363d] hover:bg-[#21262d] transition-all"
            title="Reset Simulation Capital"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Reset $10K</span>
          </button>

          {/* Connection Status Indicator */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#161b22] border border-[#30363d] text-[11px] font-medium">
            <Radio className={`h-3 w-3 ${isConnected ? 'text-[#00d084]' : 'text-red-400'}`} />
            <span className={isConnected ? 'text-gray-300' : 'text-red-400'}>
              {isConnected ? (mode === 'live' ? 'Kalshi WS' : 'Mock Feed') : 'Connecting'}
            </span>
          </div>
        </div>
      </div>
    </header>
  );
};
