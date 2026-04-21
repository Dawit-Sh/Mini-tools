# simple-todo

Task manager with priorities, due dates, and a statistics chart.

## Features

- Add tasks with title, description, priority (High / Medium / Low) and due date
- Three columns: **Pending** · **Finished** · **Cancelled** — click checkbox to cycle
- Edit and Delete buttons per task
- Search bar + status filter + priority filter
- Progress stats bar (% completed)
- Bar chart on the Statistics tab
- Persistent CSV storage — survives restarts

## Usage

```bash
pip install PyQt5 matplotlib
python main.py
```

## Requirements

Python 3.9+ · `PyQt5` · `matplotlib`
