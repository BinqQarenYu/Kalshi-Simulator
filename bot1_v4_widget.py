import tkinter as tk
import urllib.request
import json
import threading

API_URL = "http://127.0.0.1:8000/api/settings"

class Bot1V4Widget:
    def __init__(self, root):
        self.root = root
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.geometry("240x70+120+120")
        
        self.armed = True
        
        self.frame = tk.Frame(root, bg='#0d1117', bd=1, relief=tk.RIDGE)
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        # Header Row: Indicator Light + Title
        self.top_frame = tk.Frame(self.frame, bg='#0d1117')
        self.top_frame.pack(fill=tk.X, pady=(4, 2))
        
        self.canvas = tk.Canvas(self.top_frame, width=18, height=18, bg='#0d1117', highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, padx=(8, 4))
        self.light = self.canvas.create_oval(2, 2, 16, 16, fill='#00ff66', outline='#00ff66')
        
        self.label = tk.Label(self.top_frame, text="BOT 1 V4 ARMED", fg='#00ff66', bg='#0d1117', font=("Consolas", 10, "bold"))
        self.label.pack(side=tk.LEFT, padx=2)
        
        self.mode_badge = tk.Label(self.top_frame, text="LIVE 24/7", fg='#58a6ff', bg='#161b22', font=("Consolas", 7, "bold"), padx=4, pady=1)
        self.mode_badge.pack(side=tk.RIGHT, padx=(0, 8))
        
        # Sub-status details row
        self.detail_label = tk.Label(self.frame, text="1-Trade-Per-Cycle | EV Coupled | $0.85 TP", fg='#8b949e', bg='#0d1117', font=("Consolas", 8))
        self.detail_label.pack(side=tk.TOP, pady=0)
        
        # Bottom controls reminder
        self.hint_label = tk.Label(self.frame, text="Left-Click: Toggle | Drag: Move | Right-Click: Exit", fg='#484f58', bg='#0d1117', font=("Consolas", 7))
        self.hint_label.pack(side=tk.TOP, pady=(1, 3))
        
        # Bind interactions across all widget components
        def bind_all(w):
            w.bind("<ButtonRelease-1>", self.toggle_arm)
            w.bind("<ButtonPress-1>", self.start_drag)
            w.bind("<B1-Motion>", self.drag)
            w.bind("<ButtonRelease-3>", lambda e: root.destroy())
            
        for w in (self.frame, self.top_frame, self.canvas, self.label, self.mode_badge, self.detail_label, self.hint_label):
            bind_all(w)
            
        self.update_ui()
        
    def start_drag(self, event):
        self._x = event.x
        self._y = event.y
        
    def drag(self, event):
        x = self.root.winfo_x() - self._x + event.x
        y = self.root.winfo_y() - self._y + event.y
        self.root.geometry(f"+{x}+{y}")
        
    def toggle_arm(self, event=None):
        self.armed = not self.armed
        self.update_ui()
        threading.Thread(target=self.send_api_update, daemon=True).start()
        
    def update_ui(self):
        if self.armed:
            self.canvas.itemconfig(self.light, fill='#00ff66', outline='#00ff66')
            self.label.config(text="BOT 1 V4 ARMED", fg='#00ff66')
            self.mode_badge.config(text="LIVE 24/7", fg='#58a6ff')
            self.detail_label.config(text="1-Trade-Per-Cycle | EV Coupled | $0.85 TP", fg='#8b949e')
        else:
            self.canvas.itemconfig(self.light, fill='#30363d', outline='#f85149')
            self.label.config(text="V4 DISARMED", fg='#f85149')
            self.mode_badge.config(text="STANDBY", fg='#8b949e')
            self.detail_label.config(text="Trading Paused by Manual Override", fg='#f85149')
            
    def send_api_update(self):
        payload = {
            "active_strategy_bot": "bot1_v4_domination",
            "mode": "live",
            "ai_auto_trade": self.armed
        }
        try:
            req = urllib.request.Request(
                API_URL,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

if __name__ == "__main__":
    root = tk.Tk()
    app = Bot1V4Widget(root)
    root.mainloop()
