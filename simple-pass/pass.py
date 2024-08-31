import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import secrets
import string
from cryptography.fernet import Fernet
import base64
import os

class PasswordManager:
    def __init__(self, master):
        self.master = master
        master.title("Password Manager")
        master.geometry("600x400")
        master.configure(bg="#2E2E2E")

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('.', background='#2E2E2E', foreground='#FFFFFF')
        self.style.configure('TLabel', background='#2E2E2E', foreground='#FFFFFF')
        self.style.configure('TButton', background='#4CAF50', foreground='#FFFFFF')
        self.style.map('TButton', background=[('active', '#45A049')])
        self.style.configure('Treeview', background='#3E3E3E', foreground='#FFFFFF', fieldbackground='#3E3E3E')
        self.style.map('Treeview', background=[('selected', '#4CAF50')])

        self.frame = ttk.Frame(master, padding="20")
        self.frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        master.grid_columnconfigure(0, weight=1)
        master.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(self.frame, columns=('Service', 'Username'), show='headings')
        self.tree.heading('Service', text='Service')
        self.tree.heading('Username', text='Username')
        self.tree.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.scrollbar = ttk.Scrollbar(self.frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.scrollbar.grid(row=0, column=2, sticky=(tk.N, tk.S))
        self.tree.configure(yscrollcommand=self.scrollbar.set)

        self.add_button = ttk.Button(self.frame, text="Add Password", command=self.add_password)
        self.add_button.grid(row=1, column=0, pady=10, sticky=tk.W)

        self.view_button = ttk.Button(self.frame, text="View Password", command=self.view_password)
        self.view_button.grid(row=1, column=1, pady=10)

        self.update_button = ttk.Button(self.frame, text="Update Password", command=self.update_password)
        self.update_button.grid(row=2, column=0, pady=10, sticky=tk.W)

        self.delete_button = ttk.Button(self.frame, text="Delete Password", command=self.delete_password)
        self.delete_button.grid(row=2, column=1, pady=10)

        self.generate_button = ttk.Button(self.frame, text="Generate Password", command=self.generate_password)
        self.generate_button.grid(row=3, column=0, columnspan=2, pady=10, sticky=(tk.W, tk.E))

        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)
        self.frame.rowconfigure(0, weight=1)

        self.conn = sqlite3.connect('passwords.db')
        self.create_table()
        self.load_passwords()

        self.key = self.load_or_generate_key()
        self.cipher_suite = Fernet(self.key)

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS passwords
            (id INTEGER PRIMARY KEY,
             service TEXT,
             username TEXT,
             password TEXT)
        ''')
        self.conn.commit()

    def load_or_generate_key(self):
        key_file = 'encryption_key.key'
        if os.path.exists(key_file):
            with open(key_file, 'rb') as file:
                key = file.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as file:
                file.write(key)
        return key

    def load_passwords(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT service, username FROM passwords')
        for row in cursor.fetchall():
            self.tree.insert('', 'end', values=row)

    def add_password(self):
        service = simpledialog.askstring("Add Password", "Enter service name:")
        if not service:
            return
        username = simpledialog.askstring("Add Password", "Enter username:")
        if not username:
            return
        password = simpledialog.askstring("Add Password", "Enter password:", show='*')
        if not password:
            return

        encrypted_password = self.cipher_suite.encrypt(password.encode()).decode()

        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO passwords (service, username, password) VALUES (?, ?, ?)',
                       (service, username, encrypted_password))
        self.conn.commit()

        self.tree.insert('', 'end', values=(service, username))

    def view_password(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a password to view.")
            return

        service = self.tree.item(selected_item)['values'][0]

        cursor = self.conn.cursor()
        cursor.execute('SELECT password FROM passwords WHERE service = ?', (service,))
        encrypted_password = cursor.fetchone()[0]

        decrypted_password = self.cipher_suite.decrypt(encrypted_password.encode()).decode()

        messagebox.showinfo("Password", f"Password for {service}: {decrypted_password}")

    def update_password(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a password to update.")
            return

        service = self.tree.item(selected_item)['values'][0]
        new_password = simpledialog.askstring("Update Password", f"Enter new password for {service}:", show='*')
        if not new_password:
            return

        encrypted_password = self.cipher_suite.encrypt(new_password.encode()).decode()

        cursor = self.conn.cursor()
        cursor.execute('UPDATE passwords SET password = ? WHERE service = ?', (encrypted_password, service))
        self.conn.commit()

        messagebox.showinfo("Success", f"Password for {service} updated successfully.")

    def delete_password(self):
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("No Selection", "Please select a password to delete.")
            return

        service = self.tree.item(selected_item)['values'][0]

        if messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete the password for {service}?"):
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM passwords WHERE service = ?', (service,))
            self.conn.commit()

            self.tree.delete(selected_item)

    def generate_password(self):
        length = simpledialog.askinteger("Generate Password", "Enter password length:", minvalue=8, maxvalue=32)
        if not length:
            return

        alphabet = string.ascii_letters + string.digits + string.punctuation
        password = ''.join(secrets.choice(alphabet) for _ in range(length))

        messagebox.showinfo("Generated Password", f"Generated password: {password}")

    def __del__(self):
        self.conn.close()

def main():
    root = tk.Tk()
    app = PasswordManager(root)
    root.mainloop()

if __name__ == "__main__":
    main()
