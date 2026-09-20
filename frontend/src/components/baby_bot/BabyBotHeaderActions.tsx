import React from 'react';
import {
  Volume2,
  VolumeX,
  Minimize2,
  ExternalLink,
  Award,
} from 'lucide-react';
import { BotProfile, BOT_PROFILES } from './BabyBotProfiles';
import { SealRegistry } from '../../types';
import { soundFX } from '../../utils/audioFX';

export interface BabyBotHeaderActionsProps {
  isLiveRealMoney: boolean;
  effectiveLaneBadge: 'live' | 'shadow' | 'sim';
  activeProfile: BotProfile;
  isAudioMuted: boolean;
  setIsAudioMuted: (muted: boolean) => void;
  onTogglePopOut?: () => void;
  isPoppedOut: boolean;
  sealOfExcellence?: SealRegistry;
  onSelectBot?: (botId: string) => void;
  isBotSealed: boolean;
  activeSeal: any;
}

export const BabyBotHeaderActions: React.FC<BabyBotHeaderActionsProps> = ({
  isLiveRealMoney,
  effectiveLaneBadge,
  activeProfile,
  isAudioMuted,
  setIsAudioMuted,
  onTogglePopOut,
  isPoppedOut,
  sealOfExcellence,
  onSelectBot,
  isBotSealed,
  activeSeal,
}) => {
  return (
    <>
      {/* 1. Header: Execution Mode, Bot Name & Telemetry */}
      <div
        className={`px-4 py-2.5 border-b flex items-center justify-between transition-colors ${
          isLiveRealMoney
            ? 'bg-[#4c111e]/50 border-[#f43f5e]/40'
            : effectiveLaneBadge === 'shadow'
            ? 'bg-[#115e59]/40 border-[#00bda5]/40'
            : 'bg-[#291f0b]/50 border-amber-500/40'
        }`}
      >
        <div className="flex items-center gap-2 overflow-hidden">
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono font-bold tracking-wider uppercase border shadow-sm shrink-0 ${
              isLiveRealMoney
                ? 'bg-[#d31a38] text-white border-rose-400 animate-pulse'
                : effectiveLaneBadge === 'shadow'
                ? 'bg-[#00bda5]/20 text-[#2dd4bf] border-[#00bda5]/50'
                : 'bg-amber-500/20 text-amber-300 border-amber-500/50'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isLiveRealMoney ? 'bg-white' : effectiveLaneBadge === 'shadow' ? 'bg-[#2dd4bf]' : 'bg-amber-400'
              }`}
            />
            <span>{isLiveRealMoney ? 'LIVE REAL-MONEY' : effectiveLaneBadge === 'shadow' ? 'SHADOW (PAPER)' : 'OFFLINE SIM'}</span>
          </div>

          <span className="text-xs font-mono font-bold text-slate-200 truncate">
            {activeProfile.name}
          </span>
        </div>

        <div className="flex items-center gap-2 text-[11px] font-mono shrink-0">
          <span className="text-emerald-400 flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            14ms
          </span>
          <button
            onClick={() => {
              setIsAudioMuted(!isAudioMuted);
              soundFX.playClickSound();
            }}
            aria-label="Toggle sound FX"
            className="p-1 rounded text-slate-400 hover:text-white transition-colors cursor-pointer"
          >
            {isAudioMuted ? <VolumeX className="w-3.5 h-3.5" /> : <Volume2 className="w-3.5 h-3.5" />}
          </button>
          {onTogglePopOut && (
            <button
              onClick={onTogglePopOut}
              aria-label={isPoppedOut ? 'Dock into parent' : 'Pop out window'}
              title={isPoppedOut ? 'Dock into parent' : 'Pop out into standalone window'}
              className="p-1 rounded text-slate-400 hover:text-white transition-colors cursor-pointer"
            >
              {isPoppedOut ? <Minimize2 className="w-3.5 h-3.5" /> : <ExternalLink className="w-3.5 h-3.5" />}
            </button>
          )}
        </div>
      </div>

      {/* 2. Embedded Strategy Switcher Pill Bar */}
      <div className="px-3 py-1.5 bg-[#090b0e] border-b border-[#1f262d] flex items-center gap-1.5 overflow-x-auto scrollbar-none">
        <span className="text-[9px] font-mono uppercase text-[#8c9ba5] font-bold shrink-0 mr-1">
          Model:
        </span>
        {[
          BOT_PROFILES['3_step_domination_bot'],
          BOT_PROFILES['bot1_v4_domination'],
          BOT_PROFILES['dual_onnx'] || BOT_PROFILES['the_onnx_strategy'] || BOT_PROFILES['macro_onnx'],
          BOT_PROFILES['macro_trend_dominion'],
          BOT_PROFILES['gold_onnx_bot'],
        ].filter(Boolean).map((profile) => {
          const profileSeal =
            sealOfExcellence?.seals?.[profile.id] ||
            (profile.id === 'bot1_v4_domination'
              ? { seal_status: 'SEALED_BRAVE', live_trading_authorized: true }
              : profile.id === '3_step_domination_bot' || profile.id === 'macro_trend_dominion'
              ? { seal_status: 'SEALED_EXCELLENT', live_trading_authorized: true }
              : null);
          const profileIsSealed = Boolean(
            (profileSeal?.seal_status === 'SEALED_EXCELLENT' || profileSeal?.seal_status === 'SEALED_BRAVE') && profileSeal?.live_trading_authorized
          );
          const isActive =
            activeProfile.id === profile.id ||
            (profile.id === 'macro_trend_dominion' && (activeProfile.id.includes('macro_trend') || activeProfile.id === 'macro_onnx')) ||
            ((profile.id === 'dual_onnx' || profile.id === 'macro_onnx') && (activeProfile.id === 'onnx_microstructure_bot' || activeProfile.id === 'the_onnx_strategy'));
          return (
            <button
              key={profile.id}
              onClick={() => {
                soundFX.playClickSound();
                onSelectBot?.(profile.id);
              }}
              className={`px-2.5 py-0.5 rounded text-[10px] font-mono font-bold whitespace-nowrap transition-all flex items-center gap-1 border cursor-pointer ${
                isActive
                  ? profileIsSealed
                    ? 'bg-amber-500/25 text-amber-300 border-amber-500/60 shadow-sm ring-1 ring-amber-500/40'
                    : 'bg-[#00bda5]/20 text-[#2dd4bf] border-[#00bda5] shadow-sm ring-1 ring-[#00bda5]/40'
                  : 'bg-[#12161a] text-[#8c9ba5] border-[#262d35] hover:text-white hover:border-[#384451]'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  profileIsSealed
                    ? 'bg-amber-400 animate-pulse'
                    : profile.laneBadge === 'live'
                    ? 'bg-[#f43f5e] animate-pulse'
                    : 'bg-[#2dd4bf]'
                }`}
              />
              <span>{profile.shortName}</span>
              {profileIsSealed && (
                <span className="text-[8px] px-1 py-0.2 rounded bg-amber-500/20 text-amber-300 font-extrabold ml-0.5">
                  LIVE
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* 2b. Institutional Seal of Excellence Status Banner */}
      <div
        className={`px-4 py-2 border-b flex items-center justify-between text-xs font-mono transition-all ${
          isBotSealed
            ? 'bg-amber-500/15 border-amber-500/40 text-amber-300'
            : 'bg-purple-500/10 border-purple-500/30 text-purple-300'
        }`}
      >
        <div className="flex items-center gap-2">
          <Award className={`w-4 h-4 shrink-0 ${isBotSealed ? 'text-amber-400' : 'text-purple-400'}`} />
          <div className="flex flex-col">
            <div className="flex items-center gap-1.5">
              <span className="font-extrabold text-[11px] uppercase tracking-wider text-white">
                {activeSeal?.seal_status === 'SEALED_BRAVE'
                  ? '🦁 SEAL OF THE BRAVE'
                  : isBotSealed
                  ? '🏆 SEAL OF EXCELLENCE'
                  : '⏳ INCUBATOR SHADOW'}
              </span>
              <span
                className={`text-[9px] px-1.5 py-0.5 rounded font-mono font-bold border ${
                  activeSeal?.seal_status === 'SEALED_BRAVE'
                    ? 'bg-cyan-500/25 text-cyan-200 border-cyan-500/50'
                    : isBotSealed
                    ? 'bg-amber-500/25 text-amber-200 border-amber-500/50'
                    : 'bg-purple-500/20 text-purple-200 border-purple-500/40'
                }`}
              >
                {activeSeal?.seal_token || (isBotSealed ? 'SEAL-EXCELLENT' : 'PENDING-TOKEN')}
              </span>
            </div>
            <span className="text-[10px] text-[#8c9ba5]">
              {activeSeal?.seal_status === 'SEALED_BRAVE'
                ? 'Brave multi-turnover explorer · Lane 1 Live trading authorized'
                : isBotSealed
                ? 'Shadow paper trading removed · Lane 1 Live trading authorized'
                : 'Cooking in Lane 2 Shadow · Live trading blocked'}
            </span>
          </div>
        </div>

        <div className="flex flex-col items-end shrink-0">
          <span
            className={`px-2 py-0.5 rounded text-[10px] font-extrabold border uppercase tracking-wider ${
              isBotSealed
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                : 'bg-yellow-500/15 text-yellow-300 border border-yellow-500/30'
            }`}
          >
            {isBotSealed ? 'LANE 1 LIVE' : `INCUBATING (${activeSeal?.settled_cycles_verified ?? 0}/30)`}
          </span>
          {activeSeal?.empirical_win_rate ? (
            <span className="text-[10px] text-slate-300 mt-0.5 font-bold">
              {(activeSeal.empirical_win_rate * 100).toFixed(1)}% WR · {activeSeal.profit_factor ? `${activeSeal.profit_factor.toFixed(2)} PF` : '—'}
            </span>
          ) : null}
        </div>
      </div>
    </>
  );
};
