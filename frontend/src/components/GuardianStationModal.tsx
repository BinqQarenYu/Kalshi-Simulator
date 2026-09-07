/**
 * @file GuardianStationModal.tsx
 * @description Consolidated Institutional Guardian Station Modal uniting:
 * 1. 15M Event Win/Loss Reports & Trade Journal
 * 2. Real-Time Parity & Quantitative Integrity Audit
 * 3. CFTC Regulatory & Law & Order Compliance
 * 4. System Governor, CPU/RAM Metrics & GC Sweep
 */

import React from 'react';
import { 
  WinLossEventReport, 
  IntegrityStatus, 
  ComplianceStatus, 
  SystemResourceMetrics 
} from '../types';
import { WinLossReportsModal } from './WinLossReportsModal';
import { IntegrityModal } from './IntegrityModal';
import { ComplianceModal } from './ComplianceModal';
import { SystemResourcesModal } from './SystemResourcesModal';
import { 
  Trophy, 
  ShieldCheck, 
  Scale, 
  Cpu, 
  X 
} from 'lucide-react';
import { soundFX } from '../utils/audioFX';

export type GuardianTab = 'reports' | 'integrity' | 'compliance' | 'resources';

interface GuardianStationModalProps {
  isOpen: boolean;
  onClose: () => void;
  activeTab: GuardianTab;
  onSelectTab: (tab: GuardianTab) => void;
  // Reports
  reports?: WinLossEventReport[];
  onTestBot?: () => Promise<any>;
  isLiveMode?: boolean;
  // Integrity
  integrityStatus?: IntegrityStatus;
  onRunAuditNow: () => Promise<void>;
  isLoadingAudit: boolean;
  // Compliance
  complianceStatus?: ComplianceStatus;
  // Resources
  systemResources?: SystemResourceMetrics;
}

export const GuardianStationModal: React.FC<GuardianStationModalProps> = ({
  isOpen,
  onClose,
  activeTab,
  onSelectTab,
  reports = [],
  onTestBot,
  isLiveMode = false,
  integrityStatus,
  onRunAuditNow,
  isLoadingAudit,
  complianceStatus,
  systemResources,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-black/85 backdrop-blur-md animate-in fade-in">
      <div className="bg-[#0b0e14] border border-[#21262d] w-full max-w-5xl rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Master Guardian Station Header */}
        <div className="bg-[#111620] border-b border-[#21262d] px-4 py-3 sm:px-6 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
            </div>
            <div>
              <h2 className="text-sm sm:text-base font-extrabold text-white flex items-center gap-2">
                <span>Terminal Guardian & Analytics Station</span>
                <span className="px-2 py-0.5 text-[9px] font-mono font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-full">
                  VERIFIED
                </span>
              </h2>
              <p className="text-[11px] text-[#8b949e]">
                Unified institutional telemetry, audit trails, regulatory shields & system telemetry
              </p>
            </div>
          </div>

          <button
            onClick={() => {
              soundFX.playClickSound();
              onClose();
            }}
            className="p-1.5 text-[#8b949e] hover:text-white rounded-lg hover:bg-[#21262d] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
            aria-label="Close Station"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Tab Navigation Strip */}
        <div className="bg-[#161b22] border-b border-[#21262d] px-4 sm:px-6 flex items-center gap-2 sm:gap-4 overflow-x-auto text-xs font-semibold py-2">
          <button
            onClick={() => {
              soundFX.playClickSound();
              onSelectTab('reports');
            }}
            className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-2 shrink-0 ${
              activeTab === 'reports'
                ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40 shadow-sm'
                : 'text-[#8b949e] hover:text-white hover:bg-[#21262d] border border-transparent'
            }`}
          >
            <Trophy className="h-3.5 w-3.5" />
            <span>15M Event Reports & Journal</span>
            {reports.length > 0 && (
              <span className="px-1.5 py-0.2 text-[10px] font-mono bg-amber-500/20 rounded-full">
                {reports.length}
              </span>
            )}
          </button>

          <button
            onClick={() => {
              soundFX.playClickSound();
              onSelectTab('integrity');
            }}
            className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-2 shrink-0 ${
              activeTab === 'integrity'
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 shadow-sm'
                : 'text-[#8b949e] hover:text-white hover:bg-[#21262d] border border-transparent'
            }`}
          >
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>Integrity & Parity Audit</span>
            <span className="px-1.5 py-0.2 text-[10px] font-mono bg-emerald-500/20 rounded-full">
              {integrityStatus?.score ?? 100}%
            </span>
          </button>

          <button
            onClick={() => {
              soundFX.playClickSound();
              onSelectTab('compliance');
            }}
            className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-2 shrink-0 ${
              activeTab === 'compliance'
                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40 shadow-sm'
                : 'text-[#8b949e] hover:text-white hover:bg-[#21262d] border border-transparent'
            }`}
          >
            <Scale className="h-3.5 w-3.5" />
            <span>CFTC Compliance & API Limits</span>
          </button>

          <button
            onClick={() => {
              soundFX.playClickSound();
              onSelectTab('resources');
            }}
            className={`px-3 py-1.5 rounded-lg transition-all flex items-center gap-2 shrink-0 ${
              activeTab === 'resources'
                ? 'bg-purple-500/20 text-purple-400 border border-purple-500/40 shadow-sm'
                : 'text-[#8b949e] hover:text-white hover:bg-[#21262d] border border-transparent'
            }`}
          >
            <Cpu className="h-3.5 w-3.5" />
            <span>System Resources & Governor</span>
            {systemResources?.process_cpu_pct !== undefined && (
              <span className="px-1.5 py-0.2 text-[10px] font-mono bg-purple-500/20 rounded-full">
                {systemResources.process_cpu_pct.toFixed(1)}%
              </span>
            )}
          </button>
        </div>

        {/* Tab Content Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 bg-[#0b0e14]">
          {activeTab === 'reports' && (
            <WinLossReportsModal
              isOpen={true}
              onClose={onClose}
              reports={reports}
              onTestBot={onTestBot}
              isLiveMode={isLiveMode}
            />
          )}

          {activeTab === 'integrity' && (
            <IntegrityModal
              isOpen={true}
              onClose={onClose}
              integrityStatus={integrityStatus}
              onRunAuditNow={onRunAuditNow}
              isLoadingAudit={isLoadingAudit}
            />
          )}

          {activeTab === 'compliance' && (
            <ComplianceModal
              isOpen={true}
              onClose={onClose}
              complianceStatus={complianceStatus}
            />
          )}

          {activeTab === 'resources' && (
            <SystemResourcesModal
              isOpen={true}
              onClose={onClose}
              metrics={systemResources}
            />
          )}
        </div>
      </div>
    </div>
  );
};
