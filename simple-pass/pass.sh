#!/usr/bin/env bash
# Simple CLI Password Manager — cross-platform (bash + openssl)
# Passwords are AES-256-CBC encrypted at rest. Requires: openssl, awk, grep

set -euo pipefail

STORE="${PASS_STORE:-$HOME/.simple-pass/vault.enc}"
TMP_PLAIN=""

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

die()  { echo -e "${RED}Error: $*${RESET}" >&2; _cleanup; exit 1; }
info() { echo -e "${CYAN}$*${RESET}"; }
ok()   { echo -e "${GREEN}$*${RESET}"; }

_cleanup() {
    if [[ -n "$TMP_PLAIN" && -f "$TMP_PLAIN" ]]; then
        command -v shred &>/dev/null && shred -u "$TMP_PLAIN" 2>/dev/null || rm -f "$TMP_PLAIN"
    fi
}
trap _cleanup EXIT INT TERM

_prompt_master() {
    read -rsp "${BOLD}Master password: ${RESET}" MASTER_PASS; echo
    [[ -z "$MASTER_PASS" ]] && die "Master password cannot be empty."
}

_decrypt_vault() {
    TMP_PLAIN=$(mktemp /tmp/pass_XXXXXX)
    chmod 600 "$TMP_PLAIN"
    if [[ -f "$STORE" ]]; then
        openssl enc -aes-256-cbc -pbkdf2 -iter 480000 -d \
            -in "$STORE" -out "$TMP_PLAIN" -pass "pass:${MASTER_PASS}" 2>/dev/null \
            || die "Wrong master password or corrupted vault."
    else
        touch "$TMP_PLAIN"
    fi
}

_encrypt_vault() {
    mkdir -p "$(dirname "$STORE")"
    chmod 700 "$(dirname "$STORE")"
    openssl enc -aes-256-cbc -pbkdf2 -iter 480000 \
        -in "$TMP_PLAIN" -out "$STORE" -pass "pass:${MASTER_PASS}"
    chmod 600 "$STORE"
}

# Internal format: service<TAB>username<TAB>password
_entry_line() { printf '%s\t%s\t%s\n' "$1" "$2" "$3"; }

cmd_add() {
    read -rp "Service:  " service
    read -rp "Username: " username
    read -rsp "Password: " password; echo
    [[ -z "$service" || -z "$username" || -z "$password" ]] && die "All fields required."

    _prompt_master
    _decrypt_vault

    if grep -qP "^\Q${service}\E\t" "$TMP_PLAIN" 2>/dev/null; then
        read -rp "Service '$service' exists. Overwrite? [y/N] " ans
        [[ "$ans" != "y" && "$ans" != "Y" ]] && { info "Aborted."; return; }
        grep -vP "^\Q${service}\E\t" "$TMP_PLAIN" > "${TMP_PLAIN}.new" \
            && mv "${TMP_PLAIN}.new" "$TMP_PLAIN"
    fi

    _entry_line "$service" "$username" "$password" >> "$TMP_PLAIN"
    _encrypt_vault
    ok "Saved '$service'."
}

cmd_get() {
    read -rp "Service to retrieve: " service
    [[ -z "$service" ]] && die "Service name required."
    _prompt_master
    _decrypt_vault

    local match
    match=$(grep -P "^\Q${service}\E\t" "$TMP_PLAIN" 2>/dev/null || true)
    [[ -z "$match" ]] && die "No entry found for '$service'."

    local user pass
    user=$(printf '%s' "$match" | awk -F'\t' '{print $2}')
    pass=$(printf '%s' "$match" | awk -F'\t' '{print $3}')
    echo -e "${BOLD}Service:  ${RESET}$service"
    echo -e "${BOLD}Username: ${RESET}$user"
    echo -e "${BOLD}Password: ${RESET}${YELLOW}$pass${RESET}"

    # Copy to clipboard if available
    if command -v xclip &>/dev/null; then
        printf '%s' "$pass" | xclip -selection clipboard && info "(Password copied to clipboard)"
    elif command -v xsel &>/dev/null; then
        printf '%s' "$pass" | xsel --clipboard --input && info "(Password copied to clipboard)"
    elif command -v pbcopy &>/dev/null; then
        printf '%s' "$pass" | pbcopy && info "(Password copied to clipboard)"
    fi
}

cmd_list() {
    _prompt_master
    _decrypt_vault
    if [[ ! -s "$TMP_PLAIN" ]]; then
        info "Vault is empty."; return
    fi
    echo -e "\n${BOLD}Stored services:${RESET}"
    awk -F'\t' '{printf "  %-30s %s\n", $1, $2}' "$TMP_PLAIN" | sort
    echo
}

cmd_delete() {
    read -rp "Service to delete: " service
    [[ -z "$service" ]] && die "Service name required."
    _prompt_master
    _decrypt_vault

    grep -qP "^\Q${service}\E\t" "$TMP_PLAIN" 2>/dev/null || die "No entry found for '$service'."
    read -rp "Delete '$service'? [y/N] " ans
    [[ "$ans" != "y" && "$ans" != "Y" ]] && { info "Aborted."; return; }
    grep -vP "^\Q${service}\E\t" "$TMP_PLAIN" > "${TMP_PLAIN}.new" \
        && mv "${TMP_PLAIN}.new" "$TMP_PLAIN"
    _encrypt_vault
    ok "Deleted '$service'."
}

cmd_generate() {
    read -rp "Password length [16]: " len; len=${len:-16}
    local chars='A-Za-z0-9!@#$%^&*()-_=+[]{}|;:,.<>?'
    local pw
    pw=$(LC_ALL=C tr -dc "$chars" < /dev/urandom | head -c "$len")
    ok "Generated: $pw"
    if command -v xclip &>/dev/null; then
        printf '%s' "$pw" | xclip -selection clipboard && info "(Copied to clipboard)"
    elif command -v pbcopy &>/dev/null; then
        printf '%s' "$pw" | pbcopy && info "(Copied to clipboard)"
    fi
}

cmd_change_master() {
    info "Enter CURRENT master password to unlock vault."
    _prompt_master
    _decrypt_vault

    echo -e "${YELLOW}Enter NEW master password:${RESET}"
    read -rsp "New master password:  " NEW_PASS; echo
    read -rsp "Confirm new password: " CONF_PASS; echo
    [[ "$NEW_PASS" != "$CONF_PASS" ]] && die "Passwords do not match."
    [[ -z "$NEW_PASS" ]] && die "New password cannot be empty."
    MASTER_PASS="$NEW_PASS"
    _encrypt_vault
    ok "Master password changed."
}

usage() {
cat <<EOF
${BOLD}Simple CLI Password Manager${RESET}  (vault: $STORE)

Commands:
  ${CYAN}add${RESET}            Add or update a password
  ${CYAN}get${RESET}            Retrieve a password (auto-copies to clipboard)
  ${CYAN}list${RESET}           List all services and usernames
  ${CYAN}delete${RESET}         Delete an entry
  ${CYAN}generate${RESET}       Generate a random password
  ${CYAN}change-master${RESET}  Re-encrypt vault with a new master password

Usage: $(basename "$0") [command]
       Run without arguments for interactive menu.
EOF
}

interactive_menu() {
    while true; do
        echo -e "\n${BOLD}── Simple Pass ──${RESET}"
        echo "  1) Add / update password"
        echo "  2) Get / view password"
        echo "  3) List all services"
        echo "  4) Delete entry"
        echo "  5) Generate password"
        echo "  6) Change master password"
        echo "  0) Exit"
        read -rp "Choice: " choice
        case "$choice" in
            1) cmd_add ;;
            2) cmd_get ;;
            3) cmd_list ;;
            4) cmd_delete ;;
            5) cmd_generate ;;
            6) cmd_change_master ;;
            0) break ;;
            *) echo "Invalid choice." ;;
        esac
    done
}

case "${1:-}" in
    add)           cmd_add ;;
    get)           cmd_get ;;
    list)          cmd_list ;;
    delete|rm)     cmd_delete ;;
    generate|gen)  cmd_generate ;;
    change-master) cmd_change_master ;;
    help|--help)   usage ;;
    "")            interactive_menu ;;
    *)             usage; exit 1 ;;
esac
