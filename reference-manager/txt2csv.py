import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
import re

class TextToCSVConverterApp:
    def __init__(self, master):
        self.master = master
        master.title("Text to CSV Converter")

        self.file_path_label = ttk.Label(master, text="File Path:")
        self.file_path_label.grid(row=0, column=0, padx=10, pady=5, sticky="e")
        self.file_path_entry = ttk.Entry(master, width=50, state="disabled")
        self.file_path_entry.grid(row=0, column=1, padx=10, pady=5, sticky="we")
        self.browse_button = ttk.Button(master, text="Browse", command=self.browse_file)
        self.browse_button.grid(row=0, column=2, padx=10, pady=5)

        self.convert_button = ttk.Button(master, text="Convert", command=self.convert_to_csv)
        self.convert_button.grid(row=1, columnspan=3, padx=10, pady=10, sticky="we")

    def browse_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file_path:
            self.file_path_entry.config(state="normal")
            self.file_path_entry.delete(0, tk.END)
            self.file_path_entry.insert(0, file_path)
            self.file_path_entry.config(state="disabled")

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
                match = re.match(r'(.+) - (.+) \((\d+)\) - (.+)', line.strip())
                if match:
                    title, author, year, link = match.groups()
                    data.append([title.strip(), author.strip(), year.strip(), link.strip()])
                else:
                    messagebox.showwarning("Invalid Format", f"Line '{line.strip()}' does not match the required format and will be skipped.")

            if data:
                df = pd.DataFrame(data, columns=["Title", "Author", "Year", "Link"])
                csv_file_path = file_path.replace(".txt", ".csv")
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

