import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import secrets
import string
import hashlib
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "passwords.db")
SALT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "salt.bin")


def derive_key(master_password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480000)
    return base64.urlsafe_b64encode(kdf.derive(master_password.encode()))


def load_or_create_salt() -> bytes:
    if os.path.exists(SALT_FILE):
        with open(SALT_FILE, "rb") as f:
            return f.read()
    salt = os.urandom(32)
    with open(SALT_FILE, "wb") as f:
        f.write(salt)
    return salt


class MasterPasswordDialog(tk.Toplevel):
    def __init__(self, parent, is_new: bool):
        super().__init__(parent)
        self.title("Master Password")
        self.resizable(False, False)
        self.grab_set()
        self.configure(bg="#2E2E2E")
        self.result = None

        ttk.Label(self, text="Master Password:", background="#2E2E2E", foreground="#FFFFFF").grid(
            row=0, column=0, padx=16, pady=(16, 4), sticky="w")
        self._pw = ttk.Entry(self, show="*", width=30)
        self._pw.grid(row=1, column=0, columnspan=2, padx=16, pady=4, sticky="ew")

        if is_new:
            ttk.Label(self, text="Confirm Password:", background="#2E2E2E", foreground="#FFFFFF").grid(
                row=2, column=0, padx=16, pady=(8, 4), sticky="w")
            self._pw2 = ttk.Entry(self, show="*", width=30)
            self._pw2.grid(row=3, column=0, columnspan=2, padx=16, pady=4, sticky="ew")
        else:
            self._pw2 = None

        self._is_new = is_new
        btn = ttk.Button(self, text="OK", command=self._ok)
        btn.grid(row=4, column=0, columnspan=2, pady=12)
        self._pw.bind("<Return>", lambda _: self._ok())
        self._pw.focus_set()
        self.wait_window()

    def _ok(self):
        pw = self._pw.get()
        if not pw:
            messagebox.showwarning("Empty", "Password cannot be empty.", parent=self)
            return
        if self._is_new:
            if pw != self._pw2.get():
                messagebox.showwarning("Mismatch", "Passwords do not match.", parent=self)
                return
        self.result = pw
        self.destroy()


class PasswordManager:
    def __init__(self, master):
        self.master = master
        master.title("Password Manager")
        master.geometry("680x480")
        master.configure(bg="#2E2E2E")
        master.resizable(True, True)

        self._setup_style()

        self.conn = sqlite3.connect(DB_FILE)
        self._create_table()

        self.cipher = None
        if not self._authenticate():
            master.destroy()
            return

        self._build_ui()
        self._load_passwords()

    # ── auth ─────────────────────────────────────────────────────────────────

    def _authenticate(self) -> bool:
        salt = load_or_create_salt()
        is_new = not self._has_any_passwords()

        dlg = MasterPasswordDialog(self.master, is_new=is_new)
        if dlg.result is None:
            return False

        key = derive_key(dlg.result, salt)

        if not is_new:
            # Verify key by trying to decrypt one stored password
            cur = self.conn.cursor()
            cur.execute("SELECT password FROM passwords LIMIT 1")
            row = cur.fetchone()
            if row:
                try:
                    Fernet(key).decrypt(row[0].encode())
                except Exception:
                    messagebox.showerror("Wrong Password", "Master password is incorrect.")
                    return False

        self.cipher = Fernet(key)
        return True

    def _has_any_passwords(self) -> bool:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM passwords")
        return cur.fetchone()[0] > 0

    # ── DB ───────────────────────────────────────────────────────────────────

    def _create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS passwords (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                service  TEXT NOT NULL,
                username TEXT NOT NULL,
                password TEXT NOT NULL,
                notes    TEXT DEFAULT ''
            )
        """)
        self.conn.commit()

    def _load_passwords(self, filter_text=""):
        for row in self.tree.get_children():
            self.tree.delete(row)
        cur = self.conn.cursor()
        q = "%" + filter_text.lower() + "%"
        cur.execute("""
            SELECT id, service, username FROM passwords
            WHERE LOWER(service) LIKE ? OR LOWER(username) LIKE ?
            ORDER BY service
        """, (q, q))
        for row in cur.fetchall():
            self.tree.insert("", "end", iid=str(row[0]), values=(row[1], row[2]))

    # ── UI ───────────────────────────────────────────────────────────────────

    def _setup_style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background="#2E2E2E", foreground="#FFFFFF")
        s.configure("TLabel", background="#2E2E2E", foreground="#FFFFFF")
        s.configure("TButton", background="#4CAF50", foreground="#FFFFFF")
        s.map("TButton", background=[("active", "#45A049"), ("disabled", "#333")])
        s.configure("TEntry", fieldbackground="#3E3E3E", foreground="#FFFFFF")
        s.configure("Treeview", background="#3E3E3E", foreground="#FFFFFF", fieldbackground="#3E3E3E", rowheight=24)
        s.map("Treeview", background=[("selected", "#4CAF50")])
        s.configure("Treeview.Heading", background="#4a4a4a", foreground="#FFFFFF")

    def _build_ui(self):
        frame = ttk.Frame(self.master, padding="12")
        frame.grid(row=0, column=0, sticky="nsew")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        # Search
        search_row = ttk.Frame(frame)
        search_row.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        ttk.Label(search_row, text="Search:").pack(side=tk.LEFT, padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._load_passwords(self.search_var.get()))
        ttk.Entry(search_row, textvariable=self.search_var, width=36).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Tree
        cols = ("Service", "Username")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for col in cols:
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_tree(c))
            self.tree.column(col, width=240)
        self.tree.grid(row=1, column=0, sticky="nsew")

        sb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<Double-1>", lambda _: self.view_password())

        # Buttons
        btn_col = ttk.Frame(frame)
        btn_col.grid(row=1, column=2, padx=(8, 0), sticky="n")
        for text, cmd in [
            ("Add",      self.add_password),
            ("View",     self.view_password),
            ("Copy",     self.copy_password),
            ("Update",   self.update_password),
            ("Delete",   self.delete_password),
            ("Generate", self.generate_password),
        ]:
            ttk.Button(btn_col, text=text, command=cmd, width=10).pack(pady=3)

        self.status_var = tk.StringVar()
        ttk.Label(frame, textvariable=self.status_var, foreground="#aaaaaa").grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))

    # ── sort ─────────────────────────────────────────────────────────────────

    def _sort_tree(self, col):
        data = [(self.tree.set(c, col), c) for c in self.tree.get_children("")]
        data.sort(key=lambda x: x[0].lower())
        for i, (_, iid) in enumerate(data):
            self.tree.move(iid, "", i)

    # ── operations ────────────────────────────────────────────────────────────

    def _selected_id(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Select an entry first.")
            return None
        return int(sel[0])

    def add_password(self):
        dlg = _EntryDialog(self.master, title="Add Password")
        if dlg.result is None:
            return
        service, username, password, notes = dlg.result
        enc = self.cipher.encrypt(password.encode()).decode()
        self.conn.execute(
            "INSERT INTO passwords (service, username, password, notes) VALUES (?,?,?,?)",
            (service, username, enc, notes))
        self.conn.commit()
        self._load_passwords(self.search_var.get())
        self._flash(f"Added: {service}")

    def view_password(self):
        rid = self._selected_id()
        if rid is None:
            return
        row = self.conn.execute(
            "SELECT service, username, password, notes FROM passwords WHERE id=?", (rid,)
        ).fetchone()
        pw = self.cipher.decrypt(row[2].encode()).decode()
        msg = f"Service:  {row[0]}\nUsername: {row[1]}\nPassword: {pw}"
        if row[3]:
            msg += f"\nNotes:    {row[3]}"
        messagebox.showinfo("Password Details", msg)

    def copy_password(self):
        rid = self._selected_id()
        if rid is None:
            return
        row = self.conn.execute("SELECT service, password FROM passwords WHERE id=?", (rid,)).fetchone()
        pw = self.cipher.decrypt(row[1].encode()).decode()
        self.master.clipboard_clear()
        self.master.clipboard_append(pw)
        self._flash(f"Copied password for {row[0]} to clipboard")

    def update_password(self):
        rid = self._selected_id()
        if rid is None:
            return
        row = self.conn.execute(
            "SELECT service, username, password, notes FROM passwords WHERE id=?", (rid,)
        ).fetchone()
        current_pw = self.cipher.decrypt(row[2].encode()).decode()
        dlg = _EntryDialog(self.master, title="Update Password",
                           prefill=(row[0], row[1], current_pw, row[3]))
        if dlg.result is None:
            return
        service, username, password, notes = dlg.result
        enc = self.cipher.encrypt(password.encode()).decode()
        self.conn.execute(
            "UPDATE passwords SET service=?, username=?, password=?, notes=? WHERE id=?",
            (service, username, enc, notes, rid))
        self.conn.commit()
        self._load_passwords(self.search_var.get())
        self._flash(f"Updated: {service}")

    def delete_password(self):
        rid = self._selected_id()
        if rid is None:
            return
        row = self.conn.execute("SELECT service FROM passwords WHERE id=?", (rid,)).fetchone()
        if messagebox.askyesno("Confirm Delete", f"Delete password for '{row[0]}'?"):
            self.conn.execute("DELETE FROM passwords WHERE id=?", (rid,))
            self.conn.commit()
            self._load_passwords(self.search_var.get())
            self._flash(f"Deleted: {row[0]}")

    def generate_password(self):
        dlg = _GenDialog(self.master)
        if dlg.result:
            self.master.clipboard_clear()
            self.master.clipboard_append(dlg.result)
            self._flash(f"Generated password copied to clipboard ({len(dlg.result)} chars)")

    def _flash(self, msg):
        self.status_var.set(msg)
        self.master.after(4000, lambda: self.status_var.set(""))

    def __del__(self):
        try:
            self.conn.close()
        except Exception:
            pass


class _EntryDialog(tk.Toplevel):
    def __init__(self, parent, title, prefill=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.configure(bg="#2E2E2E")
        self.result = None

        fields = [("Service", False), ("Username", False), ("Password", True), ("Notes", False)]
        self._entries = {}
        for i, (label, secret) in enumerate(fields):
            ttk.Label(self, text=label + ":", background="#2E2E2E", foreground="#FFFFFF").grid(
                row=i, column=0, padx=14, pady=5, sticky="w")
            e = ttk.Entry(self, width=34, show="*" if secret else "")
            e.grid(row=i, column=1, padx=14, pady=5, sticky="ew")
            self._entries[label] = e

        if prefill:
            for (label, _), val in zip(fields, prefill):
                self._entries[label].insert(0, val or "")

        btn_row = ttk.Frame(self, padding=(0, 6))
        btn_row.grid(row=len(fields), column=0, columnspan=2)
        ttk.Button(btn_row, text="OK", command=self._ok, width=10).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="Cancel", command=self.destroy, width=10).pack(side=tk.LEFT, padx=6)

        self._entries["Service"].focus_set()
        self.wait_window()

    def _ok(self):
        s = self._entries["Service"].get().strip()
        u = self._entries["Username"].get().strip()
        p = self._entries["Password"].get()
        n = self._entries["Notes"].get().strip()
        if not s or not u or not p:
            messagebox.showwarning("Incomplete", "Service, username, and password are required.", parent=self)
            return
        self.result = (s, u, p, n)
        self.destroy()


class _GenDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Generate Password")
        self.resizable(False, False)
        self.grab_set()
        self.configure(bg="#2E2E2E")
        self.result = None

        self._length = tk.IntVar(value=16)
        self._upper = tk.BooleanVar(value=True)
        self._digits = tk.BooleanVar(value=True)
        self._symbols = tk.BooleanVar(value=True)
        self._ambiguous = tk.BooleanVar(value=False)

        r = 0
        ttk.Label(self, text="Length:", background="#2E2E2E", foreground="#FFFFFF").grid(row=r, column=0, padx=14, pady=6, sticky="w")
        ttk.Spinbox(self, from_=8, to=128, textvariable=self._length, width=8).grid(row=r, column=1, padx=14, pady=6, sticky="w")

        for label, var in [
            ("Uppercase letters", self._upper),
            ("Digits", self._digits),
            ("Symbols", self._symbols),
            ("Exclude ambiguous (0OIl)", self._ambiguous),
        ]:
            r += 1
            cb = ttk.Checkbutton(self, text=label, variable=var)
            cb.grid(row=r, column=0, columnspan=2, padx=14, sticky="w")

        r += 1
        self._preview = ttk.Label(self, text="", foreground="#4CAF50", background="#2E2E2E", font=("Consolas", 11))
        self._preview.grid(row=r, column=0, columnspan=2, padx=14, pady=(8, 0))

        r += 1
        bf = ttk.Frame(self)
        bf.grid(row=r, column=0, columnspan=2, pady=10)
        ttk.Button(bf, text="Generate", command=self._gen, width=10).pack(side=tk.LEFT, padx=6)
        ttk.Button(bf, text="Accept", command=self._accept, width=10).pack(side=tk.LEFT, padx=6)
        ttk.Button(bf, text="Cancel", command=self.destroy, width=10).pack(side=tk.LEFT, padx=6)

        self._gen()
        self.wait_window()

    def _gen(self):
        pool = string.ascii_lowercase
        if self._upper.get():
            pool += string.ascii_uppercase
        if self._digits.get():
            pool += string.digits
        if self._symbols.get():
            pool += string.punctuation
        if self._ambiguous.get():
            for ch in "0O1Il|":
                pool = pool.replace(ch, "")
        if not pool:
            pool = string.ascii_lowercase
        pw = "".join(secrets.choice(pool) for _ in range(self._length.get()))
        self._preview.config(text=pw)
        self._current = pw

    def _accept(self):
        self.result = self._current
        self.destroy()


def main():
    root = tk.Tk()
    app = PasswordManager(root)
    if root.winfo_exists():
        root.mainloop()


if __name__ == "__main__":
    main()
