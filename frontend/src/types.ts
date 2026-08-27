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

export interface DashboardState {
  timestamp: string;
  market: MarketState;
  chart: ChartPoint[];
  trade_tape: TradeTapeItem[];
  orderbook_ladder: OrderBookLadderRow[];
  ai_signals: AISignals;
  portfolio: PortfolioState;
  settings: {
    ai_auto_trade: boolean;
    mode: 'mock' | 'live';
    timeframe: string;
  };
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
  positions: LivePositionItem[];
  updated_at: string;
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

