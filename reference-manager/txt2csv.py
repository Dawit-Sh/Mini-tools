import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
import re

class TextToCSVConverterApp:
    def __init__(self, master):
        self.master = master
        master.title("Text to CSV Converter")
        master.geometry("600x400")
        master.configure(bg="#2E2E2E")

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('.', background='#2E2E2E', foreground='#FFFFFF')
        self.style.configure('TLabel', background='#2E2E2E', foreground='#FFFFFF')
        self.style.configure('TEntry', fieldbackground='#3E3E3E', foreground='#FFFFFF')
        self.style.configure('TButton', background='#4CAF50', foreground='#FFFFFF')
        self.style.map('TButton', background=[('active', '#45A049')])

        self.frame = ttk.Frame(master, padding="20")
        self.frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        master.grid_columnconfigure(0, weight=1)
        master.grid_rowconfigure(0, weight=1)

        self.file_path_label = ttk.Label(self.frame, text="File Path:")
        self.file_path_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.file_path_entry = ttk.Entry(self.frame, width=50, state="readonly")
        self.file_path_entry.grid(row=0, column=1, padx=5, pady=5, sticky="we")
        self.browse_button = ttk.Button(self.frame, text="Browse", command=self.browse_file)
        self.browse_button.grid(row=0, column=2, padx=5, pady=5)

        self.preview_text = tk.Text(self.frame, height=10, bg="#3E3E3E", fg="#FFFFFF")
        self.preview_text.grid(row=1, column=0, columnspan=3, padx=5, pady=10, sticky="nswe")
        self.preview_text.config(state=tk.DISABLED)

        self.scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.preview_text.yview)
        self.scrollbar.grid(row=1, column=3, sticky="ns")
        self.preview_text.configure(yscrollcommand=self.scrollbar.set)

        self.convert_button = ttk.Button(self.frame, text="Convert", command=self.convert_to_csv)
        self.convert_button.grid(row=2, column=0, columnspan=3, padx=5, pady=10, sticky="we")

        self.frame.columnconfigure(1, weight=1)
        self.frame.rowconfigure(1, weight=1)

    def browse_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if file_path:
            self.file_path_entry.config(state="normal")
            self.file_path_entry.delete(0, tk.END)
            self.file_path_entry.insert(0, file_path)
            self.file_path_entry.config(state="readonly")
            self.preview_file(file_path)

    def preview_file(self, file_path):
        try:
            with open(file_path, "r") as file:
                content = file.read(1000)  # Read first 1000 characters for preview
            self.preview_text.config(state=tk.NORMAL)
            self.preview_text.delete(1.0, tk.END)
            self.preview_text.insert(tk.END, content)
            self.preview_text.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while reading the file: {str(e)}")

    def convert_to_csv(self):
        file_path = self.file_path_entry.get()
        if not file_path:
            messagebox.showerror("Error", "Please select a file to convert.")
            return

        try:
            with open(file_path, "r") as file:
                lines = file.readlines()

            data = []
            for line in lines:
                match = re.match(r'(.+) - (.+) \((\d+)\)(?: - (.+))?', line.strip())
                if match:
                    title, author, year, link = match.groups()
                    data.append([title.strip(), author.strip(), year.strip(), link.strip() if link else ""])
                else:
                    messagebox.showwarning("Invalid Format", f"Line '{line.strip()}' does not match the required format and will be skipped.")

            if data:
                df = pd.DataFrame(data, columns=["Title", "Author", "Year", "Link"])
                csv_file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
                if csv_file_path:
                    df.to_csv(csv_file_path, index=False)
                    messagebox.showinfo("Conversion Successful", f"CSV file saved at {csv_file_path}")
            else:
                messagebox.showwarning("No Data", "No valid data found in the text file.")

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")

def main():
    root = tk.Tk()
    app = TextToCSVConverterApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
