import React, { useState, useRef, useEffect } from 'react';
import { AISignals } from '../types';
import {
  Cpu,
  Zap,
  ShieldCheck,
  ShieldAlert,
  DollarSign,
  Activity,
  Play,
  Loader2,
  Award,
  ChevronDown,
  Check,
  Sliders,
  Flame,
  TrendingUp,
  Target,
  Sparkles,
  Crown,
  Shield,
} from 'lucide-react';
import { soundFX } from '../utils/audioFX';
import { getAssetMeta } from '../utils/assets';

interface AIMicrostructureCardProps {
  signals: AISignals;
  activeAsset?: string;
  onSelectStrategy?: (strategyId: string) => Promise<any>;
  onTestBot?: () => Promise<any>;
  onOpenReports?: () => void;
  dominationDiscountPrice?: number;
  onUpdateDiscountPrice?: (price: number) => Promise<any>;
}

export const AIMicrostructureCard: React.FC<AIMicrostructureCardProps> = React.memo(({
  signals,
  activeAsset,
  onSelectStrategy,
  onTestBot,
  onOpenReports,
  dominationDiscountPrice,
  onUpdateDiscountPrice,
}) => {
  const assetMeta = getAssetMeta(activeAsset);
  const [isTesting, setIsTesting] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [isDropdownOpen, setIsDropdownOpen] = useState<boolean>(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const [localDiscount, setLocalDiscount] = useState<number>(
    dominationDiscountPrice ?? signals.discount_limit_price ?? 0.48
  );

  useEffect(() => {
    if (dominationDiscountPrice !== undefined) {
      setLocalDiscount(dominationDiscountPrice);
    } else if (signals.discount_limit_price !== undefined) {
      setLocalDiscount(signals.discount_limit_price);
    }
  }, [dominationDiscountPrice, signals.discount_limit_price]);

  const handleDiscountChange = async (newPrice: number) => {
    const rounded = Math.round(newPrice * 100) / 100;
    const clamped = Math.min(0.50, Math.max(0.15, rounded));
    setLocalDiscount(clamped);
    if (onUpdateDiscountPrice) {
      try {
        await onUpdateDiscountPrice(clamped);
        setFeedback(`Maker Discount Limit set to $${clamped.toFixed(2)} (${(clamped * 100).toFixed(0)}¢)`);
        setTimeout(() => setFeedback(null), 3000);
      } catch (err) {
        setFeedback('Failed to update discount limit');
        setTimeout(() => setFeedback(null), 3000);
      }
    }
  };

  const activeStrategy = signals.strategy_id || '3_step_domination_bot';
  const isMacroOnnx = activeStrategy === 'macro_onnx' || activeStrategy === 'macro_onnx_bot' || activeStrategy === 'macro_trend_onnx_fusion';
  const isMacroTrend = !isMacroOnnx && (activeStrategy === 'macro_trend_dominion' || activeStrategy === 'macro_trend');
  const isDominion2 = activeStrategy === 'dominion_2_bot';
  const is3StepBot = activeStrategy === '3_step_domination_bot';
  const isOnnxBot = activeStrategy === 'onnx_microstructure_bot';

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const pUpPct = (((signals?.p_up ?? 0)) * 100).toFixed(1);
  const pDnPct = (((signals?.p_down ?? 0)) * 100).toFixed(1);
  const pWaitPct = (((signals?.p_wait ?? 0)) * 100).toFixed(1);

  const handleStrategyChange = async (strategyId: string) => {
    soundFX.playClickSound();
    setIsDropdownOpen(false);
    if (onSelectStrategy) {
      try {
        await onSelectStrategy(strategyId);
        setFeedback(`Switched to ${strategyId.replace(/_/g, ' ')}`);
        setTimeout(() => setFeedback(null), 3000);
      } catch (err: any) {
        setFeedback('Failed to switch strategy');
        setTimeout(() => setFeedback(null), 3000);
      }
    }
  };

  const handleTestBot = async () => {
    if (!onTestBot || isTesting) return;
    setIsTesting(true);
    soundFX.playOrderFillSound();
    try {
      const res = await onTestBot();
      const stratName = isMacroOnnx ? 'Macro ONNX Bot' : isMacroTrend ? 'Macro Trend Dominion' : isDominion2 ? 'Dominion 2' : is3StepBot ? '3-Step Domination' : 'ONNX ML';
      setFeedback(`Generated Test Trade for ${stratName}!`);
      setTimeout(() => setFeedback(null), 4000);
    } catch (err: any) {
      setFeedback('Test trade failed');
      setTimeout(() => setFeedback(null), 3000);
    } finally {
      setIsTesting(false);
    }
  };

  // Playbook badge styling
  const getPlaybookBadge = () => {
    const pb = signals.active_playbook || '';
    if (pb.includes('Playbook 3') || pb.includes('Gamma')) {
      return {
        icon: <Flame className="h-3 w-3 text-rose-400" />,
        text: 'Playbook 3: Gamma Snub',
        bg: 'bg-rose-500/15 border-rose-500/30 text-rose-300',
      };
    }
    if (pb.includes('Playbook 2') || pb.includes('OFI') || pb.includes('Continuation')) {
      return {
        icon: <Zap className="h-3 w-3 text-amber-400" />,
        text: 'Playbook 2: Trend Continuation',
        bg: 'bg-amber-500/15 border-amber-500/30 text-amber-300',
      };
    }
    if (pb.includes('Playbook 1') || pb.includes('Expansion') || pb.includes('Breakout')) {
      return {
        icon: <TrendingUp className="h-3 w-3 text-cyan-400" />,
        text: 'Playbook 1: Trend Expansion',
        bg: 'bg-cyan-500/15 border-cyan-500/30 text-cyan-300',
      };
    }
    return {
      icon: <Target className="h-3 w-3 text-emerald-400" />,
      text: signals.active_playbook || 'Quantitative Playbook Active',
      bg: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300',
    };
  };

  const playbook = getPlaybookBadge();

  return (
    <div className="bg-[#111620] border border-[#21262d] rounded-2xl p-4 sm:p-5 flex flex-col gap-4 shadow-xl">
      {/* Header with Strategy Dropdown Selector */}
      <div className="flex items-center justify-between border-b border-[#21262d] pb-3">
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => {
              soundFX.playClickSound();
              setIsDropdownOpen(!isDropdownOpen);
            }}
            className="flex items-center gap-2 px-3 py-1.5 bg-[#161b22] hover:bg-[#21262d] border border-[#30363d] hover:border-blue-500/50 rounded-xl transition-all shadow-sm group"
            title="Click to switch strategy bot"
          >
            {isMacroOnnx ? (
              <div className="h-5 w-5 rounded-lg bg-purple-500/20 border border-purple-500/40 flex items-center justify-center">
                <Cpu className="h-3.5 w-3.5 text-purple-300" />
              </div>
            ) : isMacroTrend ? (
              <div className="h-5 w-5 rounded-lg bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center">
                <TrendingUp className="h-3.5 w-3.5 text-cyan-400" />
              </div>
            ) : isDominion2 ? (
              <div className="h-5 w-5 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center">
                <Crown className="h-3.5 w-3.5 text-emerald-400" />
              </div>
            ) : is3StepBot ? (
              <div className="h-5 w-5 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center justify-center">
                <Zap className="h-3.5 w-3.5 text-amber-400" />
              </div>
            ) : (
              <div className="h-5 w-5 rounded-lg bg-blue-500/20 border border-blue-500/40 flex items-center justify-center">
                <Cpu className="h-3.5 w-3.5 text-blue-400" />
              </div>
            )}

            <div className="text-left">
              <div className="text-xs font-bold text-white flex items-center gap-1.5">
                <span>{isMacroOnnx ? 'Macro ONNX Bot' : isMacroTrend ? 'Macro Trend Dominion' : isDominion2 ? 'Dominion 2 Bot' : is3StepBot ? '3-Step Domination Bot' : 'ONNX Microstructure Bot'}</span>
                <ChevronDown className={`h-3 w-3 text-gray-400 transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`} />
              </div>
            </div>
          </button>

          {/* Strategy Dropdown Menu */}
          {isDropdownOpen && (
            <div className="absolute left-0 top-full mt-2 w-72 bg-[#161b22] border border-[#30363d] rounded-2xl shadow-2xl z-50 p-2 flex flex-col gap-1 animate-in fade-in zoom-in-95">
              <div className="px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wider text-gray-400 border-b border-[#21262d]">
                Select Quantitative Trading Bot
              </div>

              {/* Champion: Macro ONNX Bot */}
              <button
                onClick={() => handleStrategyChange('macro_onnx')}
                className={`w-full p-2.5 rounded-xl text-left flex items-start justify-between gap-2 transition-all ${
                  isMacroOnnx
                    ? 'bg-purple-500/20 border border-purple-500/50'
                    : 'hover:bg-[#21262d] border border-transparent'
                }`}
              >
                <div className="flex items-start gap-2.5">
                  <div className="h-7 w-7 rounded-lg bg-purple-500/25 border border-purple-500/50 flex items-center justify-center shrink-0 mt-0.5">
                    <Cpu className="h-4 w-4 text-purple-300" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-white flex items-center gap-1.5">
                      <span>Macro ONNX Bot</span>
                      <span className="px-1.5 py-0.2 text-[9px] font-mono bg-purple-500/30 text-purple-200 border border-purple-500/40 rounded-full font-bold">
                        Champion
                      </span>
                    </div>
                    <p className="text-[10px] text-gray-400 mt-0.5 leading-tight">
                      1h/15m Macro Trend + {assetMeta.id} L2 Orderflow • ${assetMeta.minSpotDiff} Gate
                    </p>
                  </div>
                </div>
                {isMacroOnnx && <Check className="h-4 w-4 text-purple-400 shrink-0 mt-1" />}
              </button>

              {/* Bot: Macro Trend Dominion */}
              <button
                onClick={() => handleStrategyChange('macro_trend_dominion')}
                className={`w-full p-2.5 rounded-xl text-left flex items-start justify-between gap-2 transition-all ${
                  isMacroTrend
                    ? 'bg-cyan-500/15 border border-cyan-500/40'
                    : 'hover:bg-[#21262d] border border-transparent'
                }`}
              >
                <div className="flex items-start gap-2.5">
                  <div className="h-7 w-7 rounded-lg bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center shrink-0 mt-0.5">
                    <TrendingUp className="h-4 w-4 text-cyan-400" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-white flex items-center gap-1.5">
                      <span>Macro Trend Dominion</span>
                      <span className="px-1.5 py-0.2 text-[9px] font-mono bg-cyan-500/20 text-cyan-300 rounded-full font-bold">
                        Macro Trend
                      </span>
                    </div>
                    <p className="text-[10px] text-gray-400 mt-0.5 leading-tight">
                      1h Trend Alignment • Anti-Countertrend • 1-Ct Sizing • Late Sniper
                    </p>
                  </div>
                </div>
                {isMacroTrend && <Check className="h-4 w-4 text-cyan-400 shrink-0 mt-1" />}
              </button>

              {/* Bot 0: Dominion 2 Bot (Anti-Pin Scalper) */}
              <button
                onClick={() => handleStrategyChange('dominion_2_bot')}
                className={`w-full p-2.5 rounded-xl text-left flex items-start justify-between gap-2 transition-all ${
                  isDominion2
                    ? 'bg-emerald-500/15 border border-emerald-500/40'
                    : 'hover:bg-[#21262d] border border-transparent'
                }`}
              >
                <div className="flex items-start gap-2.5">
                  <div className="h-7 w-7 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center shrink-0 mt-0.5">
                    <Crown className="h-4 w-4 text-emerald-400" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-white flex items-center gap-1.5">
                      <span>Dominion 2 Bot</span>
                      <span className="px-1.5 py-0.2 text-[9px] font-mono bg-emerald-500/20 text-emerald-300 rounded-full font-bold">
                        Anti-Pin Scalper
                      </span>
                    </div>
                    <p className="text-[10px] text-gray-400 mt-0.5 leading-tight">
                      Entry Ceiling ≤$0.55 • Discount Hunting • Tie Edge • Pin Defense
                    </p>
                  </div>
                </div>
                {isDominion2 && <Check className="h-4 w-4 text-emerald-400 shrink-0 mt-1" />}
              </button>

              {/* Bot 1: 3-Step Domination Bot */}
              <button
                onClick={() => handleStrategyChange('3_step_domination_bot')}
                className={`w-full p-2.5 rounded-xl text-left flex items-start justify-between gap-2 transition-all ${
                  is3StepBot
                    ? 'bg-amber-500/15 border border-amber-500/40'
                    : 'hover:bg-[#21262d] border border-transparent'
                }`}
              >
                <div className="flex items-start gap-2.5">
                  <div className="h-7 w-7 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center justify-center shrink-0 mt-0.5">
                    <Zap className="h-4 w-4 text-amber-400" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-white flex items-center gap-1.5">
                      <span>3-Step Domination Bot</span>
                      <span className="px-1.5 py-0.2 text-[9px] font-mono bg-amber-500/20 text-amber-300 rounded-full font-bold">
                        Playbooks
                      </span>
                    </div>
                    <p className="text-[10px] text-gray-400 mt-0.5 leading-tight">
                      Early Breakout • Mid OFI Drift • Late Gamma Snub
                    </p>
                  </div>
                </div>
                {is3StepBot && <Check className="h-4 w-4 text-amber-400 shrink-0 mt-1" />}
              </button>

              {/* Bot 2: ONNX Microstructure Bot */}
              <button
                onClick={() => handleStrategyChange('onnx_microstructure_bot')}
                className={`w-full p-2.5 rounded-xl text-left flex items-start justify-between gap-2 transition-all ${
                  isOnnxBot
                    ? 'bg-blue-500/15 border border-blue-500/40'
                    : 'hover:bg-[#21262d] border border-transparent'
                }`}
              >
                <div className="flex items-start gap-2.5">
                  <div className="h-7 w-7 rounded-lg bg-blue-500/20 border border-blue-500/40 flex items-center justify-center shrink-0 mt-0.5">
                    <Cpu className="h-4 w-4 text-blue-400" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-white flex items-center gap-1.5">
                      <span>ONNX Microstructure Bot</span>
                      <span className="px-1.5 py-0.2 text-[9px] font-mono bg-blue-500/20 text-blue-300 rounded-full font-bold">
                        Neural Net
                      </span>
                    </div>
                    <p className="text-[10px] text-gray-400 mt-0.5 leading-tight">
                      28-D Deep Feature Tensor + ONNX CPU Inference
                    </p>
                  </div>
                </div>
                {isOnnxBot && <Check className="h-4 w-4 text-blue-400 shrink-0 mt-1" />}
              </button>
            </div>
          )}
        </div>

        {/* Reports & Model Indicator */}
        <div className="flex items-center gap-2">
          {onOpenReports && (
            <button
              onClick={onOpenReports}
              className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-bold text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 rounded-xl transition-colors shadow-sm"
              title="Open 15-Minute Event Win/Loss Reports"
            >
              <Award className="h-3.5 w-3.5" />
              <span>Reports</span>
            </button>
          )}
          <span className="text-[10px] font-mono text-gray-500 hidden sm:inline">
            {isMacroOnnx ? 'nano_microscope_overhauled.onnx' : isMacroTrend ? 'macro_trend_dominion.py' : isDominion2 ? 'dominion_2_bot.py' : is3StepBot ? '3_step_domination.py' : 'nano_microscope.onnx'}
          </span>
        </div>
      </div>

      {/* 3-Step Domination Bot: Active Playbook Stage Badge */}
      {is3StepBot && (
        <div className={`p-2.5 rounded-xl border flex items-center justify-between text-xs font-semibold ${playbook.bg}`}>
          <div className="flex items-center gap-2">
            {playbook.icon}
            <span className="text-[11px] font-bold tracking-tight">{playbook.text}</span>
          </div>
          <span className="px-2 py-0.5 text-[10px] font-mono font-bold bg-black/30 rounded-full uppercase">
            Active
          </span>
        </div>
      )}

      {/* ⚡ Option B: Maker Discount Sniper Controller ($0.00 Fees) */}
      {is3StepBot && (
        <div className="bg-[#161b22] border border-amber-500/30 rounded-xl p-3.5 flex flex-col gap-3 shadow-inner">
          <div className="flex items-center justify-between border-b border-[#21262d] pb-2">
            <div className="flex items-center gap-2">
              <div className="h-6 w-6 rounded-lg bg-amber-500/20 border border-amber-500/40 flex items-center justify-center">
                <Sliders className="h-3.5 w-3.5 text-amber-400" />
              </div>
              <div>
                <div className="text-xs font-bold text-white flex items-center gap-1.5">
                  <span>DISCOUNT SNIPER CONTROLLER</span>
                  <span className="px-1.5 py-0.2 text-[9px] font-mono bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 rounded-full font-bold">
                    $0.00 FEE
                  </span>
                </div>
                <div className="text-[10px] text-gray-400">
                  Option B: Resting Maker Limit Orders • Never chases expensive asks
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs font-mono font-bold text-amber-400">
                {(localDiscount * 100).toFixed(0)}¢ Cap
              </div>
              <div className="text-[9px] font-mono text-gray-500">
                Max Entry Limit
              </div>
            </div>
          </div>

          {/* Quick Preset Pills */}
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between items-center text-[10px] font-semibold text-[#8b949e]">
              <span>QUICK PRESETS</span>
              <span className="font-mono text-gray-400">Target Entry Price</span>
            </div>
            <div className="grid grid-cols-5 gap-1.5">
              {[0.30, 0.35, 0.40, 0.45, 0.48].map((preset) => {
                const isActive = Math.abs(localDiscount - preset) < 0.005;
                return (
                  <button
                    key={preset}
                    onClick={() => {
                      soundFX.playClickSound();
                      handleDiscountChange(preset);
                    }}
                    className={`py-1.5 px-2 rounded-lg text-xs font-mono font-bold transition-all border ${
                      isActive
                        ? 'bg-amber-500/25 border-amber-400 text-amber-300 shadow-sm shadow-amber-500/30 scale-[1.02]'
                        : 'bg-[#0d1117] border-[#30363d] text-gray-300 hover:border-amber-500/50 hover:bg-[#21262d]'
                    }`}
                  >
                    {(preset * 100).toFixed(0)}¢
                  </button>
                );
              })}
            </div>
          </div>

          {/* Precision Range Slider */}
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between items-center text-[10px] font-semibold text-[#8b949e]">
              <span>FINE-TUNE DISCOUNT CEILING</span>
              <span className="font-mono text-amber-300 font-bold">${localDiscount.toFixed(2)}</span>
            </div>
            <input
              type="range"
              min="0.15"
              max="0.50"
              step="0.01"
              value={localDiscount}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                setLocalDiscount(val);
              }}
              onPointerUp={() => handleDiscountChange(localDiscount)}
              onKeyUp={() => handleDiscountChange(localDiscount)}
              className="w-full h-1.5 bg-[#21262d] rounded-lg appearance-none cursor-pointer accent-amber-400"
            />
            <div className="flex justify-between text-[9px] font-mono text-gray-500">
              <span>15¢ (Deep Value)</span>
              <span>35¢ (Sweet Spot)</span>
              <span>50¢ (Even Odds)</span>
            </div>
          </div>

          {/* Live Asymmetric Risk/Reward Matrix */}
          <div className="grid grid-cols-4 gap-2 bg-[#0d1117] border border-[#30363d] rounded-lg p-2 text-center">
            <div>
              <div className="text-[9px] text-gray-400 font-medium">MAX RISK</div>
              <div className="text-xs font-mono font-bold text-rose-400">
                {(localDiscount * 100).toFixed(0)}¢
              </div>
            </div>
            <div>
              <div className="text-[9px] text-gray-400 font-medium">MAX PROFIT</div>
              <div className="text-xs font-mono font-bold text-emerald-400">
                {((1 - localDiscount) * 100).toFixed(0)}¢
              </div>
            </div>
            <div>
              <div className="text-[9px] text-gray-400 font-medium">PAYOUT ROI</div>
              <div className="text-xs font-mono font-bold text-amber-300">
                {localDiscount > 0 ? (((1 - localDiscount) / localDiscount)).toFixed(2) : '0.00'}x
              </div>
            </div>
            <div>
              <div className="text-[9px] text-gray-400 font-medium">MAKER FEE</div>
              <div className="text-xs font-mono font-bold text-cyan-400">
                $0.00
              </div>
            </div>
          </div>

          {/* Maker Sniper Status Banner */}
          <div className="text-[10px] text-gray-400 bg-amber-500/10 border border-amber-500/20 rounded-lg p-2 flex items-center gap-2">
            <Target className="h-3.5 w-3.5 text-amber-400 shrink-0" />
            <span className="leading-tight">
              {signals.order_type === 'limit' && signals.limit_price
                ? `Resting Maker Limit armed at $${signals.limit_price.toFixed(2)} (${signals.recommended_side?.toUpperCase()}). Auto-cancels at T<=45s.`
                : `Sniper will rest limit order at ≤$${localDiscount.toFixed(2)} with $0.00 fee when edge triggers.`}
            </span>
          </div>
        </div>
      )}

      {/* Directional Probabilities */}
      <div className="flex flex-col gap-2">
        <div className="flex justify-between items-center text-xs">
          <span className="text-[#8b949e] font-semibold">
            {isMacroOnnx ? 'Macro Trend + 15M ONNX Directional Inference' : is3StepBot ? 'Digital Option Moneyness Probability' : 'Directional Microstructure Inference'}
          </span>
          <span className="text-[11px] font-mono text-gray-400">
            {isMacroOnnx ? 'Macro Trend + 28-D ONNX' : is3StepBot ? 'Phi(z) Normal CDF' : '28-D Feature Tensor'}
          </span>
        </div>

        {/* Probability Bar */}
        <div className="h-3 w-full bg-[#161b22] rounded-full overflow-hidden flex border border-[#30363d]">
          <div
            style={{ width: `${pUpPct}%` }}
            className="bg-[#00d084] h-full transition-all duration-300"
            title={`P(YES/UP): ${pUpPct}%`}
          />
          <div
            style={{ width: `${pWaitPct}%` }}
            className="bg-gray-500 h-full transition-all duration-300"
            title={`P(WAIT): ${pWaitPct}%`}
          />
          <div
            style={{ width: `${pDnPct}%` }}
            className="bg-[#ff4d4d] h-full transition-all duration-300"
            title={`P(NO/DOWN): ${pDnPct}%`}
          />
        </div>

        <div className="grid grid-cols-3 text-center text-xs font-mono pt-1">
          <div className="text-[#00d084] font-bold">
            YES: {pUpPct}%
          </div>
          <div className="text-gray-400 font-medium">
            WAIT: {pWaitPct}%
          </div>
          <div className="text-[#ff4d4d] font-bold">
            NO: {pDnPct}%
          </div>
        </div>
      </div>

      {/* Mathematical EV & Kelly Optimizer (Net Post-Fee) */}
      <div className="grid grid-cols-2 gap-2.5 pt-1 text-xs">
        {/* Expected Value YES */}
        <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-2.5 flex flex-col gap-1">
          <div className="text-[11px] text-[#8b949e] flex items-center justify-between font-semibold">
            <span className="flex items-center gap-1">
              <DollarSign className="h-3 w-3 text-[#00d084]" />
              <span>Net E[YES]</span>
            </span>
            <span className="text-[9px] text-gray-500 font-mono">-1¢ fee</span>
          </div>
          <div className={`font-mono text-sm font-bold ${(signals?.ev_yes ?? 0) >= 0.02 ? 'text-[#00d084]' : 'text-gray-300'}`}>
            {(signals?.ev_yes ?? 0) >= 0 ? '+' : ''}${(((signals?.ev_yes ?? 0)) * 100).toFixed(1)}¢
          </div>
          <div className="text-[10px] text-[#8b949e]">
            Kelly f*: {(((signals?.kelly_f_yes ?? 0)) * 100).toFixed(1)}%
          </div>
        </div>

        {/* Expected Value NO */}
        <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-2.5 flex flex-col gap-1">
          <div className="text-[11px] text-[#8b949e] flex items-center justify-between font-semibold">
            <span className="flex items-center gap-1">
              <DollarSign className="h-3 w-3 text-[#ff4d4d]" />
              <span>Net E[NO]</span>
            </span>
            <span className="text-[9px] text-gray-500 font-mono">-1¢ fee</span>
          </div>
          <div className={`font-mono text-sm font-bold ${(signals?.ev_no ?? 0) >= 0.02 ? 'text-[#ff4d4d]' : 'text-gray-300'}`}>
            {(signals?.ev_no ?? 0) >= 0 ? '+' : ''}${(((signals?.ev_no ?? 0)) * 100).toFixed(1)}¢
          </div>
          <div className="text-[10px] text-[#8b949e]">
            Kelly f*: {(((signals?.kelly_f_no ?? 0)) * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Real Bitcoin Orderflow Telemetry (ONNX Machine Learning) */}
      {signals.onnx_signal && (
        <div className="flex items-center justify-between bg-[#161b22] border border-cyan-500/30 rounded-xl p-3 text-xs">
          <div className="flex items-center gap-2">
            <Cpu className="h-4 w-4 text-cyan-400" />
            <div>
              <div className="font-semibold text-white flex items-center gap-1.5">
                <span>{assetMeta.name} Orderflow (ONNX)</span>
                <span className="px-1.5 py-0.2 text-[8px] font-mono bg-cyan-500/20 text-cyan-300 rounded font-bold">
                  {assetMeta.id} SPOT L2
                </span>
              </div>
              <div className="text-[10px] text-[#8b949e]">
                Long: {((signals.onnx_prob_long ?? 0) * 100).toFixed(1)}% • Short: {((signals.onnx_prob_short ?? 0) * 100).toFixed(1)}%
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full font-bold font-mono text-[11px] ${
              signals.onnx_signal === 'LONG'
                ? 'bg-[#00d084]/20 text-[#00d084] border border-[#00d084]/40'
                : signals.onnx_signal === 'SHORT'
                ? 'bg-[#ff4d4d]/20 text-[#ff4d4d] border border-[#ff4d4d]/40'
                : 'bg-gray-500/20 text-gray-300 border border-gray-500/40'
            }`}>
              {signals.onnx_signal} ({((signals.onnx_confidence ?? 0) * 100).toFixed(0)}%)
            </span>
          </div>
        </div>
      )}

      {/* VPIN Toxicity Guardrail */}
      <div className="flex items-center justify-between bg-[#161b22] border border-[#30363d] rounded-xl p-3 text-xs">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-[#f59e0b]" />
          <div>
            <div className="font-semibold text-white">VPIN Toxicity Index</div>
            <div className="text-[10px] text-[#8b949e]">Volume-Synchronized Imbalance</div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-mono font-bold text-white text-sm">
            {(signals?.vpin ?? 0).toFixed(2)}
          </span>
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-bold text-[10px] ${
            signals.vpin_is_safe
              ? 'bg-[#00d084]/15 text-[#00d084] border border-[#00d084]/30'
              : 'bg-[#ff4d4d]/15 text-[#ff4d4d] border border-[#ff4d4d]/30'
          }`}>
            {signals.vpin_is_safe ? (
              <>
                <ShieldCheck className="h-3 w-3" />
                SAFE
              </>
            ) : (
              <>
                <ShieldAlert className="h-3 w-3" />
                VETO
              </>
            )}
          </span>
        </div>
      </div>

      {/* AI Decision Rationale */}
      <div className="p-2.5 rounded-xl bg-[#161b22] border border-[#30363d] text-xs flex flex-col gap-1">
        <div className="text-[10px] font-bold uppercase tracking-wider text-[#8b949e]">
          Quantitative Alpha Rationale
        </div>
        <p className="text-gray-300 font-medium leading-relaxed text-[11px]">
          {signals.rationale}
        </p>
      </div>

      {/* Test Bot Trigger Button */}
      {onTestBot && (
        <div className="flex flex-col gap-2 pt-1">
          <button
            onClick={handleTestBot}
            disabled={isTesting}
            className={`w-full py-2.5 px-4 text-white font-bold text-xs rounded-xl shadow-lg active:scale-[0.98] flex items-center justify-center gap-2 transition-all disabled:opacity-50 ${
              isMacroOnnx
                ? 'bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 shadow-purple-500/25'
                : isMacroTrend
                ? 'bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 shadow-cyan-500/20'
                : isDominion2
                ? 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 shadow-emerald-500/20'
                : is3StepBot
                ? 'bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 shadow-amber-500/20'
                : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 shadow-blue-500/20'
            }`}
            title="Execute immediate AI Evaluation & 15-Minute Cycle Test Trade"
          >
            {isTesting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin text-white" />
                <span>Running {isMacroOnnx ? 'Macro ONNX (84.6% WR)' : isMacroTrend ? 'Macro Trend' : isDominion2 ? 'Dominion 2' : is3StepBot ? '3-Step Playbook' : 'ONNX AI'} Evaluation...</span>
              </>
            ) : (
              <>
                <Play className="h-3.5 w-3.5 fill-current text-white/90" />
                <span>🧪 Test {isMacroOnnx ? 'Macro ONNX Bot (84.6% WR)' : isMacroTrend ? 'Macro Trend Dominion' : isDominion2 ? 'Dominion 2' : is3StepBot ? '3-Step Domination' : 'ONNX Bot'} (15M Event)</span>
              </>
            )}
          </button>

          {feedback && (
            <div className="p-2 bg-blue-500/15 border border-blue-500/30 rounded-xl text-[11px] font-mono text-blue-300 flex items-center gap-1.5 animate-in fade-in">
              <Activity className="h-3.5 w-3.5 text-blue-400 shrink-0" />
              <span className="truncate">{feedback}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
});
