# simple-pass

Password manager available as both a GUI app and a CLI bash script. All passwords are encrypted at rest.

## GUI (`pass.py`)

### Features
- Master password required on launch — key derived via PBKDF2 (480 000 iterations)
- Fernet (AES-128-CBC) encryption per entry
- Add / View / Edit / Delete entries
- Copy password to clipboard in one click
- Search / filter and column sort
- Password generator — length, charset, exclude-ambiguous

### Usage
```bash
pip install cryptography
python pass.py
```

---

## CLI (`pass.sh`)

### Features
- AES-256-CBC vault encrypted via `openssl`
- Master password required every session — never stored
- Auto-copies retrieved password to clipboard (`xclip` / `xsel` / `pbcopy`)
- Commands: `add`, `get`, `list`, `delete`, `generate`, `change-master`

### Usage
```bash
bash pass.sh          # interactive menu
bash pass.sh add
bash pass.sh get
bash pass.sh list
```

Vault location: `~/.simple-pass/vault.enc` (override with `PASS_STORE` env var)

## Requirements

- GUI: Python 3.9+, `pip install cryptography`
- CLI: bash, openssl, awk, grep
