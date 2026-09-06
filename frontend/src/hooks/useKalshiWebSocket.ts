import { useEffect, useRef, useState, useCallback } from 'react';
import { DashboardState } from '../types';

const INITIAL_STATE: DashboardState = {
  timestamp: new Date().toISOString(),
  market: {
    title: 'BTC 15 min',
    series: 'KXBTC15M',
    ticker: 'KXBTC15M-T78650',
    target_strike: 77645.14,
    target_strike_str: '$77,645.14',
    current_btc_price: 78500.22,
    current_btc_price_str: '$78,500.22',
    diff: 855.08,
    diff_pct: 1.10,
    expiry_countdown_seconds: 87,
    expiry_countdown_str: '01:27',
    market_chance_pct: 5.9,
    volume_24h_str: '$1,547,966',
    best_yes_ask: 0.034,
    best_yes_bid: 0.031,
    best_no_ask: 0.969,
    best_no_bid: 0.966,
    yes_cents_str: '3.4¢',
    no_cents_str: '96.9¢',
  },
  chart: [],
  trade_tape: [],
  orderbook_ladder: [
    { side: 'yes', price_cents: '4.9¢', price_raw: 0.049, contracts: 2200, total: '$107.80', depth_pct: 44 },
    { side: 'yes', price_cents: '4.8¢', price_raw: 0.048, contracts: 1, total: '$0.05', depth_pct: 2 },
    { side: 'yes', price_cents: '4.6¢', price_raw: 0.046, contracts: 2001, total: '$92.05', depth_pct: 40 },
    { side: 'yes', price_cents: '4.4¢', price_raw: 0.044, contracts: 3054, total: '$134.38', depth_pct: 61 },
    { side: 'yes', price_cents: '4.2¢', price_raw: 0.042, contracts: 16, total: '$0.67', depth_pct: 5 },
    { side: 'yes', price_cents: '4.1¢', price_raw: 0.041, contracts: 516, total: '$21.16', depth_pct: 12 },
    { side: 'yes', price_cents: '4.0¢', price_raw: 0.040, contracts: 1002, total: '$40.08', depth_pct: 20 },
    { side: 'yes', price_cents: '3.9¢', price_raw: 0.039, contracts: 16, total: '$0.62', depth_pct: 5 },
  ],
  ai_signals: {
    p_up: 0.684,
    p_down: 0.211,
    p_wait: 0.105,
    vpin: 0.18,
    vpin_is_safe: true,
    ev_yes: 0.042,
    ev_no: -0.015,
    edge_yes: 0.065,
    edge_no: -0.02,
    kelly_f_yes: 0.125,
    kelly_f_no: 0.0,
    recommended_side: 'yes',
    rationale: 'High OFI buyer pressure & positive EV edge (+4.2¢)',
  },
  portfolio: {
    balance: 100,
    equity: 100,
    realized_pnl: 0,
    unrealized_pnl: 0,
    win_rate: 0,
    total_trades: 0,
    wins: 0,
    losses: 0,
    positions: [],
    settlements: [],
  },
  settings: {
    ai_auto_trade: true,
    mode: 'mock',
    timeframe: '15m',
  },
};

export function useKalshiWebSocket() {
  const [data, setData] = useState<DashboardState>(INITIAL_STATE);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const pendingDataRef = useRef<DashboardState | null>(null);
  const throttleTimeoutRef = useRef<number | null>(null);
  const lastCommitTimeRef = useRef<number>(0);

  const THROTTLE_INTERVAL_MS = 250; // Smooth 4Hz updates (250ms) for rock-solid zero-jitter rendering

  const commitData = useCallback((nextState: DashboardState) => {
    setData(nextState);
    lastCommitTimeRef.current = performance.now();
    pendingDataRef.current = null;
    if (throttleTimeoutRef.current !== null) {
      clearTimeout(throttleTimeoutRef.current);
      throttleTimeoutRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    // Connect to WebSocket server
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          if (parsed && parsed.market) {
            const now = performance.now();
            const elapsed = now - lastCommitTimeRef.current;

            if (elapsed >= THROTTLE_INTERVAL_MS) {
              commitData(parsed);
            } else {
              pendingDataRef.current = parsed;
              if (throttleTimeoutRef.current === null) {
                throttleTimeoutRef.current = window.setTimeout(() => {
                  if (pendingDataRef.current) {
                    commitData(pendingDataRef.current);
                  }
                }, THROTTLE_INTERVAL_MS - elapsed);
              }
            }
          }
        } catch (err) {
          console.error('Error parsing WebSocket payload:', err);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        // Attempt reconnect after 1.5 seconds
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 1500);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (err) {
      setIsConnected(false);
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect();
      }, 2000);
    }
  }, [commitData]);

  // Immediate fetch on mount & resilient fallback polling when disconnected
  useEffect(() => {
    const fetchState = async () => {
      try {
        const resp = await fetch('/api/state');
        if (resp.ok) {
          const s = await resp.json();
          if (s && s.market) {
            setData(s);
          }
        }
      } catch {
        // Ignore background fetch error
      }
    };

    fetchState();
    const interval = setInterval(() => {
      if (!isConnected) {
        fetchState();
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [isConnected]);

  useEffect(() => {
    connect();

    return () => {
      if (throttleTimeoutRef.current !== null) {
        clearTimeout(throttleTimeoutRef.current);
        throttleTimeoutRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);


  const sendOrder = async (
    side: 'yes' | 'no',
    size: number,
    limitPrice?: number,
    orderType: 'market' | 'limit' = 'market',
    restingOnly: boolean = false,
    executionMode: 'paper' | 'live' = 'paper'
  ) => {
    try {
      const resp = await fetch('/api/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: data.market.ticker,
          side,
          size,
          order_type: orderType,
          limit_price: limitPrice,
          resting_only: restingOnly,
          execution_mode: executionMode,
        }),
      });
      return await resp.json();
    } catch (err) {
      console.error('Failed to submit order:', err);
      return { success: false, error: String(err) };
    }
  };

  const cancelOrder = async (orderId: string, executionMode: 'paper' | 'live' = 'paper') => {
    try {
      const url = executionMode === 'live'
        ? `/api/kalshi/orders/live/${orderId}`
        : `/api/orders/${orderId}`;
      const resp = await fetch(url, {
        method: 'DELETE',
      });
      return await resp.json();
    } catch (err) {
      console.error('Failed to cancel resting order:', err);
      return { success: false, error: String(err) };
    }
  };

  const toggleAIAutoTrade = async (enabled: boolean) => {
    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ai_auto_trade: enabled }),
      });
    } catch (err) {
      console.error('Failed to update settings:', err);
    }
  };

  const changeTimeframe = async (tf: string) => {
    try {
      await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active_timeframe: tf }),
      });
    } catch (err) {
      console.error('Failed to switch timeframe:', err);
    }
  };

  const resetPortfolio = async (capital: number = 15) => {
    try {
      await fetch('/api/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ capital }),
      });
    } catch (err) {
      console.error('Failed to reset portfolio:', err);
    }
  };

  const closePosition = async (ticker: string, executionMode: 'paper' | 'live' = 'paper') => {
    try {
      const resp = await fetch('/api/positions/close', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker, execution_mode: executionMode }),
      });
      return await resp.json();
    } catch (err) {
      console.error('Failed to close position:', err);
      return { success: false, error: String(err) };
    }
  };

  const toggleFeedMode = async (mode: 'mock' | 'live') => {
    try {
      setData((prev) => ({
        ...prev,
        settings: { ...prev.settings, mode },
      }));
      const resp = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
      return await resp.json();
    } catch (err) {
      console.error('Failed to toggle feed mode:', err);
    }
  };

  const resetCircuitBreaker = async () => {
    try {
      const resp = await fetch('/api/circuit-breaker/reset', {
        method: 'POST',
      });
      return await resp.json();
    } catch (err) {
      console.error('Failed to reset circuit breaker:', err);
      return { success: false, error: String(err) };
    }
  };

  const triggerKillSwitch = async () => {
    try {
      const resp = await fetch('/api/bot/kill-switch', {
        method: 'POST',
      });
      return await resp.json();
    } catch (err) {
      console.error('Failed to trigger emergency kill switch:', err);
      return { success: false, error: String(err) };
    }
  };

  const testBotTrade = async () => {
    try {
      const resp = await fetch('/api/bot/test-trade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      return await resp.json();
    } catch (err) {
      console.error('Failed to execute bot test trade:', err);
      return { success: false, error: String(err) };
    }
  };

  const selectStrategyBot = async (strategyId: string) => {
    try {
      const resp = await fetch('/api/bot/strategy/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ strategy_id: strategyId }),
      });
      return await resp.json();
    } catch (err) {
      console.error('Failed to select strategy bot:', err);
      return { success: false, error: String(err) };
    }
  };

  const fetchWinLossReports = async (limit: number = 50) => {
    try {
      const resp = await fetch(`/api/reports/win-loss?limit=${limit}`);
      return await resp.json();
    } catch (err) {
      console.error('Failed to fetch win/loss reports:', err);
      return null;
    }
  };

  const updateDominationDiscountPrice = async (price: number) => {
    try {
      setData((prev) => ({
        ...prev,
        settings: { ...prev.settings, domination_discount_price: price },
        ai_signals: { ...prev.ai_signals, discount_limit_price: price },
      }));
      const resp = await fetch('/api/bot/domination/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ discount_limit_price: price }),
      });
      return await resp.json();
    } catch (err) {
      console.error('Failed to update domination discount price:', err);
      return { success: false, error: String(err) };
    }
  };

  return {
    data,
    isConnected,
    sendOrder,
    cancelOrder,
    closePosition,
    toggleAIAutoTrade,
    toggleFeedMode,
    changeTimeframe,
    resetPortfolio,
    resetCircuitBreaker,
    triggerKillSwitch,
    selectStrategyBot,
    testBotTrade,
    fetchWinLossReports,
    updateDominationDiscountPrice,
  };
}

