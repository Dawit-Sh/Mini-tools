# mini-pop

Send emails from your terminal. Inspired by [charmbracelet/pop](https://github.com/charmbracelet/pop).

## Features

- Interactive compose mode and CLI mode
- SMTP with STARTTLS / SSL
- Presets for Gmail, Outlook, Yahoo, iCloud, or custom server
- Multiple named profiles
- Attachments, HTML body, CC/BCC, Reply-To, signatures
- Pipe-friendly — body from stdin
- `--dry-run` to preview without sending
- Draft saving
- `test` command to verify your config

## Setup

```bash
pip install colorama   # optional — colored output on Windows
python pop.py config   # walks you through SMTP setup
```

> **Gmail users:** use an [App Password](https://myaccount.google.com/apppasswords), not your regular password.

## Usage

```bash
# Interactive compose
python pop.py

# Quick send
python pop.py send -t friend@example.com -s "Hello" -b "How are you?"

# Pipe body from stdin
echo "Meeting at 3pm" | python pop.py send -t boss@example.com -s "Reminder"
cat report.txt        | python pop.py send -t team@example.com -s "Report"

# Attachments
python pop.py send -t client@example.com -s "Invoice" --attach invoice.pdf

# Multiple recipients
python pop.py send -t a@x.com -t b@x.com -s "Hi all" -b "See you soon"

# CC / BCC
python pop.py send -t a@x.com --cc boss@x.com --bcc log@x.com -s "Update" -b "..."

# HTML email
python pop.py send -t a@x.com -s "Newsletter" --html "<h1>Hello</h1>"

# Dry run (no email sent)
python pop.py send -t a@x.com -s "Test" -b "body" --dry-run

# Multiple profiles
python pop.py --profile work config
python pop.py --profile work send -t client@x.com -s "Hi"

# Utilities
python pop.py test        # send test email to yourself
python pop.py profiles    # list saved profiles
python pop.py drafts      # list saved drafts
python pop.py config --show    # show current config
python pop.py config --delete  # remove profile
```

## Config location

`~/.config/mini-pop/config.json` (permissions set to 600)

## Requirements

Python 3.9+ · stdlib only · `colorama` optional (colored output)
