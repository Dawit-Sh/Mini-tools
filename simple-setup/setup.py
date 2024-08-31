import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os

class LinuxProgramInstallerApp:
    def __init__(self, master):
        self.master = master
        master.title("Linux Program Installer")
        master.geometry("600x500")
        master.configure(bg="#2E2E2E")

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('.', background='#2E2E2E', foreground='#FFFFFF')
        self.style.configure('TLabel', background='#2E2E2E', foreground='#FFFFFF')
        self.style.configure('TButton', background='#4CAF50', foreground='#FFFFFF')
        self.style.map('TButton', background=[('active', '#45A049')])
        self.style.configure('TCheckbutton', background='#2E2E2E', foreground='#FFFFFF')

        self.frame = ttk.Frame(master, padding="20")
        self.frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        master.grid_columnconfigure(0, weight=1)
        master.grid_rowconfigure(0, weight=1)

        self.distribution_label = ttk.Label(self.frame, text="Select Distribution:")
        self.distribution_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        self.distribution_var = tk.StringVar()
        self.distribution_combobox = ttk.Combobox(self.frame, textvariable=self.distribution_var, 
                                                  values=["Ubuntu", "Fedora", "openSUSE", "Arch"],
                                                  state="readonly")
        self.distribution_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="we")
        self.distribution_combobox.set("Ubuntu")

        self.file_path_label = ttk.Label(self.frame, text="Programs File:")
        self.file_path_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.file_path_entry = ttk.Entry(self.frame, width=50, state="readonly")
        self.file_path_entry.grid(row=1, column=1, padx=5, pady=5, sticky="we")
        self.browse_button = ttk.Button(self.frame, text="Browse", command=self.browse_file)
        self.browse_button.grid(row=1, column=2, padx=5, pady=5)

        self.programs_frame = ttk.Frame(self.frame)
        self.programs_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=10, sticky="nswe")
        self.programs_canvas = tk.Canvas(self.programs_frame, bg="#2E2E2E")
        self.programs_scrollbar = ttk.Scrollbar(self.programs_frame, orient="vertical", command=self.programs_canvas.yview)
        self.programs_scrollable_frame = ttk.Frame(self.programs_canvas)

        self.programs_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.programs_canvas.configure(
                scrollregion=self.programs_canvas.bbox("all")
            )
        )

        self.programs_canvas.create_window((0, 0), window=self.programs_scrollable_frame, anchor="nw")
        self.programs_canvas.configure(yscrollcommand=self.programs_scrollbar.set)

        self.programs_canvas.pack(side="left", fill="both", expand=True)
        self.programs_scrollbar.pack(side="right", fill="y")

        self.install_button = ttk.Button(self.frame, text="Install Selected Programs", command=self.install_programs)
        self.install_button.grid(row=3, column=0, columnspan=3, padx=5, pady=10, sticky="we")

        self.frame.columnconfigure(1, weight=1)
        self.frame.rowconfigure(2, weight=1)

        self.programs = []
        self.program_vars = []

    def browse_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file_path:
            self.file_path_entry.config(state="normal")
            self.file_path_entry.delete(0, tk.END)
            self.file_path_entry.insert(0, file_path)
            self.file_path_entry.config(state="readonly")
            self.load_programs(file_path)

    def load_programs(self, file_path):
        try:
            with open(file_path, "r") as file:
                self.programs = [line.strip() for line in file if line.strip()]
            
            for widget in self.programs_scrollable_frame.winfo_children():
                widget.destroy()
            
            self.program_vars = []
            for program in self.programs:
                var = tk.BooleanVar()
                checkbox = ttk.Checkbutton(self.programs_scrollable_frame, text=program, variable=var)
                checkbox.pack(anchor="w", padx=5, pady=2)
                self.program_vars.append((program, var))
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while reading the file: {str(e)}")

    def install_programs(self):
        distribution = self.distribution_var.get()
        selected_programs = [program for program, var in self.program_vars if var.get()]

        if not selected_programs:
            messagebox.showwarning("No Programs Selected", "Please select at least one program to install.")
            return

        package_manager = self.get_package_manager(distribution)
        install_command = self.get_install_command(distribution)

        additional_commands = self.get_additional_commands(distribution)

        command = f"#!/bin/bash\n\n"
        command += f"# Update package manager\n"
        command += f"{package_manager} update\n\n"

        command += f"# Install selected programs\n"
        command += f"{install_command} {' '.join(selected_programs)}\n\n"

        if additional_commands:
            command += f"# Additional commands\n"
            command += additional_commands

        script_path = os.path.expanduser("~/install_programs.sh")
        with open(script_path, "w") as script_file:
            script_file.write(command)

        os.chmod(script_path, 0o755)

        messagebox.showinfo("Installation Script Created", 
                            f"An installation script has been created at {script_path}.\n"
                            f"Please run this script with sudo privileges to install the selected programs.")

    def get_package_manager(self, distribution):
        if distribution == "Ubuntu":
            return "sudo apt"
        elif distribution == "Fedora":
            return "sudo dnf"
        elif distribution == "openSUSE":
            return "sudo zypper"
        elif distribution == "Arch":
            return "sudo pacman"

    def get_install_command(self, distribution):
        if distribution == "Ubuntu":
            return "sudo apt install -y"
        elif distribution == "Fedora":
            return "sudo dnf install -y"
        elif distribution == "openSUSE":
            return "sudo zypper install -y"
        elif distribution == "Arch":
            return "sudo pacman -S --noconfirm"

    def get_additional_commands(self, distribution):
        commands = ""
        if distribution == "Ubuntu":
            commands += "# Enable Flatpak support\n"
            commands += "sudo apt install flatpak\n"
            commands += "sudo flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo\n\n"
        elif distribution == "Fedora":
            commands += "# Enable RPM Fusion repositories\n"
            commands += "sudo dnf install https://download1.rpmfusion.org/free/fedora/rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm\n"
            commands += "sudo dnf install https://download1.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-$(rpm -E %fedora).noarch.rpm\n\n"
        elif distribution == "openSUSE":
            commands += "# Add Packman repository\n"
            commands += "sudo zypper ar -cfp 90 https://ftp.gwdg.de/pub/linux/misc/packman/suse/openSUSE_Tumbleweed/ packman\n"
            commands += "sudo zypper dup --from packman --allow-vendor-change\n\n"
        elif distribution == "Arch":
            commands += "# Enable multilib repository\n"
            commands += "sudo sed -i '/\\[multilib\\]/,/Include/s/^#//' /etc/pacman.conf\n"
            commands += "sudo pacman -Sy\n\n"
        return commands

def main():
    root = tk.Tk()
    app = LinuxProgramInstallerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
