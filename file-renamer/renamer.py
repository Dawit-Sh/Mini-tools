"""
Batch File Renamer — cross-platform (Windows / macOS / Linux)
Supports: find & replace, add prefix/suffix, case change, numbering,
          regex, date-stamp, extension change, live preview.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import re
import datetime


DARK   = "#2E2E2E"
DARKER = "#3E3E3E"
GREEN  = "#4CAF50"
ACCENT = "#5E81AC"


class FileRenamer:
    def __init__(self, master):
        self.master = master
        master.title("Batch File Renamer")
        master.geometry("900x640")
        master.configure(bg=DARK)
        master.resizable(True, True)

        self._files: list[str] = []      # original names
        self._folder: str = ""
        self._history: list[dict] = []   # undo stack

        self._setup_style()
        self._build_ui()

    def _setup_style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=DARK, foreground="#FFFFFF")
        s.configure("TLabel", background=DARK, foreground="#FFFFFF")
        s.configure("TEntry", fieldbackground=DARKER, foreground="#FFFFFF")
        s.configure("TButton", background=ACCENT, foreground="#FFFFFF")
        s.map("TButton", background=[("active", "#4C6FA5")])
        s.configure("TCheckbutton", background=DARK, foreground="#FFFFFF")
        s.map("TCheckbutton", background=[("active", DARK)])
        s.configure("TCombobox", fieldbackground=DARKER, foreground="#FFFFFF",
                    selectbackground=DARKER)
        s.configure("Treeview", background=DARKER, foreground="#FFFFFF",
                    fieldbackground=DARKER, rowheight=22)
        s.map("Treeview", background=[("selected", ACCENT)])
        s.configure("Treeview.Heading", background="#4a4a4a", foreground="#FFFFFF")
        s.configure("TFrame", background=DARK)
        s.configure("TLabelframe", background=DARK, foreground="#FFFFFF")
        s.configure("TLabelframe.Label", background=DARK, foreground="#FFFFFF")

    def _build_ui(self):
        frame = ttk.Frame(self.master, padding=10)
        frame.grid(row=0, column=0, sticky="nsew")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(3, weight=1)

        # Folder picker
        ttk.Label(frame, text="Folder:").grid(row=0, column=0, sticky="w", padx=5, pady=4)
        self._folder_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self._folder_var, state="readonly", width=55).grid(
            row=0, column=1, sticky="ew", padx=5)
        ttk.Button(frame, text="Browse", command=self._browse).grid(row=0, column=2, padx=5)

        # Filter
        filter_row = ttk.Frame(frame)
        filter_row.grid(row=1, column=0, columnspan=3, sticky="ew", pady=4)
        ttk.Label(filter_row, text="Filter (glob):").pack(side=tk.LEFT, padx=(5, 4))
        self._filter_var = tk.StringVar(value="*")
        filter_e = ttk.Entry(filter_row, textvariable=self._filter_var, width=16)
        filter_e.pack(side=tk.LEFT)
        filter_e.bind("<Return>", lambda _: self._load_files())
        ttk.Button(filter_row, text="Load", command=self._load_files).pack(side=tk.LEFT, padx=6)
        self._include_sub = tk.BooleanVar(value=False)
        ttk.Checkbutton(filter_row, text="Include subfolders", variable=self._include_sub).pack(side=tk.LEFT)

        # Operations panel
        ops = ttk.LabelFrame(frame, text="Rename Operations", padding=8)
        ops.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=6)
        ops.columnconfigure(1, weight=1)
        ops.columnconfigure(3, weight=1)

        # Find & Replace
        ttk.Label(ops, text="Find:").grid(row=0, column=0, sticky="w", padx=(0, 4), pady=3)
        self._find_var = tk.StringVar()
        ttk.Entry(ops, textvariable=self._find_var, width=22).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Label(ops, text="Replace:").grid(row=0, column=2, sticky="w", padx=(8, 4))
        self._replace_var = tk.StringVar()
        ttk.Entry(ops, textvariable=self._replace_var, width=22).grid(row=0, column=3, sticky="ew", padx=4)
        self._regex_var = tk.BooleanVar()
        ttk.Checkbutton(ops, text="Regex", variable=self._regex_var).grid(row=0, column=4, padx=4)
        self._case_var = tk.BooleanVar()
        ttk.Checkbutton(ops, text="Case-sensitive", variable=self._case_var).grid(row=0, column=5, padx=4)

        # Prefix / Suffix
        ttk.Label(ops, text="Prefix:").grid(row=1, column=0, sticky="w", pady=3)
        self._prefix_var = tk.StringVar()
        ttk.Entry(ops, textvariable=self._prefix_var, width=22).grid(row=1, column=1, sticky="ew", padx=4)
        ttk.Label(ops, text="Suffix:").grid(row=1, column=2, sticky="w", padx=(8, 4))
        self._suffix_var = tk.StringVar()
        ttk.Entry(ops, textvariable=self._suffix_var, width=22).grid(row=1, column=3, sticky="ew", padx=4)

        # Extension / Case / Numbering
        ttk.Label(ops, text="Change ext to:").grid(row=2, column=0, sticky="w", pady=3)
        self._ext_var = tk.StringVar()
        ttk.Entry(ops, textvariable=self._ext_var, width=10).grid(row=2, column=1, sticky="w", padx=4)

        ttk.Label(ops, text="Case:").grid(row=2, column=2, sticky="w", padx=(8, 4))
        self._case_mode = tk.StringVar(value="original")
        ttk.Combobox(ops, textvariable=self._case_mode, width=14, state="readonly",
                     values=["original", "UPPER", "lower", "Title Case", "Sentence case"]
                     ).grid(row=2, column=3, sticky="w", padx=4)

        # Numbering
        num_row = ttk.Frame(ops)
        num_row.grid(row=3, column=0, columnspan=6, sticky="w", pady=3)
        self._num_var = tk.BooleanVar()
        ttk.Checkbutton(num_row, text="Add numbering", variable=self._num_var).pack(side=tk.LEFT)
        ttk.Label(num_row, text="Start:").pack(side=tk.LEFT, padx=(10, 4))
        self._num_start = tk.IntVar(value=1)
        ttk.Spinbox(num_row, from_=0, to=9999, textvariable=self._num_start, width=6).pack(side=tk.LEFT)
        ttk.Label(num_row, text="Padding:").pack(side=tk.LEFT, padx=(8, 4))
        self._num_pad = tk.IntVar(value=2)
        ttk.Spinbox(num_row, from_=1, to=6, textvariable=self._num_pad, width=4).pack(side=tk.LEFT)
        ttk.Label(num_row, text="Position:").pack(side=tk.LEFT, padx=(8, 4))
        self._num_pos = tk.StringVar(value="prefix")
        ttk.Combobox(num_row, textvariable=self._num_pos, values=["prefix", "suffix"],
                     width=8, state="readonly").pack(side=tk.LEFT)

        # Date stamp
        ds_row = ttk.Frame(ops)
        ds_row.grid(row=4, column=0, columnspan=6, sticky="w", pady=3)
        self._date_var = tk.BooleanVar()
        ttk.Checkbutton(ds_row, text="Add date stamp", variable=self._date_var).pack(side=tk.LEFT)
        ttk.Label(ds_row, text="Format:").pack(side=tk.LEFT, padx=(10, 4))
        self._date_fmt = tk.StringVar(value="%Y-%m-%d")
        ttk.Entry(ds_row, textvariable=self._date_fmt, width=14).pack(side=tk.LEFT)
        ttk.Label(ds_row, text="Position:").pack(side=tk.LEFT, padx=(8, 4))
        self._date_pos = tk.StringVar(value="suffix")
        ttk.Combobox(ds_row, textvariable=self._date_pos, values=["prefix", "suffix"],
                     width=8, state="readonly").pack(side=tk.LEFT)

        # Preview button
        ttk.Button(ops, text="Preview Changes", command=self._preview
                   ).grid(row=5, column=0, columnspan=6, pady=(6, 0), sticky="w")

        # File list (before → after)
        self.tree = ttk.Treeview(frame, columns=("Original", "New Name"), show="headings")
        self.tree.heading("Original", text="Original Name")
        self.tree.heading("New Name", text="New Name (preview)")
        self.tree.column("Original", width=380)
        self.tree.column("New Name", width=380)
        self.tree.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=5, pady=4)
        sb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        sb.grid(row=3, column=2, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        frame.rowconfigure(3, weight=1)

        # Action row
        act_row = ttk.Frame(frame)
        act_row.grid(row=4, column=0, columnspan=3, sticky="ew", padx=5, pady=6)
        ttk.Button(act_row, text="Apply Rename", command=self._apply).pack(side=tk.LEFT, padx=4)
        ttk.Button(act_row, text="Undo Last", command=self._undo).pack(side=tk.LEFT, padx=4)
        ttk.Button(act_row, text="Clear", command=self._clear).pack(side=tk.LEFT, padx=4)

        self._status_var = tk.StringVar(value="No folder loaded.")
        ttk.Label(frame, textvariable=self._status_var, foreground="#aaaaaa").grid(
            row=5, column=0, columnspan=3, sticky="w", padx=5)

    # ── file loading ──────────────────────────────────────────────────────────

    def _browse(self):
        d = filedialog.askdirectory(title="Select folder")
        if d:
            self._folder = d
            self._folder_var.set(d)
            self._load_files()

    def _load_files(self):
        if not self._folder or not os.path.isdir(self._folder):
            return
        import fnmatch
        pattern = self._filter_var.get().strip() or "*"
        self._files = []
        if self._include_sub.get():
            for root, _, files in os.walk(self._folder):
                for f in files:
                    if fnmatch.fnmatch(f, pattern):
                        rel = os.path.relpath(os.path.join(root, f), self._folder)
                        self._files.append(rel)
        else:
            self._files = [f for f in os.listdir(self._folder)
                           if os.path.isfile(os.path.join(self._folder, f))
                           and fnmatch.fnmatch(f, pattern)]
        self._files.sort()
        self._show_files()
        self._status_var.set(f"{len(self._files)} files loaded from {self._folder}")

    def _show_files(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for f in self._files:
            self.tree.insert("", "end", values=(f, f))

    # ── preview ───────────────────────────────────────────────────────────────

    def _apply_rules(self, name: str, index: int) -> str:
        stem, ext = os.path.splitext(name)

        # Find & Replace
        find = self._find_var.get()
        if find:
            replace = self._replace_var.get()
            flags = 0 if self._case_var.get() else re.IGNORECASE
            try:
                if self._regex_var.get():
                    stem = re.sub(find, replace, stem, flags=flags)
                else:
                    if self._case_var.get():
                        stem = stem.replace(find, replace)
                    else:
                        stem = re.sub(re.escape(find), replace, stem, flags=flags)
            except re.error as e:
                return f"[regex error: {e}]"

        # Case
        mode = self._case_mode.get()
        if mode == "UPPER":
            stem = stem.upper()
        elif mode == "lower":
            stem = stem.lower()
        elif mode == "Title Case":
            stem = stem.title()
        elif mode == "Sentence case":
            stem = stem.capitalize()

        # Extension change
        new_ext = self._ext_var.get().strip()
        if new_ext:
            ext = ("." if not new_ext.startswith(".") else "") + new_ext

        # Numbering
        if self._num_var.get():
            n = str(self._num_start.get() + index).zfill(self._num_pad.get())
            if self._num_pos.get() == "prefix":
                stem = n + "_" + stem
            else:
                stem = stem + "_" + n

        # Date stamp
        if self._date_var.get():
            try:
                stamp = datetime.datetime.now().strftime(self._date_fmt.get())
            except Exception:
                stamp = ""
            if stamp:
                if self._date_pos.get() == "prefix":
                    stem = stamp + "_" + stem
                else:
                    stem = stem + "_" + stamp

        # Prefix / Suffix
        stem = self._prefix_var.get() + stem + self._suffix_var.get()

        return stem + ext

    def _preview(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for i, f in enumerate(self._files):
            folder = os.path.dirname(f)
            base = os.path.basename(f)
            new_base = self._apply_rules(base, i)
            new_name = os.path.join(folder, new_base) if folder else new_base
            color = "" if new_name == f else "modified"
            self.tree.insert("", "end", values=(f, new_name), tags=(color,))
        self.tree.tag_configure("modified", foreground="#A3BE8C")
        self._status_var.set("Preview ready. Click 'Apply Rename' to commit.")

    # ── apply ─────────────────────────────────────────────────────────────────

    def _apply(self):
        if not self._files:
            messagebox.showwarning("No Files", "Load a folder first.")
            return
        renames = []
        for i, f in enumerate(self._files):
            folder = os.path.dirname(f)
            base = os.path.basename(f)
            new_base = self._apply_rules(base, i)
            new_name = os.path.join(folder, new_base) if folder else new_base
            if new_name != f:
                renames.append((f, new_name))

        if not renames:
            messagebox.showinfo("Nothing Changed", "No files would be renamed with current settings.")
            return

        if not messagebox.askyesno("Confirm", f"Rename {len(renames)} file(s)?"):
            return

        done, errors = [], []
        for old, new in renames:
            src = os.path.join(self._folder, old)
            dst = os.path.join(self._folder, new)
            os.makedirs(os.path.dirname(dst), exist_ok=True) if os.path.dirname(dst) else None
            try:
                if os.path.exists(dst):
                    raise FileExistsError(f"Target already exists: {new}")
                os.rename(src, dst)
                done.append((old, new))
            except Exception as e:
                errors.append(f"{old} → {new}: {e}")

        if done:
            self._history.append({"folder": self._folder, "renames": done})

        self._load_files()
        msg = f"Renamed {len(done)} file(s)."
        if errors:
            msg += f"\n\nErrors ({len(errors)}):\n" + "\n".join(errors)
            messagebox.showwarning("Done with Errors", msg)
        else:
            messagebox.showinfo("Done", msg)
        self._status_var.set(msg.splitlines()[0])

    def _undo(self):
        if not self._history:
            messagebox.showinfo("Nothing to Undo", "No rename history available.")
            return
        last = self._history.pop()
        folder = last["folder"]
        errors = []
        for old, new in reversed(last["renames"]):
            src = os.path.join(folder, new)
            dst = os.path.join(folder, old)
            try:
                os.rename(src, dst)
            except Exception as e:
                errors.append(str(e))
        self._load_files()
        if errors:
            messagebox.showwarning("Undo Errors", "\n".join(errors))
        else:
            messagebox.showinfo("Undone", "Last rename reversed successfully.")

    def _clear(self):
        self._files = []
        self._folder = ""
        self._folder_var.set("")
        for row in self.tree.get_children():
            self.tree.delete(row)
        self._status_var.set("Cleared.")


def main():
    root = tk.Tk()
    FileRenamer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
