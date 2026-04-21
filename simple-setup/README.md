# simple-setup

Cross-platform package installer — generates or runs an install script for your chosen packages.

## Supported platforms

| Platform | Package manager |
|---|---|
| Ubuntu / Debian | `apt` |
| Fedora | `dnf` |
| openSUSE | `zypper` |
| Arch / Manjaro | `pacman` |
| macOS | `brew` (Homebrew) |
| Windows | `winget` |
| Windows | `choco` (Chocolatey) |

Auto-detects your current OS on launch.

## Features

- Load packages from a `.txt` file or type them inline
- Checkbox list — select/deselect, remove individual entries
- Optional extras per distro (Flatpak, RPM Fusion, Packman, Homebrew Cask…)
- **Generate Script** — saves a `.sh` or `.ps1` ready to run
- **Run Now** — launches the script in a terminal immediately

## Usage

```bash
python setup.py
```

## Requirements

Python 3.9+ · stdlib only · tkinter
