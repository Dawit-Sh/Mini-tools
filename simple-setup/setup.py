import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
import platform
import sys

DARK = "#2E2E2E"
DARKER = "#3E3E3E"
GREEN = "#4CAF50"

DISTROS = {
    "Ubuntu / Debian": {
        "update":  "sudo apt update && sudo apt upgrade -y",
        "install": "sudo apt install -y",
        "extras": [
            ("Enable Flatpak",
             "sudo apt install -y flatpak\n"
             "sudo flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo"),
        ],
    },
    "Fedora": {
        "update":  "sudo dnf upgrade -y",
        "install": "sudo dnf install -y",
        "extras": [
            ("Enable RPM Fusion (free)",
             "sudo dnf install -y https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm"),
            ("Enable RPM Fusion (nonfree)",
             "sudo dnf install -y https://download1.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm"),
        ],
    },
    "openSUSE": {
        "update":  "sudo zypper refresh && sudo zypper update -y",
        "install": "sudo zypper install -y",
        "extras": [
            ("Add Packman repo",
             "sudo zypper ar -cfp 90 'https://ftp.gwdg.de/pub/linux/misc/packman/suse/openSUSE_Tumbleweed/' packman\n"
             "sudo zypper dup --from packman --allow-vendor-change -y"),
        ],
    },
    "Arch / Manjaro": {
        "update":  "sudo pacman -Syu --noconfirm",
        "install": "sudo pacman -S --noconfirm",
        "extras": [
            ("Enable multilib",
             "sudo sed -i '/\\[multilib\\]/,/Include/s/^#//' /etc/pacman.conf\n"
             "sudo pacman -Sy"),
        ],
    },
    "macOS (Homebrew)": {
        "update":  "brew update && brew upgrade",
        "install": "brew install",
        "extras": [
            ("Install Homebrew (if missing)",
             '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'),
            ("Install Cask support", "brew tap homebrew/cask"),
        ],
    },
    "Windows (winget)": {
        "update":  "winget upgrade --all --accept-source-agreements --accept-package-agreements",
        "install": "winget install --accept-source-agreements --accept-package-agreements",
        "extras": [],
        "shell":  "powershell",
    },
    "Windows (Chocolatey)": {
        "update":  "choco upgrade all -y",
        "install": "choco install -y",
        "extras": [
            ("Install Chocolatey (run as Admin)",
             "Set-ExecutionPolicy Bypass -Scope Process -Force; "
             "[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; "
             "iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))"),
        ],
        "shell": "powershell",
    },
}


class SetupApp:
    def __init__(self, master):
        self.master = master
        master.title("Simple Setup")
        master.geometry("680x580")
        master.configure(bg=DARK)
        master.resizable(True, True)

        self.programs: list[str] = []
        self.program_vars: list[tuple[str, tk.BooleanVar]] = []
        self.extra_vars: list[tuple[str, str, tk.BooleanVar]] = []

        self._setup_style()
        self._build_ui()
        self._auto_detect_distro()

    def _setup_style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=DARK, foreground="#FFFFFF")
        s.configure("TLabel", background=DARK, foreground="#FFFFFF")
        s.configure("TButton", background=GREEN, foreground="#FFFFFF")
        s.map("TButton", background=[("active", "#45A049")])
        s.configure("TCheckbutton", background=DARK, foreground="#FFFFFF")
        s.map("TCheckbutton", background=[("active", DARK)])
        s.configure("TEntry", fieldbackground=DARKER, foreground="#FFFFFF")
        s.configure("TCombobox", fieldbackground=DARKER, foreground="#FFFFFF",
                    selectbackground=DARKER, selectforeground="#FFFFFF")

    def _build_ui(self):
        frame = ttk.Frame(self.master, padding="14")
        frame.grid(row=0, column=0, sticky="nsew")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(3, weight=1)

        # Distribution selector
        ttk.Label(frame, text="Platform / Distribution:").grid(row=0, column=0, padx=5, pady=6, sticky="w")
        self._distro_var = tk.StringVar()
        self._distro_cb = ttk.Combobox(frame, textvariable=self._distro_var,
                                        values=list(DISTROS.keys()), state="readonly", width=28)
        self._distro_cb.grid(row=0, column=1, padx=5, pady=6, sticky="ew")
        self._distro_cb.bind("<<ComboboxSelected>>", lambda _: self._on_distro_change())

        # Programs file
        ttk.Label(frame, text="Programs file:").grid(row=1, column=0, padx=5, pady=4, sticky="w")
        self._file_entry = ttk.Entry(frame, width=40, state="readonly")
        self._file_entry.grid(row=1, column=1, padx=5, pady=4, sticky="ew")
        ttk.Button(frame, text="Browse", command=self._browse_file).grid(row=1, column=2, padx=5, pady=4)

        # Add program inline
        add_row = ttk.Frame(frame)
        add_row.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        ttk.Label(add_row, text="Add package:").pack(side=tk.LEFT, padx=(0, 6))
        self._add_entry = ttk.Entry(add_row, width=24)
        self._add_entry.pack(side=tk.LEFT)
        self._add_entry.bind("<Return>", lambda _: self._add_program_inline())
        ttk.Button(add_row, text="Add", command=self._add_program_inline).pack(side=tk.LEFT, padx=6)
        ttk.Button(add_row, text="Select All", command=self._select_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(add_row, text="Clear All", command=self._clear_all).pack(side=tk.LEFT, padx=2)

        # Programs checklist
        prog_outer = ttk.Frame(frame)
        prog_outer.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=8)
        prog_outer.rowconfigure(0, weight=1)
        prog_outer.columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(prog_outer, bg=DARK, highlightthickness=0)
        vsb = ttk.Scrollbar(prog_outer, orient=tk.VERTICAL, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        self._canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        self._prog_frame = ttk.Frame(self._canvas)
        self._canvas_win = self._canvas.create_window((0, 0), window=self._prog_frame, anchor="nw")
        self._prog_frame.bind("<Configure>",
                              lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
                          lambda e: self._canvas.itemconfig(self._canvas_win, width=e.width))

        # Extras section
        self._extras_label = ttk.Label(frame, text="Optional extras:")
        self._extras_label.grid(row=4, column=0, padx=5, pady=(4, 0), sticky="w")
        self._extras_frame = ttk.Frame(frame)
        self._extras_frame.grid(row=5, column=0, columnspan=3, sticky="ew")

        # Action buttons
        btn_row = ttk.Frame(frame)
        btn_row.grid(row=6, column=0, columnspan=3, pady=10, sticky="ew")
        ttk.Button(btn_row, text="Generate Script", command=self._generate_script).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="Run Now", command=self._run_now).pack(side=tk.LEFT, padx=4)

        self._status_var = tk.StringVar()
        ttk.Label(frame, textvariable=self._status_var, foreground="#aaaaaa").grid(
            row=7, column=0, columnspan=3, sticky="w")

    # ── auto detect ───────────────────────────────────────────────────────────

    def _auto_detect_distro(self):
        system = platform.system()
        if system == "Darwin":
            self._distro_var.set("macOS (Homebrew)")
        elif system == "Windows":
            self._distro_var.set("Windows (winget)")
        else:
            # Try to read /etc/os-release
            try:
                with open("/etc/os-release") as f:
                    content = f.read().lower()
                if "ubuntu" in content or "debian" in content:
                    self._distro_var.set("Ubuntu / Debian")
                elif "fedora" in content:
                    self._distro_var.set("Fedora")
                elif "opensuse" in content:
                    self._distro_var.set("openSUSE")
                elif "arch" in content or "manjaro" in content:
                    self._distro_var.set("Arch / Manjaro")
                else:
                    self._distro_var.set("Ubuntu / Debian")
            except Exception:
                self._distro_var.set("Ubuntu / Debian")
        self._on_distro_change()

    def _on_distro_change(self):
        distro = self._distro_var.get()
        cfg = DISTROS.get(distro, {})
        # Rebuild extras
        for w in self._extras_frame.winfo_children():
            w.destroy()
        self.extra_vars.clear()
        for label, cmd in cfg.get("extras", []):
            var = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(self._extras_frame, text=label, variable=var)
            cb.pack(anchor="w", padx=5)
            self.extra_vars.append((label, cmd, var))

    # ── programs list ─────────────────────────────────────────────────────────

    def _browse_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self._file_entry.config(state="normal")
            self._file_entry.delete(0, tk.END)
            self._file_entry.insert(0, path)
            self._file_entry.config(state="readonly")
            self._load_programs(path)

    def _load_programs(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
            for prog in lines:
                if prog not in [p for p, _ in self.program_vars]:
                    self._add_checkbox(prog)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _add_program_inline(self):
        name = self._add_entry.get().strip()
        if not name:
            return
        if name in [p for p, _ in self.program_vars]:
            messagebox.showinfo("Duplicate", f"'{name}' is already in the list.")
            return
        self._add_checkbox(name)
        self._add_entry.delete(0, tk.END)

    def _add_checkbox(self, name):
        var = tk.BooleanVar(value=True)
        row_frame = ttk.Frame(self._prog_frame)
        row_frame.pack(fill=tk.X, pady=1)
        ttk.Checkbutton(row_frame, text=name, variable=var).pack(side=tk.LEFT, padx=5)
        ttk.Button(row_frame, text="✕", width=3,
                   command=lambda n=name: self._remove_program(n)).pack(side=tk.RIGHT, padx=4)
        self.program_vars.append((name, var))

    def _remove_program(self, name):
        self.program_vars = [(p, v) for p, v in self.program_vars if p != name]
        for w in self._prog_frame.winfo_children():
            w.destroy()
        for prog, var in self.program_vars:
            row_frame = ttk.Frame(self._prog_frame)
            row_frame.pack(fill=tk.X, pady=1)
            ttk.Checkbutton(row_frame, text=prog, variable=var).pack(side=tk.LEFT, padx=5)
            ttk.Button(row_frame, text="✕", width=3,
                       command=lambda n=prog: self._remove_program(n)).pack(side=tk.RIGHT, padx=4)

    def _select_all(self):
        for _, var in self.program_vars:
            var.set(True)

    def _clear_all(self):
        for _, var in self.program_vars:
            var.set(False)

    # ── script generation ─────────────────────────────────────────────────────

    def _build_script(self) -> tuple[str, bool]:
        distro = self._distro_var.get()
        cfg = DISTROS.get(distro, {})
        selected = [p for p, v in self.program_vars if v.get()]

        if not selected and not any(v.get() for _, _, v in self.extra_vars):
            return "", False

        is_win = "Windows" in distro
        shebang = "" if is_win else "#!/usr/bin/env bash\nset -e\n\n"

        lines = [shebang]
        if selected:
            lines.append(f"# Update system\n{cfg['update']}\n")
            pkgs = " ".join(selected)
            lines.append(f"# Install packages\n{cfg['install']} {pkgs}\n")

        for label, cmd, var in self.extra_vars:
            if var.get():
                lines.append(f"# {label}\n{cmd}\n")

        return "\n".join(lines), is_win

    def _generate_script(self):
        script, is_win = self._build_script()
        if not script.strip():
            messagebox.showwarning("Nothing Selected", "Select at least one package or extra.")
            return

        ext = ".ps1" if is_win else ".sh"
        path = filedialog.asksaveasfilename(
            defaultextension=ext,
            initialfile=f"install_programs{ext}",
            filetypes=[("PowerShell Script", "*.ps1"), ("Shell Script", "*.sh"), ("All", "*.*")]
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(script)
        if not is_win:
            os.chmod(path, 0o755)
        messagebox.showinfo("Script Saved", f"Script saved to:\n{path}")
        self._status_var.set(f"Script saved: {path}")

    def _run_now(self):
        script, is_win = self._build_script()
        if not script.strip():
            messagebox.showwarning("Nothing Selected", "Select at least one package or extra.")
            return

        distro = self._distro_var.get()
        cfg = DISTROS.get(distro, {})

        if not messagebox.askyesno("Confirm Run",
                                    "This will execute the install commands on your system.\n"
                                    "Ensure you have the required permissions.\n\nProceed?"):
            return

        tmp = os.path.join(os.path.expanduser("~"), f"_mini_setup_tmp{''.join(['.ps1' if is_win else '.sh'])}")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(script)

        try:
            if is_win:
                shell = cfg.get("shell", "powershell")
                subprocess.Popen([shell, "-ExecutionPolicy", "Bypass", "-File", tmp],
                                  creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                os.chmod(tmp, 0o755)
                term = self._find_terminal()
                if term:
                    subprocess.Popen([term, "-e", f"bash {tmp}; read -p 'Press Enter to close'"])
                else:
                    subprocess.Popen(["bash", tmp])
            self._status_var.set("Script launched in terminal.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _find_terminal(self):
        for t in ["x-terminal-emulator", "gnome-terminal", "konsole", "xterm", "alacritty", "kitty"]:
            if subprocess.call(["which", t], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                return t
        return None


def main():
    root = tk.Tk()
    SetupApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
