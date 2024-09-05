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
        master.geometry("500x500")
        master.configure(bg="#2c2c2c")

        self.backup_thread = None
        self.paused = False
        self.running = False

        self.setup_custom_style()

        self.source_directory = tk.StringVar()
        self.backup_directory = tk.StringVar()
        self.status = tk.StringVar()
        self.status.set("Stopped")

        self.create_widgets()

    def setup_custom_style(self):
        style = ttk.Style()
        style.theme_create("darktheme", parent="alt", settings={
            "TFrame": {"configure": {"background": "#2c2c2c"}},
            "TButton": {
                "configure": {"font": ("Arial", 10), "background": "#4a4a4a", "foreground": "white"},
                "map": {"background": [("active", "#5a5a5a")], "foreground": [("active", "white")]}
            },
            "TLabel": {"configure": {"font": ("Arial", 10), "background": "#2c2c2c", "foreground": "white"}},
            "TEntry": {"configure": {"font": ("Arial", 10), "fieldbackground": "#3c3c3c", "foreground": "white"}},
            "Horizontal.TProgressbar": {"configure": {"background": "#4CAF50"}},
        })
        style.theme_use("darktheme")

    def create_widgets(self):
        frame = ttk.Frame(self.master, padding="10")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)

        ttk.Label(frame, text="Source Directory:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frame, textvariable=self.source_directory, width=30).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(frame, text="Browse", command=self.browse_source_directory).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(frame, text="Backup Directory:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frame, textvariable=self.backup_directory, width=30).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(frame, text="Browse", command=self.browse_backup_directory).grid(row=1, column=2, padx=5, pady=5)

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=2, column=0, columnspan=3, pady=10)

        self.start_button = ttk.Button(button_frame, text="Start Backup", command=self.start_backup)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.pause_button = ttk.Button(button_frame, text="Pause Backup", command=self.pause_backup, state=tk.DISABLED)
        self.pause_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(button_frame, text="Stop Backup", command=self.stop_backup, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.restore_button = ttk.Button(button_frame, text="Restore Backup", command=self.restore_backup)
        self.restore_button.pack(side=tk.LEFT, padx=5)

        ttk.Label(frame, text="Status:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.status_label = ttk.Label(frame, textvariable=self.status)
        self.status_label.grid(row=3, column=1, padx=5, pady=5, sticky="w")

        self.progress_bar = ttk.Progressbar(frame, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.grid(row=4, column=0, columnspan=3, padx=5, pady=5, sticky="we")

        self.log = tk.Text(frame, height=10, width=55, bg="#3c3c3c", fg="white", font=("Arial", 10))
        self.log.grid(row=5, column=0, columnspan=3, padx=5, pady=5)

    def browse_source_directory(self):
        directory = filedialog.askdirectory()
        self.source_directory.set(directory)

    def browse_backup_directory(self):
        directory = filedialog.askdirectory()
        self.backup_directory.set(directory)

    def start_backup(self):
        if not self.source_directory.get() or not self.backup_directory.get():
            self.log_message("Please select both source and backup directories.")
            return

        self.running = True
        self.paused = False
        self.status.set("Running")
        self.status_label.config(foreground="#4CAF50")
        self.start_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.NORMAL)
        self.backup_thread = threading.Thread(target=self.backup_loop, daemon=True)
        self.backup_thread.start()

    def pause_backup(self):
        if self.running:
            self.paused = not self.paused
            if self.paused:
                self.status.set("Paused")
                self.status_label.config(foreground="#FFC107")
                self.pause_button.config(text="Resume Backup")
            else:
                self.status.set("Running")
                self.status_label.config(foreground="#4CAF50")
                self.pause_button.config(text="Pause Backup")

    def stop_backup(self):
        self.running = False
        self.paused = False
        self.status.set("Stopped")
        self.status_label.config(foreground="#F44336")
        self.start_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.DISABLED)
        self.progress_bar["value"] = 0

    def backup_loop(self):
        while self.running:
            if not self.paused:
                self.create_snapshot()
            time.sleep(3600)  # Wait for 1 hour

    def create_snapshot(self):
        try:
            source_dir = self.source_directory.get()
            backup_dir = self.backup_directory.get()
            source_dir_name = os.path.basename(source_dir)
            timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
            snapshot_name = f"{source_dir_name}_{timestamp}.tar.gz"
            snapshot_path = os.path.join(backup_dir, snapshot_name)
            
            total_files = sum([len(files) for r, d, files in os.walk(source_dir)])
            self.progress_bar["maximum"] = total_files
            self.progress_bar["value"] = 0
            
            with tarfile.open(snapshot_path, "w:gz") as tar:
                for root, dirs, files in os.walk(source_dir):
                    for file in files:
                        if self.paused:
                            while self.paused and self.running:
                                time.sleep(0.1)
                        if not self.running:
                            return
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, source_dir)
                        tar.add(file_path, arcname=arcname)
                        self.progress_bar["value"] += 1
                        self.master.update_idletasks()

            # Check for duplicates
            if self.is_duplicate(snapshot_path):
                os.remove(snapshot_path)
                self.log_message(f"Duplicate snapshot detected. Deleted {snapshot_name}")
            else:
                self.log_message(f"Snapshot created: {snapshot_name}")

        except Exception as e:
            self.log_message(f"Error creating snapshot: {str(e)}")
        finally:
            self.progress_bar["value"] = 0

    def is_duplicate(self, new_snapshot):
        backup_dir = self.backup_directory.get()
        source_dir_name = os.path.basename(self.source_directory.get())
        for file in os.listdir(backup_dir):
            if file.startswith(f"{source_dir_name}_") and file.endswith(".tar.gz") and file != os.path.basename(new_snapshot):
                if self.get_file_hash(os.path.join(backup_dir, file)) == self.get_file_hash(new_snapshot):
                    return True
        return False

    def get_file_hash(self, filename):
        hasher = hashlib.md5()
        with open(filename, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()

    def log_message(self, message):
        self.log.insert(tk.END, f"{datetime.datetime.now()}: {message}\n")
        self.log.see(tk.END)

    def restore_backup(self):
        backup_file = filedialog.askopenfilename(
            initialdir=self.backup_directory.get(),
            title="Select backup file to restore",
            filetypes=[("Tar GZ files", "*.tar.gz")]
        )
        if not backup_file:
            return

        restore_dir = filedialog.askdirectory(
            title="Select directory to restore backup",
            initialdir=self.source_directory.get()
        )
        if not restore_dir:
            return

        warning_message = f"Warning: Restoring the backup will overwrite files in the restore directory.\n\nRestore Directory: {restore_dir}\n\nAre you sure you want to proceed?"
        if messagebox.askyesno("Confirm Restore", warning_message):
            self.running = True
            self.paused = False
            self.status.set("Restoring")
            self.status_label.config(foreground="#4CAF50")
            self.start_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.NORMAL)
            
            restore_thread = threading.Thread(target=self.perform_restore, args=(backup_file, restore_dir), daemon=True)
            restore_thread.start()

    def perform_restore(self, backup_file, restore_dir):
        try:
            with tarfile.open(backup_file, "r:gz") as tar:
                members = tar.getmembers()
                self.progress_bar["maximum"] = len(members)
                self.progress_bar["value"] = 0
                for member in members:
                    if self.paused:
                        while self.paused and self.running:
                            time.sleep(0.1)
                    if not self.running:
                        return
                    tar.extract(member, path=restore_dir)
                    self.progress_bar["value"] += 1
                    self.master.update_idletasks()
            self.log_message(f"Backup restored to: {restore_dir}")
        except Exception as e:
            self.log_message(f"Error restoring backup: {str(e)}")
        finally:
            self.progress_bar["value"] = 0
            self.stop_backup()  # Reset the UI state

if __name__ == "__main__":
    root = tk.Tk()
    app = CoRrUptEdFile(root)
    root.mainloop()
