export type CryptoAsset = 'BTC' | 'ETH' | 'SOL' | 'DOGE';

export interface SupportedAssetInfo {
  id: CryptoAsset;
  name: string;
  series_15m: string;
  cf_index_id: string;
  price_decimals: number;
  min_spot_diff: number;
  spot_price: number | null;
  spot_price_str: string;
  twap_60s: number | null;
  twap_60s_str: string;
  is_active: boolean;
}

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
  diff_str?: string;
  expiry_countdown_seconds: number;
  expiry_countdown_str: string;
  timeframe?: string;
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
  active_asset?: CryptoAsset;
  active_asset_name?: string;
  active_asset_decimals?: number;
  cf_indices?: Record<string, {
    price: number | null;
    price_str: string;
    twap_60s: number | null;
    twap_60s_str: string;
    source_ts_ms?: number;
    updated_at?: number;
  }>;
  twap_60s_price?: number | null;
  is_twap_active?: boolean;
  twap_60s_str?: string;
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
  order_type?: string;
  limit_price?: number;
  discount_limit_price?: number;
  quolas_signal?: string;
  quolas_confidence?: number;
  kalshi_signal?: string;
  kalshi_confidence?: number;
  dual_onnx_regime?: 'MOMENTUM_SCALP' | 'CONTRADICTION_ARBITRAGE' | 'CHOP_WAIT' | 'TOXIC_VETO' | string;
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
  | 'dual_onnx'
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
  settlement_spot_price?: number;
  asset?: string;
  bot_side: 'yes' | 'no';
  side?: 'yes' | 'no';
  contracts: number;
  entry_price: number;
  settlement_price: number;
  outcome: 'win' | 'loss' | 'breakeven' | 'flat';
  pnl: number;
  net_pnl?: number;
  roi_pct: number;
  ai_confidence: number;
  ai_rationale: string;
  vpin_score: number;
  ev_edge: number;
  balance_after: number;
  bot_type?: string;
  bot_id?: string;
  strategy_id?: string;
  execution_mode?: string;
  lane?: string;
  timestamp_utc: string;
}

export interface BotPerformanceSummary {
  bot_id: string;
  bot_name: string;
  execution_mode: 'live' | 'paper' | 'all';
  total_events: number;
  wins: number;
  losses: number;
  win_rate_pct: number;
  total_pnl: number;
  profit_factor: number;
  avg_pnl_per_cycle: number;
  last_trade_time?: string;
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
  bot_summary?: BotPerformanceSummary;
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

export interface SealOfExcellenceRecord {
  bot_id: string;
  bot_name: string;
  seal_status: 'SEALED_EXCELLENT' | 'IN_INCUBATION' | 'SEAL_DENIED';
  seal_token: string;
  live_trading_authorized: boolean;
  granted_at: string;
  council_signoff?: string | null;
  settled_cycles_verified: number;
  graduation_threshold: number;
  empirical_win_rate: number;
  profit_factor: number;
  pillars_passed: number;
  pillars_total: number;
  quarantine_lane: string;
  details?: Record<string, any>;
}

export interface SealRegistry {
  version: string;
  last_updated: string;
  active_live_strategy: string;
  seals: Record<string, SealOfExcellenceRecord>;
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
  bot_audit_status?: {
    active_bot: string;
    is_certified: boolean;
    is_sealed?: boolean;
    report?: {
      bot_id: string;
      bot_name: string;
      status: 'CERTIFIED' | 'BLOCKED';
      certification_id: string;
      certified_at: string;
      pillars: Record<string, {
        pillar_name: string;
        status: 'PASS' | 'FAIL';
        message: string;
        details?: Record<string, any>;
      }>;
      failure_reasons: string[];
      seal?: SealOfExcellenceRecord;
    };
    seal?: SealOfExcellenceRecord;
  };
  seal_of_excellence?: SealRegistry;
  memory_profile?: MemoryProfileData;
  system_resources?: SystemResourceMetrics;
  settings: {
    ai_auto_trade: boolean;
    active_strategy_bot?: string;
    bot_certified?: boolean;
    bot_sealed?: boolean;
    mode: 'mock' | 'live';
    timeframe: string;
    domination_discount_price?: number;
  };
  btc_orderflow?: BtcOrderflowSummary;
  continuous_training?: ContinuousTrainingTelemetry;
  dual_onnx_telemetry?: DualONNXTelemetry;
  macro_trend_dominion_telemetry?: MacroDominionTelemetry;
  hmm_macro_regime?: HMMMacroRegimeTelemetry;
  preflight_gates?: PreflightGates;
}

export interface HMMMacroRegimeTelemetry {
  current_regime: 'STABLE_RANGE' | 'VOL_EXPANSION' | 'RISK_OFF' | string;
  probabilities?: Record<string, number>;
  confidence?: number;
  sample_count?: number;
  last_updated?: string;
  [key: string]: any;
}

export interface MacroDominionTelemetry {
  active: boolean;
  strategy_id: string;
  strategy_name: string;
  call: 'YES' | 'NO' | 'DONT' | string;
  side: 'yes' | 'no' | 'wait' | string;
  confidence_pct: number;
  limit_price_cents: number;
  limit_price: number;
  expected_value: number;
  net_edge_pct: number;
  recommended_contracts: number;
  macro_trend: 'BULL' | 'BEAR' | 'CHOP' | string;
  hmm_regime: 'STABLE_RANGE' | 'VOL_EXPANSION' | 'RISK_OFF' | string;
  spot_signal: string;
  spot_confidence: number;
  kalshi_signal: string;
  kalshi_confidence: number;
  rationale: string;
  brier_score: number;
  brier_shrinkage_factor: number;
  active_price_cap: number;
  pruned_deciles: number[];
  failure_counts: Record<string, number>;
  parameters?: Record<string, any>;
  settled_cycles?: number;
  today_wins?: number;
  today_losses?: number;
  today_win_rate?: number;
  today_pnl?: number;
}

export interface DualONNXTelemetry {
  regime: 'MOMENTUM_SCALP' | 'CONTRADICTION_ARBITRAGE' | 'CHOP_WAIT' | 'TOXIC_VETO' | string;
  action: string;
  side: string | null;
  quolas_signal: string;
  quolas_confidence: number;
  kalshi_signal: string;
  kalshi_confidence: number;
  recommended_limit_price: number;
  expected_value: number;
  recommended_contracts: number;
  rationale: string;
  active: boolean;
  settled_cycles?: number;
  today_wins?: number;
  today_losses?: number;
  today_win_rate?: number;
  today_pnl?: number;
  // The 5 Strategy Execution Dials
  brain_priority_mode?: 'TREND_ALIGNED_SCALP' | 'CONTRADICTION_SNIPER' | 'UNANIMOUS_CONSENSUS' | string;
  contract_scaling_mode?: 'TIER_0_STRICT_1' | 'TIER_1_CONVICTION_2' | 'TIER_2_KELLY' | string;
  volatility_floor?: number;
  volatility_ceiling?: number;
  entry_discount_depth?: number;
  tape_confirmation_ticks?: number;
  taker_cross_ev_threshold?: number;
  dynamic_moat_multiplier?: number;
  current_atr?: number;
  tape_streak?: number;
}

export interface BotParameters {
  strategy_id?: string;
  strategy_name?: string;
  brain_priority_mode?: 'TREND_ALIGNED_SCALP' | 'CONTRADICTION_SNIPER' | 'UNANIMOUS_CONSENSUS' | string;
  contract_scaling_mode?: 'TIER_0_STRICT_1' | 'TIER_1_CONVICTION_2' | 'TIER_2_KELLY' | string;
  volatility_floor?: number;
  volatility_ceiling?: number;
  entry_discount_depth?: number;
  tape_confirmation_ticks?: number;
  taker_cross_ev_threshold?: number;
  dynamic_moat_multiplier?: number;
  discount_limit_price?: number;
  discount_ceiling?: number;
  max_contracts?: number;
  min_confidence?: number;
  min_ev_dollars?: number;
  min_edge_pct?: number;
  min_spot_diff?: number;
  vpin_toxic_threshold?: number;
  momentum_max_price?: number;
  take_profit_price_threshold?: number;
  enable_take_profit_ceiling?: boolean;
  require_reversal_for_tp_ceiling?: boolean;
  enable_reverse_take_profit_roi?: boolean;
  reverse_indicator_threshold?: number;
  min_take_profit_roi?: number;
  enable_trailing_ratchet?: boolean;
  trailing_ratchet_buffer?: number;
  spot_delta_front_run_threshold?: number;
  enable_dynamic_reversal_curve?: boolean;
  twap_immutability_sniper_cents?: number;
  max_queue_depth_ahead?: number;
  max_clob_spread_cents?: number;
  [key: string]: any;
}

export interface PreflightGate {
  status: 'PASS' | 'VETO' | 'READY' | 'LOCKED' | 'WAIT';
  label: string;
  reason: string;
  [key: string]: any;
}

export interface PreflightGates {
  moat_gate: PreflightGate & {
    current_diff: number;
    abs_diff: number;
    required_moat: number;
    floor: number;
    sweet_spot: number;
    ceiling: number;
  };
  vpin_gate: PreflightGate & {
    current_vpin: number;
    threshold: number;
  };
  cycle_lock_gate: PreflightGate & {
    locked: boolean;
  };
  edge_gate: PreflightGate & {
    edge_pct: number;
    ev: number;
  };
}

export interface ContinuousTrainingTelemetry {
  status: string;
  is_enabled: boolean;
  is_running: boolean;
  is_paused: boolean;
  cycles_completed: number;
  models_promoted: number;
  best_val_loss?: number | null;
  last_val_loss?: number | null;
  last_val_accuracy?: number | null;
  last_val_f1?: number | null;
  last_trained_time?: string | null;
  last_promoted_time?: string | null;
  samples_trained: number;
  last_error?: string | null;
  priority_class?: string;
  cpu_thread_cap?: number;
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
  balance_dollars: number | string;
  available_margin: number | string;
  payout_pending: number | string;
  positions_count?: number;
  positions: LivePositionItem[];
  updated_at: string;
  environment?: string;
  is_authenticated?: boolean;
  today_pnl?: number;
  settled_cycles?: number;
  today_wins?: number;
  today_losses?: number;
  today_win_rate?: number;
  consecutive_losses?: number;
  max_consecutive_losses?: number;
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

export interface BotPreset {
  preset_id: string;
  preset_name: string;
  version?: string;
  created_at?: string;
  author?: string;
  description?: string;
  is_council_certified?: boolean;
  is_active?: boolean;
  checksum?: string;
}

export interface PresetListResponse {
  status: string;
  presets: BotPreset[];
  active_preset: BotPreset;
}

export interface IncubatorScorecard {
  bot_id: string;
  bot_name: string;
  total_trades: number;
  wins: number;
  losses: number;
  win_rate_pct: string;
  total_pnl: string;
  profit_factor: string;
  max_drawdown_pct: string;
  adverse_selection_count: number;
  toxic_vpin_trades_count: number;
  promotion_status: 'COOKING' | 'AUDITING' | 'READY_FOR_PROMOTION' | 'PROMOTED' | 'BLOCKED';
  readiness_score_pct: number;
  last_audit?: any;
}

export interface IncubatorPostMortem {
  cycle_id: string;
  ticker: string;
  settlement_twap: string;
  target_strike: string;
  outcome: string;
  trades: any[];
  total_pnl: string;
  diagnosis: string;
  timestamp: string;
}

export interface NeuralEngineSpec {
  id: string;
  name: string;
  filename: string;
  version: string;
  dimension: number;
  features_description: string;
  target_assets: string[];
  supported_venues: string[];
  role: string;
  status: 'ACTIVE_LANE_1' | 'STANDALONE_LAB' | 'STANDBY';
  architecture: string;
  input_shape: string;
  output_shape: string;
  latency_budget_ms: number;
  physics_features?: string[];
  adapters?: string[];
}


