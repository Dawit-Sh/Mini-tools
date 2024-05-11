import tkinter as tk
from tkinter import messagebox

class ToDoListApp:
    def __init__(self, master):
        self.master = master
        self.master.title("To-Do List App")
        
        self.tasks = []
        self.create_widgets()
        
    def create_widgets(self):
        # Entry box for adding tasks
        self.task_entry = tk.Entry(self.master, width=50)
        self.task_entry.grid(row=0, column=0, padx=10, pady=10)
        
        # Button to add tasks
        self.add_button = tk.Button(self.master, text="Add Task", command=self.add_task)
        self.add_button.grid(row=0, column=1, padx=5, pady=10)
        
        # Listbox to display tasks
        self.task_listbox = tk.Listbox(self.master, width=60)
        self.task_listbox.grid(row=1, column=0, columnspan=2, padx=10, pady=5)
        
        # Buttons for progress, finished, and cancelled
        self.progress_button = tk.Button(self.master, text="Progress", command=self.mark_progress)
        self.progress_button.grid(row=2, column=0, padx=5, pady=5)
        
        self.finish_button = tk.Button(self.master, text="Finished", command=self.mark_finished)
        self.finish_button.grid(row=2, column=1, padx=5, pady=5)
        
        self.cancel_button = tk.Button(self.master, text="Cancelled", command=self.mark_cancelled)
        self.cancel_button.grid(row=3, column=0, columnspan=2, padx=5, pady=5)
        
    def add_task(self):
        task = self.task_entry.get()
        if task:
            self.tasks.append((task, "To-Do"))
            self.update_task_listbox()
            self.task_entry.delete(0, tk.END)
        else:
            messagebox.showwarning("Warning", "Please enter a task.")
            
    def update_task_listbox(self):
        self.task_listbox.delete(0, tk.END)
        for task, status in self.tasks:
            self.task_listbox.insert(tk.END, f"{task} - {status}")
            
    def mark_progress(self):
        selected_index = self.task_listbox.curselection()
        if selected_index:
            task_index = selected_index[0]
            task, _ = self.tasks[task_index]
            self.tasks[task_index] = (task, "In Progress")
            self.update_task_listbox()
        else:
            messagebox.showwarning("Warning", "Please select a task.")
            
    def mark_finished(self):
        selected_index = self.task_listbox.curselection()
        if selected_index:
            task_index = selected_index[0]
            task, _ = self.tasks[task_index]
            self.tasks[task_index] = (task, "Finished")
            self.update_task_listbox()
        else:
            messagebox.showwarning("Warning", "Please select a task.")
            
    def mark_cancelled(self):
        selected_index = self.task_listbox.curselection()
        if selected_index:
            task_index = selected_index[0]
            task, _ = self.tasks[task_index]
            self.tasks[task_index] = (task, "Cancelled")
            self.update_task_listbox()
        else:
            messagebox.showwarning("Warning", "Please select a task.")

def main():
    root = tk.Tk()
    app = ToDoListApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()

