import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
import json

class Reference:
    def __init__(self, title, author, year, link=None):
        self.title = title
        self.author = author
        self.year = year
        self.link = link

class ReferenceManagerApp:
    def __init__(self, master):
        self.master = master
        master.title("Reference Manager")
        master.geometry("600x500")
        master.configure(bg="#2E2E2E")

        self.references = []

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

        self.title_label = ttk.Label(self.frame, text="Title:")
        self.title_label.grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.title_entry = ttk.Entry(self.frame, width=40)
        self.title_entry.grid(row=0, column=1, padx=5, pady=5, sticky="we")
        self.title_entry.bind('<Return>', lambda event: self.focus_next_entry(event, self.author_entry))

        self.author_label = ttk.Label(self.frame, text="Author:")
        self.author_label.grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.author_entry = ttk.Entry(self.frame, width=40)
        self.author_entry.grid(row=1, column=1, padx=5, pady=5, sticky="we")
        self.author_entry.bind('<Return>', lambda event: self.focus_next_entry(event, self.year_entry))

        self.year_label = ttk.Label(self.frame, text="Year:")
        self.year_label.grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.year_entry = ttk.Entry(self.frame, width=40)
        self.year_entry.grid(row=2, column=1, padx=5, pady=5, sticky="we")
        self.year_entry.bind('<Return>', lambda event: self.focus_next_entry(event, self.link_entry))

        self.link_label = ttk.Label(self.frame, text="Link (optional):")
        self.link_label.grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.link_entry = ttk.Entry(self.frame, width=40)
        self.link_entry.grid(row=3, column=1, padx=5, pady=5, sticky="we")
        self.link_entry.bind('<Return>', self.add_reference)

        self.button_frame = ttk.Frame(self.frame)
        self.button_frame.grid(row=4, column=0, columnspan=2, pady=10)

        self.add_button = ttk.Button(self.button_frame, text="Add Reference", command=self.add_reference)
        self.add_button.pack(side=tk.LEFT, padx=5)

        self.export_button = ttk.Button(self.button_frame, text="Export References", command=self.export_references)
        self.export_button.pack(side=tk.LEFT, padx=5)

        self.import_button = ttk.Button(self.button_frame, text="Import References", command=self.import_references)
        self.import_button.pack(side=tk.LEFT, padx=5)

        self.reference_listbox = tk.Listbox(self.frame, width=70, bg="#3E3E3E", fg="#FFFFFF", selectbackground="#4CAF50")
        self.reference_listbox.grid(row=5, column=0, columnspan=2, padx=5, pady=10, sticky="nswe")
        self.reference_listbox.bind('<Double-1>', self.edit_reference)

        self.scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.reference_listbox.yview)
        self.scrollbar.grid(row=5, column=2, sticky="ns")
        self.reference_listbox.configure(yscrollcommand=self.scrollbar.set)

        self.frame.columnconfigure(1, weight=1)
        self.frame.rowconfigure(5, weight=1)

    def add_reference(self, event=None):
        title = self.title_entry.get()
        author = self.author_entry.get()
        year = self.year_entry.get()
        link = self.link_entry.get()

        if title and author and year:
            ref = Reference(title, author, year, link)
            self.references.append(ref)
            self.update_reference_listbox()
            self.clear_entries()
        else:
            messagebox.showwarning("Incomplete Data", "Please fill in all required fields.")

    def update_reference_listbox(self):
        self.reference_listbox.delete(0, tk.END)
        for ref in self.references:
            if ref.link:
                self.reference_listbox.insert(tk.END, f"{ref.title} - {ref.author} ({ref.year}) - {ref.link}")
            else:
                self.reference_listbox.insert(tk.END, f"{ref.title} - {ref.author} ({ref.year})")

    def clear_entries(self):
        self.title_entry.delete(0, tk.END)
        self.author_entry.delete(0, tk.END)
        self.year_entry.delete(0, tk.END)
        self.link_entry.delete(0, tk.END)

    def export_references(self):
        if not self.references:
            messagebox.showinfo("No References", "There are no references to export.")
            return

        filename = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if filename:
            with open(filename, "w") as f:
                json.dump([ref.__dict__ for ref in self.references], f, indent=2)
            messagebox.showinfo("Export Successful", f"References exported to {filename}.")

    def import_references(self):
        filename = filedialog.askopenfilename(filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if filename:
            with open(filename, "r") as f:
                imported_refs = json.load(f)
            for ref_dict in imported_refs:
                self.references.append(Reference(**ref_dict))
            self.update_reference_listbox()
            messagebox.showinfo("Import Successful", f"References imported from {filename}.")

    def focus_next_entry(self, event, next_entry):
        next_entry.focus_set()

    def edit_reference(self, event):
        selection = self.reference_listbox.curselection()
        if selection:
            index = selection[0]
            ref = self.references[index]
            self.title_entry.delete(0, tk.END)
            self.title_entry.insert(0, ref.title)
            self.author_entry.delete(0, tk.END)
            self.author_entry.insert(0, ref.author)
            self.year_entry.delete(0, tk.END)
            self.year_entry.insert(0, ref.year)
            self.link_entry.delete(0, tk.END)
            self.link_entry.insert(0, ref.link if ref.link else "")
            self.references.pop(index)
            self.update_reference_listbox()

def main():
    root = tk.Tk()
    app = ReferenceManagerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
