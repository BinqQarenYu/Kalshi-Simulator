import tkinter as tk
import urllib.request
import json
import threading
import datetime

API_URL = "http://127.0.0.1:8000/api/settings"

class BotWidget:
    def __init__(self, root):
        self.root = root
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.geometry("220x65+100+100")
        
        self.armed = True
        
        self.frame = tk.Frame(root, bg='#1a1a1a', bd=1, relief=tk.RIDGE)
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        self.top_frame = tk.Frame(self.frame, bg='#1a1a1a')
        self.top_frame.pack(fill=tk.X, pady=5)
        
        self.canvas = tk.Canvas(self.top_frame, width=20, height=20, bg='#1a1a1a', highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, padx=10)
        self.light = self.canvas.create_oval(2, 2, 18, 18, fill='#00ff00', outline='#00ff00')
        
        self.label = tk.Label(self.top_frame, text="BOT 1 ARMED", fg='#00ff00', bg='#1a1a1a', font=("Consolas", 11, "bold"))
        self.label.pack(side=tk.LEFT, padx=5)
        
        self.timer_label = tk.Label(self.frame, text="Starts: --:--:-- | Pauses: --:--:--", fg='#aaaaaa', bg='#1a1a1a', font=("Consolas", 8))
        self.timer_label.pack(side=tk.TOP, pady=0)
        
        # Bindings
        def bind_all(widget):
            widget.bind("<ButtonRelease-1>", self.toggle_arm)
            widget.bind("<ButtonPress-1>", self.start_drag)
            widget.bind("<B1-Motion>", self.drag)
            widget.bind("<ButtonRelease-3>", lambda e: root.destroy())
            
        bind_all(self.frame)
        bind_all(self.top_frame)
        bind_all(self.canvas)
        bind_all(self.label)
        bind_all(self.timer_label)
        
        self.update_ui()
        self.update_timers()
        
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
            self.canvas.itemconfig(self.light, fill='#00ff00', outline='#00ff00')
            self.label.config(text="BOT 1 ARMED", fg='#00ff00')
        else:
            self.canvas.itemconfig(self.light, fill='#555555', outline='#ff0000')
            self.label.config(text="DISARMED (MANUAL)", fg='#ff0000')

    def update_timers(self):
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        now_est = now_utc - datetime.timedelta(hours=4)
        
        current_hour = now_est.hour
        current_min = now_est.minute
        current_sec = now_est.second
        
        total_seconds = current_hour * 3600 + current_min * 60 + current_sec
        
        starts = [6*3600, 15*3600, 22*3600, 30*3600]
        pauses = [9*3600, 18*3600, 30*3600, 33*3600]
        
        next_start = next((t for t in starts if t > total_seconds), starts[0] + 24*3600)
        next_pause = next((t for t in pauses if t > total_seconds), pauses[0] + 24*3600)
        
        is_active = (6 <= current_hour < 9) or (15 <= current_hour < 18) or (current_hour >= 22) or (current_hour < 6)
        
        def fmt(secs):
            h = secs // 3600
            m = (secs % 3600) // 60
            s = secs % 60
            return f"{h:02d}h {m:02d}m {s:02d}s"
            
        if is_active:
            s_rem_str = "ACTIVE NOW"
            p_rem_str = fmt(next_pause - total_seconds)
        else:
            s_rem_str = fmt(next_start - total_seconds)
            p_rem_str = "PAUSED NOW"
            
        if self.armed:
            if is_active:
                self.canvas.itemconfig(self.light, fill='#00ff00', outline='#00ff00')
                self.label.config(text="BOT 1 ARMED", fg='#00ff00')
            else:
                self.canvas.itemconfig(self.light, fill='#ffaa00', outline='#ffaa00')
                self.label.config(text="STANDBY (TIME)", fg='#ffaa00')
                
        self.timer_label.config(text=f"Starts: {s_rem_str} | Pauses: {p_rem_str}")
        
        self.root.after(1000, self.update_timers)
            
    def send_api_update(self):
        payload = {
            "active_strategy_bot": "3_step_domination_bot",
            "mode": "live",
            "ai_auto_trade": self.armed
        }
        try:
            req = urllib.request.Request(API_URL, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=3)
        except Exception as e:
            pass

if __name__ == "__main__":
    root = tk.Tk()
    app = BotWidget(root)
    root.mainloop()
