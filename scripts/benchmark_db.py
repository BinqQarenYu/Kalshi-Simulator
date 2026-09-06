import asyncio
import sqlite3
import time
from pathlib import Path
from kalshi_sim.db.connection import get_db

DB_PATH = Path('data/test_benchmark.db')

async def init_test_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    db = get_db(DB_PATH)
    await db.init_db()
    async with db.get_connection() as conn:
        for i in range(100):
            await conn.execute(
                'INSERT INTO trades (trade_id, timestamp_utc, timestamp_epoch_ms, ticker, timeframe, side, size, price, gross_value, fees, bot_type, execution_mode, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (f'tr_{i}', '2025-01-01T00:00:00Z', 1000+i, f'KXBTC_{i%5}', '15m', 'yes', 10, 0.5, 5.0, 0.0, '3_step_domination_bot', 'live', 'filled')
            )
        await conn.commit()

# Simulated synchronous blocking DB operation (Current implementation in server.py)
def sync_db_op():
    live_db_trades = {}
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    cur.execute("SELECT trade_id, ticker, side, size, price, gross_value, timestamp_utc, bot_type FROM trades WHERE execution_mode = 'live'")
    for row in cur.fetchall():
        live_db_trades[row[1]] = {
            'trade_id': row[0],
            'ticker': row[1],
            'side': row[2],
            'size': row[3],
            'price': row[4],
            'gross_value': row[5],
            'timestamp_utc': row[6],
            'bot_type': row[7],
        }

    # Write back 20 settlement records
    for i in range(20):
        cur.execute(
            'INSERT OR REPLACE INTO settlements (settlement_id, timestamp_utc, timestamp_epoch_ms, ticker, side, size, entry_price, settlement_price, outcome, pnl, balance_after, bot_type, execution_mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (f'settle_{i}', '2025-01-01T00:00:00Z', 2000+i, f'KXBTC_{i}', 'yes', 10, 0.5, 1.0, 'win', 5.0, 105.0, '3_step_domination_bot', 'live')
        )
    con.commit()
    con.close()
    return len(live_db_trades)

# Optimized async DB operation using aiosqlite / get_db()
async def async_db_op():
    live_db_trades = {}
    db = get_db(DB_PATH)
    async with db.get_connection() as conn:
        async with conn.execute("SELECT trade_id, ticker, side, size, price, gross_value, timestamp_utc, bot_type FROM trades WHERE execution_mode = 'live'") as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                live_db_trades[row[1]] = {
                    'trade_id': row[0],
                    'ticker': row[1],
                    'side': row[2],
                    'size': row[3],
                    'price': row[4],
                    'gross_value': row[5],
                    'timestamp_utc': row[6],
                    'bot_type': row[7],
                }

        # Write back 20 settlement records
        for i in range(20):
            await conn.execute(
                'INSERT OR REPLACE INTO settlements (settlement_id, timestamp_utc, timestamp_epoch_ms, ticker, side, size, entry_price, settlement_price, outcome, pnl, balance_after, bot_type, execution_mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (f'settle_{i}', '2025-01-01T00:00:00Z', 2000+i, f'KXBTC_{i}', 'yes', 10, 0.5, 1.0, 'win', 5.0, 105.0, '3_step_domination_bot', 'live')
            )
        await conn.commit()
    return len(live_db_trades)

async def tick_worker(stop_event, tick_counts, tick_lags):
    target_interval = 0.010 # 10ms tick target
    while not stop_event.is_set():
        t0 = time.perf_counter()
        await asyncio.sleep(target_interval)
        dt = time.perf_counter() - t0
        tick_counts[0] += 1
        tick_lags.append((dt - target_interval) * 1000.0) # in ms

async def run_benchmark():
    await init_test_db()

    N = 20

    # 1. Test Synchronous Pattern (blocking async loop)
    sync_tick_counts = [0]
    sync_lags = []
    stop_event = asyncio.Event()
    worker_task = asyncio.create_task(tick_worker(stop_event, sync_tick_counts, sync_lags))

    async def run_sync_calls():
        for _ in range(N):
            sync_db_op() # blocking call in async function
            await asyncio.sleep(0.001)

    t0 = time.perf_counter()
    await run_sync_calls()
    sync_time = time.perf_counter() - t0

    stop_event.set()
    await worker_task
    max_sync_lag_ms = max(sync_lags) if sync_lags else 0
    avg_sync_lag_ms = (sum(sync_lags) / len(sync_lags)) if sync_lags else 0

    # 2. Test Async Pattern (non-blocking)
    async_tick_counts = [0]
    async_lags = []
    stop_event = asyncio.Event()
    worker_task = asyncio.create_task(tick_worker(stop_event, async_tick_counts, async_lags))

    async def run_async_calls():
        for _ in range(N):
            await async_db_op()
            await asyncio.sleep(0.001)

    t0 = time.perf_counter()
    await run_async_calls()
    async_time = time.perf_counter() - t0

    stop_event.set()
    await worker_task
    max_async_lag_ms = max(async_lags) if async_lags else 0
    avg_async_lag_ms = (sum(async_lags) / len(async_lags)) if async_lags else 0

    print('=== BENCHMARK RESULTS ===')
    print(f'Sync sqlite3: Total Time: {sync_time:.4f}s | Concurrent Ticks: {sync_tick_counts[0]} | Max Tick Lag: {max_sync_lag_ms:.2f}ms | Avg Lag: {avg_sync_lag_ms:.2f}ms')
    print(f'Async aiosqlite: Total Time: {async_time:.4f}s | Concurrent Ticks: {async_tick_counts[0]} | Max Tick Lag: {max_async_lag_ms:.2f}ms | Avg Lag: {avg_async_lag_ms:.2f}ms')

    if DB_PATH.exists():
        DB_PATH.unlink()

if __name__ == '__main__':
    asyncio.run(run_benchmark())
