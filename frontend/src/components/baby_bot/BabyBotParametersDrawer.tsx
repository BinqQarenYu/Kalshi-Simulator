import React from 'react';
import { Sliders, Lock, ShieldCheck, RefreshCw, Save, Zap, Brain } from 'lucide-react';
import { soundFX } from '../../utils/audioFX';
import { BotProfile } from './BabyBotProfiles';
import { MacroDominionDials } from './MacroDominionDials';
import { DualOnnxDials } from './DualOnnxDials';
import { DominationSliders } from './DominationSliders';

export interface BabyBotParametersDrawerProps {
  isMacroDominion: boolean;
  activeProfile: BotProfile;
  botParams: Record<string, any>;
  setBotParams: React.Dispatch<React.SetStateAction<Record<string, any>>>;
  activeAssetKey: string;
  currentAtr: number;
  volFloor: number;
  volCeil: number;
  isSafeVol: boolean;
  isDeadChop: boolean;
  entryDiscount: number;
  maxWinRoi: string;
  tapeStreak: number;
  reqTapeTicks: number;
  isTapeConfirmed: boolean;
  saveSuccessMsg: string | null;
  isSavingParams: boolean;
  handleResetDefaults: () => void;
  handleSaveParameters: () => Promise<void> | void;
  handlePromoteToLive: () => Promise<void> | void;
}

export const BabyBotParametersDrawer: React.FC<BabyBotParametersDrawerProps> = ({
  isMacroDominion,
  activeProfile,
  botParams,
  setBotParams,
  activeAssetKey,
  currentAtr,
  volFloor,
  volCeil,
  isSafeVol,
  isDeadChop,
  entryDiscount,
  maxWinRoi,
  tapeStreak,
  reqTapeTicks,
  isTapeConfirmed,
  saveSuccessMsg,
  isSavingParams,
  handleResetDefaults,
  handleSaveParameters,
  handlePromoteToLive,
}) => {
  return (
          <div className="p-4 bg-[#12161a] border-t border-[#1f262d] space-y-3 font-mono text-xs">
            {isMacroDominion ? (
              <MacroDominionDials
                botParams={botParams}
                setBotParams={setBotParams}
              />
            ) : activeProfile.telemetryType === 'onnx' ? (
              <DualOnnxDials
                botParams={botParams}
                setBotParams={setBotParams}
                currentAtr={currentAtr}
                volFloor={volFloor}
                volCeil={volCeil}
                isSafeVol={isSafeVol}
                isDeadChop={isDeadChop}
                entryDiscount={entryDiscount}
                maxWinRoi={maxWinRoi}
                tapeStreak={tapeStreak}
                reqTapeTicks={reqTapeTicks}
                isTapeConfirmed={isTapeConfirmed}
              />
            ) : (
              <DominationSliders
                botParams={botParams}
                setBotParams={setBotParams}
                activeAssetKey={activeAssetKey}
              />
            )}

            {/* Footer with Reset Defaults & Apply & Save */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2 border-t border-[#1f262d]">
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-[#8c9ba5] flex items-center gap-1">
                  <span>Target:</span>
                  <span className="text-white font-semibold">{activeProfile.name}</span>
                </span>
                {saveSuccessMsg && (
                  <span className="text-[10px] font-mono text-emerald-400 font-bold animate-pulse">
                    {saveSuccessMsg}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleResetDefaults}
                  type="button"
                  title="Reset to recommended quant sweetspots"
                  className="px-2.5 py-1.5 rounded bg-[#171c22] hover:bg-[#222933] text-amber-300 hover:text-amber-200 border border-amber-500/30 text-[10px] font-bold transition-all cursor-pointer flex items-center gap-1"
                >
                  <span>🎯</span>
                  <span>{activeProfile.telemetryType === 'macro_dominion' ? 'Reset Macro Sweetspots' : activeProfile.telemetryType === 'onnx' ? 'Reset Quant Sweetspots' : 'Sweetspots Preset'}</span>
                </button>
                <button
                  onClick={handleSaveParameters}
                  disabled={isSavingParams}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#00bda5] text-black font-bold text-xs hover:bg-[#2dd4bf] transition-all shadow cursor-pointer disabled:opacity-50"
                >
                  {isSavingParams ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                  <span>{activeProfile.telemetryType === 'macro_dominion' || activeProfile.telemetryType === 'onnx' ? 'Apply Strategy Dials' : 'Apply & Save as Default'}</span>
                </button>

                <button
                  onClick={handlePromoteToLive}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-red-600 text-white font-bold text-xs hover:bg-red-500 transition-all shadow cursor-pointer"
                >
                  <Zap className="w-3.5 h-3.5" />
                  <span>PROMOTE TO LIVE</span>
                </button>
              </div>
            </div>
          </div>
  );
};
