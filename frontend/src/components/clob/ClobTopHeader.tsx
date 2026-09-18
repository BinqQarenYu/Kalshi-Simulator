import React from 'react';
import { Bell, ChevronDown, Clock, Search } from 'lucide-react';
import { soundFX } from '../../utils/audioFX';

export type TopNavTab = 'Trading' | 'Live' | 'Topics' | 'Events' | 'Community' | 'Support';

interface ClobTopHeaderProps {
  activeTopTab: TopNavTab;
  setActiveTopTab: (tab: TopNavTab) => void;
  timeZoneDisplay: 'EST' | 'UTC';
  setTimeZoneDisplay: (fn: (prev: 'EST' | 'UTC') => 'EST' | 'UTC') => void;
  currentTimeStr: string;
  isSearchModalOpen: boolean;
  setIsSearchModalOpen: (val: boolean) => void;
  isNotificationsOpen: boolean;
  setIsNotificationsOpen: (val: boolean) => void;
}

export const ClobTopHeader: React.FC<ClobTopHeaderProps> = ({
  activeTopTab,
  setActiveTopTab,
  timeZoneDisplay,
  setTimeZoneDisplay,
  currentTimeStr,
  isSearchModalOpen,
  setIsSearchModalOpen,
  isNotificationsOpen,
  setIsNotificationsOpen,
}) => {
  return (
      <header className="h-12 bg-[#0e131b] border-b border-[#1f2937] px-4 flex items-center justify-between shrink-0 z-30">
        {/* Brand & Left Navigation Links */}
        <div className="flex items-center gap-6">
          {/* Kalshi Logo Badge */}
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-1 rounded bg-[#00c978] text-black font-extrabold text-xs tracking-tight shadow-md">
              Kalshi
            </span>
          </div>

          {/* Navigation Items */}
          <nav className="flex items-center gap-1 text-xs font-semibold">
            {(['Trading', 'Live', 'Topics', 'Events', 'Community', 'Support'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => {
                  soundFX.playClickSound();
                  setActiveTopTab(tab);
                }}
                className={`px-3 py-1.5 rounded transition flex items-center gap-1 cursor-pointer ${
                  activeTopTab === tab
                    ? 'text-white bg-[#17202d] border-b-2 border-[#00c978] font-bold'
                    : 'text-[#8c9ba5] hover:text-white hover:bg-[#131923]'
                }`}
              >
                <span>{tab}</span>
                {['Topics', 'Events', 'Community'].includes(tab) && (
                  <ChevronDown className="w-3 h-3 text-[#64748b]" />
                )}
              </button>
            ))}
          </nav>
        </div>

        {/* Right Section: Status Pill, Clock, Utilities & Avatar */}
        <div className="flex items-center gap-4 text-xs font-mono">
          {/* Live Status Badge */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#00c978]/15 border border-[#00c978]/30 text-[#00c978] font-bold">
            <span className="w-2 h-2 rounded-full bg-[#00c978] animate-ping" />
            <span>LIVE</span>
          </div>

          {/* Eastern Time / UTC Live Clock Toggle */}
          <button
            onClick={() => {
              soundFX.playClickSound();
              setTimeZoneDisplay((prev) => (prev === 'EST' ? 'UTC' : 'EST'));
            }}
            title="Click to toggle EST / UTC"
            className="text-slate-300 hover:text-white transition flex items-center gap-1 bg-[#131923] px-2.5 py-1 rounded border border-[#1f2937]"
          >
            <Clock className="w-3.5 h-3.5 text-[#00c978]" />
            <span>{currentTimeStr || 'May 24, 2024 14:58:15 EST'}</span>
          </button>

          {/* Search Icon Trigger */}
          <button
            onClick={() => {
              soundFX.playClickSound();
              setIsSearchModalOpen(!isSearchModalOpen);
            }}
            className="p-1.5 rounded text-[#8c9ba5] hover:text-white hover:bg-[#17202d] transition"
            title="Search Markets & Contracts"
          >
            <Search className="w-4 h-4" />
          </button>

          {/* Notification Bell */}
          <button
            onClick={() => {
              soundFX.playClickSound();
              setIsNotificationsOpen(!isNotificationsOpen);
            }}
            className="p-1.5 rounded text-[#8c9ba5] hover:text-white hover:bg-[#17202d] transition relative"
            title="Notifications"
          >
            <Bell className="w-4 h-4" />
            <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-[#00c978]" />
          </button>

          {/* User Profile Avatar */}
          <div className="flex items-center gap-2 pl-2 border-l border-[#1f2937]">
            <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-emerald-600 to-teal-400 flex items-center justify-center font-bold text-black text-xs shadow">
              OP
            </div>
          </div>
        </div>
      </header>
  );
};
