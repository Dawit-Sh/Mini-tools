import os
import tarfile
import time
import hashlib
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import threading
import datetime

class CoRrUptEdFile:
    def __init__(self, master):
        self.master = master
        master.title("CoRrUptEd File")
        master.geometry("560x580")
        master.configure(bg="#2c2c2c")
        master.resizable(True, True)

        self.backup_thread = None
        self.paused = False
        self.running = False
        self._lock = threading.Lock()

        self.setup_custom_style()

        self.source_directory = tk.StringVar()
        self.backup_directory = tk.StringVar()
        self.status = tk.StringVar(value="Stopped")
        self.interval_var = tk.IntVar(value=60)
        self.max_backups_var = tk.IntVar(value=10)

        self.create_widgets()

    def setup_custom_style(self):
        style = ttk.Style()
        style.theme_create("darktheme", parent="alt", settings={
            "TFrame": {"configure": {"background": "#2c2c2c"}},
            "TButton": {
                "configure": {"font": ("Arial", 10), "background": "#4a4a4a", "foreground": "white"},
                "map": {"background": [("active", "#5a5a5a"), ("disabled", "#333333")],
                        "foreground": [("active", "white"), ("disabled", "#888888")]}
            },
            "TLabel": {"configure": {"font": ("Arial", 10), "background": "#2c2c2c", "foreground": "white"}},
            "TEntry": {"configure": {"font": ("Arial", 10), "fieldbackground": "#3c3c3c", "foreground": "white"}},
            "TSpinbox": {"configure": {"fieldbackground": "#3c3c3c", "foreground": "white", "background": "#4a4a4a"}},
            "Horizontal.TProgressbar": {"configure": {"background": "#4CAF50", "troughcolor": "#3c3c3c"}},
        })
        style.theme_use("darktheme")

    def create_widgets(self):
        frame = ttk.Frame(self.master, padding="10")
        frame.grid(row=0, column=0, sticky="nsew")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)

        # Source dir
        ttk.Label(frame, text="Source Directory:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        src_entry = ttk.Entry(frame, textvariable=self.source_directory, width=32)
        src_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(frame, text="Browse", command=self.browse_source_directory).grid(row=0, column=2, padx=5, pady=5)

        # Backup dir
        ttk.Label(frame, text="Backup Directory:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        bak_entry = ttk.Entry(frame, textvariable=self.backup_directory, width=32)
        bak_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(frame, text="Browse", command=self.browse_backup_directory).grid(row=1, column=2, padx=5, pady=5)

        # Options row
        opts = ttk.Frame(frame)
        opts.grid(row=2, column=0, columnspan=3, pady=4, sticky="w")
        ttk.Label(opts, text="Interval (min):").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Spinbox(opts, from_=1, to=1440, textvariable=self.interval_var, width=6).pack(side=tk.LEFT, padx=(0, 16))
        ttk.Label(opts, text="Max backups:").pack(side=tk.LEFT, padx=(0, 4))
        ttk.Spinbox(opts, from_=1, to=100, textvariable=self.max_backups_var, width=6).pack(side=tk.LEFT)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=8)

        self.start_button = ttk.Button(btn_frame, text="Start Backup", command=self.start_backup)
        self.start_button.pack(side=tk.LEFT, padx=4)

        self.pause_button = ttk.Button(btn_frame, text="Pause", command=self.pause_backup, state=tk.DISABLED)
        self.pause_button.pack(side=tk.LEFT, padx=4)

        self.stop_button = ttk.Button(btn_frame, text="Stop", command=self.stop_backup, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=4)

        ttk.Button(btn_frame, text="Backup Now", command=self.backup_now).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Restore", command=self.restore_backup).pack(side=tk.LEFT, padx=4)

        # Status row
        status_row = ttk.Frame(frame)
        status_row.grid(row=4, column=0, columnspan=3, pady=2, sticky="w")
        ttk.Label(status_row, text="Status:").pack(side=tk.LEFT, padx=(0, 6))
        self.status_label = ttk.Label(status_row, textvariable=self.status, foreground="#F44336")
        self.status_label.pack(side=tk.LEFT)

        self.next_label = ttk.Label(frame, text="", foreground="#aaaaaa")
        self.next_label.grid(row=5, column=0, columnspan=3, sticky="w", padx=5)

        # Progress
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(frame, orient="horizontal", length=300,
                                             mode="determinate", variable=self.progress_var)
        self.progress_bar.grid(row=6, column=0, columnspan=3, padx=5, pady=4, sticky="ew")
        self.progress_pct = ttk.Label(frame, text="0%")
        self.progress_pct.grid(row=7, column=0, columnspan=3, sticky="e", padx=8)

        # Log
        log_frame = ttk.Frame(frame)
        log_frame.grid(row=8, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
        frame.rowconfigure(8, weight=1)
        frame.columnconfigure(1, weight=1)

        self.log = tk.Text(log_frame, height=12, bg="#3c3c3c", fg="white",
                           font=("Consolas", 9), wrap=tk.WORD, state=tk.DISABLED)
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log.yview)
        self.log.configure(yscrollcommand=log_scroll.set)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Button(frame, text="Clear Log", command=self.clear_log).grid(row=9, column=2, padx=5, pady=4, sticky="e")

    # ── directory browsing ──────────────────────────────────────────────────

    def browse_source_directory(self):
        d = filedialog.askdirectory(title="Select Source Directory")
        if d:
            self.source_directory.set(d)

    def browse_backup_directory(self):
        d = filedialog.askdirectory(title="Select Backup Directory")
        if d:
            self.backup_directory.set(d)

    # ── controls ────────────────────────────────────────────────────────────

    def start_backup(self):
        if not self._validate_dirs():
            return
        self.running = True
        self.paused = False
        self._set_status("Running", "#4CAF50")
        self.start_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.NORMAL)
        self.backup_thread = threading.Thread(target=self.backup_loop, daemon=True)
        self.backup_thread.start()

    def pause_backup(self):
        if not self.running:
            return
        self.paused = not self.paused
        if self.paused:
            self._set_status("Paused", "#FFC107")
            self.pause_button.config(text="Resume")
        else:
            self._set_status("Running", "#4CAF50")
            self.pause_button.config(text="Pause")

    def stop_backup(self):
        self.running = False
        self.paused = False
        self._set_status("Stopped", "#F44336")
        self.start_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED, text="Pause")
        self.stop_button.config(state=tk.DISABLED)
        self._set_progress(0, 0)
        self.next_label.config(text="")

    def backup_now(self):
        if not self._validate_dirs():
            return
        threading.Thread(target=self.create_snapshot, daemon=True).start()

    # ── backup loop ─────────────────────────────────────────────────────────

    def backup_loop(self):
        while self.running:
            if not self.paused:
                self.create_snapshot()
            interval_sec = self.interval_var.get() * 60
            end_time = time.monotonic() + interval_sec
            while self.running and time.monotonic() < end_time:
                remaining = int(end_time - time.monotonic())
                self.master.after(0, self._update_next_label, remaining)
                time.sleep(min(10, remaining + 1))
        self.master.after(0, self.next_label.config, {"text": ""})

    def _update_next_label(self, remaining_sec):
        if not self.running or self.paused:
            self.next_label.config(text="")
            return
        m, s = divmod(remaining_sec, 60)
        self.next_label.config(text=f"Next backup in: {m:02d}:{s:02d}")

    # ── snapshot creation ────────────────────────────────────────────────────

    def create_snapshot(self):
        source_dir = self.source_directory.get()
        backup_dir = self.backup_directory.get()

        try:
            os.makedirs(backup_dir, exist_ok=True)
            source_dir_name = os.path.basename(os.path.normpath(source_dir))
            timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
            snapshot_name = f"{source_dir_name}_{timestamp}.tar.gz"
            snapshot_path = os.path.join(backup_dir, snapshot_name)

            all_files = []
            for root, _, files in os.walk(source_dir):
                for f in files:
                    all_files.append(os.path.join(root, f))

            total = max(len(all_files), 1)
            self.master.after(0, self._set_progress, 0, total)
            self.log_message(f"Creating snapshot: {snapshot_name} ({total} files)")

            with tarfile.open(snapshot_path, "w:gz") as tar:
                for i, file_path in enumerate(all_files):
                    while self.paused and self.running:
                        time.sleep(0.1)
                    if not self.running:
                        tar.close()
                        if os.path.exists(snapshot_path):
                            os.remove(snapshot_path)
                        return
                    try:
                        arcname = os.path.relpath(file_path, source_dir)
                        tar.add(file_path, arcname=arcname)
                    except (PermissionError, OSError) as e:
                        self.log_message(f"  Skip {file_path}: {e}")
                    self.master.after(0, self._set_progress, i + 1, total)

            if self._is_duplicate(snapshot_path, backup_dir, source_dir_name, snapshot_name):
                os.remove(snapshot_path)
                self.log_message(f"Duplicate — removed {snapshot_name}")
            else:
                size_mb = os.path.getsize(snapshot_path) / (1024 * 1024)
                self.log_message(f"Snapshot saved: {snapshot_name} ({size_mb:.1f} MB)")
                self._enforce_max_backups(backup_dir, source_dir_name)

        except Exception as e:
            self.log_message(f"Error creating snapshot: {e}")
        finally:
            self.master.after(0, self._set_progress, 0, 0)

    # ── duplicate detection ──────────────────────────────────────────────────

    def _is_duplicate(self, new_path, backup_dir, source_name, new_name):
        new_hash = self._file_hash(new_path)
        for fname in os.listdir(backup_dir):
            if fname == new_name or not (fname.startswith(f"{source_name}_") and fname.endswith(".tar.gz")):
                continue
            if self._file_hash(os.path.join(backup_dir, fname)) == new_hash:
                return True
        return False

    def _file_hash(self, path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    # ── retention ────────────────────────────────────────────────────────────

    def _enforce_max_backups(self, backup_dir, source_name):
        max_b = self.max_backups_var.get()
        snapshots = sorted([
            os.path.join(backup_dir, f)
            for f in os.listdir(backup_dir)
            if f.startswith(f"{source_name}_") and f.endswith(".tar.gz")
        ], key=os.path.getmtime)
        while len(snapshots) > max_b:
            oldest = snapshots.pop(0)
            os.remove(oldest)
            self.log_message(f"Removed old backup: {os.path.basename(oldest)}")

    # ── restore ───────────────────────────────────────────────────────────────

    def restore_backup(self):
        backup_file = filedialog.askopenfilename(
            initialdir=self.backup_directory.get() or os.path.expanduser("~"),
            title="Select backup to restore",
            filetypes=[("Tar GZ archives", "*.tar.gz"), ("All files", "*.*")]
        )
        if not backup_file:
            return
        restore_dir = filedialog.askdirectory(title="Select restore destination")
        if not restore_dir:
            return

        msg = (f"Restoring will extract files into:\n{restore_dir}\n\n"
               f"Existing files with the same name will be overwritten.\nContinue?")
        if not messagebox.askyesno("Confirm Restore", msg):
            return

        self._set_status("Restoring", "#2196F3")
        threading.Thread(target=self._perform_restore, args=(backup_file, restore_dir), daemon=True).start()

    def _perform_restore(self, backup_file, restore_dir):
        try:
            with tarfile.open(backup_file, "r:gz") as tar:
                members = tar.getmembers()
                total = max(len(members), 1)
                self.master.after(0, self._set_progress, 0, total)
                for i, member in enumerate(members):
                    while self.paused and self.running:
                        time.sleep(0.1)
                    tar.extract(member, path=restore_dir)
                    self.master.after(0, self._set_progress, i + 1, total)
            self.log_message(f"Restored to: {restore_dir}")
        except Exception as e:
            self.log_message(f"Restore error: {e}")
        finally:
            self.master.after(0, self._set_progress, 0, 0)
            self.master.after(0, self._set_status, "Stopped", "#F44336")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _validate_dirs(self):
        src = self.source_directory.get().strip()
        bak = self.backup_directory.get().strip()
        if not src or not bak:
            messagebox.showwarning("Missing Directories", "Please select both source and backup directories.")
            return False
        if not os.path.isdir(src):
            messagebox.showerror("Invalid Source", f"Source directory does not exist:\n{src}")
            return False
        real_src = os.path.realpath(src)
        real_bak = os.path.realpath(bak)
        if real_bak.startswith(real_src + os.sep) or real_bak == real_src:
            messagebox.showerror("Invalid Directories", "Backup directory cannot be inside the source directory.")
            return False
        return True

    def _set_status(self, text, color):
        self.status.set(text)
        self.status_label.config(foreground=color)

    def _set_progress(self, value, maximum):
        if maximum > 0:
            self.progress_bar.config(maximum=maximum)
            self.progress_var.set(value)
            pct = int(value / maximum * 100)
            self.progress_pct.config(text=f"{pct}%")
        else:
            self.progress_bar.config(maximum=100)
            self.progress_var.set(0)
            self.progress_pct.config(text="0%")

    def log_message(self, message):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.master.after(0, self._append_log, f"[{ts}] {message}\n")

    def _append_log(self, text):
        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, text)
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)

    def clear_log(self):
        self.log.config(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.config(state=tk.DISABLED)


if __name__ == "__main__":
    root = tk.Tk()
    app = CoRrUptEdFile(root)
    root.mainloop()
