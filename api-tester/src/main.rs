use base64::Engine as _;
use clap::{Args, Parser, Subcommand};
use colored::Colorize;
use dirs::config_dir;
use reqwest::{
    blocking::{Client, ClientBuilder},
    header::{HeaderMap, HeaderName, HeaderValue, ACCEPT, AUTHORIZATION, CONTENT_TYPE},
    Method, StatusCode,
};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::{
    collections::HashMap,
    fs,
    io::{self, Read},
    path::PathBuf,
    str::FromStr,
    time::{Duration, Instant},
};

// ── CLI ──────────────────────────────────────────────────────────────────────

#[derive(Parser)]
#[command(
    name = "mini-req",
    version,
    about = "Fast terminal HTTP client for API testing",
    long_about = None,
    propagate_version = true,
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Send an HTTP request  [aliases: r, get, post, put, patch, delete]
    #[command(name = "req", alias = "r", visible_aliases = &["GET","POST","PUT","PATCH","DELETE","HEAD"])]
    Req(ReqArgs),

    /// Save a request as a named collection entry
    #[command(name = "save")]
    Save(SaveArgs),

    /// Run a saved collection entry
    #[command(name = "run")]
    Run(RunArgs),

    /// List saved collection entries
    #[command(name = "ls", alias = "list")]
    List,

    /// Show/edit a saved collection entry
    #[command(name = "show")]
    Show(ShowArgs),

    /// Delete a saved collection entry
    #[command(name = "rm", alias = "delete-entry")]
    Rm(RmArgs),

    /// Manage environment variables used in URLs and headers  ({{VAR}} syntax)
    #[command(name = "env")]
    Env(EnvCmd),

    /// Print request history
    #[command(name = "history", alias = "hist")]
    History(HistoryArgs),
}

#[derive(Args, Debug, Clone)]
struct ReqArgs {
    /// HTTP method: GET POST PUT PATCH DELETE HEAD OPTIONS
    method: String,

    /// Target URL  (supports {{ENV_VAR}} interpolation)
    url: String,

    /// Request header  "Name: Value"  (repeatable)
    #[arg(short = 'H', long = "header", value_name = "NAME:VAL")]
    headers: Vec<String>,

    /// Request body.  Use @filename to read from file, - to read stdin
    #[arg(short = 'd', long = "data", value_name = "DATA|@FILE|-")]
    data: Option<String>,

    /// Shorthand JSON body  (sets Content-Type and Accept to application/json)
    #[arg(long, value_name = "JSON")]
    json: Option<String>,

    /// Basic auth  "user:password"
    #[arg(short = 'u', long = "user", value_name = "USER:PASS")]
    user: Option<String>,

    /// Bearer token  (sets Authorization: Bearer …)
    #[arg(long, value_name = "TOKEN")]
    bearer: Option<String>,

    /// Query parameter  "key=value"  (repeatable)
    #[arg(short = 'q', long = "query", value_name = "KEY=VAL")]
    query: Vec<String>,

    /// Save response body to file
    #[arg(short = 'o', long = "output", value_name = "FILE")]
    output: Option<PathBuf>,

    /// Show request details before sending
    #[arg(short = 'v', long)]
    verbose: bool,

    /// Include response headers in output
    #[arg(short = 'i', long = "include-headers")]
    include_headers: bool,

    /// Timeout in seconds  [default: 30]
    #[arg(long, default_value = "30")]
    timeout: u64,

    /// Skip TLS certificate verification
    #[arg(long)]
    no_verify: bool,

    /// Follow redirects
    #[arg(short = 'L', long)]
    follow: bool,

    /// Exit non-zero on 4xx/5xx responses
    #[arg(short = 'f', long)]
    fail: bool,

    /// Suppress status/timing lines (response body only)
    #[arg(short = 's', long)]
    silent: bool,

    /// Save this request after sending (give it a name)
    #[arg(long, value_name = "NAME")]
    save_as: Option<String>,

    /// Form data  "key=value"  (repeatable; sets Content-Type multipart/form-data)
    #[arg(short = 'F', long = "form", value_name = "KEY=VAL")]
    form: Vec<String>,

    /// Max redirects  [default: 10]
    #[arg(long, default_value = "10")]
    max_redirects: usize,
}

#[derive(Args, Debug)]
struct SaveArgs {
    /// Name for the collection entry
    name: String,
    /// HTTP method
    method: String,
    /// URL
    url: String,
    /// Headers  "Name: Value"
    #[arg(short = 'H', long = "header")]
    headers: Vec<String>,
    /// Request body
    #[arg(short = 'd', long = "data")]
    data: Option<String>,
    /// Bearer token
    #[arg(long)]
    bearer: Option<String>,
    /// Query params
    #[arg(short = 'q', long = "query")]
    query: Vec<String>,
    /// Description for this entry
    #[arg(long)]
    desc: Option<String>,
}

#[derive(Args, Debug)]
struct RunArgs {
    /// Collection entry name
    name: String,
    /// Override bearer token
    #[arg(long)]
    bearer: Option<String>,
    /// Verbose output
    #[arg(short = 'v', long)]
    verbose: bool,
    /// Extra headers
    #[arg(short = 'H', long = "header")]
    headers: Vec<String>,
}

#[derive(Args, Debug)]
struct ShowArgs {
    name: String,
}

#[derive(Args, Debug)]
struct RmArgs {
    name: String,
}

#[derive(Args, Debug)]
struct EnvCmd {
    #[command(subcommand)]
    action: EnvAction,
}

#[derive(Subcommand, Debug)]
enum EnvAction {
    /// Set an environment variable  KEY=VALUE
    #[command(name = "set")]
    Set { assignment: String },
    /// Unset an environment variable
    #[command(name = "unset", alias = "rm")]
    Unset { key: String },
    /// List all environment variables
    #[command(name = "list", alias = "ls")]
    List,
}

#[derive(Args, Debug)]
struct HistoryArgs {
    /// Number of entries to show  [default: 20]
    #[arg(short = 'n', default_value = "20")]
    count: usize,
    /// Clear history
    #[arg(long)]
    clear: bool,
}

// ── Data types ───────────────────────────────────────────────────────────────

#[derive(Serialize, Deserialize, Debug, Clone)]
struct CollectionEntry {
    name: String,
    method: String,
    url: String,
    headers: Vec<String>,
    data: Option<String>,
    bearer: Option<String>,
    query: Vec<String>,
    desc: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
struct HistoryEntry {
    timestamp: String,
    method: String,
    url: String,
    status: u16,
    duration_ms: u128,
}

// ── Config paths ──────────────────────────────────────────────────────────────

fn config_path() -> PathBuf {
    config_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("mini-req")
}

fn collections_dir() -> PathBuf {
    config_path().join("collections")
}

fn env_file() -> PathBuf {
    config_path().join("env.json")
}

fn history_file() -> PathBuf {
    config_path().join("history.json")
}

fn ensure_dirs() {
    let _ = fs::create_dir_all(collections_dir());
}

// ── Environment variables ─────────────────────────────────────────────────────

fn load_env() -> HashMap<String, String> {
    let path = env_file();
    if path.exists() {
        let s = fs::read_to_string(&path).unwrap_or_default();
        serde_json::from_str(&s).unwrap_or_default()
    } else {
        HashMap::new()
    }
}

fn save_env(map: &HashMap<String, String>) {
    ensure_dirs();
    let s = serde_json::to_string_pretty(map).unwrap_or_default();
    let _ = fs::write(env_file(), s);
}

fn interpolate(s: &str, env: &HashMap<String, String>) -> String {
    let mut result = s.to_string();
    for (k, v) in env {
        result = result.replace(&format!("{{{{{}}}}}", k), v);
    }
    result
}

// ── History ───────────────────────────────────────────────────────────────────

fn load_history() -> Vec<HistoryEntry> {
    let path = history_file();
    if path.exists() {
        let s = fs::read_to_string(&path).unwrap_or_default();
        serde_json::from_str(&s).unwrap_or_default()
    } else {
        Vec::new()
    }
}

fn append_history(entry: HistoryEntry) {
    ensure_dirs();
    let mut hist = load_history();
    hist.push(entry);
    if hist.len() > 500 {
        hist.drain(0..hist.len() - 500);
    }
    let s = serde_json::to_string_pretty(&hist).unwrap_or_default();
    let _ = fs::write(history_file(), s);
}

// ── Request builder ───────────────────────────────────────────────────────────

fn build_headers(raw: &[String], bearer: &Option<String>, is_json: bool) -> Result<HeaderMap, String> {
    let mut map = HeaderMap::new();
    if is_json {
        map.insert(CONTENT_TYPE, HeaderValue::from_static("application/json"));
        map.insert(ACCEPT, HeaderValue::from_static("application/json"));
    }
    if let Some(token) = bearer {
        let val = format!("Bearer {}", token);
        map.insert(
            AUTHORIZATION,
            HeaderValue::from_str(&val).map_err(|e| e.to_string())?,
        );
    }
    for h in raw {
        if let Some(idx) = h.find(':') {
            let name = h[..idx].trim();
            let value = h[idx + 1..].trim();
            let key = HeaderName::from_str(name).map_err(|e| format!("Bad header name '{}': {}", name, e))?;
            let val = HeaderValue::from_str(value).map_err(|e| format!("Bad header value '{}': {}", value, e))?;
            map.insert(key, val);
        } else {
            return Err(format!("Header '{}' must be in 'Name: Value' format", h));
        }
    }
    Ok(map)
}

fn resolve_body(data: &Option<String>) -> Result<Option<String>, String> {
    match data {
        None => Ok(None),
        Some(s) if s == "-" => {
            let mut buf = String::new();
            io::stdin().read_to_string(&mut buf).map_err(|e| e.to_string())?;
            Ok(Some(buf))
        }
        Some(s) if s.starts_with('@') => {
            let path = &s[1..];
            let contents = fs::read_to_string(path)
                .map_err(|e| format!("Cannot read '{}': {}", path, e))?;
            Ok(Some(contents))
        }
        Some(s) => Ok(Some(s.clone())),
    }
}

// ── Response printing ─────────────────────────────────────────────────────────

fn status_colored(status: StatusCode) -> colored::ColoredString {
    let code = status.as_u16();
    let s = format!("{} {}", code, status.canonical_reason().unwrap_or(""));
    if code < 200 {
        s.blue().bold()
    } else if code < 300 {
        s.green().bold()
    } else if code < 400 {
        s.cyan().bold()
    } else if code < 500 {
        s.yellow().bold()
    } else {
        s.red().bold()
    }
}

fn pretty_json(s: &str) -> String {
    match serde_json::from_str::<Value>(s) {
        Ok(v) => colorize_json(&v, 0),
        Err(_) => s.to_string(),
    }
}

fn colorize_json(v: &Value, depth: usize) -> String {
    let indent = "  ".repeat(depth);
    let inner  = "  ".repeat(depth + 1);
    match v {
        Value::Null    => "null".bright_black().to_string(),
        Value::Bool(b) => if *b { "true".blue().to_string() } else { "false".blue().to_string() },
        Value::Number(n) => n.to_string().yellow().to_string(),
        Value::String(s) => format!("\"{}\"", s.escape_default()).green().to_string(),
        Value::Array(arr) => {
            if arr.is_empty() {
                return "[]".to_string();
            }
            let items: Vec<String> = arr.iter().map(|x| format!("{}{}", inner, colorize_json(x, depth + 1))).collect();
            format!("[\n{}\n{}]", items.join(",\n"), indent)
        }
        Value::Object(map) => {
            if map.is_empty() {
                return "{}".to_string();
            }
            let items: Vec<String> = map.iter().map(|(k, val)| {
                format!("{}{}: {}", inner, format!("\"{}\"", k).cyan(), colorize_json(val, depth + 1))
            }).collect();
            format!("{{\n{}\n{}}}", items.join(",\n"), indent)
        }
    }
}

fn print_response(
    resp: reqwest::blocking::Response,
    duration: Duration,
    args: &ReqArgs,
) -> Result<bool, Box<dyn std::error::Error>> {
    let status = resp.status();
    let headers = resp.headers().clone();
    let body = resp.text()?;

    if !args.silent {
        println!();
        println!(
            "{}  {}  {}",
            status_colored(status),
            format!("{}ms", duration.as_millis()).bright_black(),
            format!("{} bytes", body.len()).bright_black()
        );

        if args.include_headers || args.verbose {
            println!("\n{}", "Response Headers:".bold().underline());
            for (k, v) in &headers {
                println!("  {}: {}", k.as_str().cyan(), v.to_str().unwrap_or("?").white());
            }
        }
        println!();
    }

    let ct = headers
        .get("content-type")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");

    let output = if ct.contains("json") {
        pretty_json(&body)
    } else {
        body.clone()
    };

    if let Some(path) = &args.output {
        fs::write(path, &body)?;
        if !args.silent {
            println!("{} {}", "Saved to".bright_black(), path.display().to_string().cyan());
        }
    } else {
        println!("{}", output);
    }

    Ok(status.is_success())
}

// ── Send request ──────────────────────────────────────────────────────────────

fn send(args: &ReqArgs) -> Result<(), Box<dyn std::error::Error>> {
    let env = load_env();
    let url = interpolate(&args.url, &env);

    let method = Method::from_str(&args.method.to_uppercase())
        .map_err(|_| format!("Unknown HTTP method: {}", args.method))?;

    let is_json = args.json.is_some()
        || args
            .headers
            .iter()
            .any(|h| h.to_lowercase().starts_with("content-type") && h.contains("json"));

    // Resolve body
    let body_string = if let Some(j) = &args.json {
        Some(j.clone())
    } else {
        resolve_body(&args.data)?
    };

    // Parse query params
    let query: Vec<(String, String)> = args
        .query
        .iter()
        .filter_map(|q| {
            q.find('=').map(|i| (q[..i].to_string(), q[i + 1..].to_string()))
        })
        .collect();

    // Parse form data
    let form_pairs: Vec<(String, String)> = args
        .form
        .iter()
        .filter_map(|f| {
            f.find('=').map(|i| (f[..i].to_string(), f[i + 1..].to_string()))
        })
        .collect();

    // Build headers
    let raw_headers: Vec<String> = args
        .headers
        .iter()
        .map(|h| interpolate(h, &env))
        .collect();
    let headers = build_headers(&raw_headers, &args.bearer, is_json)?;

    // Build basic auth
    let basic: Option<(String, String)> = args.user.as_ref().and_then(|u| {
        u.find(':').map(|i| (u[..i].to_string(), u[i + 1..].to_string()))
    });

    // Build client
    let mut cb = ClientBuilder::new()
        .timeout(Duration::from_secs(args.timeout))
        .danger_accept_invalid_certs(args.no_verify);
    if args.follow {
        cb = cb.redirect(reqwest::redirect::Policy::limited(args.max_redirects));
    } else {
        cb = cb.redirect(reqwest::redirect::Policy::none());
    }
    let client: Client = cb.build()?;

    // Build request
    let mut req = client.request(method.clone(), &url).headers(headers);

    if !query.is_empty() {
        req = req.query(&query);
    }

    if let Some((user, pass)) = &basic {
        req = req.basic_auth(user, Some(pass));
    }

    if !form_pairs.is_empty() {
        req = req.form(&form_pairs);
    } else if let Some(body) = &body_string {
        req = req.body(body.clone());
    }

    // Verbose: show request
    if args.verbose {
        let final_url = format!("{}", &url);
        println!("{} {}", method.as_str().bold().magenta(), final_url.cyan());
        if let Some(b) = &body_string {
            println!("\n{}", "Request Body:".bold().underline());
            if is_json {
                println!("{}", pretty_json(b));
            } else {
                println!("{}", b);
            }
        }
        println!();
    }

    let start = Instant::now();
    let response = req.send()?;
    let duration = start.elapsed();

    let status_code = response.status().as_u16();
    let method_str = method.as_str().to_string();
    let url_str = url.clone();

    let success = print_response(response, duration, args)?;

    append_history(HistoryEntry {
        timestamp: chrono_now(),
        method: method_str,
        url: url_str,
        status: status_code,
        duration_ms: duration.as_millis(),
    });

    if let Some(name) = &args.save_as {
        let entry = CollectionEntry {
            name: name.clone(),
            method: args.method.clone(),
            url: args.url.clone(),
            headers: args.headers.clone(),
            data: body_string,
            bearer: args.bearer.clone(),
            query: args.query.clone(),
            desc: None,
        };
        save_entry(&entry)?;
        println!("\n{} {}", "Saved as".bright_black(), name.cyan());
    }

    if args.fail && !success {
        std::process::exit(1);
    }

    Ok(())
}

fn chrono_now() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let (y, mo, d, h, mi, s) = secs_to_parts(secs);
    format!("{}-{:02}-{:02} {:02}:{:02}:{:02}", y, mo, d, h, mi, s)
}

fn secs_to_parts(secs: u64) -> (u64, u64, u64, u64, u64, u64) {
    let s = secs % 60;
    let total_min = secs / 60;
    let mi = total_min % 60;
    let total_hr = total_min / 60;
    let h = total_hr % 24;
    let total_days = total_hr / 24;
    let (y, mo, d) = days_to_ymd(total_days);
    (y, mo, d, h, mi, s)
}

fn days_to_ymd(mut days: u64) -> (u64, u64, u64) {
    days += 719468;
    let era = days / 146097;
    let doe = days % 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    (y, m, d)
}

// ── Collection management ─────────────────────────────────────────────────────

fn entry_path(name: &str) -> PathBuf {
    collections_dir().join(format!("{}.json", name))
}

fn save_entry(entry: &CollectionEntry) -> Result<(), Box<dyn std::error::Error>> {
    ensure_dirs();
    let s = serde_json::to_string_pretty(entry)?;
    fs::write(entry_path(&entry.name), s)?;
    Ok(())
}

fn load_entry(name: &str) -> Result<CollectionEntry, Box<dyn std::error::Error>> {
    let path = entry_path(name);
    if !path.exists() {
        return Err(format!("No collection entry named '{}'", name).into());
    }
    let s = fs::read_to_string(&path)?;
    Ok(serde_json::from_str(&s)?)
}

fn cmd_save(args: &SaveArgs) -> Result<(), Box<dyn std::error::Error>> {
    let entry = CollectionEntry {
        name: args.name.clone(),
        method: args.method.clone(),
        url: args.url.clone(),
        headers: args.headers.clone(),
        data: args.data.clone(),
        bearer: args.bearer.clone(),
        query: args.query.clone(),
        desc: args.desc.clone(),
    };
    save_entry(&entry)?;
    println!("{} {}", "Saved:".green().bold(), args.name.cyan());
    Ok(())
}

fn cmd_run(args: &RunArgs) -> Result<(), Box<dyn std::error::Error>> {
    let entry = load_entry(&args.name)?;
    println!("{} {}", "Running:".bright_black(), entry.name.cyan());
    let mut merged_headers = entry.headers.clone();
    merged_headers.extend(args.headers.clone());
    let req_args = ReqArgs {
        method: entry.method,
        url: entry.url,
        headers: merged_headers,
        data: entry.data,
        json: None,
        user: None,
        bearer: args.bearer.clone().or(entry.bearer),
        query: entry.query,
        output: None,
        verbose: args.verbose,
        include_headers: false,
        timeout: 30,
        no_verify: false,
        follow: true,
        fail: false,
        silent: false,
        save_as: None,
        form: Vec::new(),
        max_redirects: 10,
    };
    send(&req_args)
}

fn cmd_list() {
    let dir = collections_dir();
    if !dir.exists() {
        println!("{}", "No saved requests.".bright_black());
        return;
    }
    let entries: Vec<_> = fs::read_dir(&dir)
        .unwrap()
        .filter_map(|e| e.ok())
        .filter(|e| e.path().extension().map(|x| x == "json").unwrap_or(false))
        .collect();

    if entries.is_empty() {
        println!("{}", "No saved requests.".bright_black());
        return;
    }

    println!("\n{}", "Saved Requests".bold().underline());
    for e in entries {
        let name = e.path().file_stem().unwrap().to_string_lossy().to_string();
        if let Ok(entry) = load_entry(&name) {
            let desc = entry.desc.as_deref().unwrap_or("");
            println!(
                "  {}  {} {}  {}",
                entry.name.cyan().bold(),
                entry.method.to_uppercase().magenta(),
                entry.url.white(),
                desc.bright_black()
            );
        }
    }
    println!();
}

fn cmd_show(name: &str) -> Result<(), Box<dyn std::error::Error>> {
    let entry = load_entry(name)?;
    println!("\n{}", entry.name.cyan().bold());
    println!("  {} {}", "Method:".bright_black(), entry.method.magenta());
    println!("  {} {}", "URL:   ".bright_black(), entry.url.white());
    if !entry.headers.is_empty() {
        println!("  {}", "Headers:".bright_black());
        for h in &entry.headers {
            println!("    {}", h.white());
        }
    }
    if let Some(b) = &entry.bearer {
        println!("  {} Bearer {}", "Auth:  ".bright_black(), b.bright_black());
    }
    if let Some(d) = &entry.data {
        println!("  {}", "Body:  ".bright_black());
        println!("    {}", pretty_json(d));
    }
    if !entry.query.is_empty() {
        println!("  {}", "Query: ".bright_black());
        for q in &entry.query {
            println!("    {}", q.white());
        }
    }
    println!();
    Ok(())
}

fn cmd_rm(name: &str) -> Result<(), Box<dyn std::error::Error>> {
    let path = entry_path(name);
    if !path.exists() {
        return Err(format!("No entry named '{}'", name).into());
    }
    fs::remove_file(&path)?;
    println!("{} {}", "Deleted:".red(), name.cyan());
    Ok(())
}

// ── Env management ────────────────────────────────────────────────────────────

fn cmd_env(action: &EnvAction) {
    match action {
        EnvAction::Set { assignment } => {
            let mut map = load_env();
            if let Some(idx) = assignment.find('=') {
                let key   = assignment[..idx].trim().to_string();
                let value = assignment[idx + 1..].to_string();
                map.insert(key.clone(), value.clone());
                save_env(&map);
                println!("{} {}={}", "Set:".green(), key.cyan(), value.white());
            } else {
                eprintln!("{}", "Usage: env set KEY=VALUE".red());
            }
        }
        EnvAction::Unset { key } => {
            let mut map = load_env();
            if map.remove(key).is_some() {
                save_env(&map);
                println!("{} {}", "Removed:".yellow(), key.cyan());
            } else {
                println!("{} {}", "Not found:".bright_black(), key.cyan());
            }
        }
        EnvAction::List => {
            let map = load_env();
            if map.is_empty() {
                println!("{}", "No environment variables set.".bright_black());
                return;
            }
            println!("\n{}", "Environment Variables".bold().underline());
            let mut pairs: Vec<_> = map.iter().collect();
            pairs.sort_by_key(|(k, _)| k.as_str());
            for (k, v) in pairs {
                println!("  {} = {}", k.cyan(), v.white());
            }
            println!();
        }
    }
}

// ── History ───────────────────────────────────────────────────────────────────

fn cmd_history(args: &HistoryArgs) {
    if args.clear {
        let _ = fs::remove_file(history_file());
        println!("{}", "History cleared.".green());
        return;
    }
    let hist = load_history();
    if hist.is_empty() {
        println!("{}", "No history yet.".bright_black());
        return;
    }
    let show: Vec<_> = hist.iter().rev().take(args.count).collect();
    println!("\n{}", "Request History".bold().underline());
    for e in show.iter().rev() {
        let status_str = if e.status < 300 {
            e.status.to_string().green().bold()
        } else if e.status < 400 {
            e.status.to_string().cyan().bold()
        } else if e.status < 500 {
            e.status.to_string().yellow().bold()
        } else {
            e.status.to_string().red().bold()
        };
        println!(
            "  {}  {}  {:>6}ms  {} {}",
            e.timestamp.bright_black(),
            status_str,
            e.duration_ms.to_string().bright_black(),
            e.method.magenta(),
            e.url.white()
        );
    }
    println!();
}

// ── Main ──────────────────────────────────────────────────────────────────────

fn main() {
    let cli = Cli::parse();

    let result: Result<(), Box<dyn std::error::Error>> = match &cli.command {
        Commands::Req(args)            => send(args),
        Commands::Save(args)           => cmd_save(args),
        Commands::Run(args)            => cmd_run(args),
        Commands::List                 => { cmd_list(); Ok(()) }
        Commands::Show(args)           => cmd_show(&args.name),
        Commands::Rm(args)             => cmd_rm(&args.name),
        Commands::Env(e)               => { cmd_env(&e.action); Ok(()) }
        Commands::History(args)        => { cmd_history(args); Ok(()) }
    };

    if let Err(e) = result {
        eprintln!("{} {}", "Error:".red().bold(), e);
        std::process::exit(1);
    }
}
