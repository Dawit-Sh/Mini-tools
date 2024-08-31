import sys
import csv
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QTabWidget, 
                             QLabel, QTextEdit, QSplitter, QInputDialog, QCheckBox, QScrollArea)
from PyQt5.QtGui import QPalette, QColor, QFont
from PyQt5.QtCore import Qt, pyqtSignal
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class Task:
    def __init__(self, title, description, status="Pending"):
        self.title = title
        self.description = description
        self.status = status

class TaskItemWidget(QWidget):
    status_changed = pyqtSignal(object)
    task_clicked = pyqtSignal(object)

    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task
        self.init_ui()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        self.status_checkbox = QCheckBox()
        self.status_checkbox.clicked.connect(self.update_status)
        self.status_checkbox.setFixedSize(20, 20)

        self.title_label = QLabel(self.task.title)
        self.title_label.setStyleSheet("color: #ECEFF4; font-size: 14px;")
        self.title_label.setWordWrap(True)
        self.title_label.setMinimumWidth(200)  # Ensure minimum width for readability
        self.title_label.mousePressEvent = self.on_title_click

        layout.addWidget(self.status_checkbox)
        layout.addWidget(self.title_label, 1)

        self.update_status_style()

    def update_status(self):
        if self.task.status == "Pending":
            self.task.status = "Finished"
        elif self.task.status == "Finished":
            self.task.status = "Cancelled"
        else:
            self.task.status = "Pending"
        self.update_status_style()
        self.status_changed.emit(self.task)

    def update_status_style(self):
        if self.task.status == "Pending":
            self.status_checkbox.setStyleSheet("""
                QCheckBox::indicator {
                    background-color: #3B4252;
                    border: 1px solid #D8DEE9;
                    border-radius: 2px;
                    width: 18px;
                    height: 18px;
                }
            """)
            self.title_label.setStyleSheet("color: #ECEFF4; font-size: 14px;")
        elif self.task.status == "Finished":
            self.status_checkbox.setStyleSheet("""
                QCheckBox::indicator {
                    background-color: #A3BE8C;
                    border: 1px solid #D8DEE9;
                    border-radius: 2px;
                    width: 18px;
                    height: 18px;
                }
            """)
            self.title_label.setStyleSheet("color: #A3BE8C; font-size: 14px; text-decoration: line-through;")
        else:  # Cancelled
            self.status_checkbox.setStyleSheet("""
                QCheckBox::indicator {
                    background-color: #BF616A;
                    border: 1px solid #D8DEE9;
                    border-radius: 2px;
                    width: 18px;
                    height: 18px;
                }
            """)
            self.title_label.setStyleSheet("color: #BF616A; font-size: 14px;")

    def on_title_click(self, event):
        self.task_clicked.emit(self.task)

class TodoApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("My Todolist")
        self.setGeometry(100, 100, 800, 600)

        self.tasks = self.load_tasks()

        main_widget = QTabWidget()
        self.setCentralWidget(main_widget)

        # Task management tab
        task_management_widget = QWidget()
        task_management_layout = QVBoxLayout()
        task_management_widget.setLayout(task_management_layout)

        # Input area
        input_layout = QHBoxLayout()
        self.task_input = QLineEdit()
        self.task_input.setPlaceholderText("Enter a new task...")
        self.task_input.setStyleSheet("padding: 8px; border-radius: 4px; background: #3B4252; color: #ECEFF4;")
        self.task_input.returnPressed.connect(self.add_task)
        add_button = QPushButton("Add")
        add_button.setStyleSheet("padding: 8px 16px; background: #5E81AC; color: #ECEFF4; border: none; border-radius: 4px;")
        add_button.clicked.connect(self.add_task)
        input_layout.addWidget(self.task_input)
        input_layout.addWidget(add_button)
        task_management_layout.addLayout(input_layout)

        # Task lists
        lists_layout = QHBoxLayout()
        self.pending_list = QListWidget()
        self.finished_list = QListWidget()
        self.cancelled_list = QListWidget()

        for task_list in [self.pending_list, self.finished_list, self.cancelled_list]:
            task_list.setStyleSheet("""
                QListWidget {
                    background-color: #3B4252;
                    border: none;
                    border-radius: 4px;
                }
                QListWidget::item {
                    padding: 5px;
                    margin: 2px 0;
                }
            """)
            task_list.setSpacing(2)
            task_list.setVerticalScrollMode(QListWidget.ScrollPerPixel)

        lists_layout.addWidget(self.create_list_with_label("Pending", self.pending_list))
        lists_layout.addWidget(self.create_list_with_label("Finished", self.finished_list))
        lists_layout.addWidget(self.create_list_with_label("Cancelled", self.cancelled_list))
        task_management_layout.addLayout(lists_layout)

        # Statistics tab
        statistics_widget = QWidget()
        statistics_layout = QVBoxLayout()
        statistics_widget.setLayout(statistics_layout)

        self.figure, self.ax = plt.subplots(figsize=(5, 4))
        self.canvas = FigureCanvas(self.figure)
        statistics_layout.addWidget(self.canvas)

        # Add tabs
        main_widget.addTab(task_management_widget, "Tasks")
        main_widget.addTab(statistics_widget, "Statistics")

        self.load_tasks_to_lists()
        self.update_graph()

    def create_list_with_label(self, label, list_widget):
        container = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(QLabel(label))
        layout.addWidget(list_widget)
        container.setLayout(layout)
        return container

    def add_task(self):
        title = self.task_input.text()
        if title:
            description, ok = QInputDialog.getMultiLineText(self, "Task Description", "Enter task description:")
            if ok:
                task = Task(title, description)
                self.tasks.append(task)
                self.add_task_to_list(task)
                self.task_input.clear()
                self.save_tasks()
                self.update_graph()

    def add_task_to_list(self, task):
        item = QListWidgetItem(self.pending_list)
        task_widget = TaskItemWidget(task)
        task_widget.status_changed.connect(self.on_task_status_changed)
        task_widget.task_clicked.connect(self.show_task_description)
        item.setSizeHint(task_widget.sizeHint())
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        self.pending_list.addItem(item)
        self.pending_list.setItemWidget(item, task_widget)

    def on_task_status_changed(self, task):
        self.remove_task_from_all_lists(task)
        if task.status == "Pending":
            self.add_task_to_list(task)
        elif task.status == "Finished":
            self.add_task_to_finished_list(task)
        else:  # Cancelled
            self.add_task_to_cancelled_list(task)
        self.save_tasks()
        self.update_graph()

    def remove_task_from_all_lists(self, task):
        for list_widget in [self.pending_list, self.finished_list, self.cancelled_list]:
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                widget = list_widget.itemWidget(item)
                if widget.task == task:
                    list_widget.takeItem(i)
                    break

    def add_task_to_finished_list(self, task):
        item = QListWidgetItem(self.finished_list)
        task_widget = TaskItemWidget(task)
        task_widget.status_changed.connect(self.on_task_status_changed)
        task_widget.task_clicked.connect(self.show_task_description)
        item.setSizeHint(task_widget.sizeHint())
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        self.finished_list.addItem(item)
        self.finished_list.setItemWidget(item, task_widget)

    def add_task_to_cancelled_list(self, task):
        item = QListWidgetItem(self.cancelled_list)
        task_widget = TaskItemWidget(task)
        task_widget.status_changed.connect(self.on_task_status_changed)
        task_widget.task_clicked.connect(self.show_task_description)
        item.setSizeHint(task_widget.sizeHint())
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        self.cancelled_list.addItem(item)
        self.cancelled_list.setItemWidget(item, task_widget)

    def show_task_description(self, task):
        QMessageBox.information(self, "Task Description", f"Title: {task.title}\n\nDescription: {task.description}")

    def update_graph(self):
        status_counts = {
            "Pending": self.pending_list.count(),
            "Finished": self.finished_list.count(),
            "Cancelled": self.cancelled_list.count()
        }

        self.ax.clear()
        statuses = list(status_counts.keys())
        counts = list(status_counts.values())
        colors = ['#EBCB8B', '#A3BE8C', '#BF616A']
        
        self.ax.bar(statuses, counts, color=colors)
        self.ax.set_title("Task Status Distribution", color='white')
        self.ax.set_ylabel("Number of Tasks", color='white')
        self.ax.tick_params(axis='x', colors='white')
        self.ax.tick_params(axis='y', colors='white')
        
        for i, v in enumerate(counts):
            self.ax.text(i, v, str(v), ha='center', va='bottom', color='white')
        
        self.figure.patch.set_facecolor('#2E3440')
        self.ax.set_facecolor('#3B4252')
        
        self.canvas.draw()

    def save_tasks(self):
        with open('tasks.csv', 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['Title', 'Description', 'Status'])
            for task in self.tasks:
                writer.writerow([task.title, task.description, task.status])

    def load_tasks(self):
        tasks = []
        try:
            with open('tasks.csv', 'r') as file:
                reader = csv.reader(file)
                next(reader)  # Skip header
                for row in reader:
                    tasks.append(Task(row[0], row[1], row[2]))
        except FileNotFoundError:
            pass
        return tasks

    def load_tasks_to_lists(self):
        for task in self.tasks:
            if task.status == "Pending":
                self.add_task_to_list(task)
            elif task.status == "Finished":
                self.add_task_to_finished_list(task)
            else:
                self.add_task_to_cancelled_list(task)

def set_dark_theme(app):
    app.setStyle("Fusion")
    app.setFont(QFont('Arial', 10))
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(46, 52, 64))
    palette.setColor(QPalette.WindowText, QColor(236, 239, 244))
    palette.setColor(QPalette.Base, QColor(59, 66, 82))
    palette.setColor(QPalette.AlternateBase, QColor(67, 76, 94))
    palette.setColor(QPalette.ToolTipBase, QColor(236, 239, 244))
    palette.setColor(QPalette.ToolTipText, QColor(236, 239, 244))
    palette.setColor(QPalette.Text, QColor(236, 239, 244))
    palette.setColor(QPalette.Button, QColor(59, 66, 82))
    palette.setColor(QPalette.ButtonText, QColor(236, 239, 244))
    palette.setColor(QPalette.BrightText, QColor(236, 239, 244))
    palette.setColor(QPalette.Link, QColor(143, 188, 187))
    palette.setColor(QPalette.Highlight, QColor(143, 188, 187))
    palette.setColor(QPalette.HighlightedText, QColor(46, 52, 64))
    app.setPalette(palette)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    set_dark_theme(app)
    window = TodoApp()
    window.show()
    sys.exit(app.exec_())
