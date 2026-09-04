export interface MarketState {
  title: string;
  series: string;
  ticker: string;
  target_strike: number;
  target_strike_str: string;
  current_btc_price: number;
  current_btc_price_str: string;
  diff: number;
  diff_pct: number;
  expiry_countdown_seconds: number;
  expiry_countdown_str: string;
  market_chance_pct: number;
  volume_24h_str: string;
  best_yes_ask: number;
  best_yes_bid: number;
  best_no_ask: number;
  best_no_bid: number;
  target_time_str?: string;
  time_window_str?: string;
  yes_cents_str: string;
  no_cents_str: string;
}

export interface ChartPoint {
  time: string;
  price: number;
  target: number;
}

export interface TradeTapeItem {
  ticker: string;
  side: 'yes' | 'no';
  price_cents: string;
  contracts: number;
  val_str: string;
  time: string;
}

export interface OrderBookLadderRow {
  side: 'yes' | 'no';
  price_cents: string;
  price_raw: number;
  contracts: number;
  total: string;
  depth_pct: number;
}

export interface AISignals {
  p_up: number;
  p_down: number;
  p_wait: number;
  vpin: number;
  vpin_is_safe: boolean;
  ev_yes: number;
  ev_no: number;
  edge_yes: number;
  edge_no: number;
  kelly_f_yes: number;
  kelly_f_no: number;
  recommended_side: 'yes' | 'no' | 'wait';
  rationale: string;
  strategy_id?: string;
  strategy_name?: string;
  active_playbook?: string;
  playbook_stage?: string;
  edge_pct?: number;
  onnx_signal?: string;
  onnx_confidence?: number;
  onnx_prob_long?: number;
  onnx_prob_short?: number;
  onnx_prob_wait?: number;
}

export interface BtcOrderflowSummary {
  spot_price: number;
  best_bid: number;
  best_ask: number;
  spread_bps: number;
  cvd_btc: number;
  ofi_l1: number;
  connected: boolean;
  source: string;
  ticks_count: number;
  trades_count: number;
  recent_trades_buffer?: number;
}

export type StrategyBotId =
  | 'macro_onnx'
  | 'macro_trend_dominion'
  | 'dominion_2_bot'
  | '3_step_domination_bot'
  | 'onnx_microstructure_bot';

export interface StrategyBotInfo {
  id: string;
  name: string;
  description: string;
  active: boolean;
  badge: string;
  icon: string;
  features: string[];
}

export interface Position {
  ticker: string;
  side: 'yes' | 'no';
  size: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
}

export interface Settlement {
  ticker: string;
  side: 'yes' | 'no';
  size: number;
  entry_price: number;
  settlement_price: number;
  outcome: 'win' | 'loss';
  pnl: number;
  timestamp: string;
}

export interface OpenOrder {
  order_id: string;
  ticker: string;
  side: 'yes' | 'no';
  size: number;
  limit_price: number;
  timeframe: string;
  status: string;
  created_at: string;
}

export interface PortfolioState {
  balance: number;
  equity: number;
  realized_pnl: number;
  unrealized_pnl: number;
  win_rate: number;
  total_trades: number;
  wins: number;
  losses: number;
  circuit_breaker_tripped?: boolean;
  current_drawdown_pct?: number;
  positions: Position[];
  settlements: Settlement[];
  open_orders?: OpenOrder[];
}

export interface MemoryProfileData {
  total_hot_ticks: number;
  total_offloaded_ticks: number;
  estimated_hot_memory_kb: number;
  is_pressure_critical: boolean;
}

export interface WinLossEventReport {
  report_id: string;
  cycle_time: string;
  ticker: string;
  timeframe: string;
  strike_price: number;
  settlement_btc_price: number;
  bot_side: 'yes' | 'no';
  contracts: number;
  entry_price: number;
  settlement_price: number;
  outcome: 'win' | 'loss' | 'breakeven' | 'flat';
  pnl: number;
  roi_pct: number;
  ai_confidence: number;
  ai_rationale: string;
  vpin_score: number;
  ev_edge: number;
  balance_after: number;
  bot_type?: string;
  execution_mode?: string;
  timestamp_utc: string;
}

export interface WinLossReportsSummary {
  total_events: number;
  wins: number;
  losses: number;
  win_rate_pct: number;
  total_pnl: number;
  profit_factor: number;
  avg_pnl_per_cycle: number;
}

export interface WinLossReportsResponse {
  summary: WinLossReportsSummary;
  domination_summary?: WinLossReportsSummary;
  onnx_summary?: WinLossReportsSummary;
  live_summary?: WinLossReportsSummary;
  reports: WinLossEventReport[];
}

export interface IntegrityCheckItem {
  name: string;
  category: 'math' | 'microstructure' | 'latency' | 'truth' | 'connection';
  status: 'PASS' | 'WARN' | 'FAIL';
  message: string;
  metric_value?: string;
  threshold?: string;
  timestamp: string;
}

export interface IntegrityStatus {
  score: number;
  status: 'HEALTHY' | 'WARNING' | 'CRITICAL';
  total_checks: number;
  passed: number;
  warnings: number;
  failed: number;
  audit_count: number;
  total_flaws_caught: number;
  scan_duration_ms: number;
  timestamp: string;
  checks: IntegrityCheckItem[];
}

export interface ComplianceCheckItem {
  name: string;
  category: 'cftc_conduct' | 'api_terms' | 'rate_limits' | 'position_limits' | 'security';
  status: 'PASS' | 'WARN' | 'FAIL';
  message: string;
  authority: string;
  metric_value?: string;
  rule_reference?: string;
  timestamp: string;
}

export interface ComplianceViolationItem {
  timestamp: string;
  rule_name: string;
  authority: string;
  description: string;
}

export interface ComplianceStatus {
  score: number;
  status: 'COMPLIANT' | 'WARNING' | 'NON_COMPLIANT';
  total_checks: number;
  passed: number;
  warnings: number;
  failed: number;
  pre_trade_checks_total: number;
  pre_trade_rejections: number;
  total_api_calls: number;
  rate_limit_violations: number;
  recent_violations_count: number;
  recent_violations: ComplianceViolationItem[];
  timestamp: string;
  checks: ComplianceCheckItem[];
}

export interface LegalDoItem {
  title: string;
  authority: string;
  description: string;
  app_enforcement: string;
}

export interface LegalDontItem {
  title: string;
  authority: string;
  description: string;
  consequence: string;
}

export interface LegalHandbookResponse {
  dos: LegalDoItem[];
  donts: LegalDontItem[];
}

export interface SystemResourceMetrics {
  process_cpu_pct: number;
  system_cpu_pct: number;
  cpu_cores_count: number;
  process_rss_mb: number;
  process_vms_mb: number;
  system_ram_total_mb: number;
  system_ram_used_pct: number;
  gc_gen0_collections: number;
  gc_gen1_collections: number;
  gc_gen2_collections: number;
  gc_uncollectable_count: number;
  memory_status: 'OPTIMAL' | 'ELEVATED' | 'CRITICAL';
  is_pressure_critical: boolean;
  active_thread_count: number;
  uptime_seconds: number;
  timestamp: string;
}

export interface DashboardState {
  timestamp: string;
  market: MarketState;
  chart: ChartPoint[];
  trade_tape: TradeTapeItem[];
  orderbook_ladder: OrderBookLadderRow[];
  ai_signals: AISignals;
  portfolio: PortfolioState;
  live_portfolio?: LivePortfolioState | null;
  win_loss_reports?: WinLossEventReport[];
  integrity_status?: IntegrityStatus;
  compliance_status?: ComplianceStatus;
  memory_profile?: MemoryProfileData;
  system_resources?: SystemResourceMetrics;
  settings: {
    ai_auto_trade: boolean;
    active_strategy_bot?: string;
    mode: 'mock' | 'live';
    timeframe: string;
  };
  btc_orderflow?: BtcOrderflowSummary;
}

export interface LivePositionItem {
  ticker: string;
  position: number;
  side: 'yes' | 'no';
  fees_paid: number;
  realized_pnl: number;
  resting_orders_count: number;
}

export interface LivePortfolioState {
  balance_dollars: number;
  available_margin: number;
  payout_pending: number;
  positions_count?: number;
  positions: LivePositionItem[];
  updated_at: string;
  environment?: string;
  is_authenticated?: boolean;
}

export interface ReconciliationReport {
  is_synchronized: boolean;
  simulated_cash: number;
  exchange_cash: number;
  cash_discrepancy: number;
  simulated_positions_count: number;
  exchange_positions_count: number;
  alerts: string[];
  timestamp: string;
}

export interface OrderResponse {
  success: boolean;
  order_id?: string;
  fill_price?: number;
  cost?: number;
  slippage?: number;
  status?: string;
  reason?: string;
  message?: string;
  error?: string;
  freeze_trading?: boolean;
  action_required?: string;
  live_balance?: number;
  execution_mode?: string;
}
