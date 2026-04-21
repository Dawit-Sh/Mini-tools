# CoRrUptEd-File

Automated backup tool with periodic snapshots, duplicate detection, and restore.

## Features

- Configurable backup interval (1 min – 24 hrs)
- Max-backup retention — oldest auto-deleted when limit reached
- SHA-256 streaming duplicate detection (skips identical snapshots)
- Pause / Resume / Stop controls
- **Backup Now** for on-demand snapshots
- Restore any `.tar.gz` snapshot to a chosen directory
- Thread-safe UI — progress bar and timestamped log

## Usage

```bash
python corrupt.py
```

1. Select **Source Directory** (what to back up)
2. Select **Backup Directory** (where to store `.tar.gz` files)
3. Set interval and max backups
4. Click **Start Backup**

## Requirements

Python 3.9+ · stdlib only (no pip install needed) · tkinter
