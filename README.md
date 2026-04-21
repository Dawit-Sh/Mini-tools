# Mini-tools

Cross-platform collection of utility scripts and GUI tools (Windows / macOS / Linux).

## Tools

### Original tools (improved)

| Tool | Description | Dependencies |
|---|---|---|
| [**CoRrUptEd-File**](CoRrUptEd-File/README.md) | Automated backup/restore, configurable interval, retention, SHA-256 dedup | stdlib |
| [**simple-pass**](simple-pass/README.md) | GUI + CLI password manager — PBKDF2 master password, AES encrypted vault | `cryptography` / `openssl` |
| [**reference-manager**](reference-manager/README.md) | Academic reference manager — BibTeX, APA, JSON export | stdlib |
| [**simple-setup**](simple-setup/README.md) | Package installer — Ubuntu/Fedora/Arch/macOS/Windows, auto-detects OS | stdlib |
| [**simple-todo**](simple-todo/README.md) | Task manager — priorities, due dates, edit/delete, search, stats chart | `PyQt5`, `matplotlib` |
| [**file-renamer**](file-renamer/README.md) | Batch file renamer — regex, numbering, date-stamp, live preview, undo | stdlib |
| [**hash-checker**](hash-checker/README.md) | File integrity — MD5/SHA-1/SHA-256/SHA-512, batch, verify, CSV export | stdlib |
| [**sys-info**](sys-info/README.md) | System monitor — CPU/memory/disk/network/processes, live refresh | `psutil` |

### New tools

| Tool | Description | Language | Dependencies |
|---|---|---|---|
| [**api-tester**](api-tester/README.md) | Terminal HTTP client — requests, collections, env vars, history, colored output | **Rust** | `reqwest`, `clap`, `colored` |
| [**codeflow**](codeflow/README.md) | Local code architecture visualizer — dependency graph, security scan, health grades | Python | stdlib (D3 via CDN) |
| [**mini-pop**](mini-pop/README.md) | Terminal email sender — SMTP, attachments, profiles, pipe-friendly | Python | `colorama` (optional) |
| [**texpad**](texpad/README.md) | LaTeX + Typst editor — split pane, syntax highlight, live PDF preview | Python | `PyQt5`, `PyMuPDF` |

## Quick start

```bash
# Install dependencies for any tool
pip install -r <tool-folder>/requirements.txt

# Run any Python GUI tool
python <tool-folder>/<script>.py

# Build the Rust API tester
cd api-tester && cargo build --release
./target/release/mini-req req GET https://httpbin.org/get

# CLI password manager (Linux/macOS)
bash simple-pass/pass.sh

# codeflow — analyze a directory and open in browser
python codeflow/codeflow.py . --open

# mini-pop — configure SMTP then send
python mini-pop/pop.py config
python mini-pop/pop.py send -t you@example.com -s "Hello" -b "World"

# texpad — LaTeX/Typst editor
python texpad/texpad.py
```

## Requirements

- **Python tools**: Python 3.9+, tkinter (Linux: `sudo apt install python3-tk`)
- **api-tester**: Rust + Cargo — install from [rustup.rs](https://rustup.rs)
- **texpad**: also needs `pdflatex`/`xelatex` (TeX Live / MiKTeX) or `typst` CLI on PATH
- **mini-pop**: outbound SMTP access (use an App Password for Gmail)
