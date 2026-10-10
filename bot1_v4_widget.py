import tkinter as tk
import urllib.request
import json
import threading
import time
from decimal import Decimal

BASE_URL = "http://127.0.0.1:8000"

class Bot1V4Widget:
    def __init__(self, root):
        self.root = root
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.geometry("280x92+120+120")
        
        self.armed = True
        self.is_connected = False
        self.balance_str = "$36.64"
        self.margin_str = "$26.52"
        self.ticker_str = "KXBTC15M"
        self.diff_str = "--"
        self.cycle_locked = False
        self.circuit_tripped = False
        self.losses = 0
        
        # Outer Frame
        self.frame = tk.Frame(root, bg='#0d1117', bd=1, relief=tk.RIDGE, highlightbackground='#30363d', highlightthickness=1)
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        # Row 1: Indicator Light + Title + Badge + Balance
        self.row1 = tk.Frame(self.frame, bg='#0d1117')
        self.row1.pack(fill=tk.X, padx=6, pady=(4, 1))
        
        self.canvas = tk.Canvas(self.row1, width=16, height=16, bg='#0d1117', highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, padx=(0, 4))
        self.light = self.canvas.create_oval(2, 2, 14, 14, fill='#00ff66', outline='#00ff66')
        
        self.title_label = tk.Label(self.row1, text="BOT 1 V4", fg='#00ff66', bg='#0d1117', font=("Consolas", 9, "bold"))
        self.title_label.pack(side=tk.LEFT, padx=1)
        
        self.mode_badge = tk.Label(self.row1, text="LIVE", fg='#58a6ff', bg='#161b22', font=("Consolas", 7, "bold"), padx=3, pady=0)
        self.mode_badge.pack(side=tk.LEFT, padx=3)
        
        self.balance_label = tk.Label(self.row1, text="$36.64", fg='#e6edf3', bg='#0d1117', font=("Consolas", 9, "bold"))
        self.balance_label.pack(side=tk.RIGHT, padx=0)
        
        # Row 2: Active Market + Spot vs Strike
        self.row2 = tk.Frame(self.frame, bg='#0d1117')
        self.row2.pack(fill=tk.X, padx=6, pady=0)
        
        self.market_label = tk.Label(self.row2, text="KXBTC15M | Spot vs Strike: --", fg='#8b949e', bg='#0d1117', font=("Consolas", 7))
        self.market_label.pack(side=tk.LEFT)
        
        # Row 3: Guardrail Invariants & Seal
        self.row3 = tk.Frame(self.frame, bg='#0d1117')
        self.row3.pack(fill=tk.X, padx=6, pady=0)
        
        self.guardrail_label = tk.Label(self.row3, text="1-Trade-Lock: ON | Seal: EXCELLENCE | TP: $0.85", fg='#7ee787', bg='#0d1117', font=("Consolas", 7))
        self.guardrail_label.pack(side=tk.LEFT)
        
        # Row 4: Status / Breaker details
        self.row4 = tk.Frame(self.frame, bg='#0d1117')
        self.row4.pack(fill=tk.X, padx=6, pady=(1, 3))
        
        self.status_label = tk.Label(self.row4, text="Streak: 0/6 | 45s Throttle | Click: Rearm/Toggle", fg='#484f58', bg='#0d1117', font=("Consolas", 7))
        self.status_label.pack(side=tk.LEFT)

        # Bind dragging and clicking across all sub-components
        def bind_all(w):
            w.bind("<ButtonRelease-1>", self.toggle_arm)
            w.bind("<ButtonPress-1>", self.start_drag)
            w.bind("<B1-Motion>", self.drag)
            w.bind("<ButtonRelease-3>", lambda e: root.destroy())
            
        for w in (self.frame, self.row1, self.row2, self.row3, self.row4, self.canvas,
                 self.title_label, self.mode_badge, self.balance_label,
                 self.market_label, self.guardrail_label, self.status_label):
            bind_all(w)
            
        # Start background polling thread
        self.running = True
        self.poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.poll_thread.start()
        
    def start_drag(self, event):
        self._x = event.x
        self._y = event.y
        
    def drag(self, event):
        x = self.root.winfo_x() - self._x + event.x
        y = self.root.winfo_y() - self._y + event.y
        self.root.geometry(f"+{x}+{y}")
        
    def toggle_arm(self, event=None):
        self.armed = not self.armed
        self._update_display()
        threading.Thread(target=self._execute_toggle_api, daemon=True).start()

    def _execute_toggle_api(self):
        try:
            if self.armed:
                # 1. Rearm guardrails (clears consecutive loss streak / breaker trip)
                req_rearm = urllib.request.Request(
                    f"{BASE_URL}/api/guardrails/rearm",
                    data=b'{}',
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                urllib.request.urlopen(req_rearm, timeout=4)
                
                # 2. Select bot1_v4_domination
                req_select = urllib.request.Request(
                    f"{BASE_URL}/api/bot/strategy/select",
                    data=json.dumps({"strategy_id": "bot1_v4_domination"}).encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                urllib.request.urlopen(req_select, timeout=4)
                
                # 3. Update settings to live auto-trade
                req_settings = urllib.request.Request(
                    f"{BASE_URL}/api/settings",
                    data=json.dumps({
                        "active_strategy_bot": "bot1_v4_domination",
                        "mode": "live",
                        "ai_auto_trade": True
                    }).encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                urllib.request.urlopen(req_settings, timeout=4)
            else:
                # 1. Disarm guardrails
                req_disarm = urllib.request.Request(
                    f"{BASE_URL}/api/guardrails/disarm",
                    data=b'{}',
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                urllib.request.urlopen(req_disarm, timeout=4)
                
                # 2. Disarm auto-trade in settings
                req_settings = urllib.request.Request(
                    f"{BASE_URL}/api/settings",
                    data=json.dumps({
                        "ai_auto_trade": False
                    }).encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                urllib.request.urlopen(req_settings, timeout=4)
        except Exception:
            pass

    def _poll_loop(self):
        while self.running:
            try:
                # 1. Poll Balance
                req_b = urllib.request.Request(f"{BASE_URL}/api/kalshi/balance")
                res_b = json.loads(urllib.request.urlopen(req_b, timeout=3).read().decode('utf-8'))
                bal_val = Decimal(str(res_b.get("balance_dollars", "36.64")))
                margin_val = Decimal(str(res_b.get("available_margin", "26.52")))
                self.balance_str = f"${bal_val:.2f}"
                self.margin_str = f"${margin_val:.2f}"
                
                # 2. Poll Guardrails Status
                req_g = urllib.request.Request(f"{BASE_URL}/api/guardrails/status")
                res_g = json.loads(urllib.request.urlopen(req_g, timeout=3).read().decode('utf-8'))
                self.circuit_tripped = res_g.get("circuit_breaker_tripped", False)
                self.cycle_locked = res_g.get("locked_cycles_count", 0) > 0
                self.losses = res_g.get("consecutive_losses", 0)
                
                # 3. Poll State for Market Ticker and Diff
                req_s = urllib.request.Request(f"{BASE_URL}/api/state")
                res_s = json.loads(urllib.request.urlopen(req_s, timeout=4).read().decode('utf-8'))
                mkt = res_s.get("market", {})
                self.ticker_str = mkt.get("ticker", "KXBTC15M")
                if len(self.ticker_str) > 18:
                    # Truncate ticker to fit nicely: e.g. KXBTC15M-26OCT100645
                    self.ticker_str = self.ticker_str[:18]
                diff = mkt.get("diff_str", "--")
                self.diff_str = diff
                
                self.is_connected = True
            except Exception:
                self.is_connected = False
                
            self.root.after(0, self._update_display)
            time.sleep(1.8)

    def _update_display(self):
        if not self.is_connected:
            self.canvas.itemconfig(self.light, fill='#8b949e', outline='#8b949e')
            self.title_label.config(text="CONNECTING...", fg='#8b949e')
            self.mode_badge.config(text="OFFLINE", fg='#8b949e')
            self.balance_label.config(text=self.balance_str, fg='#8b949e')
            self.market_label.config(text="Connecting to Port 8000 Engine...")
            return

        self.balance_label.config(text=self.balance_str, fg='#e6edf3')
        self.market_label.config(text=f"{self.ticker_str} | Diff: {self.diff_str}")

        if not self.armed or self.circuit_tripped:
            self.canvas.itemconfig(self.light, fill='#f85149', outline='#f85149')
            self.title_label.config(text="V4 DISARMED", fg='#f85149')
            self.mode_badge.config(text="STANDBY", fg='#8b949e')
            self.guardrail_label.config(text="Trading Paused | Circuit/Manual Disarmed", fg='#f85149')
            self.status_label.config(text=f"Streak: {self.losses}/6 | Click to RE-ARM & RESUME", fg='#f85149')
        elif self.cycle_locked:
            self.canvas.itemconfig(self.light, fill='#d29922', outline='#d29922')
            self.title_label.config(text="BOT 1 V4", fg='#d29922')
            self.mode_badge.config(text="LOCKED", fg='#d29922')
            self.guardrail_label.config(text="1-Trade-Per-Cycle: ACTIVE | Next Cycle Pending", fg='#d29922')
            self.status_label.config(text=f"Streak: {self.losses}/6 | Margin: {self.margin_str} | Active", fg='#8b949e')
        else:
            self.canvas.itemconfig(self.light, fill='#00ff66', outline='#00ff66')
            self.title_label.config(text="BOT 1 V4 ARMED", fg='#00ff66')
            self.mode_badge.config(text="LIVE 24/7", fg='#58a6ff')
            self.guardrail_label.config(text="1-Trade-Lock: ON | Seal: EXCELLENCE | TP: $0.85", fg='#7ee787')
            self.status_label.config(text=f"Streak: {self.losses}/6 | Margin: {self.margin_str} | Throttle: 45s", fg='#8b949e')


if __name__ == "__main__":
    root = tk.Tk()
    app = Bot1V4Widget(root)
    root.mainloop()
