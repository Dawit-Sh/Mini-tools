import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import re
import webbrowser

DARK = "#2E2E2E"
DARKER = "#3E3E3E"
GREEN = "#4CAF50"
GREEN_HOV = "#45A049"


class Reference:
    def __init__(self, title, author, year, link="", tags="", notes=""):
        self.title = title
        self.author = author
        self.year = str(year)
        self.link = link
        self.tags = tags
        self.notes = notes

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: d.get(k, "") for k in ("title", "author", "year", "link", "tags", "notes")})

    def display(self):
        base = f"{self.author} ({self.year}). {self.title}."
        if self.link:
            base += f"  [{self.link}]"
        if self.tags:
            base += f"  #{self.tags}"
        return base

    def apa(self):
        return f"{self.author} ({self.year}). {self.title}." + (f" Retrieved from {self.link}" if self.link else "")

    def bibtex(self):
        key = re.sub(r"\W", "", self.author.split()[0] if self.author else "ref") + self.year
        return (f"@article{{{key},\n"
                f"  author = {{{self.author}}},\n"
                f"  title  = {{{self.title}}},\n"
                f"  year   = {{{self.year}}},\n"
                + (f"  url    = {{{self.link}}},\n" if self.link else "") +
                f"}}")


class _RefDialog(tk.Toplevel):
    def __init__(self, parent, title="Reference", ref: Reference = None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.configure(bg=DARK)
        self.result = None

        fields = [
            ("Title *",   "title",  False),
            ("Author *",  "author", False),
            ("Year *",    "year",   False),
            ("Link",      "link",   False),
            ("Tags",      "tags",   False),
        ]
        self._vars = {}
        for i, (label, key, _secret) in enumerate(fields):
            ttk.Label(self, text=label, background=DARK, foreground="#FFFFFF").grid(
                row=i, column=0, padx=14, pady=5, sticky="w")
            v = tk.StringVar(value=getattr(ref, key, "") if ref else "")
            self._vars[key] = v
            e = ttk.Entry(self, textvariable=v, width=42)
            e.grid(row=i, column=1, padx=14, pady=5, sticky="ew")
            if i == 0:
                e.focus_set()

        # Notes (multiline)
        ttk.Label(self, text="Notes", background=DARK, foreground="#FFFFFF").grid(
            row=len(fields), column=0, padx=14, pady=5, sticky="nw")
        self._notes = tk.Text(self, height=4, width=42, bg=DARKER, fg="#FFFFFF",
                              insertbackground="white", font=("Arial", 10))
        self._notes.grid(row=len(fields), column=1, padx=14, pady=5, sticky="ew")
        if ref and ref.notes:
            self._notes.insert("1.0", ref.notes)

        bf = ttk.Frame(self)
        bf.grid(row=len(fields) + 1, column=0, columnspan=2, pady=10)
        ttk.Button(bf, text="Save", command=self._ok, width=10).pack(side=tk.LEFT, padx=6)
        ttk.Button(bf, text="Cancel", command=self.destroy, width=10).pack(side=tk.LEFT, padx=6)

        self.wait_window()

    def _ok(self):
        title = self._vars["title"].get().strip()
        author = self._vars["author"].get().strip()
        year = self._vars["year"].get().strip()
        if not title or not author or not year:
            messagebox.showwarning("Incomplete", "Title, Author and Year are required.", parent=self)
            return
        if not re.fullmatch(r"\d{1,4}", year):
            messagebox.showwarning("Invalid Year", "Year must be a number.", parent=self)
            return
        self.result = Reference(
            title=title,
            author=author,
            year=year,
            link=self._vars["link"].get().strip(),
            tags=self._vars["tags"].get().strip(),
            notes=self._notes.get("1.0", tk.END).strip(),
        )
        self.destroy()


class ReferenceManagerApp:
    def __init__(self, master):
        self.master = master
        master.title("Reference Manager")
        master.geometry("800x560")
        master.configure(bg=DARK)
        master.resizable(True, True)

        self.references: list[Reference] = []
        self._sort_col = "author"
        self._sort_rev = False

        self._setup_style()
        self._build_ui()

    def _setup_style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=DARK, foreground="#FFFFFF")
        s.configure("TLabel", background=DARK, foreground="#FFFFFF")
        s.configure("TEntry", fieldbackground=DARKER, foreground="#FFFFFF")
        s.configure("TButton", background=GREEN, foreground="#FFFFFF")
        s.map("TButton", background=[("active", GREEN_HOV)])
        s.configure("Treeview", background=DARKER, foreground="#FFFFFF",
                    fieldbackground=DARKER, rowheight=24)
        s.map("Treeview", background=[("selected", GREEN)])
        s.configure("Treeview.Heading", background="#4a4a4a", foreground="#FFFFFF")

    def _build_ui(self):
        frame = ttk.Frame(self.master, padding="12")
        frame.grid(row=0, column=0, sticky="nsew")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        # Search bar
        search_row = ttk.Frame(frame)
        search_row.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Label(search_row, text="Search:").pack(side=tk.LEFT, padx=(0, 6))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._refresh())
        ttk.Entry(search_row, textvariable=self._search_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Treeview
        cols = ("Title", "Author", "Year", "Tags")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        col_widths = {"Title": 320, "Author": 180, "Year": 60, "Tags": 120}
        for col in cols:
            self.tree.heading(col, text=col, command=lambda c=col: self._sort(c))
            self.tree.column(col, width=col_widths[col])
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<Double-1>", lambda _: self.edit_reference())
        self.tree.bind("<Return>", lambda _: self.edit_reference())

        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        vsb.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)

        # Buttons row
        btn_row = ttk.Frame(frame)
        btn_row.grid(row=2, column=0, columnspan=2, pady=(8, 0), sticky="w")
        for text, cmd in [
            ("Add",      self.add_reference),
            ("Edit",     self.edit_reference),
            ("Delete",   self.delete_reference),
            ("Open URL", self.open_url),
            ("Export",   self.export_dialog),
            ("Import",   self.import_references),
        ]:
            ttk.Button(btn_row, text=text, command=cmd).pack(side=tk.LEFT, padx=4)

        # Status
        self._status_var = tk.StringVar(value="0 references")
        ttk.Label(frame, textvariable=self._status_var, foreground="#aaaaaa").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))

    # ── data ops ──────────────────────────────────────────────────────────────

    def add_reference(self):
        dlg = _RefDialog(self.master, title="Add Reference")
        if dlg.result:
            self.references.append(dlg.result)
            self._refresh()

    def edit_reference(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        dlg = _RefDialog(self.master, title="Edit Reference", ref=self.references[idx])
        if dlg.result:
            self.references[idx] = dlg.result
            self._refresh()

    def delete_reference(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select a reference to delete.")
            return
        idx = int(sel[0])
        ref = self.references[idx]
        if messagebox.askyesno("Confirm Delete", f"Delete reference:\n{ref.title}?"):
            self.references.pop(idx)
            self._refresh()

    def open_url(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        ref = self.references[idx]
        if ref.link:
            webbrowser.open(ref.link)
        else:
            messagebox.showinfo("No Link", "This reference has no URL.")

    # ── display ───────────────────────────────────────────────────────────────

    def _refresh(self):
        q = self._search_var.get().lower()
        for item in self.tree.get_children():
            self.tree.delete(item)

        visible = [
            (i, r) for i, r in enumerate(self.references)
            if q in r.title.lower() or q in r.author.lower()
            or q in r.year or q in r.tags.lower()
        ]

        key_map = {"Title": "title", "Author": "author", "Year": "year", "Tags": "tags"}
        col_key = key_map.get(self._sort_col, "author")
        visible.sort(key=lambda x: getattr(x[1], col_key, "").lower(), reverse=self._sort_rev)

        for i, ref in visible:
            self.tree.insert("", "end", iid=str(i),
                             values=(ref.title, ref.author, ref.year, ref.tags))

        count = len(self.references)
        shown = len(visible)
        self._status_var.set(f"{shown} of {count} reference{'s' if count != 1 else ''}")

    def _sort(self, col):
        if self._sort_col == col:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col
            self._sort_rev = False
        self._refresh()

    # ── import / export ───────────────────────────────────────────────────────

    def export_dialog(self):
        if not self.references:
            messagebox.showinfo("Empty", "No references to export.")
            return
        fmt = _PickDialog(self.master, "Export Format", ["JSON", "BibTeX", "APA Text"])
        if fmt.result == "JSON":
            path = filedialog.asksaveasfilename(defaultextension=".json",
                                                filetypes=[("JSON", "*.json")])
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump([r.to_dict() for r in self.references], f, indent=2)
                messagebox.showinfo("Exported", f"Saved {len(self.references)} references to {path}")
        elif fmt.result == "BibTeX":
            path = filedialog.asksaveasfilename(defaultextension=".bib",
                                                filetypes=[("BibTeX", "*.bib")])
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n\n".join(r.bibtex() for r in self.references))
                messagebox.showinfo("Exported", f"Exported to {path}")
        elif fmt.result == "APA Text":
            path = filedialog.asksaveasfilename(defaultextension=".txt",
                                                filetypes=[("Text", "*.txt")])
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(r.apa() for r in self.references))
                messagebox.showinfo("Exported", f"Exported to {path}")

    def import_references(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            added = 0
            for d in data:
                self.references.append(Reference.from_dict(d))
                added += 1
            self._refresh()
            messagebox.showinfo("Imported", f"Added {added} references.")
        except Exception as e:
            messagebox.showerror("Import Error", str(e))


class _PickDialog(tk.Toplevel):
    def __init__(self, parent, title, options):
        super().__init__(parent)
        self.title(title)
        self.grab_set()
        self.configure(bg=DARK)
        self.resizable(False, False)
        self.result = None
        for opt in options:
            ttk.Button(self, text=opt, width=18,
                       command=lambda o=opt: self._pick(o)).pack(padx=20, pady=6)
        self.wait_window()

    def _pick(self, v):
        self.result = v
        self.destroy()


def main():
    root = tk.Tk()
    ReferenceManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
