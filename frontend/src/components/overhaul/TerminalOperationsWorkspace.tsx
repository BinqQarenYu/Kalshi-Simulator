import React, { useState } from 'react';
import {
  AISignals,
  ChartPoint,
  ComplianceStatus,
  CryptoAsset,
  IntegrityStatus,
  LivePortfolioState,
  MacroDominionTelemetry,
  MarketState,
  OrderBookLadderRow,
  PreflightGates,
  TradeTapeItem,
} from '../../types';
import { PriceHero } from '../PriceHero';
import { TargetChart } from '../TargetChart';
import { OrderBookLadder } from '../OrderBookLadder';
import { TradeTape } from '../TradeTape';
import { PortfolioDrawer } from '../PortfolioDrawer';
import { AIMicrostructureCard } from '../AIMicrostructureCard';
import { LiveGuardrailsCard } from '../LiveGuardrailsCard';
import { HistoricalAnalyticsTab } from '../HistoricalAnalyticsTab';
import { SettingsView } from '../parenthub/SettingsView';
import { CouncilModal } from '../CouncilModal';
import { PresetVaultModal } from '../PresetVaultModal';

interface TerminalOperationsWorkspaceProps {
  market: MarketState;
  ladder?: OrderBookLadderRow[];
  aiSignals?: AISignals;
  livePortfolio?: LivePortfolioState | null;
  portfolio?: any;
  tradeTape?: TradeTapeItem[];
  chartPoints?: ChartPoint[];
  reports?: any[];
  integrityStatus?: IntegrityStatus;
  complianceStatus?: ComplianceStatus;
  macroDominionTelemetry?: MacroDominionTelemetry;
  preflightGates?: PreflightGates;
  tradingMode: 'paper' | 'live';
  consecutiveLosses: number;
  onQuickTrade?: (side: 'yes' | 'no') => void;
  onFlattenHalt?: () => void;
  onResetCircuitBreaker?: () => void;
  onClosePosition?: (ticker: string) => Promise<any>;
  onCancelOrder?: (orderId: string) => Promise<any>;
  onSelectAsset?: (asset: CryptoAsset) => void;
}

type TerminalSubTab = 'clob' | 'journal' | 'council' | 'guardrails';

export const TerminalOperationsWorkspace: React.FC<TerminalOperationsWorkspaceProps> = ({
  market,
  ladder = [],
  aiSignals,
  livePortfolio,
  portfolio,
  tradeTape = [],
  chartPoints = [],
  reports = [],
  integrityStatus,
  complianceStatus,
  macroDominionTelemetry,
  preflightGates,
  tradingMode,
  consecutiveLosses,
  onQuickTrade,
  onFlattenHalt,
  onResetCircuitBreaker,
  onClosePosition,
  onCancelOrder,
}) => {
  const [subTab, setSubTab] = useState<TerminalSubTab>('clob');
  const [isCouncilModalOpen, setIsCouncilModalOpen] = useState<boolean>(false);
  const [isPresetVaultOpen, setIsPresetVaultOpen] = useState<boolean>(false);

  return (
    <div className="w-full max-w-[1600px] mx-auto px-6 py-5 space-y-5">
      {/* Header & Sub-Tab Selector */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-xs font-medium text-[#f59e0b] tracking-wide">
            Execution Orderbook, Forensic Ledger, Multi-Agent Council & Risk Station
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white font-display">
            Terminal Operations
          </h1>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center bg-[#121621] border border-[#1e2536] rounded-lg p-1 gap-1">
            {[
              { id: 'clob', label: 'L2 CLOB & Order Entry' },
              { id: 'journal', label: 'Trade Journal & 15M Ledger' },
              { id: 'council', label: '7-Councilor AI Chamber' },
              { id: 'guardrails', label: 'Guardrails & Settings' },
            ].map((t) => (
              <button
                key={t.id}
                onClick={() => setSubTab(t.id as TerminalSubTab)}
                className={`px-3.5 py-1.5 text-xs font-medium rounded-md transition-colors whitespace-nowrap shrink-0 ${
                  subTab === t.id
                    ? 'bg-[#6366f1] text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          <button
            onClick={() => setIsPresetVaultOpen(true)}
            className="px-3.5 py-2 rounded-lg bg-[#121621] border border-[#1e2536] hover:border-slate-600 text-xs font-medium text-slate-200 whitespace-nowrap shrink-0"
          >
            Preset Vault
          </button>
        </div>
      </div>

      {/* SUB-TAB 1: L2 CLOB & MANUAL ORDER ENTRY */}
      {subTab === 'clob' && (
        <div className="space-y-5">
          <PriceHero market={market} preflightGates={preflightGates} />

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
            <div className="lg:col-span-8 bg-[#121621] border border-[#1e2536] rounded-xl p-4">
              <TargetChart
                market={market}
                chart={chartPoints}
                tradeTape={tradeTape}
                winLossReports={reports}
              />
            </div>

            <div className="lg:col-span-4 bg-[#121621] border border-[#1e2536] rounded-xl p-5 flex flex-col justify-between space-y-4">
              <div>
                <h2 className="text-sm font-semibold text-white font-display border-b border-[#1e2536] pb-3">
                  Direct 1-Contract Execution Ticket
                </h2>
                <div className="my-4 space-y-3 text-xs font-mono tabular-nums">
                  <div className="flex justify-between text-slate-400">
                    <span>Active Contract</span>
                    <span className="text-white">{market?.ticker || 'KXBTC15M'}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>Best YES Ask / Bid</span>
                    <span className="text-[#10b981]">{market?.yes_cents_str || '52.0¢'}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>Best NO Ask / Bid</span>
                    <span className="text-[#f43f5e]">{market?.no_cents_str || '48.0¢'}</span>
                  </div>
                  <div className="flex justify-between text-slate-400">
                    <span>Micro-Bankroll Cap</span>
                    <span className="text-[#06b6d4]">1 Contract Locked</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 pt-2">
                  <button
                    onClick={() => onQuickTrade?.('yes')}
                    className="py-3 rounded-lg bg-[#10b981] hover:bg-[#059669] text-slate-950 font-bold text-xs transition-colors"
                  >
                    Buy 1 YES ({market?.yes_cents_str || '52¢'})
                  </button>
                  <button
                    onClick={() => onQuickTrade?.('no')}
                    className="py-3 rounded-lg bg-[#f43f5e] hover:bg-[#e11d48] text-white font-bold text-xs transition-colors"
                  >
                    Buy 1 NO ({market?.no_cents_str || '48¢'})
                  </button>
                </div>
              </div>

              <PortfolioDrawer
                portfolio={portfolio}
                livePortfolio={livePortfolio}
                tradingMode={tradingMode}
                onClosePosition={onClosePosition || (async () => {})}
                onCancelOrder={onCancelOrder}
                onResetCircuitBreaker={
                  onResetCircuitBreaker ? async () => onResetCircuitBreaker() : undefined
                }
              />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            <div className="bg-[#121621] border border-[#1e2536] rounded-xl p-5">
              <h2 className="text-sm font-semibold text-white font-display mb-3">
                Level-2 Order Book Ladder
              </h2>
              <OrderBookLadder ladder={ladder} onSelectPrice={() => onQuickTrade?.('yes')} />
            </div>

            <div className="bg-[#121621] border border-[#1e2536] rounded-xl p-5">
              <h2 className="text-sm font-semibold text-white font-display mb-3">
                Live Time & Sales Tape
              </h2>
              <TradeTape tradeTape={tradeTape} />
            </div>
          </div>
        </div>
      )}

      {/* SUB-TAB 2: TRADE JOURNAL & 15M FORENSIC LEDGER */}
      {subTab === 'journal' && (
        <div className="bg-[#121621] border border-[#1e2536] rounded-xl p-5">
          <HistoricalAnalyticsTab />
        </div>
      )}

      {/* SUB-TAB 3: 7-COUNCILOR AI DELIBERATION CHAMBER */}
      {subTab === 'council' && (
        <div className="bg-[#121621] border border-[#1e2536] rounded-xl p-6 space-y-5">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#1e2536] pb-4">
            <div>
              <h2 className="text-base font-bold text-white font-display">
                LangGraph 7-Councilor Deliberation & KEV Oracle
              </h2>
              <p className="text-xs text-slate-400">
                Dr. Nash, Vance, Barnaby, Apex, Jackal, Silas, and Koko Arbiter multi-agent consensus
              </p>
            </div>
            <button
              onClick={() => setIsCouncilModalOpen(true)}
              className="px-4 py-2 rounded-lg bg-[#6366f1] hover:bg-[#4f46e5] text-white text-xs font-semibold"
            >
              Launch Interactive Council Session
            </button>
          </div>

          {aiSignals && (
            <AIMicrostructureCard
              signals={aiSignals}
              macroDominionTelemetry={macroDominionTelemetry}
            />
          )}
        </div>
      )}

      {/* SUB-TAB 4: GUARDRAILS, CFTC COMPLIANCE & SYSTEM SETTINGS */}
      {subTab === 'guardrails' && (
        <div className="space-y-5">
          <LiveGuardrailsCard
            livePortfolio={livePortfolio}
            integrityStatus={integrityStatus}
            complianceStatus={complianceStatus}
            isKillSwitchTripped={consecutiveLosses >= 3}
            onKillSwitch={onFlattenHalt || (() => {})}
            onResumeTrading={onResetCircuitBreaker || (() => {})}
          />
          <SettingsView onFlattenHalt={onFlattenHalt} />
        </div>
      )}

      <CouncilModal isOpen={isCouncilModalOpen} onClose={() => setIsCouncilModalOpen(false)} />
      <PresetVaultModal isOpen={isPresetVaultOpen} onClose={() => setIsPresetVaultOpen(false)} />
    </div>
  );
};
