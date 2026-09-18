import { WinLossEventReport } from '../../types';

export interface PortfolioMetrics {
  total_trades: number;
  wins: number;
  losses: number;
  win_rate_pct: number;
  gross_profit: number;
  gross_loss: number;
  profit_factor: number;
  total_fees_paid: number;
  total_realized_pnl: number;
  net_pnl: number;
  total_roi_pct: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  avg_trade_pnl: number;
  avg_win: number;
  avg_loss: number;
  payoff_ratio: number;
  expectancy_per_trade: number;
  current_equity: number;
  current_balance: number;
}

export interface EquityPoint {
  id: number;
  timestamp_utc: string;
  timestamp_epoch_ms: number;
  balance: number;
  equity: number;
  realized_pnl: number;
  unrealized_pnl: number;
  drawdown_pct: number;
  win_rate: number;
  total_trades: number;
  bot_type?: string;
  execution_mode?: string;
}

export interface HistoricalTrade {
  id: number;
  trade_id: string;
  timestamp_utc: string;
  timestamp_epoch_ms: number;
  ticker: string;
  timeframe: string;
  side: string;
  size: number;
  price: number;
  gross_value: number;
  fees: number;
  vpin: number | null;
  kelly_fraction: number | null;
  bot_type?: string;
  execution_mode: string;
  status: string;
}

export interface HistoricalSettlement {
  id: number;
  settlement_id: string;
  timestamp_utc: string;
  timestamp_epoch_ms: number;
  ticker: string;
  side: string;
  size: number;
  entry_price: number;
  settlement_price: number;
  outcome: string;
  pnl: number;
  balance_after: number;
  bot_type?: string;
  execution_mode?: string;
}

export interface AIPrediction {
  id: number;
  timestamp_utc: string;
  timestamp_epoch_ms: number;
  ticker: string;
  p_up: number;
  p_down: number;
  p_wait: number;
  vpin: number;
  ev_yes: number;
  ev_no: number;
  recommended_side: string;
  rationale: string | null;
  bot_type?: string;
}

export interface GateItem {
  name: string;
  passed: boolean;
  current: string;
  threshold: string;
}

export interface ForwardValidationStatus {
  forward_testing: {
    total_cycles_completed: number;
    target_cycles: number;
    progress_pct: number;
    wins: number;
    losses: number;
    win_rate_pct: number;
    net_pnl: number;
    total_fees_paid: number;
    expectancy_per_trade: number;
    profit_factor: number;
    max_drawdown_pct: number;
    sharpe_ratio: number;
  };
  gates: {
    gate_1_positive_expectancy: GateItem;
    gate_2_profit_factor: GateItem;
    gate_3_max_drawdown: GateItem;
    gate_4_100_cycle_sample: GateItem;
    gate_5_integrity_audit: GateItem;
  };
  real_money_readiness: {
    is_ready_for_real_money: boolean;
    micro_capital_cap: {
      max_contracts_per_trade: number;
      max_risk_per_trade_dollars: number;
      daily_max_loss_circuit_breaker: number;
    };
    live_account?: {
      balance_dollars: number;
      available_margin: number;
      positions_count: number;
    } | null;
  };
  timestamp: string;
}

export type SystemFilter =
  | 'all'
  | 'macro_onnx'
  | 'macro_trend_dominion'
  | 'dominion_2_bot'
  | '3_step_domination_bot'
  | 'onnx_ml_bot'
  | 'live';

export type SubTabType = '15m_reports' | 'journal' | 'settlements' | 'ai' | 'validation';

export interface SystemComparisonItem {
  key: SystemFilter;
  label: string;
  sublabel: string;
  icon: string;
  metrics: PortfolioMetrics | null;
}

export const ITEMS_PER_PAGE = 15;

export function formatETTime(val: string | number | null | undefined): string {
  if (!val) return '--';
  try {
    const d = typeof val === 'number' ? new Date(val) : new Date(val);
    if (isNaN(d.getTime())) return String(val);
    return (
      d.toLocaleTimeString('en-US', {
        timeZone: 'America/New_York',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true,
      }) + ' ET'
    );
  } catch {
    return String(val);
  }
}

export function formatETDate(val: string | number | null | undefined): string {
  if (!val) return '';
  try {
    const d = typeof val === 'number' ? new Date(val) : new Date(val);
    if (isNaN(d.getTime())) return '';
    return d.toLocaleDateString('en-US', {
      timeZone: 'America/New_York',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return '';
  }
}
