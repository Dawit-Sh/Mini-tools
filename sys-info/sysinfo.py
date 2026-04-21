"""
System Info — cross-platform system monitor (Windows / macOS / Linux)
Requires: psutil  (pip install psutil)
Shows: CPU, memory, disk, network, processes — with live refresh.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import os
import platform
import datetime

try:
    import psutil
    PSUTIL_OK = True
except ImportError:
    PSUTIL_OK = False

DARK   = "#2E2E2E"
DARKER = "#3E3E3E"
ACCENT = "#5E81AC"
GREEN  = "#A3BE8C"
YELLOW = "#EBCB8B"
RED    = "#BF616A"


def _fmt_bytes(n: int, suffix="B") -> str:
    for unit in ("", "K", "M", "G", "T"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}{suffix}"
        n /= 1024.0
    return f"{n:.1f} P{suffix}"


def _color_pct(pct: float) -> str:
    if pct >= 85:
        return RED
    if pct >= 60:
        return YELLOW
    return GREEN


class SysInfoApp:
    def __init__(self, master):
        self.master = master
        master.title("System Info")
        master.geometry("820x680")
        master.configure(bg=DARK)
        master.resizable(True, True)

        self._refresh_interval = tk.IntVar(value=3)
        self._running = True
        self._prev_net = None
        self._prev_net_time = None

        self._setup_style()
        self._build_ui()

        if not PSUTIL_OK:
            messagebox.showwarning(
                "Missing Dependency",
                "psutil is not installed.\nRun: pip install psutil\n\n"
                "Static info will still be shown.")

        self._refresh_once()
        self._schedule_refresh()
        master.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=DARK, foreground="#FFFFFF")
        s.configure("TLabel",   background=DARK, foreground="#FFFFFF")
        s.configure("TFrame",   background=DARK)
        s.configure("TLabelframe", background=DARK, foreground="#FFFFFF")
        s.configure("TLabelframe.Label", background=DARK, foreground="#FFFFFF")
        s.configure("TButton",  background=ACCENT, foreground="#FFFFFF")
        s.map("TButton",        background=[("active", "#4C6FA5")])
        s.configure("TNotebook", background=DARK)
        s.configure("TNotebook.Tab", background="#3a3a3a", foreground="#FFFFFF", padding=(10, 4))
        s.map("TNotebook.Tab",  background=[("selected", ACCENT)])
        s.configure("Treeview", background=DARKER, foreground="#FFFFFF",
                    fieldbackground=DARKER, rowheight=22)
        s.configure("Treeview.Heading", background="#4a4a4a", foreground="#FFFFFF")
        s.map("Treeview",       background=[("selected", ACCENT)])
        s.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=DARKER)

    def _build_ui(self):
        top = ttk.Frame(self.master, padding=(10, 6))
        top.pack(fill=tk.X)

        ttk.Label(top, text="Auto-refresh (s):").pack(side=tk.LEFT)
        ttk.Spinbox(top, from_=1, to=60, textvariable=self._refresh_interval,
                    width=5).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Refresh Now", command=self._refresh_once).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Export TXT", command=self._export_txt).pack(side=tk.LEFT, padx=6)

        self._hostname_lbl = ttk.Label(top, text="", foreground="#88C0D0")
        self._hostname_lbl.pack(side=tk.RIGHT, padx=10)

        self._notebook = ttk.Notebook(self.master)
        self._notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        self._notebook.add(self._build_overview_tab(), text="Overview")
        self._notebook.add(self._build_cpu_tab(),      text="CPU")
        self._notebook.add(self._build_memory_tab(),   text="Memory")
        self._notebook.add(self._build_disk_tab(),     text="Disks")
        self._notebook.add(self._build_network_tab(),  text="Network")
        self._notebook.add(self._build_process_tab(),  text="Processes")

    # ── tabs ──────────────────────────────────────────────────────────────────

    def _build_overview_tab(self):
        f = ttk.Frame(self._notebook, padding=12)
        self._ov_labels = {}
        fields = [
            ("OS",          "os"),
            ("Hostname",    "hostname"),
            ("Architecture","arch"),
            ("Python",      "python"),
            ("Boot Time",   "boot"),
            ("Uptime",      "uptime"),
            ("CPU",         "cpu_name"),
            ("CPU Cores",   "cpu_cores"),
            ("Total RAM",   "ram_total"),
            ("IP Address",  "ip"),
        ]
        for i, (label, key) in enumerate(fields):
            ttk.Label(f, text=label + ":", font=("Arial", 10, "bold")).grid(
                row=i, column=0, sticky="w", padx=(0, 16), pady=3)
            lbl = ttk.Label(f, text="…", foreground="#ECEFF4")
            lbl.grid(row=i, column=1, sticky="w")
            self._ov_labels[key] = lbl
        return f

    def _build_cpu_tab(self):
        f = ttk.Frame(self._notebook, padding=12)
        f.columnconfigure(0, weight=1)

        self._cpu_usage_lbl = ttk.Label(f, text="CPU Usage: —", font=("Arial", 12, "bold"))
        self._cpu_usage_lbl.grid(row=0, column=0, sticky="w", pady=(0, 6))

        self._cpu_bar = ttk.Progressbar(f, maximum=100, length=400)
        self._cpu_bar.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        ttk.Label(f, text="Per-core usage:", font=("Arial", 10)).grid(row=2, column=0, sticky="w")
        self._core_frame = ttk.Frame(f)
        self._core_frame.grid(row=3, column=0, sticky="ew")
        self._core_bars: list[tuple] = []

        ttk.Label(f, text="Frequency:", font=("Arial", 10)).grid(row=4, column=0, sticky="w", pady=(10, 0))
        self._cpu_freq_lbl = ttk.Label(f, text="—")
        self._cpu_freq_lbl.grid(row=5, column=0, sticky="w")

        ttk.Label(f, text="Load Average (1/5/15 min):", font=("Arial", 10)).grid(row=6, column=0, sticky="w", pady=(8, 0))
        self._load_lbl = ttk.Label(f, text="—")
        self._load_lbl.grid(row=7, column=0, sticky="w")
        return f

    def _build_memory_tab(self):
        f = ttk.Frame(self._notebook, padding=12)
        f.columnconfigure(0, weight=1)

        for i, (label, key) in enumerate([
            ("Total RAM",   "ram_total"),
            ("Used RAM",    "ram_used"),
            ("Available",   "ram_avail"),
            ("Usage %",     "ram_pct"),
            ("Swap Total",  "swap_total"),
            ("Swap Used",   "swap_used"),
            ("Swap %",      "swap_pct"),
        ]):
            ttk.Label(f, text=label + ":", font=("Arial", 10, "bold")).grid(
                row=i, column=0, sticky="w", padx=(0, 16), pady=3)
            lbl = ttk.Label(f, text="—")
            lbl.grid(row=i, column=1, sticky="w")
            setattr(self, f"_mem_{key}", lbl)

        self._ram_bar = ttk.Progressbar(f, maximum=100, length=400)
        self._ram_bar.grid(row=7, column=0, columnspan=2, sticky="ew", pady=8)
        return f

    def _build_disk_tab(self):
        f = ttk.Frame(self._notebook, padding=12)
        f.rowconfigure(0, weight=1)
        f.columnconfigure(0, weight=1)

        cols = ("Mount", "Device", "FS", "Total", "Used", "Free", "Usage %")
        self._disk_tree = ttk.Treeview(f, columns=cols, show="headings")
        widths = [120, 140, 60, 90, 90, 90, 70]
        for col, w in zip(cols, widths):
            self._disk_tree.heading(col, text=col)
            self._disk_tree.column(col, width=w)
        self._disk_tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(f, orient=tk.VERTICAL, command=self._disk_tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self._disk_tree.configure(yscrollcommand=sb.set)
        return f

    def _build_network_tab(self):
        f = ttk.Frame(self._notebook, padding=12)
        f.rowconfigure(1, weight=1)
        f.columnconfigure(0, weight=1)

        stats_f = ttk.LabelFrame(f, text="Live Stats", padding=6)
        stats_f.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self._net_sent_lbl  = ttk.Label(stats_f, text="Sent/s: —")
        self._net_recv_lbl  = ttk.Label(stats_f, text="Recv/s: —")
        self._net_sent_lbl.pack(side=tk.LEFT, padx=16)
        self._net_recv_lbl.pack(side=tk.LEFT, padx=16)

        cols = ("Interface", "IP", "MAC", "Speed", "Bytes Sent", "Bytes Recv")
        self._net_tree = ttk.Treeview(f, columns=cols, show="headings")
        widths = [130, 140, 150, 80, 110, 110]
        for col, w in zip(cols, widths):
            self._net_tree.heading(col, text=col)
            self._net_tree.column(col, width=w)
        self._net_tree.grid(row=1, column=0, sticky="nsew")
        sb = ttk.Scrollbar(f, orient=tk.VERTICAL, command=self._net_tree.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self._net_tree.configure(yscrollcommand=sb.set)
        return f

    def _build_process_tab(self):
        f = ttk.Frame(self._notebook, padding=12)
        f.rowconfigure(1, weight=1)
        f.columnconfigure(0, weight=1)

        top_row = ttk.Frame(f)
        top_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(top_row, text="Search:").pack(side=tk.LEFT, padx=(0, 4))
        self._proc_search = tk.StringVar()
        self._proc_search.trace_add("write", lambda *_: self._filter_processes())
        ttk.Entry(top_row, textvariable=self._proc_search, width=24).pack(side=tk.LEFT)
        ttk.Label(top_row, text="Sort by:").pack(side=tk.LEFT, padx=(12, 4))
        self._proc_sort = tk.StringVar(value="CPU %")
        ttk.Combobox(top_row, textvariable=self._proc_sort, width=12, state="readonly",
                     values=["CPU %", "Memory %", "PID", "Name"]).pack(side=tk.LEFT)
        self._proc_sort.trace_add("write", lambda *_: self._filter_processes())
        ttk.Button(top_row, text="Refresh", command=self._refresh_once).pack(side=tk.LEFT, padx=8)

        cols = ("PID", "Name", "CPU %", "Memory %", "Status", "User")
        self._proc_tree = ttk.Treeview(f, columns=cols, show="headings")
        widths = [60, 200, 70, 80, 80, 110]
        for col, w in zip(cols, widths):
            self._proc_tree.heading(col, text=col,
                                    command=lambda c=col: self._sort_proc_tree(c))
            self._proc_tree.column(col, width=w)
        self._proc_tree.grid(row=1, column=0, sticky="nsew")
        sb = ttk.Scrollbar(f, orient=tk.VERTICAL, command=self._proc_tree.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self._proc_tree.configure(yscrollcommand=sb.set)
        self._proc_data: list[tuple] = []
        return f

    # ── refresh ───────────────────────────────────────────────────────────────

    def _schedule_refresh(self):
        if not self._running:
            return
        interval = max(1, self._refresh_interval.get()) * 1000
        self.master.after(interval, self._auto_refresh)

    def _auto_refresh(self):
        if not self._running:
            return
        self._refresh_once()
        self._schedule_refresh()

    def _refresh_once(self):
        threading.Thread(target=self._gather_data, daemon=True).start()

    def _gather_data(self):
        data = {}
        info = platform.uname()
        data["os"]        = f"{info.system} {info.release} ({info.version[:40]})"
        data["hostname"]  = info.node
        data["arch"]      = info.machine
        data["python"]    = platform.python_version()

        if PSUTIL_OK:
            boot_ts = psutil.boot_time()
            boot_dt = datetime.datetime.fromtimestamp(boot_ts)
            uptime  = datetime.datetime.now() - boot_dt
            data["boot"]   = boot_dt.strftime("%Y-%m-%d %H:%M:%S")
            data["uptime"] = str(uptime).split(".")[0]

            # CPU
            cpu_pct   = psutil.cpu_percent(interval=0.3)
            core_pcts = psutil.cpu_percent(interval=0, percpu=True)
            cpu_freq  = psutil.cpu_freq()
            data["cpu_pct"]   = cpu_pct
            data["core_pcts"] = core_pcts
            data["cpu_freq"]  = cpu_freq
            data["cpu_cores"] = f"{psutil.cpu_count(logical=False)} physical / {psutil.cpu_count()} logical"
            try:
                data["cpu_name"] = platform.processor() or "N/A"
            except Exception:
                data["cpu_name"] = "N/A"

            try:
                data["load_avg"] = os.getloadavg()
            except (AttributeError, OSError):
                data["load_avg"] = None

            # Memory
            vm = psutil.virtual_memory()
            sm = psutil.swap_memory()
            data["vm"]    = vm
            data["sm"]    = sm
            data["ram_total"] = _fmt_bytes(vm.total)

            # Disks
            disks = []
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    disks.append((part.mountpoint, part.device, part.fstype,
                                  _fmt_bytes(usage.total), _fmt_bytes(usage.used),
                                  _fmt_bytes(usage.free), f"{usage.percent}%"))
                except PermissionError:
                    pass
            data["disks"] = disks

            # Network
            net_io  = psutil.net_io_counters(pernic=True)
            net_if  = psutil.net_if_addrs()
            net_stats = psutil.net_if_stats()
            ifaces = []
            for name, addrs in net_if.items():
                ip = mac = speed = "—"
                for a in addrs:
                    import socket
                    if a.family == socket.AF_INET:
                        ip = a.address
                    elif a.family.name in ("AF_PACKET", "AF_LINK"):
                        mac = a.address
                st = net_stats.get(name)
                if st:
                    speed = f"{st.speed} Mbps" if st.speed else "—"
                io = net_io.get(name)
                sent = _fmt_bytes(io.bytes_sent) if io else "—"
                recv = _fmt_bytes(io.bytes_recv) if io else "—"
                ifaces.append((name, ip, mac, speed, sent, recv))
            data["ifaces"] = ifaces

            # Net speed
            now = time.monotonic()
            totals = psutil.net_io_counters()
            if self._prev_net and self._prev_net_time:
                dt = now - self._prev_net_time
                if dt > 0:
                    sent_s = (totals.bytes_sent - self._prev_net.bytes_sent) / dt
                    recv_s = (totals.bytes_recv - self._prev_net.bytes_recv) / dt
                    data["net_sent_s"] = _fmt_bytes(int(sent_s)) + "/s"
                    data["net_recv_s"] = _fmt_bytes(int(recv_s)) + "/s"
            self._prev_net = totals
            self._prev_net_time = now

            # Processes (top 100)
            procs = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent",
                                           "status", "username"]):
                try:
                    i = p.info
                    procs.append((i["pid"], i["name"] or "", round(i["cpu_percent"] or 0, 1),
                                  round(i["memory_percent"] or 0, 2),
                                  i["status"] or "", i["username"] or ""))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            data["procs"] = procs

            # IP
            for name, addrs in net_if.items():
                import socket as _sock
                for a in addrs:
                    if a.family == _sock.AF_INET and not a.address.startswith("127."):
                        data["ip"] = a.address
                        break
                if "ip" in data:
                    break
            data.setdefault("ip", "127.0.0.1")

        self.master.after(0, self._apply_data, data)

    def _apply_data(self, data):
        # Overview
        lbl = self._ov_labels
        lbl["os"].config(text=data.get("os", "—"))
        lbl["hostname"].config(text=data.get("hostname", "—"))
        self._hostname_lbl.config(text=data.get("hostname", ""))
        lbl["arch"].config(text=data.get("arch", "—"))
        lbl["python"].config(text=data.get("python", "—"))
        lbl["boot"].config(text=data.get("boot", "—"))
        lbl["uptime"].config(text=data.get("uptime", "—"))
        lbl["cpu_name"].config(text=data.get("cpu_name", "—"))
        lbl["cpu_cores"].config(text=data.get("cpu_cores", "—"))
        lbl["ram_total"].config(text=data.get("ram_total", "—"))
        lbl["ip"].config(text=data.get("ip", "—"))

        if not PSUTIL_OK:
            return

        # CPU
        cpu_pct = data.get("cpu_pct", 0)
        self._cpu_usage_lbl.config(text=f"CPU Usage: {cpu_pct:.1f}%",
                                    foreground=_color_pct(cpu_pct))
        self._cpu_bar["value"] = cpu_pct

        core_pcts = data.get("core_pcts", [])
        for w in self._core_frame.winfo_children():
            w.destroy()
        self._core_bars.clear()
        for i, pct in enumerate(core_pcts):
            ttk.Label(self._core_frame, text=f"Core {i}:", width=8).grid(
                row=i, column=0, sticky="w", padx=(0, 4))
            bar = ttk.Progressbar(self._core_frame, maximum=100, length=260, value=pct)
            bar.grid(row=i, column=1, sticky="ew", pady=1)
            ttk.Label(self._core_frame, text=f"{pct:.0f}%", width=5,
                      foreground=_color_pct(pct)).grid(row=i, column=2)

        freq = data.get("cpu_freq")
        if freq:
            self._cpu_freq_lbl.config(text=f"{freq.current:.0f} MHz "
                                           f"(min {freq.min:.0f}, max {freq.max:.0f})")

        load = data.get("load_avg")
        self._load_lbl.config(text=f"{load[0]:.2f} / {load[1]:.2f} / {load[2]:.2f}"
                               if load else "N/A (Windows)")

        # Memory
        vm = data.get("vm")
        sm = data.get("sm")
        if vm:
            vals = {
                "ram_total": _fmt_bytes(vm.total),
                "ram_used":  _fmt_bytes(vm.used),
                "ram_avail": _fmt_bytes(vm.available),
                "ram_pct":   f"{vm.percent}%",
                "swap_total":_fmt_bytes(sm.total) if sm else "—",
                "swap_used": _fmt_bytes(sm.used)  if sm else "—",
                "swap_pct":  f"{sm.percent}%"     if sm else "—",
            }
            for k, v in vals.items():
                getattr(self, f"_mem_{k}").config(text=v)
            self._ram_bar["value"] = vm.percent

        # Disks
        for row in self._disk_tree.get_children():
            self._disk_tree.delete(row)
        for disk in data.get("disks", []):
            self._disk_tree.insert("", "end", values=disk)

        # Network
        for row in self._net_tree.get_children():
            self._net_tree.delete(row)
        for iface in data.get("ifaces", []):
            self._net_tree.insert("", "end", values=iface)
        self._net_sent_lbl.config(text=f"Sent/s: {data.get('net_sent_s', '—')}")
        self._net_recv_lbl.config(text=f"Recv/s: {data.get('net_recv_s', '—')}")

        # Processes
        self._proc_data = data.get("procs", [])
        self._filter_processes()

    def _filter_processes(self):
        q = self._proc_search.get().lower()
        sort_key = self._proc_sort.get()
        sort_map = {"CPU %": 2, "Memory %": 3, "PID": 0, "Name": 1}
        idx = sort_map.get(sort_key, 2)
        reverse = sort_key in ("CPU %", "Memory %")

        filtered = [p for p in self._proc_data if not q or q in p[1].lower()]
        filtered.sort(key=lambda p: p[idx] if isinstance(p[idx], (int, float)) else str(p[idx]).lower(),
                      reverse=reverse)

        for row in self._proc_tree.get_children():
            self._proc_tree.delete(row)
        for p in filtered[:200]:
            self._proc_tree.insert("", "end", values=p)

    def _sort_proc_tree(self, col):
        self._proc_sort.set(col if col in ("CPU %", "Memory %", "PID", "Name") else "CPU %")

    # ── export ────────────────────────────────────────────────────────────────

    def _export_txt(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                             filetypes=[("Text", "*.txt")])
        if not path:
            return
        lines = [f"System Info — {datetime.datetime.now()}", "=" * 60]
        for key, lbl in self._ov_labels.items():
            lines.append(f"{key:15}: {lbl.cget('text')}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        messagebox.showinfo("Exported", f"Saved to {path}")

    def _on_close(self):
        self._running = False
        self.master.destroy()


def main():
    root = tk.Tk()
    SysInfoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
