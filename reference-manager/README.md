# reference-manager

Academic reference manager with multi-format export.

## Features

- Add / Edit / Delete references (Title, Author, Year, Link, Tags, Notes)
- Inline search and column sort
- Export to **JSON**, **BibTeX**, or **APA plain text**
- Import from JSON
- Double-click or Edit button to edit in a dialog
- Open URL directly in browser
- Dark-themed Tkinter GUI

## Usage

```bash
python mini-ref.py
```

### txt2csv converter

Converts plain-text bibliography lines (`Title - Author (Year)`) to CSV.

```bash
python txt2csv.py
```

## Requirements

- `mini-ref.py` — Python 3.9+ · stdlib only · tkinter
- `txt2csv.py` — also requires `pandas`:

```bash
pip install pandas
```
