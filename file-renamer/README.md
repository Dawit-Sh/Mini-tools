# file-renamer

Batch file renamer with live preview and undo.

## Features

- **Find & Replace** — literal or regex, case-sensitive toggle
- **Prefix / Suffix** insertion
- **Case change** — UPPER, lower, Title Case, Sentence case
- **Numbering** — add sequence numbers as prefix or suffix with padding
- **Date stamp** — prepend/append formatted date
- **Extension change**
- **Live preview** — see old → new names before committing
- **Undo last rename** — reverses the previous batch
- Subfolder support (opt-in)
- Glob filter (e.g. `*.jpg`)

## Usage

```bash
python renamer.py
```

1. Browse to a folder
2. Configure rename rules
3. Click **Preview Changes**
4. Click **Apply Rename**

## Requirements

Python 3.9+ · stdlib only · tkinter
