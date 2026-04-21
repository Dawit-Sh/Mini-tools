# codeflow

Local code architecture visualizer. Analyzes your codebase and generates a self-contained interactive HTML file with a dependency graph.

## Features

- **Dependency graph** — force-directed, zoomable, pannable, draggable nodes
- **Multi-language** — Python (full AST), JS/TS, Go, Rust, C/C++, Java, Ruby, PHP
- **Security scanner** — hardcoded passwords/keys/tokens, `eval()`, shell injection, SQL injection, weak hashes
- **Health grades (A–F)** per file — based on size, function count, and security issues
- **Sidebar** — sorted file list with language, line count, grade
- **Filters** — search by filename, filter by language
- **Modes** — Import edges, Health view (color-coded grades), Security view (highlights risky files)
- Click any node to highlight its connections and show a detail panel
- Zero backend — everything runs in your browser from a single HTML file

## Usage

```bash
# Analyze current directory, open in browser
python codeflow.py . --open

# Analyze a specific project, save output
python codeflow.py ~/myproject -o arch.html --open

# Also dump raw JSON
python codeflow.py src/ --json > graph.json
```

## Output

A single self-contained `codeflow.html` file (~200 KB + your data). Open in any browser — no server needed.

## Requirements

Python 3.9+ · stdlib only · tkinter not needed · D3.js v7 loaded from CDN
