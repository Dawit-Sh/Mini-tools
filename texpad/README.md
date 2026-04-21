# texpad

Simple and fast LaTeX / Typst editor with live PDF preview.

## Features

- Split-pane: syntax-highlighted editor on the left, rendered PDF preview on the right
- Syntax highlighting for both `.tex` (LaTeX) and `.typ` (Typst) files
- Background compilation — non-blocking, UI stays responsive
- **Auto-compile** mode — recompiles 1.2s after you stop typing
- Compiler selection: `pdflatex`, `xelatex`, `lualatex`, or `typst`
- Error log panel — shows the last 40 lines of compiler output
- PDF preview with zoom in/out, page navigation, fit-width
- Open compiled PDF in system viewer
- Auto-indent, 4-space tab, keyboard shortcuts
- Dark theme (Tokyo Night palette)

## Usage

```bash
pip install PyQt5 PyMuPDF
python texpad.py              # new blank document
python texpad.py myfile.tex   # open existing file
python texpad.py myfile.typ   # open Typst file
```

## Keyboard shortcuts

| Key | Action |
|---|---|
| `Ctrl+B` | Compile |
| `Ctrl+S` | Save |
| `Ctrl+N` | New document |
| `Ctrl+O` | Open file |

## External requirements

At least one of the following must be on your PATH:

| Format | Install |
|---|---|
| **LaTeX** | [TeX Live](https://tug.org/texlive/) or [MiKTeX](https://miktex.org/) |
| **Typst** | [typst.app/docs/install](https://typst.app/docs/install/) |

## Python requirements

```bash
pip install PyQt5 PyMuPDF
```

> Without `PyMuPDF` the editor still works — compilation runs but preview is disabled; the PDF path is shown so you can open it manually.
