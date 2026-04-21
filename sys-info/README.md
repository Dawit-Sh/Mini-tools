# sys-info

Live system information monitor.

## Features

| Tab | Info shown |
|---|---|
| Overview | OS, hostname, arch, Python version, boot time, uptime, IP |
| CPU | Total usage, per-core bars, frequency, load average |
| Memory | RAM total/used/available/%, swap |
| Disks | All mounted partitions — total, used, free, % |
| Network | Interfaces, IP, MAC, speed, bytes sent/received, live bytes/s |
| Processes | Top processes — PID, name, CPU%, memory%, status; search & sort |

- Configurable auto-refresh interval (1–60 s)
- Export overview to `.txt`

## Usage

```bash
pip install psutil
python sysinfo.py
```

## Requirements

Python 3.9+ · `psutil` · tkinter
