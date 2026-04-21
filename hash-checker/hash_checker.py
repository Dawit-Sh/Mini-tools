"""
Hash Checker — cross-platform file integrity verifier
Supports: MD5, SHA-1, SHA-256, SHA-512
Features: single file, batch folder scan, verify against known hash, clipboard paste
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import hashlib
import os
import threading

DARK   = "#2E2E2E"
DARKER = "#3E3E3E"
GREEN  = "#4CAF50"
RED    = "#BF616A"

ALGORITHMS = ["MD5", "SHA-1", "SHA-256", "SHA-512"]
ALG_MAP = {
    "MD5":    hashlib.md5,
    "SHA-1":  hashlib.sha1,
    "SHA-256":hashlib.sha256,
    "SHA-512":hashlib.sha512,
}

CHUNK = 65536


def file_hash(path: str, algorithm: str, progress_cb=None) -> str:
    h = ALG_MAP[algorithm]()
    size = os.path.getsize(path)
    done = 0
    with open(path, "rb") as f:
        while True:
            buf = f.read(CHUNK)
            if not buf:
                break
            h.update(buf)
            done += len(buf)
            if progress_cb and size > 0:
                progress_cb(done / size * 100)
    return h.hexdigest()


class HashChecker:
    def __init__(self, master):
        self.master = master
        master.title("Hash Checker")
        master.geometry("760x560")
        master.configure(bg=DARK)
        master.resizable(True, True)
        self._setup_style()
        self._build_ui()

    def _setup_style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=DARK, foreground="#FFFFFF")
        s.configure("TLabel",   background=DARK, foreground="#FFFFFF")
        s.configure("TEntry",   fieldbackground=DARKER, foreground="#FFFFFF")
        s.configure("TButton",  background="#5E81AC", foreground="#FFFFFF")
        s.map("TButton",        background=[("active", "#4C6FA5")])
        s.configure("TFrame",   background=DARK)
        s.configure("TLabelframe", background=DARK, foreground="#FFFFFF")
        s.configure("TLabelframe.Label", background=DARK, foreground="#FFFFFF")
        s.configure("TCombobox", fieldbackground=DARKER, foreground="#FFFFFF",
                    selectbackground=DARKER)
        s.configure("Treeview", background=DARKER, foreground="#FFFFFF",
                    fieldbackground=DARKER, rowheight=22)
        s.configure("Treeview.Heading", background="#4a4a4a", foreground="#FFFFFF")
        s.map("Treeview", background=[("selected", "#5E81AC")])

    def _build_ui(self):
        frame = ttk.Frame(self.master, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(3, weight=1)

        # Single file section
        sf = ttk.LabelFrame(frame, text="Single File", padding=8)
        sf.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        sf.columnconfigure(1, weight=1)

        ttk.Label(sf, text="File:").grid(row=0, column=0, sticky="w", padx=4)
        self._file_var = tk.StringVar()
        ttk.Entry(sf, textvariable=self._file_var, state="readonly", width=48).grid(
            row=0, column=1, sticky="ew", padx=4)
        ttk.Button(sf, text="Browse", command=self._browse_file).grid(row=0, column=2, padx=4)

        ttk.Label(sf, text="Algorithm:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self._alg_var = tk.StringVar(value="SHA-256")
        ttk.Combobox(sf, textvariable=self._alg_var, values=ALGORITHMS,
                     state="readonly", width=10).grid(row=1, column=1, sticky="w", padx=4)

        ttk.Label(sf, text="Hash:").grid(row=2, column=0, sticky="w", padx=4)
        self._hash_var = tk.StringVar()
        hash_e = ttk.Entry(sf, textvariable=self._hash_var, state="readonly", width=68,
                           font=("Consolas", 10))
        hash_e.grid(row=2, column=1, sticky="ew", padx=4)
        ttk.Button(sf, text="Copy", command=self._copy_hash).grid(row=2, column=2, padx=4)

        btn_row = ttk.Frame(sf)
        btn_row.grid(row=3, column=0, columnspan=3, pady=6, sticky="w")
        ttk.Button(btn_row, text="Compute Hash", command=self._compute_single).pack(side=tk.LEFT, padx=4)

        # Verify section
        vf = ttk.LabelFrame(frame, text="Verify Against Known Hash", padding=8)
        vf.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        vf.columnconfigure(1, weight=1)

        ttk.Label(vf, text="Known hash:").grid(row=0, column=0, sticky="w", padx=4)
        self._known_var = tk.StringVar()
        ttk.Entry(vf, textvariable=self._known_var, width=68,
                  font=("Consolas", 10)).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(vf, text="Paste", command=self._paste_known).grid(row=0, column=2, padx=4)

        self._verify_result = ttk.Label(vf, text="")
        self._verify_result.grid(row=1, column=0, columnspan=3, padx=4, pady=4, sticky="w")
        ttk.Button(vf, text="Verify", command=self._verify).grid(row=1, column=2, padx=4)

        # Progress bar
        self._progress_var = tk.DoubleVar()
        self._pbar = ttk.Progressbar(frame, variable=self._progress_var, maximum=100)
        self._pbar.grid(row=2, column=0, columnspan=3, sticky="ew", pady=4)

        # Batch section
        bf = ttk.LabelFrame(frame, text="Batch Hash — Folder", padding=8)
        bf.grid(row=3, column=0, columnspan=3, sticky="nsew")
        bf.columnconfigure(1, weight=1)
        bf.rowconfigure(1, weight=1)

        batch_top = ttk.Frame(bf)
        batch_top.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        ttk.Label(batch_top, text="Folder:").pack(side=tk.LEFT, padx=(0, 4))
        self._batch_folder_var = tk.StringVar()
        ttk.Entry(batch_top, textvariable=self._batch_folder_var, state="readonly", width=40).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(batch_top, text="Browse", command=self._browse_folder).pack(side=tk.LEFT, padx=4)
        ttk.Button(batch_top, text="Hash All Files",
                   command=self._hash_folder).pack(side=tk.LEFT, padx=4)
        ttk.Button(batch_top, text="Export CSV",
                   command=self._export_csv).pack(side=tk.LEFT, padx=4)

        cols = ("File", "Algorithm", "Hash", "Size")
        self.batch_tree = ttk.Treeview(bf, columns=cols, show="headings")
        self.batch_tree.heading("File",      text="File")
        self.batch_tree.heading("Algorithm", text="Alg")
        self.batch_tree.heading("Hash",      text="Hash")
        self.batch_tree.heading("Size",      text="Size")
        self.batch_tree.column("File",       width=200)
        self.batch_tree.column("Algorithm",  width=60)
        self.batch_tree.column("Hash",       width=340)
        self.batch_tree.column("Size",       width=80)
        self.batch_tree.grid(row=1, column=0, columnspan=2, sticky="nsew")
        bsb = ttk.Scrollbar(bf, orient=tk.VERTICAL, command=self.batch_tree.yview)
        bsb.grid(row=1, column=2, sticky="ns")
        self.batch_tree.configure(yscrollcommand=bsb.set)

        # Status
        self._status_var = tk.StringVar(value="Ready.")
        ttk.Label(frame, textvariable=self._status_var, foreground="#aaaaaa").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))

    # ── single file ───────────────────────────────────────────────────────────

    def _browse_file(self):
        path = filedialog.askopenfilename(title="Select file")
        if path:
            self._file_var.set(path)

    def _compute_single(self):
        path = self._file_var.get()
        if not path or not os.path.isfile(path):
            messagebox.showwarning("No File", "Select a file first.")
            return
        alg = self._alg_var.get()
        self._progress_var.set(0)
        self._hash_var.set("")
        self._status_var.set(f"Computing {alg} hash…")

        def run():
            try:
                h = file_hash(path, alg, lambda p: self.master.after(0, self._progress_var.set, p))
                self.master.after(0, self._hash_var.set, h)
                self.master.after(0, self._status_var.set, f"{alg} hash computed.")
            except Exception as e:
                self.master.after(0, messagebox.showerror, "Error", str(e))
            finally:
                self.master.after(0, self._progress_var.set, 0)

        threading.Thread(target=run, daemon=True).start()

    def _copy_hash(self):
        h = self._hash_var.get()
        if h:
            self.master.clipboard_clear()
            self.master.clipboard_append(h)
            self._status_var.set("Hash copied to clipboard.")

    def _paste_known(self):
        try:
            self._known_var.set(self.master.clipboard_get().strip())
        except tk.TclError:
            pass

    def _verify(self):
        computed = self._hash_var.get().strip().lower()
        known    = self._known_var.get().strip().lower()
        if not computed:
            messagebox.showwarning("No Hash", "Compute the file hash first.")
            return
        if not known:
            messagebox.showwarning("No Known Hash", "Enter the known hash to verify against.")
            return
        if computed == known:
            self._verify_result.config(text="✔  MATCH — File is intact.", foreground=GREEN)
        else:
            self._verify_result.config(text="✘  MISMATCH — File may be corrupted or tampered.", foreground=RED)

    # ── batch ─────────────────────────────────────────────────────────────────

    def _browse_folder(self):
        d = filedialog.askdirectory(title="Select folder")
        if d:
            self._batch_folder_var.set(d)

    def _hash_folder(self):
        folder = self._batch_folder_var.get()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("No Folder", "Select a folder first.")
            return
        alg = self._alg_var.get()
        for row in self.batch_tree.get_children():
            self.batch_tree.delete(row)

        def run():
            files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
            for i, fname in enumerate(sorted(files)):
                path = os.path.join(folder, fname)
                try:
                    h = file_hash(path, alg)
                    size = os.path.getsize(path)
                    size_str = self._fmt_size(size)
                    self.master.after(0, self.batch_tree.insert, "", "end",
                                      values=(fname, alg, h, size_str))
                except Exception as e:
                    self.master.after(0, self.batch_tree.insert, "", "end",
                                      values=(fname, alg, f"ERROR: {e}", ""))
                self.master.after(0, self._status_var.set,
                                  f"Hashing {i + 1}/{len(files)}: {fname}")
            self.master.after(0, self._status_var.set, f"Done. {len(files)} files hashed.")

        threading.Thread(target=run, daemon=True).start()

    def _export_csv(self):
        rows = self.batch_tree.get_children()
        if not rows:
            messagebox.showinfo("Empty", "No batch results to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                             filetypes=[("CSV", "*.csv")])
        if not path:
            return
        import csv
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["File", "Algorithm", "Hash", "Size"])
            for row in rows:
                w.writerow(self.batch_tree.item(row)["values"])
        messagebox.showinfo("Exported", f"Saved to {path}")

    @staticmethod
    def _fmt_size(n: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"


def main():
    root = tk.Tk()
    HashChecker(root)
    root.mainloop()


if __name__ == "__main__":
    main()
