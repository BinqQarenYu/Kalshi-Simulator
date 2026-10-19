/**
 * @file ParentHub.tsx
 * @description Unified Command Deck uniting the 4 Primary Workspaces:
 * 1. Performance Analytics (TradeZella-inspired KPI gauges, 6-axis Edge Score radar, Cumulative & Cycle P&L)
 * 2. Neural & Robot Bot Arena (Live 4-layer Neural Synapse diagram + articulated SVG Robot Fleet Bay)
 * 3. ML & Bot Asset Forge (Custom Bot Builder, BTC/ETH ONNX Trainer, HMM Regime Studio, Ensemble Lab & Seal Pipeline)
 * 4. Terminal Operations (L2 CLOB, Trade Journal, 7-Councilor AI Chamber, Guardrails & Settings)
 */

import React, { useState } from 'react';
import {
  AISignals,
  ChartPoint,
  ComplianceStatus,
  ContinuousTrainingTelemetry,
  CryptoAsset,
  DualONNXTelemetry,
  HMMMacroRegimeTelemetry,
  IntegrityStatus,
  LivePortfolioState,
  MacroDominionTelemetry,
  MarketState,
  OrderBookLadderRow,
  Position,
  PreflightGates,
  SealOfExcellenceRecord,
  SealRegistry,
  SystemResourceMetrics,
  TradeTapeItem,
} from '../types';
import { ZellaAnalyticsWorkspace } from './overhaul/ZellaAnalyticsWorkspace';
import { NeuralRobotArenaWorkspace } from './overhaul/NeuralRobotArenaWorkspace';
import { MlBotForgeWorkspace, ForgeTab } from './overhaul/MlBotForgeWorkspace';
import { TerminalOperationsWorkspace } from './overhaul/TerminalOperationsWorkspace';

export interface ParentHubProps {
  market: MarketState;
  ladder?: OrderBookLadderRow[];
  aiSignals?: AISignals;
  livePortfolio?: LivePortfolioState | null;
  activePosition?: Position | null;
  tradeTape?: TradeTapeItem[];
  chartPoints?: ChartPoint[];
  reports?: any[];
  integrityStatus?: IntegrityStatus;
  complianceStatus?: ComplianceStatus;
  systemResources?: SystemResourceMetrics;
  continuousTraining?: ContinuousTrainingTelemetry;
  tradingMode: 'paper' | 'live';
  timeframe: string;
  activeStrategyBot: string;
  onSelectStrategy: (botId: string) => void;
  onSelectAsset?: (asset: CryptoAsset) => void;
  onSelectTimeframe: (tf: string) => void;
  onSelectTradingMode: (mode: 'paper' | 'live') => void;
  onQuickTrade?: (side: 'yes' | 'no') => void;
  onFlattenHalt?: () => void;
  onRunAuditNow?: () => void;
  onTestBot?: () => Promise<any>;
  isPoppedOutBabyBot: boolean;
  onTogglePopOutBabyBot: (botId?: string) => void;
  consecutiveLosses: number;
  portfolio?: {
    balance: number;
    equity: number;
    realized_pnl: number;
    unrealized_pnl: number;
    win_rate: number;
    total_trades: number;
    wins: number;
    losses: number;
    positions: Position[];
    settlements: any[];
  };
  onClosePosition?: (ticker: string) => Promise<any>;
  onCancelOrder?: (orderId: string) => Promise<any>;
  onResetCircuitBreaker?: () => void;
  onResyncMemory?: () => void;
  dualOnnxTelemetry?: DualONNXTelemetry;
  preflightGates?: PreflightGates;
  macroDominionTelemetry?: MacroDominionTelemetry;
  hmmMacroRegime?: HMMMacroRegimeTelemetry;
  sealOfExcellence?: SealRegistry | SealOfExcellenceRecord;
  botAuditStatus?: Record<string, any>;
  settings?: any;
  v4Telemetry?: any;
}

type CommandWorkspace = 'analytics' | 'arena' | 'forge' | 'terminal';

export const ParentHub: React.FC<ParentHubProps> = ({
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
  tradingMode,
  activeStrategyBot,
  onSelectStrategy,
  onSelectAsset,
  onQuickTrade,
  onFlattenHalt,
  onRunAuditNow,
  onTestBot,
  onTogglePopOutBabyBot,
  consecutiveLosses,
  onClosePosition,
  onCancelOrder,
  onResetCircuitBreaker,
  onResyncMemory,
  preflightGates,
  macroDominionTelemetry,
  hmmMacroRegime,
}) => {
  const [workspace, setWorkspace] = useState<CommandWorkspace>('analytics');
  const [forgeInitialTab, setForgeInitialTab] = useState<ForgeTab>('bot_builder');

  const openAwsBridge = () => {
    setForgeInitialTab('aws_bridge');
    setWorkspace('forge');
  };

  return (
    <div className="min-h-screen w-full bg-[#0b0d13] text-[#f8fafc] flex flex-col">
      {/* STRICT 3-ZONE TOP BAR CONTRACT */}
      <header className="flex items-center justify-between gap-8 px-6 py-3.5 bg-[#121621] border-b border-[#1e2536]">
        {/* Zone 1: Single text element wordmark */}
        <a
          href="#analytics"
          onClick={(e) => {
            e.preventDefault();
            setWorkspace('analytics');
          }}
          className="text-lg font-bold tracking-tight text-white font-display whitespace-nowrap shrink-0"
        >
          Kalshi Neural Deck
        </a>

        {/* Zone 2: 5 concise single-line text navigation links */}
        <nav className="flex items-center gap-6 text-sm font-medium">
          {[
            { id: 'analytics', label: 'Analytics', onSelect: () => setWorkspace('analytics') },
            { id: 'arena', label: 'Neural Arena', onSelect: () => setWorkspace('arena') },
            {
              id: 'forge',
              label: 'ML Forge',
              onSelect: () => {
                setForgeInitialTab('bot_builder');
                setWorkspace('forge');
              },
            },
            {
              id: 'aws_cloud',
              label: 'AWS EC2 Cloud',
              onSelect: openAwsBridge,
            },
            { id: 'terminal', label: 'Terminal', onSelect: () => setWorkspace('terminal') },
          ].map((nav) => {
            const isCurrent =
              nav.id === 'aws_cloud'
                ? workspace === 'forge' && forgeInitialTab === 'aws_bridge'
                : nav.id === 'forge'
                ? workspace === 'forge' && forgeInitialTab !== 'aws_bridge'
                : workspace === nav.id;

            return (
              <a
                key={nav.id}
                href={`#${nav.id}`}
                onClick={(e) => {
                  e.preventDefault();
                  nav.onSelect();
                }}
                className={`py-1 border-b-2 transition-colors whitespace-nowrap shrink-0 ${
                  isCurrent
                    ? 'border-[#6366f1] text-white font-semibold'
                    : 'border-transparent text-slate-400 hover:text-white'
                }`}
              >
                {nav.label}
              </a>
            );
          })}
        </nav>

        {/* Zone 3: 1 primary action */}
        <div className="flex items-center shrink-0">
          <button
            onClick={() => {
              if (workspace === 'forge') {
                setWorkspace('arena');
              } else {
                setForgeInitialTab('bot_builder');
                setWorkspace('forge');
              }
            }}
            className="px-4 py-2 text-xs font-semibold text-white bg-[#6366f1] hover:bg-[#4f46e5] rounded-lg transition-colors whitespace-nowrap shrink-0"
          >
            {workspace === 'forge' ? 'Open Robot Arena' : 'Forge Bot & ML'}
          </button>
        </div>
      </header>

      {/* ACTIVE WORKSPACE VIEWPORT */}
      <main className="flex-1 w-full overflow-y-auto">
        {workspace === 'analytics' && (
          <ZellaAnalyticsWorkspace
            market={market}
            portfolio={portfolio}
            livePortfolio={livePortfolio}
            reports={reports}
            tradingMode={tradingMode}
            onResyncMemory={onResyncMemory}
            onRunAuditNow={onRunAuditNow}
            onSelectAsset={onSelectAsset}
          />
        )}

        {workspace === 'arena' && (
          <NeuralRobotArenaWorkspace
            market={market}
            aiSignals={aiSignals}
            hmmMacroRegime={hmmMacroRegime}
            preflightGates={preflightGates}
            activeStrategyBot={activeStrategyBot}
            tradingMode={tradingMode}
            onSelectStrategy={onSelectStrategy}
            onSelectAsset={onSelectAsset}
            onTestBot={onTestBot}
            onTogglePopOutBabyBot={onTogglePopOutBabyBot}
            onOpenForgeTab={() => {
              setForgeInitialTab('bot_builder');
              setWorkspace('forge');
            }}
            onOpenAwsBridge={openAwsBridge}
          />
        )}

        {workspace === 'forge' && (
          <MlBotForgeWorkspace
            activeStrategyBot={activeStrategyBot}
            onSelectStrategy={onSelectStrategy}
            onSelectAsset={onSelectAsset}
            initialTab={forgeInitialTab}
          />
        )}

        {workspace === 'terminal' && (
          <TerminalOperationsWorkspace
            market={market}
            ladder={ladder}
            aiSignals={aiSignals}
            livePortfolio={livePortfolio}
            portfolio={portfolio}
            tradeTape={tradeTape}
            chartPoints={chartPoints}
            reports={reports}
            integrityStatus={integrityStatus}
            complianceStatus={complianceStatus}
            macroDominionTelemetry={macroDominionTelemetry}
            preflightGates={preflightGates}
            tradingMode={tradingMode}
            consecutiveLosses={consecutiveLosses}
            onQuickTrade={onQuickTrade}
            onFlattenHalt={onFlattenHalt}
            onResetCircuitBreaker={onResetCircuitBreaker}
            onClosePosition={onClosePosition}
            onCancelOrder={onCancelOrder}
            onSelectAsset={onSelectAsset}
          />
        )}
      </main>
    </div>
  );
};
