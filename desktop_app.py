import threading
import time
import subprocess
import sys
import os
import requests
import tkinter as tk
from tkinter import ttk
import pystray
from PIL import Image, ImageDraw
from plyer import notification

BASE_URL = "http://localhost:5000"
POLL_INTERVAL = 10

def start_flask():
    subprocess.Popen([sys.executable, "app.py"], creationflags=subprocess.CREATE_NO_WINDOW)

def start_agent():
    time.sleep(3)
    subprocess.Popen([sys.executable, "agent.py", "--server", BASE_URL], creationflags=subprocess.CREATE_NO_WINDOW)

def fetch_devices():
    try:
        r = requests.get(f"{BASE_URL}/api/devices", timeout=5)
        return r.json() if r.status_code == 200 else []
    except:
        return []

def fetch_alerts():
    try:
        r = requests.get(f"{BASE_URL}/api/alerts", timeout=5)
        return r.json()[:20] if r.status_code == 200 else []
    except:
        return []

def format_uptime(s):
    if not s: return "—"
    d, h, m = s // 86400, (s % 86400) // 3600, (s % 3600) // 60
    if d > 0: return f"{d}d {h}h"
    if h > 0: return f"{h}h {m}m"
    return f"{m}m"

def make_tray_icon(color="#6366f1"):
    img = Image.new("RGBA", (64, 64), (0,0,0,0))
    d = ImageDraw.Draw(img)
    d.ellipse([4,4,60,60], fill=color)
    d.rectangle([20,28,44,36], fill="white")
    d.rectangle([28,20,36,44], fill="white")
    return img

# ── Color palette ──────────────────────────────────────────────────────────
BG      = "#f8fafc"
SIDEBAR = "#1e1b4b"
CARD    = "#ffffff"
CARD2   = "#f1f5f9"
BORDER  = "#e2e8f0"
TEXT    = "#0f172a"
TEXT2   = "#475569"
TEXT3   = "#94a3b8"
ACCENT  = "#6366f1"
ACCENT2 = "#818cf8"
GREEN   = "#10b981"
GREEN2  = "#d1fae5"
WARN    = "#f59e0b"
WARN2   = "#fef3c7"
CRIT    = "#ef4444"
CRIT2   = "#fee2e2"
OFFLINE = "#94a3b8"

class SysMonApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SysMon")
        self.root.geometry("960x640")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

        self.tray = None
        self.last_alert_id = None
        self.server_ready = False
        self.current_tab = "overview"

        self._build_ui()
        threading.Thread(target=self._start_backend, daemon=True).start()
        threading.Thread(target=self._start_tray, daemon=True).start()
        self._poll()

    def _build_ui(self):
        # ── Sidebar ──
        self.sidebar = tk.Frame(self.root, bg=SIDEBAR, width=200)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo area
        logo_frame = tk.Frame(self.sidebar, bg=SIDEBAR)
        logo_frame.pack(fill="x", pady=(24, 8), padx=20)

        logo_dot = tk.Canvas(logo_frame, width=32, height=32, bg=SIDEBAR, highlightthickness=0)
        logo_dot.pack(side="left", padx=(0, 10))
        logo_dot.create_oval(2, 2, 30, 30, fill=ACCENT, outline="")
        logo_dot.create_text(16, 16, text="S", fill="white", font=("Segoe UI", 14, "bold"))

        tk.Label(logo_frame, text="SysMon", font=("Segoe UI", 15, "bold"),
                 fg="white", bg=SIDEBAR).pack(side="left")

        # Status indicator
        self.status_frame = tk.Frame(self.sidebar, bg="#2d2a6e", pady=8, padx=12)
        self.status_frame.pack(fill="x", padx=16, pady=(0, 20))
        self.status_dot = tk.Label(self.status_frame, text="●", font=("Segoe UI", 9),
                                    fg=WARN, bg="#2d2a6e")
        self.status_dot.pack(side="left")
        self.status_label = tk.Label(self.status_frame, text="Starting...",
                                      font=("Segoe UI", 9), fg="#a5b4fc", bg="#2d2a6e")
        self.status_label.pack(side="left", padx=(6, 0))

        # Nav items
        self.nav_btns = {}
        nav_items = [
            ("overview", "📊", "Overview"),
            ("alerts",   "🔔", "Alerts"),
            ("settings", "⚙", "Settings"),
        ]
        for key, icon, label in nav_items:
            btn = tk.Button(
                self.sidebar, text=f"  {icon}  {label}",
                font=("Segoe UI", 11), anchor="w",
                bg=SIDEBAR, fg="#a5b4fc", bd=0, padx=16, pady=10,
                activebackground="#2d2a6e", activeforeground="white",
                cursor="hand2",
                command=lambda k=key: self._switch_tab(k)
            )
            btn.pack(fill="x", padx=8)
            self.nav_btns[key] = btn

        # Version at bottom
        tk.Label(self.sidebar, text="v1.0.0", font=("Segoe UI", 8),
                 fg="#4338ca", bg=SIDEBAR).pack(side="bottom", pady=16)

        # ── Main area ──
        self.main = tk.Frame(self.root, bg=BG)
        self.main.pack(side="left", fill="both", expand=True)

        # Top bar
        topbar = tk.Frame(self.main, bg=CARD, height=56)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        tk.Frame(topbar, bg=BORDER, height=1).pack(side="bottom", fill="x")

        self.page_title = tk.Label(topbar, text="Overview",
                                    font=("Segoe UI", 16, "bold"), fg=TEXT, bg=CARD)
        self.page_title.pack(side="left", padx=24, pady=16)

        self.refresh_btn = tk.Button(topbar, text="↻  Refresh",
                                      font=("Segoe UI", 10), fg=ACCENT, bg=CARD,
                                      bd=0, cursor="hand2", activeforeground=ACCENT2,
                                      activebackground=CARD,
                                      command=self._manual_refresh)
        self.refresh_btn.pack(side="right", padx=20)

        # Content frames
        self.frames = {}
        for name in ["overview", "alerts", "settings"]:
            f = tk.Frame(self.main, bg=BG)
            self.frames[name] = f

        self._build_overview()
        self._build_alerts()
        self._build_settings()
        self._switch_tab("overview")

    def _switch_tab(self, key):
        self.current_tab = key
        for f in self.frames.values():
            f.pack_forget()
        self.frames[key].pack(fill="both", expand=True)

        titles = {"overview": "Overview", "alerts": "Alert History", "settings": "Settings"}
        self.page_title.config(text=titles.get(key, key.title()))

        for k, btn in self.nav_btns.items():
            if k == key:
                btn.config(bg="#2d2a6e", fg="white")
            else:
                btn.config(bg=SIDEBAR, fg="#a5b4fc")

    # ── Overview ──────────────────────────────────────────────────────────────

    def _build_overview(self):
        frame = self.frames["overview"]

        # Stat cards
        stats_row = tk.Frame(frame, bg=BG)
        stats_row.pack(fill="x", padx=20, pady=(20, 0))

        self.stat_cards = {}
        stats = [
            ("total",  "Total Devices", "—",  TEXT,  "🖥"),
            ("online", "Online",        "—",  GREEN, "✓"),
            ("warn",   "Warnings",      "—",  WARN,  "⚠"),
            ("crit",   "Critical",      "—",  CRIT,  "✕"),
        ]
        for key, label, val, color, icon in stats:
            card = tk.Frame(stats_row, bg=CARD, padx=18, pady=16,
                            highlightbackground=BORDER, highlightthickness=1)
            card.pack(side="left", fill="both", expand=True, padx=(0, 12))

            top = tk.Frame(card, bg=CARD)
            top.pack(fill="x")
            tk.Label(top, text=label, font=("Segoe UI", 10),
                     fg=TEXT2, bg=CARD).pack(side="left")
            tk.Label(top, text=icon, font=("Segoe UI", 12),
                     fg=color, bg=CARD).pack(side="right")

            lbl = tk.Label(card, text=val, font=("Segoe UI", 28, "bold"),
                           fg=color, bg=CARD)
            lbl.pack(anchor="w", pady=(4, 0))
            self.stat_cards[key] = lbl

        # Section header
        sec = tk.Frame(frame, bg=BG)
        sec.pack(fill="x", padx=20, pady=(20, 8))
        tk.Label(sec, text="Monitored Devices", font=("Segoe UI", 13, "bold"),
                 fg=TEXT, bg=BG).pack(side="left")
        self.device_count_lbl = tk.Label(sec, text="", font=("Segoe UI", 10),
                                          fg=TEXT3, bg=BG)
        self.device_count_lbl.pack(side="left", padx=8, pady=2)

        # Scrollable device list
        wrap = tk.Frame(frame, bg=BG)
        wrap.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.dev_canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        sb = tk.Scrollbar(wrap, orient="vertical", command=self.dev_canvas.yview)
        self.dev_canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.dev_canvas.pack(side="left", fill="both", expand=True)

        self.dev_inner = tk.Frame(self.dev_canvas, bg=BG)
        self.dev_win_id = self.dev_canvas.create_window((0,0), window=self.dev_inner, anchor="nw")

        self.dev_inner.bind("<Configure>",
            lambda e: self.dev_canvas.configure(scrollregion=self.dev_canvas.bbox("all")))
        self.dev_canvas.bind("<Configure>",
            lambda e: self.dev_canvas.itemconfig(self.dev_win_id, width=e.width))

        self._show_placeholder("Waiting for server to start...")

    def _show_placeholder(self, msg):
        for w in self.dev_inner.winfo_children():
            w.destroy()
        f = tk.Frame(self.dev_inner, bg=CARD,
                     highlightbackground=BORDER, highlightthickness=1)
        f.pack(fill="x", pady=4)
        tk.Label(f, text=msg, font=("Segoe UI", 11),
                 fg=TEXT3, bg=CARD, pady=40).pack()

    def _render_devices(self, devices):
        for w in self.dev_inner.winfo_children():
            w.destroy()

        if not devices:
            self._show_placeholder("No devices found. Make sure the agent is running.")
            return

        online = warn = crit = 0
        for d in devices:
            cpu  = d.get("cpu")  or 0
            ram  = d.get("ram")  or 0
            disk = d.get("disk") or 0
            if d.get("status") == "online": online += 1
            if cpu >= 90 or ram >= 95 or disk >= 95: crit += 1
            elif cpu >= 80 or ram >= 85 or disk >= 85: warn += 1

        self.stat_cards["total"].config(text=str(len(devices)))
        self.stat_cards["online"].config(text=str(online))
        self.stat_cards["warn"].config(text=str(warn))
        self.stat_cards["crit"].config(text=str(crit))
        self.device_count_lbl.config(text=f"{len(devices)} device{'s' if len(devices)!=1 else ''}")

        for d in devices:
            self._device_card(d)

    def _device_card(self, d):
        cpu  = d.get("cpu")  or 0
        ram  = d.get("ram")  or 0
        disk = d.get("disk") or 0
        status = d.get("status", "unknown")

        if status == "offline":
            accent, bg_badge, fg_badge, status_txt = OFFLINE, "#f1f5f9", TEXT3, "Offline"
        elif cpu >= 90 or ram >= 95 or disk >= 95:
            accent, bg_badge, fg_badge, status_txt = CRIT, CRIT2, CRIT, "Critical"
        elif cpu >= 80 or ram >= 85 or disk >= 85:
            accent, bg_badge, fg_badge, status_txt = WARN, WARN2, WARN, "Warning"
        else:
            accent, bg_badge, fg_badge, status_txt = GREEN, GREEN2, GREEN, "Healthy"

        outer = tk.Frame(self.dev_inner, bg=BG)
        outer.pack(fill="x", pady=(0, 10))

        card = tk.Frame(outer, bg=CARD,
                        highlightbackground=accent, highlightthickness=2)
        card.pack(fill="x")

        # Left accent bar
        tk.Frame(card, bg=accent, width=4).pack(side="left", fill="y")

        inner = tk.Frame(card, bg=CARD)
        inner.pack(side="left", fill="both", expand=True, padx=16, pady=14)

        # Header row
        hdr = tk.Frame(inner, bg=CARD)
        hdr.pack(fill="x", pady=(0, 8))

        tk.Label(hdr, text=d.get("hostname", "Unknown"),
                 font=("Segoe UI", 13, "bold"), fg=TEXT, bg=CARD).pack(side="left")

        badge = tk.Label(hdr, text=f"  {status_txt}  ",
                         font=("Segoe UI", 9, "bold"),
                         fg=fg_badge, bg=bg_badge, padx=4, pady=2)
        badge.pack(side="right")

        # Subtitle
        tk.Label(inner, text=f"🌐  {d.get('ip_address','—')}    💻  {d.get('os_name','—')}",
                 font=("Segoe UI", 9), fg=TEXT2, bg=CARD).pack(anchor="w", pady=(0, 10))

        # Metric bars
        metrics_frame = tk.Frame(inner, bg=CARD)
        metrics_frame.pack(fill="x")

        for label, val, wt, ct in [("CPU", cpu, 80, 90), ("RAM", ram, 85, 95), ("DISK", disk, 85, 95)]:
            bar_color = CRIT if val >= ct else WARN if val >= wt else ACCENT
            col = tk.Frame(metrics_frame, bg=CARD)
            col.pack(side="left", expand=True, fill="x", padx=(0, 20))

            top_row = tk.Frame(col, bg=CARD)
            top_row.pack(fill="x")
            tk.Label(top_row, text=label, font=("Segoe UI", 9),
                     fg=TEXT2, bg=CARD).pack(side="left")
            tk.Label(top_row, text=f"{val:.0f}%", font=("Segoe UI", 9, "bold"),
                     fg=bar_color, bg=CARD).pack(side="right")

            # Progress bar background
            bar_bg = tk.Frame(col, bg=CARD2, height=6)
            bar_bg.pack(fill="x", pady=(3, 0))
            bar_bg.update_idletasks()
            w = bar_bg.winfo_width()
            fill_w = max(4, int(w * val / 100))
            tk.Frame(bar_bg, bg=bar_color, height=6, width=fill_w).place(x=0, y=0)

        # Footer
        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", pady=(10, 6))
        ft = tk.Frame(inner, bg=CARD)
        ft.pack(fill="x")
        tk.Label(ft, text=f"⏱  Uptime: {format_uptime(d.get('uptime'))}",
                 font=("Segoe UI", 9), fg=TEXT3, bg=CARD).pack(side="left")
        alerts_count = d.get("active_alerts", 0)
        if alerts_count > 0:
            tk.Label(ft, text=f"🔔  {alerts_count} alert{'s' if alerts_count!=1 else ''}",
                     font=("Segoe UI", 9), fg=WARN, bg=CARD).pack(side="right")

    # ── Alerts ────────────────────────────────────────────────────────────────

    def _build_alerts(self):
        frame = self.frames["alerts"]

        info = tk.Frame(frame, bg=BG)
        info.pack(fill="x", padx=20, pady=(20, 10))
        tk.Label(info, text="All triggered alerts across your devices",
                 font=("Segoe UI", 10), fg=TEXT2, bg=BG).pack(side="left")

        wrap = tk.Frame(frame, bg=CARD,
                        highlightbackground=BORDER, highlightthickness=1)
        wrap.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("M.Treeview",
                        background=CARD, foreground=TEXT,
                        fieldbackground=CARD, font=("Segoe UI", 10),
                        rowheight=32, borderwidth=0)
        style.configure("M.Treeview.Heading",
                        background=CARD2, foreground=TEXT2,
                        font=("Segoe UI", 10, "bold"), relief="flat")
        style.map("M.Treeview",
                  background=[("selected", "#ede9fe")],
                  foreground=[("selected", TEXT)])

        cols = ("Time", "Device", "Type", "Severity", "Message")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", style="M.Treeview")
        for col, w in zip(cols, [150, 140, 90, 90, 360]):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, minwidth=40)

        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        self.tree.tag_configure("critical", foreground=CRIT, font=("Segoe UI", 10))
        self.tree.tag_configure("warning",  foreground=WARN, font=("Segoe UI", 10))

    def _render_alerts(self, alerts, devices):
        dmap = {d["device_id"]: d.get("hostname", d["device_id"]) for d in devices}
        self.tree.delete(*self.tree.get_children())
        for a in alerts:
            ts   = a.get("ts", "")[:19].replace("T", " ")
            host = dmap.get(a.get("device_id", ""), "—")
            typ  = a.get("type", "—").upper()
            sev  = a.get("severity", "")
            msg  = a.get("message", "")
            self.tree.insert("", "end",
                values=(ts, host, typ, sev.upper(), msg), tags=(sev,))

    # ── Settings ──────────────────────────────────────────────────────────────

    def _build_settings(self):
        frame = self.frames["settings"]

        wrap = tk.Frame(frame, bg=BG)
        wrap.pack(fill="both", expand=True, padx=20, pady=20)

        # About card
        card = tk.Frame(wrap, bg=CARD, padx=20, pady=20,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", pady=(0, 14))

        tk.Label(card, text="SysMon Desktop", font=("Segoe UI", 13, "bold"),
                 fg=TEXT, bg=CARD).pack(anchor="w")
        tk.Label(card, text="AI-Powered System Monitor  ·  v1.0.0",
                 font=("Segoe UI", 10), fg=TEXT2, bg=CARD).pack(anchor="w", pady=(2, 12))

        for label, val in [
            ("Server", BASE_URL),
            ("Poll interval", f"{POLL_INTERVAL} seconds"),
            ("Dashboard", f"{BASE_URL}  (open in browser for full view)"),
        ]:
            row = tk.Frame(card, bg=CARD)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, font=("Segoe UI", 10),
                     fg=TEXT2, bg=CARD, width=16, anchor="w").pack(side="left")
            tk.Label(row, text=val, font=("Segoe UI", 10),
                     fg=TEXT, bg=CARD).pack(side="left")

        # Open browser button
        btn_row = tk.Frame(wrap, bg=BG)
        btn_row.pack(fill="x")
        tk.Button(btn_row, text="  🌐  Open Full Dashboard in Browser  ",
                  font=("Segoe UI", 11), fg="white", bg=ACCENT,
                  bd=0, padx=16, pady=10, cursor="hand2",
                  activebackground=ACCENT2, activeforeground="white",
                  command=lambda: __import__('webbrowser').open(BASE_URL)
                  ).pack(side="left")

    # ── Tray ──────────────────────────────────────────────────────────────────

    def _start_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("Show SysMon", self._show_window, default=True),
            pystray.MenuItem("Quit", self._quit_app)
        )
        self.tray = pystray.Icon("SysMon", make_tray_icon(ACCENT), "SysMon", menu)
        self.tray.run()

    def hide_window(self):
        self.root.withdraw()

    def _show_window(self, *args):
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)

    def _quit_app(self, *args):
        if self.tray: self.tray.stop()
        self.root.after(0, self.root.destroy)

    # ── Backend ───────────────────────────────────────────────────────────────

    def _start_backend(self):
        start_flask()
        start_agent()
        for _ in range(30):
            try:
                requests.get(f"{BASE_URL}/api/devices", timeout=2)
                self.server_ready = True
                self.root.after(0, self._on_server_ready)
                return
            except:
                time.sleep(1)
        self.root.after(0, lambda: (
            self.status_dot.config(fg=CRIT),
            self.status_label.config(text="Failed to start")
        ))

    def _on_server_ready(self):
        self.status_dot.config(fg=GREEN)
        self.status_label.config(text="Running")

    def _manual_refresh(self):
        self.refresh_btn.config(text="↻  Refreshing...")
        self.root.after(800, lambda: self.refresh_btn.config(text="↻  Refresh"))
        if self.server_ready:
            devices = fetch_devices()
            alerts  = fetch_alerts()
            self._render_devices(devices)
            self._render_alerts(alerts, devices)

    def _poll(self):
        if self.server_ready:
            try:
                devices = fetch_devices()
                alerts  = fetch_alerts()
                self._render_devices(devices)
                self._render_alerts(alerts, devices)
                self._check_alerts(alerts)
                if self.tray:
                    has_crit = any((d.get("cpu") or 0)>=90 or
                                   (d.get("ram") or 0)>=95 or
                                   (d.get("disk") or 0)>=95 for d in devices)
                    has_warn = any(d.get("active_alerts",0)>0 for d in devices)
                    color = CRIT if has_crit else WARN if has_warn else ACCENT
                    self.tray.icon = make_tray_icon(color)
            except:
                pass
        self.root.after(POLL_INTERVAL * 1000, self._poll)

    def _check_alerts(self, alerts):
        if not alerts: return
        aid = alerts[0].get("id")
        if self.last_alert_id is None:
            self.last_alert_id = aid
            return
        if aid != self.last_alert_id:
            self.last_alert_id = aid
            try:
                notification.notify(
                    title=f"SysMon — {alerts[0].get('severity','').upper()}",
                    message=alerts[0].get("message",""),
                    app_name="SysMon", timeout=8)
            except: pass


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    root = tk.Tk()
    app = SysMonApp(root)
    root.mainloop()