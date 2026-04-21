"""
texpad — Simple & fast LaTeX / Typst editor with live PDF preview
Cross-platform: Windows / macOS / Linux

Dependencies:
    pip install PyQt5 PyMuPDF

Requires one of the following installed on your PATH:
    LaTeX:  pdflatex, xelatex, or lualatex
    Typst:  typst  (https://typst.app)
"""

import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import (
    QColor, QFont, QFontMetrics, QImage, QPalette, QPixmap, QSyntaxHighlighter,
    QTextCharFormat, QTextCursor,
)
from PyQt5.QtWidgets import (
    QAction, QApplication, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPlainTextEdit, QScrollArea, QSizePolicy, QSplitter,
    QStatusBar, QTabWidget, QToolBar, QVBoxLayout, QWidget, QComboBox,
    QPushButton, QFrame,
)

try:
    import fitz  # PyMuPDF
    PYMUPDF_OK = True
except ImportError:
    PYMUPDF_OK = False

# ── Dark palette ──────────────────────────────────────────────────────────────

BG      = QColor("#1a1b26")
BG2     = QColor("#16161e")
FG      = QColor("#c0caf5")
ACCENT  = QColor("#7aa2f7")
GREEN   = QColor("#9ece6a")
YELLOW  = QColor("#e0af68")
RED     = QColor("#f7768e")
COMMENT = QColor("#565f89")
STRING  = QColor("#9ece6a")
KEYWORD = QColor("#bb9af7")
COMMAND = QColor("#7aa2f7")
MATH    = QColor("#ff9e64")


def apply_palette(app: QApplication):
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.Window,          BG)
    p.setColor(QPalette.WindowText,      FG)
    p.setColor(QPalette.Base,            BG2)
    p.setColor(QPalette.AlternateBase,   BG)
    p.setColor(QPalette.Text,            FG)
    p.setColor(QPalette.Button,          BG2)
    p.setColor(QPalette.ButtonText,      FG)
    p.setColor(QPalette.Highlight,       ACCENT)
    p.setColor(QPalette.HighlightedText, BG)
    p.setColor(QPalette.PlaceholderText, COMMENT)
    app.setPalette(p)


# ── Syntax highlighters ───────────────────────────────────────────────────────

def _fmt(color: QColor, bold=False, italic=False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(color)
    if bold:
        f.setFontWeight(QFont.Bold)
    if italic:
        f.setFontItalic(True)
    return f


class LaTeXHighlighter(QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)
        self._rules = []

        # Comments
        self._rules.append((re.compile(r"%.*"), _fmt(COMMENT, italic=True)))
        # Math inline  $...$
        self._rules.append((re.compile(r'\$[^$]*\$'), _fmt(MATH)))
        # \command
        self._rules.append((re.compile(r'\\[a-zA-Z@]+\*?'), _fmt(COMMAND, bold=True)))
        # {braces}
        self._rules.append((re.compile(r'[{}]'), _fmt(ACCENT, bold=True)))
        # [options]
        self._rules.append((re.compile(r'\[.*?\]'), _fmt(YELLOW)))
        # begin/end
        self._rules.append((re.compile(r'\\(?:begin|end)\{[^}]+\}'), _fmt(GREEN, bold=True)))
        # Strings inside braces (simple)
        self._rules.append((re.compile(r'"[^"]*"'), _fmt(STRING)))

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


class TypstHighlighter(QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)
        self._rules = []

        # Comments
        self._rules.append((re.compile(r'//.*'), _fmt(COMMENT, italic=True)))
        self._rules.append((re.compile(r'/\*.*?\*/', re.DOTALL), _fmt(COMMENT, italic=True)))
        # Strings
        self._rules.append((re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"'), _fmt(STRING)))
        # Math  $...$  or  $[ ... ]$
        self._rules.append((re.compile(r'\$[^$]+\$'), _fmt(MATH)))
        # Keywords
        kw = r'\b(let|set|show|import|include|if|else|for|while|in|return|break|continue|not|and|or|true|false|none|auto)\b'
        self._rules.append((re.compile(kw), _fmt(KEYWORD, bold=True)))
        # Functions  #name
        self._rules.append((re.compile(r'#[a-zA-Z_][a-zA-Z0-9_]*'), _fmt(COMMAND, bold=True)))
        # Numbers
        self._rules.append((re.compile(r'\b\d+(?:\.\d+)?(?:pt|mm|cm|em|rem|%|fr)?\b'), _fmt(YELLOW)))
        # Headings  = Heading
        self._rules.append((re.compile(r'^=+ .+', re.MULTILINE), _fmt(ACCENT, bold=True)))

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


# ── Compiler thread ───────────────────────────────────────────────────────────

class CompileThread(QThread):
    done    = pyqtSignal(str, str, bool)   # pdf_path, log, success
    progress = pyqtSignal(str)

    def __init__(self, source: str, mode: str, engine: str, parent=None):
        super().__init__(parent)
        self.source = source
        self.mode   = mode     # "latex" or "typst"
        self.engine = engine   # e.g. "pdflatex", "typst"

    def run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ext = ".tex" if self.mode == "latex" else ".typ"
            src_file = os.path.join(tmpdir, "document" + ext)
            pdf_file = os.path.join(tmpdir, "document.pdf")

            with open(src_file, "w", encoding="utf-8") as f:
                f.write(self.source)

            self.progress.emit(f"Compiling with {self.engine}…")

            if self.mode == "latex":
                cmd = [self.engine, "-interaction=nonstopmode",
                       "-output-directory", tmpdir, src_file]
            else:
                cmd = ["typst", "compile", src_file, pdf_file]

            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=60,
                    cwd=tmpdir,
                )
                log = result.stdout + result.stderr
                if os.path.exists(pdf_file):
                    # Read PDF bytes and write to a stable temp file
                    stable = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
                    with open(pdf_file, "rb") as pf:
                        stable.write(pf.read())
                    stable.close()
                    self.done.emit(stable.name, log, True)
                else:
                    self.done.emit("", log, False)
            except subprocess.TimeoutExpired:
                self.done.emit("", "Compilation timed out after 60s.", False)
            except FileNotFoundError:
                self.done.emit("", f"Compiler '{self.engine}' not found on PATH.", False)
            except Exception as e:
                self.done.emit("", str(e), False)


# ── Editor widget ─────────────────────────────────────────────────────────────

class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("JetBrains Mono, Cascadia Code, Fira Code, Consolas, monospace")
        font.setPointSize(12)
        font.setFixedPitch(True)
        self.setFont(font)
        self.setTabStopDistance(QFontMetrics(font).horizontalAdvance(" ") * 4)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        p = self.palette()
        p.setColor(QPalette.Base, BG2)
        p.setColor(QPalette.Text, FG)
        self.setPalette(p)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Tab:
            self.insertPlainText("    ")
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter):
            # Auto-indent
            cursor = self.textCursor()
            block  = cursor.block().text()
            indent = re.match(r'^(\s*)', block).group(1)
            super().keyPressEvent(e)
            self.insertPlainText(indent)
        else:
            super().keyPressEvent(e)


# ── Preview panel ─────────────────────────────────────────────────────────────

class PdfPreview(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet(f"background: {BG2.name()};")
        self.setWidget(self._label)
        self.setStyleSheet(f"background: {BG2.name()}; border: none;")
        self._pdf_path = ""
        self._page = 0
        self._zoom = 1.5
        self._doc = None

    def load(self, path: str):
        self._pdf_path = path
        self._page = 0
        self._reload()

    def _reload(self):
        if not PYMUPDF_OK:
            self._label.setText(
                "<span style='color:#565f89'>PyMuPDF not installed.<br>"
                "Run: <code>pip install pymupdf</code><br>"
                "PDF saved to: " + self._pdf_path + "</span>"
            )
            return
        if not self._pdf_path or not os.path.exists(self._pdf_path):
            self._label.setText("<span style='color:#565f89'>No preview yet. Compile to see output.</span>")
            return
        try:
            if self._doc:
                self._doc.close()
            self._doc = fitz.open(self._pdf_path)
            self._render_page()
        except Exception as e:
            self._label.setText(f"<span style='color:#f7768e'>Preview error: {e}</span>")

    def _render_page(self):
        if not self._doc:
            return
        total = len(self._doc)
        page  = self._doc[min(self._page, total - 1)]
        mat   = fitz.Matrix(self._zoom * 2, self._zoom * 2)   # high-DPI
        pix   = page.get_pixmap(matrix=mat, alpha=False)
        img   = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
        pm    = QPixmap.fromImage(img)
        # Scale to fit width
        avail = self.viewport().width() - 20
        if pm.width() > avail:
            pm = pm.scaledToWidth(avail, Qt.SmoothTransformation)
        self._label.setPixmap(pm)
        self._label.setFixedSize(pm.size())

    def set_zoom(self, z: float):
        self._zoom = max(0.3, min(4.0, z))
        self._render_page()

    def next_page(self):
        if self._doc and self._page < len(self._doc) - 1:
            self._page += 1
            self._render_page()

    def prev_page(self):
        if self._page > 0:
            self._page -= 1
            self._render_page()

    def page_info(self) -> str:
        if self._doc:
            return f"Page {self._page + 1} / {len(self._doc)}"
        return ""

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._render_page()


# ── Main window ───────────────────────────────────────────────────────────────

LATEX_SKELETON = r"""\documentclass{article}
\usepackage[utf8]{inputenc}
\usepackage{amsmath, amssymb}
\usepackage{geometry}
\geometry{margin=2.5cm}

\title{My Document}
\author{Author}
\date{\today}

\begin{document}
\maketitle

\section{Introduction}
Hello, \LaTeX!

\end{document}
"""

TYPST_SKELETON = """#set document(title: "My Document", author: "Author")
#set page(margin: 2.5cm)
#set text(font: "Linux Libertine", size: 11pt)

= Introduction

Hello, *Typst*! This is a simple document.

== Section

Some text with _emphasis_ and $E = m c^2$.
"""


class TexPad(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TexPad")
        self.resize(1200, 760)

        self._current_file: str = ""
        self._compile_thread = None  # type: CompileThread | None
        self._auto_compile = False
        self._compile_timer = QTimer(self)
        self._compile_timer.setSingleShot(True)
        self._compile_timer.timeout.connect(self._compile)
        self._mode = "latex"  # "latex" or "typst"
        self._tmp_pdf = ""

        self._build_ui()
        self._new_document()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_toolbar()

        # Central splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)

        # Left: editor + log
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        self._editor = CodeEditor()
        self._editor.textChanged.connect(self._on_text_changed)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        self._log.setFont(QFont("Consolas", 9))
        self._log.setStyleSheet(f"background: {BG.name()}; color: #565f89; border: none; border-top: 1px solid #292e42;")
        self._log.setPlaceholderText("Compilation log will appear here…")

        left_layout.addWidget(self._editor, 1)
        left_layout.addWidget(self._log)

        # Right: preview
        self._preview = PdfPreview()

        splitter.addWidget(left)
        splitter.addWidget(self._preview)
        splitter.setSizes([560, 580])

        self.setCentralWidget(splitter)

        # Status bar
        self._status = self.statusBar()
        self._status.setStyleSheet(f"background: {BG2.name()}; color: #565f89;")

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        tb.setStyleSheet(f"""
            QToolBar {{ background: {BG2.name()}; border-bottom: 1px solid #292e42; padding: 4px 8px; spacing: 6px; }}
            QPushButton {{ background: #1f2335; border: 1px solid #292e42; color: #c0caf5;
                           padding: 4px 10px; border-radius: 4px; font-size: 12px; }}
            QPushButton:hover {{ background: #292e42; }}
            QPushButton:pressed {{ background: {ACCENT.name()}; color: #1a1b26; }}
            QComboBox {{ background: #1f2335; border: 1px solid #292e42; color: #c0caf5;
                         padding: 3px 8px; border-radius: 4px; font-size: 12px; min-width: 80px; }}
        """)
        self.addToolBar(tb)

        def btn(text, tip, cb):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(cb)
            tb.addWidget(b)
            return b

        btn("New",     "New document",     self._new_document)
        btn("Open",    "Open file",        self._open_file)
        btn("Save",    "Save  Ctrl+S",     self._save_file)
        btn("Save As", "Save as new file", self._save_as)
        tb.addSeparator()

        # Mode selector
        self._mode_cb = QComboBox()
        self._mode_cb.addItems(["LaTeX", "Typst"])
        self._mode_cb.currentTextChanged.connect(self._on_mode_change)
        tb.addWidget(self._mode_cb)

        # Engine selector
        self._engine_cb = QComboBox()
        self._engine_cb.addItems(["pdflatex", "xelatex", "lualatex"])
        tb.addWidget(self._engine_cb)

        tb.addSeparator()
        self._compile_btn = btn("⚡ Compile", "Compile  Ctrl+B", self._compile)
        self._compile_btn.setStyleSheet(
            f"background: {ACCENT.name()}; color: #1a1b26; border: none; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: bold;")

        # Auto-compile toggle
        self._auto_btn = QPushButton("Auto")
        self._auto_btn.setCheckable(True)
        self._auto_btn.setToolTip("Auto-compile on changes (1s delay)")
        self._auto_btn.toggled.connect(self._toggle_auto)
        tb.addWidget(self._auto_btn)

        tb.addSeparator()

        # Zoom
        btn("−", "Zoom out", lambda: self._preview.set_zoom(self._preview._zoom - 0.2))
        btn("+", "Zoom in",  lambda: self._preview.set_zoom(self._preview._zoom + 0.2))
        btn("◉", "Fit width", lambda: self._preview.set_zoom(1.5))

        # Page nav
        tb.addSeparator()
        btn("◂", "Previous page", self._preview.prev_page)
        btn("▸", "Next page",     self._preview.next_page)

        tb.addSeparator()
        btn("Open PDF", "Open compiled PDF in system viewer", self._open_external)

        # Keyboard shortcuts
        for key, cb in [("Ctrl+S", self._save_file), ("Ctrl+B", self._compile),
                         ("Ctrl+N", self._new_document), ("Ctrl+O", self._open_file)]:
            act = QAction(self)
            act.setShortcut(key)
            act.triggered.connect(cb)
            self.addAction(act)

    # ── Document lifecycle ────────────────────────────────────────────────────

    def _new_document(self):
        if self._mode == "typst":
            self._editor.setPlainText(TYPST_SKELETON)
        else:
            self._editor.setPlainText(LATEX_SKELETON)
        self._current_file = ""
        self._update_title()
        self._apply_highlighter()

    def _open_file(self):
        filters = "TeX/Typst files (*.tex *.typ);;All files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Open", "", filters)
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self._current_file = path
        ext = Path(path).suffix.lower()
        self._mode = "typst" if ext == ".typ" else "latex"
        self._mode_cb.setCurrentText("Typst" if self._mode == "typst" else "LaTeX")
        self._editor.setPlainText(text)
        self._apply_highlighter()
        self._update_title()

    def _save_file(self):
        if not self._current_file:
            self._save_as()
            return
        try:
            Path(self._current_file).write_text(self._editor.toPlainText(), encoding="utf-8")
            self._status.showMessage(f"Saved: {self._current_file}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _save_as(self):
        ext = ".typ" if self._mode == "typst" else ".tex"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save As", f"document{ext}",
            "TeX files (*.tex *.typ);;All files (*)"
        )
        if path:
            self._current_file = path
            self._save_file()
            self._update_title()

    def _update_title(self):
        name = Path(self._current_file).name if self._current_file else "untitled"
        self.setWindowTitle(f"TexPad — {name}")

    # ── Mode & highlighting ───────────────────────────────────────────────────

    def _on_mode_change(self, text: str):
        self._mode = "typst" if text == "Typst" else "latex"
        # Update engine box
        if self._mode == "typst":
            self._engine_cb.clear()
            self._engine_cb.addItems(["typst"])
        else:
            self._engine_cb.clear()
            self._engine_cb.addItems(["pdflatex", "xelatex", "lualatex"])
        self._apply_highlighter()

    def _apply_highlighter(self):
        if self._mode == "typst":
            TypstHighlighter(self._editor.document())
        else:
            LaTeXHighlighter(self._editor.document())

    # ── Compilation ───────────────────────────────────────────────────────────

    def _on_text_changed(self):
        if self._auto_compile:
            self._compile_timer.start(1200)
        # Update word/line count
        text = self._editor.toPlainText()
        lines = text.count("\n") + 1
        words = len(text.split())
        page_info = self._preview.page_info()
        self._status.showMessage(f"Lines: {lines}  Words: {words}   {page_info}")

    def _toggle_auto(self, checked: bool):
        self._auto_compile = checked
        self._auto_btn.setText("Auto ✓" if checked else "Auto")

    def _compile(self):
        if self._compile_thread and self._compile_thread.isRunning():
            return
        source = self._editor.toPlainText()
        if not source.strip():
            return
        engine = self._engine_cb.currentText()
        mode   = self._mode
        self._log.clear()
        self._status.showMessage("Compiling…")
        self._compile_btn.setEnabled(False)

        self._compile_thread = CompileThread(source, mode, engine)
        self._compile_thread.done.connect(self._on_compile_done)
        self._compile_thread.progress.connect(lambda m: self._status.showMessage(m))
        self._compile_thread.start()

    def _on_compile_done(self, pdf_path: str, log: str, success: bool):
        self._compile_btn.setEnabled(True)
        # Clean up old temp PDF
        if self._tmp_pdf and os.path.exists(self._tmp_pdf):
            try:
                os.unlink(self._tmp_pdf)
            except Exception:
                pass
        self._tmp_pdf = pdf_path

        log_lines = [l for l in log.splitlines() if l.strip()]
        log_preview = "\n".join(log_lines[-40:])
        self._log.setPlainText(log_preview)

        if success:
            self._preview.load(pdf_path)
            page_info = self._preview.page_info()
            self._status.showMessage(f"Compiled OK   {page_info}")
            self._log.setStyleSheet(f"background:{BG.name()};color:#9ece6a;border:none;border-top:1px solid #292e42;")
        else:
            self._status.showMessage("Compilation failed — see log")
            self._log.setStyleSheet(f"background:{BG.name()};color:#f7768e;border:none;border-top:1px solid #292e42;")

    def _open_external(self):
        if not self._tmp_pdf or not os.path.exists(self._tmp_pdf):
            QMessageBox.information(self, "No PDF", "Compile first to generate a PDF.")
            return
        import subprocess, platform
        if platform.system() == "Windows":
            os.startfile(self._tmp_pdf)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", self._tmp_pdf])
        else:
            subprocess.Popen(["xdg-open", self._tmp_pdf])

    def closeEvent(self, e):
        if self._tmp_pdf and os.path.exists(self._tmp_pdf):
            try:
                os.unlink(self._tmp_pdf)
            except Exception:
                pass
        super().closeEvent(e)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("TexPad")
    app.setFont(QFont("Segoe UI, Arial", 10))
    apply_palette(app)

    window = TexPad()

    # Open file passed as argument
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        window._current_file = sys.argv[1]
        try:
            p = Path(sys.argv[1])
            window._mode = "typst" if p.suffix.lower() == ".typ" else "latex"
            window._mode_cb.setCurrentText("Typst" if window._mode == "typst" else "LaTeX")
            window._editor.setPlainText(p.read_text(encoding="utf-8"))
            window._apply_highlighter()
            window._update_title()
        except Exception:
            pass

    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
