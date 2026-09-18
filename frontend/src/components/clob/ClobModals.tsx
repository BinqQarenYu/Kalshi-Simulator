import React from 'react';
import { Bell, Search, Sliders, X } from 'lucide-react';
import { CryptoAsset, MarketState } from '../../types';
import { soundFX } from '../../utils/audioFX';

interface ClobModalsProps {
  isIndicatorsModalOpen: boolean;
  setIsIndicatorsModalOpen: (val: boolean) => void;
  activeIndicators: {
    vpin: boolean;
    orderFlowImbalance: boolean;
    volumeProfile: boolean;
    twap60s: boolean;
    bollingerBands: boolean;
  };
  setActiveIndicators: (fn: any) => void;
  isSearchModalOpen: boolean;
  setIsSearchModalOpen: (val: boolean) => void;
  market: MarketState;
  handleSwitchAsset: (asset: CryptoAsset) => void;
  isNotificationsOpen: boolean;
  setIsNotificationsOpen: (val: boolean) => void;
}

export const ClobModals: React.FC<ClobModalsProps> = ({
  isIndicatorsModalOpen,
  setIsIndicatorsModalOpen,
  activeIndicators,
  setActiveIndicators,
  isSearchModalOpen,
  setIsSearchModalOpen,
  market,
  handleSwitchAsset,
  isNotificationsOpen,
  setIsNotificationsOpen,
}) => {
  return (
    <>
      {isIndicatorsModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 font-mono">
          <div className="bg-[#12161a] border border-[#262d35] rounded-xl w-full max-w-md p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#262d35] pb-3">
              <div className="flex items-center gap-2">
                <Sliders className="w-4 h-4 text-[#38bdf8]" />
                <h3 className="font-bold text-white text-sm">Technical Indicators & Overlays</h3>
              </div>
              <button
                onClick={() => setIsIndicatorsModalOpen(false)}
                className="p-1 text-[#64748b] hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              {[
                { id: 'vpin', label: 'VPIN Flow Toxicity Shield', desc: 'Volume-Synchronized Probability of Toxicity' },
                { id: 'orderFlowImbalance', label: 'Order Flow Imbalance (OFI)', desc: 'Top-of-book taker delta aggression' },
                { id: 'volumeProfile', label: 'Volume Profile by Price (VPVR)', desc: 'Resting inventory distribution' },
                { id: 'twap60s', label: 'Settlement 60s TWAP Parity', desc: 'Official CME CF Benchmark reference' },
                { id: 'bollingerBands', label: 'Bollinger Probability Bands', desc: '2.0 standard deviation volatility channels' },
              ].map((ind) => (
                <div
                  key={ind.id}
                  onClick={() => {
                    soundFX.playClickSound();
                    setActiveIndicators((prev: any) => ({ ...prev, [ind.id]: !prev[ind.id] }));
                  }}
                  className="flex items-center justify-between p-2.5 rounded-lg bg-[#171c22] border border-[#262d35] hover:border-[#38bdf8]/40 cursor-pointer transition"
                >
                  <div>
                    <div className="text-white font-bold">{ind.label}</div>
                    <div className="text-[10px] text-[#8c9ba5]">{ind.desc}</div>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      (activeIndicators as any)[ind.id]
                        ? 'bg-[#00c978]/20 text-[#00c978] border border-[#00c978]/40'
                        : 'bg-[#262d35] text-[#64748b]'
                    }`}
                  >
                    {(activeIndicators as any)[ind.id] ? 'ACTIVE' : 'OFF'}
                  </span>
                </div>
              ))}
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => {
                  soundFX.playClickSound();
                  setIsIndicatorsModalOpen(false);
                }}
                className="px-4 py-1.5 rounded bg-[#00c978] text-black font-bold hover:bg-emerald-400 transition text-xs"
              >
                Apply & Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 2. Quick Search Modal */}
      {isSearchModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 font-mono">
          <div className="bg-[#12161a] border border-[#262d35] rounded-xl w-full max-w-lg p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-[#262d35] pb-3">
              <div className="flex items-center gap-2">
                <Search className="w-4 h-4 text-[#00c978]" />
                <h3 className="font-bold text-white text-sm">Search Kalshi Binary Contracts</h3>
              </div>
              <button
                onClick={() => setIsSearchModalOpen(false)}
                className="p-1 text-[#64748b] hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <input
              type="text"
              placeholder="Search ticker, asset, or strike (e.g. KXBTC15M, $68500, ETH)..."
              className="w-full bg-[#171c22] border border-[#262d35] rounded-lg px-3 py-2 text-white text-xs focus:outline-none focus:border-[#00c978]"
              autoFocus
            />

            <div className="divide-y divide-[#1f262d] text-xs">
              {[
                { asset: 'BTC', ticker: market?.ticker || 'KXBTC15M', name: `Bitcoin Above ${market?.target_strike_str || '$68,500'} at ${market?.target_time_str || 'Expiry'}`, vol: market?.volume_24h_str || '142K' },
                { asset: 'ETH', ticker: 'KXETH15M', name: 'Ethereum Above $3,500 at Expiry', vol: '89K' },
                { asset: 'SOL', ticker: 'KXSOL15M', name: 'Solana Above $175 at Expiry', vol: '64K' },
                { asset: 'DOGE', ticker: 'KXDOGE15M', name: 'Dogecoin Above $0.145 at Expiry', vol: '38K' },
              ].map((item, idx) => (
                <div
                  key={idx}
                  onClick={() => {
                    soundFX.playClickSound();
                    handleSwitchAsset(item.asset as CryptoAsset);
                    setIsSearchModalOpen(false);
                  }}
                  className="py-2.5 px-2 hover:bg-[#171c22] rounded cursor-pointer flex items-center justify-between transition"
                >
                  <div>
                    <div className="text-white font-bold">{item.ticker}</div>
                    <div className="text-[11px] text-[#8c9ba5]">{item.name}</div>
                  </div>
                  <span className="text-[10px] text-[#00c978] bg-[#00c978]/10 px-2 py-0.5 rounded font-bold">
                    {item.vol}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 3. Notifications Flyout */}
      {isNotificationsOpen && (
        <div className="fixed top-14 right-6 w-80 bg-[#12161a] border border-[#262d35] rounded-xl p-4 shadow-2xl z-50 font-mono text-xs space-y-3">
          <div className="flex items-center justify-between border-b border-[#262d35] pb-2">
            <div className="font-bold text-white flex items-center gap-1.5">
              <Bell className="w-3.5 h-3.5 text-[#00c978]" />
              <span>System Notifications</span>
            </div>
            <button onClick={() => setIsNotificationsOpen(false)} className="text-[#64748b] hover:text-white">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="space-y-2 text-[11px]">
            <div className="p-2 rounded bg-[#171c22] border-l-2 border-[#00c978]">
              <div className="text-white font-bold">CME CF Benchmarks 5Hz Active</div>
              <div className="text-[#8c9ba5]">Streaming 200ms BRTI ticks with 60s TWAP parity.</div>
            </div>
            <div className="p-2 rounded bg-[#171c22] border-l-2 border-[#38bdf8]">
              <div className="text-white font-bold">Standalone Bot Engine 8001</div>
              <div className="text-[#8c9ba5]">1-Contract Micro-Bankroll Sizing Armor enforced.</div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
