#!/usr/bin/env python3
"""
mini-pop — Send emails from your terminal  (inspired by charmbracelet/pop)
Supports SMTP (Gmail, Outlook, custom). Config saved to ~/.config/mini-pop/config.json

Usage:
    pop                                         # interactive TUI mode
    pop send -t you@example.com -s "Hi"         # CLI mode
    pop send -t a@b.com -s "Hi" < body.txt      # pipe body from stdin
    pop config                                  # configure SMTP
    pop config --show                           # show current config
    pop profiles                                # list saved profiles
"""

import argparse
import email.mime.multipart
import email.mime.text
import email.mime.base
import email.encoders
import json
import os
import re
import smtplib
import ssl
import sys
import textwrap
from getpass import getpass
from pathlib import Path

# ── Colours ───────────────────────────────────────────────────────────────────
try:
    from colorama import init as _cinit, Fore, Style
    _cinit(autoreset=True)
    R   = Fore.RED;   G  = Fore.GREEN;  Y  = Fore.YELLOW
    B   = Fore.BLUE;  C  = Fore.CYAN;   M  = Fore.MAGENTA
    DIM = Style.DIM;  BD = Style.BRIGHT; RST = Style.RESET_ALL
except ImportError:
    R=G=Y=B=C=M=DIM=BD=RST=""

def ok(msg):    print(f"{G}{BD}✓{RST} {msg}")
def err(msg):   print(f"{R}{BD}✗{RST} {msg}", file=sys.stderr)
def info(msg):  print(f"{C}{DIM}→{RST} {msg}")
def warn(msg):  print(f"{Y}{BD}⚠{RST} {msg}")
def label(k,v): print(f"  {C}{k:<14}{RST} {v}")

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG_DIR  = Path.home() / ".config" / "mini-pop"
CONFIG_FILE = CONFIG_DIR / "config.json"
DRAFTS_FILE = CONFIG_DIR / "drafts.json"

PRESETS = {
    "gmail": {
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "use_tls":   True,
        "_note": "Use an App Password (not your Google password)",
    },
    "outlook": {
        "smtp_host": "smtp.office365.com",
        "smtp_port": 587,
        "use_tls":   True,
    },
    "yahoo": {
        "smtp_host": "smtp.mail.yahoo.com",
        "smtp_port": 587,
        "use_tls":   True,
    },
    "icloud": {
        "smtp_host": "smtp.mail.me.com",
        "smtp_port": 587,
        "use_tls":   True,
    },
    "custom": {
        "smtp_host": "",
        "smtp_port": 587,
        "use_tls":   True,
    },
}


def load_config(profile: str = "default") -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(CONFIG_FILE.read_text())
        return data.get(profile, data) if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_config(cfg: dict, profile: str = "default"):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if CONFIG_FILE.exists():
        try:
            existing = json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    if not isinstance(existing, dict) or "smtp_host" in existing:
        # Migrate old flat format
        existing = {"default": existing} if existing else {}
    existing[profile] = cfg
    CONFIG_FILE.write_text(json.dumps(existing, indent=2))
    CONFIG_FILE.chmod(0o600)


def list_profiles() -> list:
    if not CONFIG_FILE.exists():
        return []
    try:
        data = json.loads(CONFIG_FILE.read_text())
        if isinstance(data, dict) and "smtp_host" not in data:
            return list(data.keys())
    except Exception:
        pass
    return ["default"]


# ── SMTP sender ───────────────────────────────────────────────────────────────

def send_email(cfg: dict, msg_data: dict) -> None:
    """Send the email. Raises on error."""
    required = ("smtp_host", "smtp_port", "username", "password", "from_addr")
    missing = [k for k in required if not cfg.get(k)]
    if missing:
        raise ValueError(f"Config missing: {', '.join(missing)}")

    if not msg_data.get("to"):
        raise ValueError("At least one recipient (--to) is required.")
    if not msg_data.get("subject"):
        raise ValueError("Subject (--subject) is required.")

    # Build message
    msg = email.mime.multipart.MIMEMultipart("alternative")
    msg["From"]    = cfg.get("from_name", cfg["from_addr"]) + f" <{cfg['from_addr']}>" \
                     if cfg.get("from_name") else cfg["from_addr"]
    msg["To"]      = ", ".join(msg_data["to"])
    if msg_data.get("cc"):
        msg["Cc"]  = ", ".join(msg_data["cc"])
    if msg_data.get("bcc"):
        msg["Bcc"] = ", ".join(msg_data["bcc"])
    msg["Subject"] = msg_data["subject"]
    msg["Reply-To"]= msg_data.get("reply_to", "")

    body = msg_data.get("body", "")
    if msg_data.get("signature") or cfg.get("signature"):
        sig = msg_data.get("signature") or cfg.get("signature", "")
        body = body + "\n\n-- \n" + sig

    if msg_data.get("html"):
        # Attach plain + html alternative
        msg.attach(email.mime.text.MIMEText(body, "plain"))
        msg.attach(email.mime.text.MIMEText(msg_data["html"], "html"))
    else:
        msg.attach(email.mime.text.MIMEText(body, "plain"))

    # Attachments
    for attach_path in msg_data.get("attachments", []):
        p = Path(attach_path)
        if not p.exists():
            warn(f"Attachment not found: {attach_path}")
            continue
        with open(p, "rb") as f:
            part = email.mime.base.MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        email.encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{p.name}"')
        msg.attach(part)

    all_rcpts = msg_data["to"] + msg_data.get("cc", []) + msg_data.get("bcc", [])

    host = cfg["smtp_host"]
    port = int(cfg["smtp_port"])
    use_tls = cfg.get("use_tls", True)
    use_ssl = cfg.get("use_ssl", False)  # port 465

    context = ssl.create_default_context()
    info(f"Connecting to {host}:{port} …")

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, context=context) as server:
            server.login(cfg["username"], cfg["password"])
            server.sendmail(cfg["from_addr"], all_rcpts, msg.as_string())
    else:
        with smtplib.SMTP(host, port) as server:
            server.ehlo()
            if use_tls:
                server.starttls(context=context)
                server.ehlo()
            server.login(cfg["username"], cfg["password"])
            server.sendmail(cfg["from_addr"], all_rcpts, msg.as_string())


# ── Interactive TUI ───────────────────────────────────────────────────────────

def tui_compose(cfg: dict) -> dict:
    """Interactive compose mode."""
    print(f"\n{B}{BD}✉  mini-pop{RST}  —  compose email\n")

    def prompt(label_str, default="", required=False, secret=False):
        while True:
            disp = f"  {C}{label_str}{RST}"
            if default:
                disp += f" {DIM}[{default}]{RST}"
            disp += ": "
            val = (getpass(disp) if secret else input(disp)).strip()
            if not val:
                val = default
            if required and not val:
                warn(f"{label_str} is required.")
                continue
            return val

    to_str  = prompt("To", required=True)
    cc_str  = prompt("Cc")
    subject = prompt("Subject", required=True)

    print(f"  {C}Body{RST} {DIM}(type your message; end with a line containing only '.' ){RST}:")
    lines = []
    while True:
        try:
            line = input("  ")
        except EOFError:
            break
        if line == ".":
            break
        lines.append(line)
    body = "\n".join(lines)

    attach_str = prompt("Attachments", "(comma-separated paths, or blank)")
    attachments = [a.strip() for a in attach_str.split(",") if a.strip()]

    return {
        "to": [t.strip() for t in re.split(r"[,;]", to_str) if t.strip()],
        "cc": [t.strip() for t in re.split(r"[,;]", cc_str) if t.strip()],
        "subject": subject,
        "body": body,
        "attachments": attachments,
    }


def tui_mode(profile: str = "default"):
    cfg = load_config(profile)
    if not cfg.get("smtp_host"):
        warn("No configuration found. Running setup…")
        cfg = interactive_config(profile)

    msg = tui_compose(cfg)

    print(f"\n{BD}Preview:{RST}")
    label("From:", cfg.get("from_addr", "?"))
    label("To:", ", ".join(msg["to"]))
    if msg.get("cc"):
        label("Cc:", ", ".join(msg["cc"]))
    label("Subject:", msg["subject"])
    label("Body:", (msg["body"][:60] + "…" if len(msg["body"]) > 60 else msg["body"]).replace("\n", "↵ "))
    if msg.get("attachments"):
        label("Attachments:", ", ".join(msg["attachments"]))

    ans = input(f"\n  {Y}Send?{RST} [Y/n] ").strip().lower()
    if ans in ("", "y", "yes"):
        try:
            send_email(cfg, msg)
            ok(f"Sent to {', '.join(msg['to'])}")
        except Exception as e:
            err(str(e))
            sys.exit(1)
    else:
        info("Cancelled.")


# ── Config wizard ─────────────────────────────────────────────────────────────

def interactive_config(profile: str = "default") -> dict:
    print(f"\n{B}{BD}mini-pop config{RST}  profile: {C}{profile}{RST}\n")
    print("  Available presets:")
    for i, k in enumerate(PRESETS, 1):
        print(f"    {i}. {k}")
    choice = input("\n  Choose preset [1-5] or press Enter for custom: ").strip()
    preset_keys = list(PRESETS.keys())
    try:
        idx = int(choice) - 1
        preset = PRESETS[preset_keys[idx]].copy()
    except (ValueError, IndexError):
        preset = PRESETS["custom"].copy()

    cfg: dict = {}
    cfg["smtp_host"] = input(f"  SMTP host [{preset.get('smtp_host','')}]: ").strip() or preset.get("smtp_host", "")
    port_raw = input(f"  SMTP port [{preset.get('smtp_port', 587)}]: ").strip()
    cfg["smtp_port"] = int(port_raw) if port_raw.isdigit() else preset.get("smtp_port", 587)
    tls_raw = input(f"  Use STARTTLS? [Y/n]: ").strip().lower()
    cfg["use_tls"] = tls_raw not in ("n", "no")
    ssl_raw = input(f"  Use SSL (port 465)? [y/N]: ").strip().lower()
    cfg["use_ssl"] = ssl_raw in ("y", "yes")

    cfg["username"]  = input("  Username / email: ").strip()
    cfg["password"]  = getpass("  Password (App Password recommended): ")
    cfg["from_addr"] = input(f"  From address [{cfg['username']}]: ").strip() or cfg["username"]
    cfg["from_name"] = input("  Display name (optional): ").strip()
    cfg["signature"] = input("  Signature (optional): ").strip()

    save_config(cfg, profile)
    ok(f"Config saved for profile '{profile}'.")
    return cfg


# ── Save / load drafts ────────────────────────────────────────────────────────

def save_draft(msg: dict, name: str = ""):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    drafts: list = []
    if DRAFTS_FILE.exists():
        try:
            drafts = json.loads(DRAFTS_FILE.read_text())
        except Exception:
            pass
    import datetime
    msg["_saved"] = datetime.datetime.now().isoformat()
    msg["_name"]  = name or msg.get("subject", "untitled")
    drafts.append(msg)
    DRAFTS_FILE.write_text(json.dumps(drafts, indent=2))
    ok(f"Draft saved: {msg['_name']}")


def list_drafts():
    if not DRAFTS_FILE.exists():
        info("No drafts saved.")
        return
    drafts: list = json.loads(DRAFTS_FILE.read_text())
    if not drafts:
        info("No drafts.")
        return
    print(f"\n{BD}Saved Drafts:{RST}")
    for i, d in enumerate(drafts):
        print(f"  {i+1}. {C}{d.get('_name','?')}{RST}  →  {d.get('to',['?'])[0]}  {DIM}{d.get('_saved','')}{RST}")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        prog="pop",
        description="mini-pop — send emails from your terminal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              pop                                           # interactive compose
              pop send -t friend@example.com -s "Hello"    # quick send
              echo "See you soon" | pop send -t a@b.com -s "Meeting"
              pop send -t a@b.com -t b@c.com -s "Hi all" -b "Message" --attach report.pdf
              pop config                                    # setup SMTP
              pop config --show                             # show current settings
              pop profiles                                  # list profiles
              pop drafts                                    # list saved drafts
        """),
    )
    p.add_argument("--profile", default="default", help="Config profile name (default: default)")

    sub = p.add_subparsers(dest="cmd")

    # send
    send_p = sub.add_parser("send", help="Send an email")
    send_p.add_argument("-t", "--to",       action="append", default=[], metavar="EMAIL", help="Recipient (repeatable)")
    send_p.add_argument("-c", "--cc",       action="append", default=[], metavar="EMAIL", help="CC recipient")
    send_p.add_argument("--bcc",            action="append", default=[], metavar="EMAIL")
    send_p.add_argument("-s", "--subject",  required=True,   help="Email subject")
    send_p.add_argument("-b", "--body",     default="",      help="Email body text")
    send_p.add_argument("--html",           default="",      help="HTML body (will be sent as alternative)")
    send_p.add_argument("--attach", "-a",   action="append", default=[], metavar="FILE", help="Attachment path (repeatable)")
    send_p.add_argument("--reply-to",       default="",      help="Reply-To address")
    send_p.add_argument("--sig",            default="",      help="Signature override")
    send_p.add_argument("--save-draft",     action="store_true", help="Save as draft instead of sending")
    send_p.add_argument("--dry-run",        action="store_true", help="Print what would be sent without sending")

    # config
    conf_p = sub.add_parser("config", help="Configure SMTP settings")
    conf_p.add_argument("--show",   action="store_true", help="Show current config")
    conf_p.add_argument("--delete", action="store_true", help="Delete this profile")

    # test
    sub.add_parser("test", help="Send a test email to yourself")

    # profiles
    sub.add_parser("profiles", help="List saved profiles")

    # drafts
    sub.add_parser("drafts", help="List saved drafts")

    return p


def cmd_send(args, cfg: dict):
    # Body: use --body, else read stdin
    body = args.body
    if not body and not sys.stdin.isatty():
        body = sys.stdin.read()

    msg = {
        "to":          args.to,
        "cc":          args.cc,
        "bcc":         getattr(args, "bcc", []),
        "subject":     args.subject,
        "body":        body,
        "html":        args.html,
        "attachments": args.attach,
        "reply_to":    args.reply_to,
        "signature":   args.sig,
    }

    if args.save_draft:
        save_draft(msg)
        return

    if args.dry_run:
        print(f"\n{BD}Dry run — would send:{RST}")
        label("From:", cfg.get("from_addr", "?"))
        label("To:", ", ".join(msg["to"]))
        if msg["cc"]:    label("Cc:", ", ".join(msg["cc"]))
        if msg["bcc"]:   label("Bcc:", ", ".join(msg["bcc"]))
        label("Subject:", msg["subject"])
        preview = (body[:80] + "…") if len(body) > 80 else body
        label("Body:", preview.replace("\n", "↵ "))
        if msg["attachments"]: label("Attachments:", str(msg["attachments"]))
        return

    if not msg["to"]:
        err("At least one --to recipient is required.")
        sys.exit(1)

    try:
        send_email(cfg, msg)
        ok(f"Email sent to: {', '.join(msg['to'])}")
    except Exception as e:
        err(str(e))
        sys.exit(1)


def cmd_config(args, profile: str):
    cfg = load_config(profile)
    if args.show:
        if not cfg:
            warn(f"No config for profile '{profile}'.")
            return
        print(f"\n{BD}Config — profile: {C}{profile}{RST}")
        for k, v in cfg.items():
            val = "●●●●●●●●" if k == "password" else str(v)
            label(k + ":", val)
        print()
        return
    if args.delete:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text())
            if isinstance(data, dict) and profile in data:
                del data[profile]
                CONFIG_FILE.write_text(json.dumps(data, indent=2))
                ok(f"Profile '{profile}' deleted.")
            else:
                warn(f"Profile '{profile}' not found.")
        return
    interactive_config(profile)


def cmd_test(cfg: dict):
    addr = cfg.get("from_addr") or cfg.get("username")
    if not addr:
        err("No from_addr in config.")
        sys.exit(1)
    info(f"Sending test email to {addr} …")
    try:
        send_email(cfg, {
            "to": [addr],
            "subject": "mini-pop test",
            "body": "If you receive this, mini-pop is configured correctly! ✓",
        })
        ok("Test email sent!")
    except Exception as e:
        err(str(e))
        sys.exit(1)


def main():
    parser = build_parser()
    args = parser.parse_args()
    profile = args.profile

    if args.cmd == "profiles":
        ps = list_profiles()
        print(f"\n{BD}Saved profiles:{RST}")
        for p in ps:
            print(f"  {C}•{RST} {p}")
        print()
        return

    if args.cmd == "drafts":
        list_drafts()
        return

    if args.cmd == "config":
        cmd_config(args, profile)
        return

    # All other commands need config
    cfg = load_config(profile)
    if not cfg.get("smtp_host") and args.cmd != "config":
        warn(f"No config for profile '{profile}'. Running setup first…")
        cfg = interactive_config(profile)

    if args.cmd == "send":
        cmd_send(args, cfg)
    elif args.cmd == "test":
        cmd_test(cfg)
    elif args.cmd is None:
        # Interactive TUI
        tui_mode(profile)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
