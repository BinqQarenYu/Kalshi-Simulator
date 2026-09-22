import os
import sys
import time
import json
import random
import urllib.request
import urllib.error
from pathlib import Path
from decimal import Decimal

# Set up paths
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

BOTS_DIR = REPO_ROOT / "src" / "kalshi_sim" / "perpetuals" / "bots"
BOTS_DIR.mkdir(parents=True, exist_ok=True)
BOT_FILE = BOTS_DIR / "experimental_quant_bot.py"
JOURNAL_FILE = REPO_ROOT / "docs" / "audits" / "PERPETUAL_QUANT_LEARNINGS.md"
ENV_PATH = REPO_ROOT / ".env"

def get_api_key() -> str:
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH)
    deerflow_env_path = Path(r"C:\Users\Admin\.gemini\mcp\deer-flow\.env")
    if deerflow_env_path.exists():
        load_dotenv(deerflow_env_path)
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key or key.startswith("$"):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as reg_key:
                key, _ = winreg.QueryValueEx(reg_key, "GEMINI_API_KEY")
        except Exception:
            pass
    return key or ""

def query_gemini(prompt: str) -> str:
    api_key = get_api_key()
    if not api_key:
        print("[!] No API key. Halting forge.")
        time.sleep(10)
        return ""
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro-latest:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3}
    }
    
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"}, method="POST")
    
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))
                candidates = resp_json.get("candidates", [])
                if candidates:
                    return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
        except Exception as e:
            time.sleep(2)
    return ""

def generate_strategy(previous_learnings: str) -> str:
    prompt = f"""
You are DEER-QUANT, the autonomous quantitative strategist for the Kalshi Simulator (Perpetuals).
Your mission: Formulate a Python-based trading strategy. 
Constraints:
1. You must output ONLY valid Python code.
2. The code must contain a class `ExperimentalQuantBot`.
3. It must have a method `def evaluate_tick(self, price: Decimal, timestamp: int) -> str:` that returns 'BUY', 'SELL', or 'HOLD'.
4. STRICT DECIMAL MATH ONLY. Zero float tolerance.

Previous Learnings / Context:
{previous_learnings}

Write the improved `ExperimentalQuantBot` class now. Do not wrap in markdown, just pure Python code starting with imports.
"""
    code = query_gemini(prompt)
    if code.startswith("```python"):
        code = code[9:]
    if code.endswith("```"):
        code = code[:-3]
    return code.strip()

def run_synthetic_backtest(bot_code: str) -> dict:
    # Write the bot
    BOT_FILE.write_text(bot_code, encoding="utf-8")
    
    # Dynamically import and run
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("experimental_quant_bot", str(BOT_FILE))
        module = importlib.util.module_from_spec(spec)
        sys.modules["experimental_quant_bot"] = module
        spec.loader.exec_module(module)
        
        bot = module.ExperimentalQuantBot()
        
        # Synthetic Random Walk (BTC style)
        price = Decimal("60000.00")
        position = 0
        pnl = Decimal("0.00")
        
        trades = 0
        for t in range(100):
            # random walk tick
            price += Decimal(str(round(random.uniform(-50.0, 50.0), 2)))
            decision = bot.evaluate_tick(price, t)
            
            if decision == 'BUY' and position == 0:
                position = 1
                entry_price = price
                trades += 1
            elif decision == 'SELL' and position == 1:
                pnl += (price - entry_price)
                position = 0
                
        # Force close
        if position == 1:
            pnl += (price - entry_price)
            
        return {"status": "SUCCESS", "pnl": float(pnl), "trades": trades}
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}

def record_learning(iteration: int, result: dict):
    if not JOURNAL_FILE.parent.exists():
        JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
        
    line = f"## Iteration {iteration}\n"
    line += f"- Status: {result.get('status')}\n"
    if result.get("status") == "SUCCESS":
        line += f"- PnL: ${result.get('pnl'):.2f}\n"
        line += f"- Trades Executed: {result.get('trades')}\n"
    else:
        line += f"- Error: {result.get('error')}\n"
        
    line += "\n"
    
    with open(JOURNAL_FILE, "a", encoding="utf-8") as f:
        f.write(line)

    print(f"[*] Iteration {iteration} complete. PnL: {result.get('pnl', 'ERROR')}")
    return line

def throttle_resources():
    """Drops the process to IDLE priority on Windows to protect laptop resources."""
    try:
        import ctypes
        # IDLE_PRIORITY_CLASS = 0x00000040
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00000040)
        import gc
        gc.enable() # Ensure GC is active
    except Exception:
        pass

def main():
    throttle_resources()
    print("[*] DEER-QUANT Perpetual Quant Forge initialized. Continuous learning loop started...")
    iteration = 1
    recent_context = "Initial state. No strategy yet. Build a simple moving average crossover or a mean-reversion using Decimal."
    
    while True:
        print(f"\n[+] Starting Iteration {iteration}...")
        
        # 1. Formulate
        print("    -> Formulating strategy...")
        code = generate_strategy(recent_context)
        
        if not code:
            print("    -> [!] Failed to generate code. Sleeping.")
            time.sleep(30)
            continue
            
        # 2. Backtest
        print("    -> Running synthetic paper live-trade...")
        result = run_synthetic_backtest(code)
        
        # 3. Learn
        print("    -> Recording learnings...")
        learning_summary = record_learning(iteration, result)
        
        # Prepare context for next loop
        recent_context = f"Last Iteration Results:\n{learning_summary}\n\nImprove the strategy to maximize PnL and fix any errors. Ensure it trades at least a few times. Return pure python code ONLY."
        
        iteration += 1
        
        # Wait before next loop
        print("    -> Sleeping for 60 seconds before next evolution...")
        import gc
        gc.collect()
        time.sleep(60)

if __name__ == "__main__":
    main()
