import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

class Reference:
    def __init__(self, title, author, year, link=None):
        self.title = title
        self.author = author
        self.year = year
        self.link = link

class ReferenceManagerApp:
    def __init__(self, master):
        self.master = master
        master.title("My References")

        self.references = []

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', background='black', foreground='white')
        style.configure('TLabel', background='black', foreground='white')
        style.configure('TEntry', background='gray', foreground='black')
        style.configure('TButton', background='gray', foreground='white')

        self.title_label = ttk.Label(master, text="Title:")
        self.title_label.grid(row=0, column=0, padx=10, pady=5, sticky="e")
        self.title_entry = ttk.Entry(master)
        self.title_entry.grid(row=0, column=1, padx=10, pady=5, sticky="we")
        self.title_entry.bind('<Return>', lambda event: self.focus_next_entry(event, self.author_entry))

        self.author_label = ttk.Label(master, text="Author:")
        self.author_label.grid(row=1, column=0, padx=10, pady=5, sticky="e")
        self.author_entry = ttk.Entry(master)
        self.author_entry.grid(row=1, column=1, padx=10, pady=5, sticky="we")
        self.author_entry.bind('<Return>', lambda event: self.focus_next_entry(event, self.year_entry))

        self.year_label = ttk.Label(master, text="Year:")
        self.year_label.grid(row=2, column=0, padx=10, pady=5, sticky="e")
        self.year_entry = ttk.Entry(master)
        self.year_entry.grid(row=2, column=1, padx=10, pady=5, sticky="we")
        self.year_entry.bind('<Return>', lambda event: self.focus_next_entry(event, self.link_entry))

        self.link_label = ttk.Label(master, text="Link (optional):")
        self.link_label.grid(row=3, column=0, padx=10, pady=5, sticky="e")
        self.link_entry = ttk.Entry(master)
        self.link_entry.grid(row=3, column=1, padx=10, pady=5, sticky="we")
        self.link_entry.bind('<Return>', self.add_reference)

        self.add_button = ttk.Button(master, text="Add Reference", command=self.add_reference)
        self.add_button.grid(row=4, columnspan=2, padx=10, pady=10, sticky="we")

        self.export_button = ttk.Button(master, text="Export References", command=self.export_references)
        self.export_button.grid(row=5, columnspan=2, padx=10, pady=10, sticky="we")

        self.reference_listbox = tk.Listbox(master, width=60)
        self.reference_listbox.grid(row=6, columnspan=2, padx=10, pady=5, sticky="we")

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

        filename = "references.txt"
        with open(filename, "w") as f:
            for ref in self.references:
                if ref.link:
                    f.write(f"{ref.title} - {ref.author} ({ref.year}) - {ref.link}\n")
                else:
                    f.write(f"{ref.title} - {ref.author} ({ref.year})\n")

        messagebox.showinfo("Export Successful", f"References exported to {filename}.")

    def focus_next_entry(self, event, next_entry):
        next_entry.focus_set()

def main():
    root = tk.Tk()
    app = ReferenceManagerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()

