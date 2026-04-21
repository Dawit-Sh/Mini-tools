# hash-checker

File integrity verifier supporting MD5, SHA-1, SHA-256, and SHA-512.

## Features

- **Single file** hash computation with progress bar
- **Verify** computed hash against a known/expected hash (paste from clipboard)
- **Batch folder** mode — hash every file in a directory
- Copy hash to clipboard
- Export batch results to CSV
- Streaming reads — handles large files without loading into RAM

## Usage

```bash
python hash_checker.py
```

## Requirements

Python 3.9+ · stdlib only · tkinter
