# api-tester (mini-req)

Fast terminal HTTP client for API testing, written in Rust.

## Build

```bash
cd api-tester
cargo build --release
# Binary: target/release/mini-req
```

Add to PATH or call directly:
```bash
./target/release/mini-req req GET https://httpbin.org/get
```

## Usage

```bash
# Basic requests
mini-req req GET  https://api.example.com/users
mini-req req POST https://api.example.com/users --json '{"name":"Alice"}' -v
mini-req req PUT  https://api.example.com/users/1 -d '{"name":"Bob"}' -H "Content-Type: application/json"
mini-req req DELETE https://api.example.com/users/1

# Auth
mini-req req GET https://api.example.com/me --bearer MY_TOKEN
mini-req req GET https://api.example.com/data -u user:password

# Query params & headers
mini-req req GET https://api.example.com/items -q page=1 -q limit=20
mini-req req GET https://api.example.com/data -H "X-Api-Key: abc123" -H "Accept: application/json"

# Body from file or stdin
mini-req req POST https://api.example.com/upload -d @payload.json
cat data.json | mini-req req POST https://api.example.com/data -d -

# Save response to file
mini-req req GET https://api.example.com/export -o output.json

# Collections (saved requests)
mini-req req GET https://api.example.com/me --bearer TOKEN --save-as get-me
mini-req run get-me
mini-req ls
mini-req show get-me
mini-req rm get-me

# Environment variables  ({{VAR}} in URLs and headers)
mini-req env set BASE=https://api.example.com
mini-req env set TOKEN=my-secret-token
mini-req req GET '{{BASE}}/users' --bearer '{{TOKEN}}'
mini-req env list

# History
mini-req history
mini-req history -n 50
mini-req history --clear
```

## Flags

| Flag | Description |
|---|---|
| `-H "Name: Value"` | Custom header (repeatable) |
| `-d DATA` | Request body (`@file` reads from file, `-` reads stdin) |
| `--json '...'` | JSON body (sets Content-Type + Accept automatically) |
| `-u user:pass` | Basic authentication |
| `--bearer TOKEN` | Bearer token |
| `-q key=val` | Query parameter (repeatable) |
| `-v` | Verbose — show request details |
| `-i` | Include response headers in output |
| `-o FILE` | Save response body to file |
| `-L` | Follow redirects |
| `-f` | Exit non-zero on 4xx/5xx |
| `-s` | Silent — body only, no status line |
| `--timeout N` | Request timeout in seconds (default: 30) |
| `--no-verify` | Skip TLS certificate verification |
| `--save-as NAME` | Save this request to collections after sending |

## Requirements

Rust + Cargo — install from [rustup.rs](https://rustup.rs)
