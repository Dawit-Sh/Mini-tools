import sys
import csv
import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QTabWidget, QLabel, QTextEdit, QInputDialog, QCheckBox, QDialog,
    QDialogButtonBox, QFormLayout, QComboBox, QFrame, QSplitter,
)
from PyQt5.QtGui import QPalette, QColor, QFont, QIcon
from PyQt5.QtCore import Qt, pyqtSignal
import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks.csv")

PRIORITY_COLORS = {
    "High":   "#BF616A",
    "Medium": "#EBCB8B",
    "Low":    "#A3BE8C",
}

STATUS_COLORS = {
    "Pending":   "#EBCB8B",
    "Finished":  "#A3BE8C",
    "Cancelled": "#BF616A",
}


class Task:
    def __init__(self, title, description="", status="Pending",
                 priority="Medium", created="", due=""):
        self.title = title
        self.description = description
        self.status = status
        self.priority = priority
        self.created = created or datetime.now().strftime("%Y-%m-%d %H:%M")
        self.due = due


class TaskDialog(QDialog):
    def __init__(self, parent=None, task: Task = None):
        super().__init__(parent)
        self.setWindowTitle("Task" if task is None else "Edit Task")
        self.setMinimumWidth(420)
        layout = QFormLayout(self)

        self._title = QLineEdit(task.title if task else "")
        self._title.setPlaceholderText("Required")
        layout.addRow("Title *:", self._title)

        self._desc = QTextEdit()
        self._desc.setFixedHeight(80)
        if task:
            self._desc.setPlainText(task.description)
        layout.addRow("Description:", self._desc)

        self._priority = QComboBox()
        self._priority.addItems(["High", "Medium", "Low"])
        if task:
            self._priority.setCurrentText(task.priority)
        layout.addRow("Priority:", self._priority)

        self._due = QLineEdit(task.due if task else "")
        self._due.setPlaceholderText("YYYY-MM-DD (optional)")
        layout.addRow("Due date:", self._due)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self._title.setFocus()

    def _validate(self):
        if not self._title.text().strip():
            QMessageBox.warning(self, "Incomplete", "Title is required.")
            return
        self.accept()

    def get_task_data(self):
        return {
            "title": self._title.text().strip(),
            "description": self._desc.toPlainText().strip(),
            "priority": self._priority.currentText(),
            "due": self._due.text().strip(),
        }


class TaskItemWidget(QWidget):
    status_changed = pyqtSignal(object)
    edit_requested = pyqtSignal(object)
    delete_requested = pyqtSignal(object)

    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self.task = task
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        # Priority dot
        dot = QLabel("●")
        dot.setFixedWidth(16)
        dot.setStyleSheet(f"color: {PRIORITY_COLORS.get(self.task.priority, '#EBCB8B')}; font-size: 10px;")
        layout.addWidget(dot)

        # Checkbox cycles status
        self._cb = QCheckBox()
        self._cb.setFixedSize(20, 20)
        self._cb.clicked.connect(self._cycle_status)
        layout.addWidget(self._cb)

        # Title
        self._title_lbl = QLabel(self.task.title)
        self._title_lbl.setWordWrap(True)
        self._title_lbl.setMinimumWidth(160)
        self._title_lbl.setCursor(Qt.PointingHandCursor)
        self._title_lbl.mousePressEvent = self._on_title_click
        layout.addWidget(self._title_lbl, 1)

        # Due date
        if self.task.due:
            due_lbl = QLabel(f"📅 {self.task.due}")
            due_lbl.setStyleSheet("color: #88C0D0; font-size: 11px;")
            layout.addWidget(due_lbl)

        # Edit / Delete buttons
        for icon, sig in [("✎", self.edit_requested), ("✕", self.delete_requested)]:
            btn = QPushButton(icon)
            btn.setFixedSize(24, 24)
            btn.setStyleSheet("QPushButton { background: transparent; color: #888; border: none; font-size: 14px; }"
                              "QPushButton:hover { color: #ECEFF4; }")
            btn.clicked.connect(lambda _, s=sig: s.emit(self.task))
            layout.addWidget(btn)

        self._apply_style()

    def _cycle_status(self):
        order = ["Pending", "Finished", "Cancelled"]
        idx = order.index(self.task.status)
        self.task.status = order[(idx + 1) % len(order)]
        self._apply_style()
        self.status_changed.emit(self.task)

    def _apply_style(self):
        s = self.task.status
        colors = {"Pending": "#ECEFF4", "Finished": "#A3BE8C", "Cancelled": "#BF616A"}
        td = "line-through" if s == "Finished" else "none"
        self._title_lbl.setStyleSheet(
            f"color: {colors[s]}; font-size: 14px; text-decoration: {td};")
        cb_bg = STATUS_COLORS.get(s, "#3B4252")
        self._cb.setStyleSheet(f"""
            QCheckBox::indicator {{
                background-color: {cb_bg};
                border: 1px solid #D8DEE9;
                border-radius: 2px;
                width: 18px; height: 18px;
            }}
        """)

    def _on_title_click(self, event):
        msg = f"<b>{self.task.title}</b>"
        if self.task.description:
            msg += f"<br><br>{self.task.description}"
        parts = [f"Status: {self.task.status}", f"Priority: {self.task.priority}",
                 f"Created: {self.task.created}"]
        if self.task.due:
            parts.append(f"Due: {self.task.due}")
        msg += "<br><br><small>" + " &nbsp;|&nbsp; ".join(parts) + "</small>"
        QMessageBox.information(self.parentWidget(), "Task Details", msg)


class TodoApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple Todo")
        self.setGeometry(100, 100, 900, 640)
        self.tasks: list[Task] = self._load_tasks()

        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        tabs.addTab(self._build_task_tab(), "Tasks")
        tabs.addTab(self._build_stats_tab(), "Statistics")

        self._populate_lists()
        self._update_graph()

    # ── task tab ──────────────────────────────────────────────────────────────

    def _build_task_tab(self):
        w = QWidget()
        vbox = QVBoxLayout(w)

        # Toolbar row
        toolbar = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search tasks…")
        self._search.setStyleSheet("padding: 6px; border-radius: 4px; background: #3B4252; color: #ECEFF4;")
        self._search.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search, 1)

        self._filter_cb = QComboBox()
        self._filter_cb.addItems(["All", "Pending", "Finished", "Cancelled"])
        self._filter_cb.setStyleSheet("padding: 4px; background: #3B4252; color: #ECEFF4;")
        self._filter_cb.currentIndexChanged.connect(self._on_search)
        toolbar.addWidget(self._filter_cb)

        self._priority_filter = QComboBox()
        self._priority_filter.addItems(["Any Priority", "High", "Medium", "Low"])
        self._priority_filter.setStyleSheet("padding: 4px; background: #3B4252; color: #ECEFF4;")
        self._priority_filter.currentIndexChanged.connect(self._on_search)
        toolbar.addWidget(self._priority_filter)
        vbox.addLayout(toolbar)

        # Input row
        input_row = QHBoxLayout()
        self._task_input = QLineEdit()
        self._task_input.setPlaceholderText("Quick-add task title (Enter to open details)…")
        self._task_input.setStyleSheet("padding: 8px; border-radius: 4px; background: #3B4252; color: #ECEFF4;")
        self._task_input.returnPressed.connect(self._quick_add)
        input_row.addWidget(self._task_input, 1)
        add_btn = QPushButton("＋ Add")
        add_btn.setStyleSheet("padding: 8px 14px; background: #5E81AC; color: #ECEFF4; border: none; border-radius: 4px;")
        add_btn.clicked.connect(self._quick_add)
        input_row.addWidget(add_btn)
        vbox.addLayout(input_row)

        # Lists
        lists_row = QHBoxLayout()
        self.pending_list   = QListWidget()
        self.finished_list  = QListWidget()
        self.cancelled_list = QListWidget()

        for lw in (self.pending_list, self.finished_list, self.cancelled_list):
            lw.setStyleSheet("""
                QListWidget { background: #3B4252; border: none; border-radius: 4px; }
                QListWidget::item { padding: 4px; margin: 2px 0; }
            """)
            lw.setSpacing(2)
            lw.setVerticalScrollMode(QListWidget.ScrollPerPixel)

        for title, lw in [("Pending", self.pending_list),
                           ("Finished", self.finished_list),
                           ("Cancelled", self.cancelled_list)]:
            col = QWidget()
            cl = QVBoxLayout(col)
            lbl = QLabel(title)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color: {STATUS_COLORS[title]}; font-weight: bold; font-size: 13px;")
            cl.addWidget(lbl)
            cl.addWidget(lw)
            lists_row.addWidget(col)

        vbox.addLayout(lists_row)

        # Stats bar
        self._stats_label = QLabel()
        self._stats_label.setStyleSheet("color: #88C0D0; font-size: 11px;")
        vbox.addWidget(self._stats_label)
        return w

    # ── stats tab ─────────────────────────────────────────────────────────────

    def _build_stats_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.figure, self.ax = plt.subplots(figsize=(6, 4))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)
        return w

    # ── populate / filter ─────────────────────────────────────────────────────

    def _populate_lists(self):
        for lw in (self.pending_list, self.finished_list, self.cancelled_list):
            lw.clear()
        q = self._search.text().lower() if hasattr(self, "_search") else ""
        status_f = self._filter_cb.currentText() if hasattr(self, "_filter_cb") else "All"
        priority_f = self._priority_filter.currentText() if hasattr(self, "_priority_filter") else "Any Priority"

        for task in sorted(self.tasks, key=lambda t: ("High", "Medium", "Low").index(t.priority)):
            if q and q not in task.title.lower() and q not in task.description.lower():
                continue
            if status_f != "All" and task.status != status_f:
                continue
            if priority_f != "Any Priority" and task.priority != priority_f:
                continue
            self._add_to_list(task)

        self._update_stats_label()

    def _add_to_list(self, task: Task):
        lw = {"Pending": self.pending_list,
              "Finished": self.finished_list,
              "Cancelled": self.cancelled_list}.get(task.status, self.pending_list)
        item = QListWidgetItem(lw)
        widget = TaskItemWidget(task)
        widget.status_changed.connect(self._on_status_changed)
        widget.edit_requested.connect(self._edit_task)
        widget.delete_requested.connect(self._delete_task)
        item.setSizeHint(widget.sizeHint())
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        lw.addItem(item)
        lw.setItemWidget(item, widget)

    def _on_search(self):
        self._populate_lists()

    # ── task operations ───────────────────────────────────────────────────────

    def _quick_add(self):
        title = self._task_input.text().strip()
        if not title:
            return
        dlg = TaskDialog(self, task=Task(title))
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_task_data()
            task = Task(**data)
            self.tasks.append(task)
            self._task_input.clear()
            self._populate_lists()
            self._save_tasks()
            self._update_graph()

    def _on_status_changed(self, task: Task):
        self._populate_lists()
        self._save_tasks()
        self._update_graph()

    def _edit_task(self, task: Task):
        dlg = TaskDialog(self, task=task)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_task_data()
            task.title = data["title"]
            task.description = data["description"]
            task.priority = data["priority"]
            task.due = data["due"]
            self._populate_lists()
            self._save_tasks()
            self._update_graph()

    def _delete_task(self, task: Task):
        reply = QMessageBox.question(self, "Delete Task",
                                     f"Delete '{task.title}'?",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.tasks.remove(task)
            self._populate_lists()
            self._save_tasks()
            self._update_graph()

    # ── graph ─────────────────────────────────────────────────────────────────

    def _update_graph(self):
        counts = {s: sum(1 for t in self.tasks if t.status == s)
                  for s in ("Pending", "Finished", "Cancelled")}
        p_counts = {p: sum(1 for t in self.tasks if t.priority == p)
                    for p in ("High", "Medium", "Low")}

        self.ax.clear()
        fig_bg = "#2E3440"
        ax_bg  = "#3B4252"
        self.figure.patch.set_facecolor(fig_bg)
        self.ax.set_facecolor(ax_bg)

        statuses = list(counts.keys())
        vals = list(counts.values())
        bars = self.ax.bar(statuses, vals, color=["#EBCB8B", "#A3BE8C", "#BF616A"], width=0.5)
        for bar, v in zip(bars, vals):
            self.ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                         str(v), ha="center", va="bottom", color="white", fontsize=11)

        self.ax.set_title("Task Status Distribution", color="white", fontsize=12)
        self.ax.set_ylabel("Count", color="white")
        for spine in self.ax.spines.values():
            spine.set_edgecolor("#4C566A")
        self.ax.tick_params(colors="white")
        self.ax.set_ylim(0, max(max(vals, default=0) + 1, 4))

        self.canvas.draw()

    # ── stats label ───────────────────────────────────────────────────────────

    def _update_stats_label(self):
        total = len(self.tasks)
        done = sum(1 for t in self.tasks if t.status == "Finished")
        pct = int(done / total * 100) if total else 0
        self._stats_label.setText(
            f"Total: {total}  |  Finished: {done}  |  Progress: {pct}%"
        )

    # ── persistence ───────────────────────────────────────────────────────────

    def _save_tasks(self):
        with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Title", "Description", "Status", "Priority", "Created", "Due"])
            for t in self.tasks:
                w.writerow([t.title, t.description, t.status, t.priority, t.created, t.due])

    def _load_tasks(self) -> list[Task]:
        tasks = []
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader)
                for row in reader:
                    if len(row) >= 3:
                        title, desc, status = row[0], row[1], row[2]
                        priority = row[3] if len(row) > 3 else "Medium"
                        created  = row[4] if len(row) > 4 else ""
                        due      = row[5] if len(row) > 5 else ""
                        tasks.append(Task(title, desc, status, priority, created, due))
        except FileNotFoundError:
            pass
        return tasks


def set_dark_theme(app):
    app.setStyle("Fusion")
    app.setFont(QFont("Arial", 10))
    p = QPalette()
    p.setColor(QPalette.Window,          QColor(46, 52, 64))
    p.setColor(QPalette.WindowText,      QColor(236, 239, 244))
    p.setColor(QPalette.Base,            QColor(59, 66, 82))
    p.setColor(QPalette.AlternateBase,   QColor(67, 76, 94))
    p.setColor(QPalette.Text,            QColor(236, 239, 244))
    p.setColor(QPalette.Button,          QColor(59, 66, 82))
    p.setColor(QPalette.ButtonText,      QColor(236, 239, 244))
    p.setColor(QPalette.Highlight,       QColor(94, 129, 172))
    p.setColor(QPalette.HighlightedText, QColor(46, 52, 64))
    app.setPalette(p)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    set_dark_theme(app)
    window = TodoApp()
    window.show()
    sys.exit(app.exec_())
