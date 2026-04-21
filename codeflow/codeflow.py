#!/usr/bin/env python3
"""
codeflow — Local code architecture visualizer
Analyzes a local codebase and generates an interactive dependency graph
(force-directed, zoomable, filterable) as a self-contained HTML file.

Supports: Python, JavaScript/TypeScript, Go, Rust, C/C++, Java, Ruby, PHP

Usage:
    python codeflow.py [path] [-o output.html] [--open] [--no-calls]
"""

import argparse
import ast
import json
import os
import re
import sys
import webbrowser
from collections import defaultdict
from pathlib import Path

# ── Language configs ──────────────────────────────────────────────────────────

LANG_CONFIG = {
    ".py":   {"name": "Python",     "color": "#3572A5"},
    ".js":   {"name": "JavaScript", "color": "#F7DF1E"},
    ".jsx":  {"name": "React",      "color": "#61DAFB"},
    ".ts":   {"name": "TypeScript", "color": "#2B7489"},
    ".tsx":  {"name": "React/TS",   "color": "#2B7489"},
    ".go":   {"name": "Go",         "color": "#00ADD8"},
    ".rs":   {"name": "Rust",       "color": "#DEA584"},
    ".c":    {"name": "C",          "color": "#555555"},
    ".cpp":  {"name": "C++",        "color": "#F34B7D"},
    ".h":    {"name": "C Header",   "color": "#555555"},
    ".hpp":  {"name": "C++ Header", "color": "#F34B7D"},
    ".java": {"name": "Java",       "color": "#B07219"},
    ".rb":   {"name": "Ruby",       "color": "#701516"},
    ".php":  {"name": "PHP",        "color": "#4F5D95"},
    ".swift":{"name": "Swift",      "color": "#F05138"},
    ".kt":   {"name": "Kotlin",     "color": "#A97BFF"},
    ".cs":   {"name": "C#",         "color": "#178600"},
    ".lua":  {"name": "Lua",        "color": "#000080"},
}

IGNORE_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv",
    "env", ".env", "dist", "build", "target", ".next", ".nuxt", "coverage",
    ".pytest_cache", ".mypy_cache", ".tox", "vendor", "Pods",
}

SECURITY_PATTERNS = [
    (r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{4,}["\']',   "Hardcoded password"),
    (r'(?i)(api_?key|apikey)\s*=\s*["\'][A-Za-z0-9_\-]{8,}["\']', "Hardcoded API key"),
    (r'(?i)(secret|token)\s*=\s*["\'][A-Za-z0-9_\-]{8,}["\']', "Hardcoded secret/token"),
    (r'(?i)eval\s*\(',                                            "Use of eval()"),
    (r'(?i)exec\s*\(',                                            "Use of exec()"),
    (r'(?i)(SELECT|INSERT|UPDATE|DELETE).{0,30}["\'\+]\s*\+',    "Potential SQL injection"),
    (r'(?i)subprocess\.call\([^,)]*shell\s*=\s*True',            "Shell injection risk (shell=True)"),
    (r'(?i)os\.system\(',                                         "os.system() usage"),
    (r'-----BEGIN (RSA |EC )?PRIVATE KEY-----',                    "Private key in source"),
    (r'(?i)md5\s*\(',                                             "Weak hash (MD5)"),
]

# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_python(path: str, src: str) -> dict:
    """Extract imports, functions, classes, calls from a Python file."""
    data = {"imports": [], "functions": [], "classes": [], "calls": [], "lines": src.count("\n") + 1}
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return data

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import,)):
            for alias in node.names:
                data["imports"].append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                data["imports"].append(node.module.split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            data["functions"].append({"name": node.name, "line": node.lineno, "args": len(node.args.args)})
        elif isinstance(node, ast.ClassDef):
            data["classes"].append({"name": node.name, "line": node.lineno})
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                data["calls"].append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                data["calls"].append(node.func.attr)

    data["imports"] = list(set(data["imports"]))
    data["calls"] = list(set(data["calls"]))
    return data


def parse_js_ts(path: str, src: str) -> dict:
    """Regex-based extraction for JS/TS."""
    data = {"imports": [], "functions": [], "classes": [], "calls": [], "lines": src.count("\n") + 1}
    # imports
    for m in re.finditer(r'(?:import|require)\s*\(?["\']([^"\']+)["\']', src):
        mod = m.group(1)
        if not mod.startswith("."):
            data["imports"].append(mod.split("/")[0].lstrip("@"))
    # functions
    for m in re.finditer(r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)', src):
        name = m.group(1) or m.group(2)
        if name:
            data["functions"].append({"name": name, "line": src[:m.start()].count("\n") + 1, "args": 0})
    # classes
    for m in re.finditer(r'class\s+(\w+)', src):
        data["classes"].append({"name": m.group(1), "line": src[:m.start()].count("\n") + 1})
    data["imports"] = list(set(data["imports"]))
    return data


def parse_go(path: str, src: str) -> dict:
    data = {"imports": [], "functions": [], "classes": [], "calls": [], "lines": src.count("\n") + 1}
    for m in re.finditer(r'"([a-z][a-z0-9/_\-\.]+)"', src):
        pkg = m.group(1).split("/")[-1]
        data["imports"].append(pkg)
    for m in re.finditer(r'func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(', src):
        data["functions"].append({"name": m.group(1), "line": src[:m.start()].count("\n") + 1, "args": 0})
    for m in re.finditer(r'type\s+(\w+)\s+struct', src):
        data["classes"].append({"name": m.group(1), "line": src[:m.start()].count("\n") + 1})
    data["imports"] = list(set(data["imports"]))
    return data


def parse_rust(path: str, src: str) -> dict:
    data = {"imports": [], "functions": [], "classes": [], "calls": [], "lines": src.count("\n") + 1}
    for m in re.finditer(r'use\s+([\w:]+)', src):
        parts = m.group(1).split("::")
        data["imports"].append(parts[0])
    for m in re.finditer(r'fn\s+(\w+)\s*\(', src):
        data["functions"].append({"name": m.group(1), "line": src[:m.start()].count("\n") + 1, "args": 0})
    for m in re.finditer(r'struct\s+(\w+)', src):
        data["classes"].append({"name": m.group(1), "line": src[:m.start()].count("\n") + 1})
    for m in re.finditer(r'impl\s+(\w+)', src):
        data["classes"].append({"name": m.group(1), "line": src[:m.start()].count("\n") + 1})
    data["imports"] = list(set(data["imports"]))
    return data


def parse_generic(path: str, src: str) -> dict:
    """Very basic extraction using common patterns."""
    data = {"imports": [], "functions": [], "classes": [], "calls": [], "lines": src.count("\n") + 1}
    for m in re.finditer(r'(?:import|include|require|use)\s+["\']?([A-Za-z0-9_/\-.]+)["\']?', src):
        data["imports"].append(m.group(1).split("/")[-1].split(".")[0])
    for m in re.finditer(r'(?:def|function|func|fn|void|int|string|bool)\s+(\w+)\s*\(', src):
        data["functions"].append({"name": m.group(1), "line": src[:m.start()].count("\n") + 1, "args": 0})
    data["imports"] = list(set(data["imports"]))
    return data


PARSERS = {
    ".py":  parse_python,
    ".js":  parse_js_ts,
    ".jsx": parse_js_ts,
    ".ts":  parse_js_ts,
    ".tsx": parse_js_ts,
    ".go":  parse_go,
    ".rs":  parse_rust,
}


def get_parser(ext: str):
    return PARSERS.get(ext, parse_generic)


# ── Security scanner ──────────────────────────────────────────────────────────

def scan_security(src: str) -> list:
    issues = []
    for pattern, label in SECURITY_PATTERNS:
        for m in re.finditer(pattern, src):
            line = src[:m.start()].count("\n") + 1
            issues.append({"type": label, "line": line, "snippet": m.group(0)[:80]})
    return issues


# ── Health metrics ────────────────────────────────────────────────────────────

def health_score(node: dict) -> dict:
    """Return a score 0-100 and grade A-F."""
    score = 100
    penalties = []

    if node.get("lines", 0) > 500:
        score -= 15
        penalties.append("Large file (>500 lines)")
    if node.get("lines", 0) > 200:
        score -= 5

    funcs = len(node.get("functions", []))
    if funcs > 20:
        score -= 15
        penalties.append("Many functions (>20)")

    issues = len(node.get("security_issues", []))
    score -= issues * 15
    if issues:
        penalties.append(f"{issues} security issue(s)")

    score = max(0, score)
    if score >= 90:
        grade = "A"
    elif score >= 75:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 45:
        grade = "D"
    else:
        grade = "F"

    return {"score": score, "grade": grade, "penalties": penalties}


# ── Directory walker ──────────────────────────────────────────────────────────

def walk(root: str, analyze_calls: bool = True) -> dict:
    root = os.path.abspath(root)
    nodes = {}    # rel_path -> node dict
    edges = []    # {source, target, type}

    file_to_modules = {}   # module_name -> rel_path (for Python)
    rel_paths_by_stem = {}  # stem -> [rel_paths]

    # First pass: collect files
    all_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in LANG_CONFIG:
                continue
            abs_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(abs_path, root)
            all_files.append((rel_path, abs_path, ext))

    # Build stem lookup
    for rel, abs_p, ext in all_files:
        stem = os.path.splitext(os.path.basename(rel))[0]
        rel_paths_by_stem.setdefault(stem, []).append(rel)
        if ext == ".py":
            # module name = path without ext, slashes → dots
            mod = rel.replace(os.sep, ".").replace("/", ".").removesuffix(".py")
            file_to_modules[mod.split(".")[-1]] = rel

    # Second pass: parse each file
    for rel, abs_p, ext in all_files:
        try:
            src = open(abs_p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue

        lang = LANG_CONFIG[ext]
        parser = get_parser(ext)
        info = parser(abs_p, src)
        sec_issues = scan_security(src)
        health = health_score({**info, "security_issues": sec_issues})

        nodes[rel] = {
            "id": rel,
            "label": os.path.basename(rel),
            "path": rel,
            "ext": ext,
            "lang": lang["name"],
            "color": lang["color"],
            "lines": info.get("lines", 0),
            "functions": info.get("functions", []),
            "classes": info.get("classes", []),
            "imports": info.get("imports", []),
            "security_issues": sec_issues,
            "health": health,
            "size": os.path.getsize(abs_p),
        }

        # Build import edges
        for imp in info.get("imports", []):
            # Check if import matches a local file
            if imp in file_to_modules and file_to_modules[imp] != rel:
                edges.append({"source": rel, "target": file_to_modules[imp], "type": "import"})
            elif imp in rel_paths_by_stem:
                for target in rel_paths_by_stem[imp]:
                    if target != rel:
                        edges.append({"source": rel, "target": target, "type": "import"})

    # Deduplicate edges
    seen_edges = set()
    deduped = []
    for e in edges:
        key = (e["source"], e["target"], e["type"])
        if key not in seen_edges:
            seen_edges.add(key)
            deduped.append(e)

    # Summary stats
    total_lines = sum(n["lines"] for n in nodes.values())
    lang_counts: dict = defaultdict(int)
    for n in nodes.values():
        lang_counts[n["lang"]] += 1
    sec_total = sum(len(n["security_issues"]) for n in nodes.values())

    return {
        "nodes": list(nodes.values()),
        "edges": deduped,
        "root": root,
        "stats": {
            "files": len(nodes),
            "lines": total_lines,
            "edges": len(deduped),
            "security_issues": sec_total,
            "languages": dict(lang_counts),
        },
    }


# ── HTML template ─────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>CodeFlow — {title}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',system-ui,sans-serif;background:#1a1b26;color:#c0caf5;height:100vh;display:flex;flex-direction:column;overflow:hidden}}
#topbar{{background:#16161e;padding:10px 18px;display:flex;align-items:center;gap:14px;border-bottom:1px solid #292e42;flex-shrink:0}}
#topbar h1{{font-size:16px;font-weight:700;color:#7aa2f7;letter-spacing:.5px}}
#topbar .stats{{font-size:12px;color:#565f89;margin-left:auto;display:flex;gap:18px}}
#topbar .stat span{{color:#c0caf5;font-weight:600}}
#controls{{background:#16161e;padding:8px 18px;display:flex;gap:10px;align-items:center;border-bottom:1px solid #292e42;flex-wrap:wrap;flex-shrink:0}}
#controls input{{background:#1f2335;border:1px solid #292e42;color:#c0caf5;padding:5px 10px;border-radius:4px;font-size:12px;width:180px;outline:none}}
#controls input:focus{{border-color:#7aa2f7}}
#controls select{{background:#1f2335;border:1px solid #292e42;color:#c0caf5;padding:5px 8px;border-radius:4px;font-size:12px;outline:none}}
#controls button{{background:#1f2335;border:1px solid #292e42;color:#c0caf5;padding:5px 10px;border-radius:4px;font-size:12px;cursor:pointer;transition:.15s}}
#controls button:hover{{background:#292e42;border-color:#7aa2f7}}
#controls button.active{{background:#7aa2f7;color:#1a1b26;border-color:#7aa2f7}}
#main{{display:flex;flex:1;overflow:hidden}}
#sidebar{{width:300px;min-width:220px;background:#16161e;border-right:1px solid #292e42;display:flex;flex-direction:column;overflow:hidden;flex-shrink:0}}
#sidebar-header{{padding:12px 14px;font-size:11px;text-transform:uppercase;letter-spacing:.8px;color:#565f89;border-bottom:1px solid #292e42}}
#sidebar-content{{overflow-y:auto;flex:1;padding:8px}}
#sidebar-content::-webkit-scrollbar{{width:4px}}
#sidebar-content::-webkit-scrollbar-thumb{{background:#292e42;border-radius:2px}}
.file-item{{padding:8px 10px;border-radius:5px;cursor:pointer;margin-bottom:2px;transition:.12s;border:1px solid transparent}}
.file-item:hover{{background:#1f2335;border-color:#292e42}}
.file-item.selected{{background:#1f2335;border-color:#7aa2f7}}
.file-item .fname{{font-size:12px;font-weight:600;color:#c0caf5;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.file-item .fmeta{{font-size:11px;color:#565f89;margin-top:2px;display:flex;gap:8px}}
.grade{{font-size:11px;font-weight:700;padding:1px 5px;border-radius:3px}}
.grade-A{{background:#9ece6a22;color:#9ece6a}}.grade-B{{background:#7aa2f722;color:#7aa2f7}}
.grade-C{{background:#e0af6822;color:#e0af68}}.grade-D{{background:#ff9e6422;color:#ff9e64}}
.grade-F{{background:#f7768e22;color:#f7768e}}
#svg-area{{flex:1;position:relative;overflow:hidden}}
#svg-area svg{{width:100%;height:100%}}
.node circle{{stroke-width:2;cursor:pointer;transition:.15s}}
.node text{{font-size:10px;fill:#c0caf5;pointer-events:none;font-family:'Segoe UI',sans-serif}}
.node.dimmed circle{{opacity:.25}}.node.dimmed text{{opacity:.15}}
.node.highlighted circle{{stroke:#fff!important;stroke-width:3}}
.link{{stroke:#292e42;stroke-opacity:.7;stroke-width:1.5;fill:none}}
.link.import{{stroke:#7aa2f7;stroke-opacity:.5}}
.link.call{{stroke:#9ece6a;stroke-opacity:.4;stroke-dasharray:3,3}}
.link.dimmed{{opacity:.05}}
.link.highlighted{{stroke-opacity:1;stroke-width:2.5}}
#detail-panel{{position:absolute;bottom:16px;right:16px;width:310px;background:#1f2335;border:1px solid #292e42;border-radius:8px;padding:14px;display:none;font-size:12px;box-shadow:0 4px 24px #0008}}
#detail-panel h3{{font-size:13px;font-weight:700;color:#7aa2f7;margin-bottom:8px}}
#detail-panel .dp-row{{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #292e42}}
#detail-panel .dp-row:last-child{{border:none}}
#detail-panel .dp-label{{color:#565f89}}
#detail-panel .dp-val{{color:#c0caf5;font-weight:600;text-align:right;max-width:180px;word-break:break-all}}
#detail-panel .sec-warn{{color:#f7768e;font-size:11px;margin-top:6px}}
#detail-panel .funcs-list{{max-height:80px;overflow-y:auto;margin-top:4px}}
#detail-panel .funcs-list span{{background:#292e42;border-radius:3px;padding:1px 5px;margin:2px;display:inline-block;font-size:10px;color:#9ece6a}}
#legend{{position:absolute;top:12px;right:16px;background:#1f233599;border:1px solid #292e42;border-radius:6px;padding:8px 12px;font-size:11px}}
#legend div{{display:flex;align-items:center;gap:6px;margin-bottom:4px}}
#legend .dot{{width:10px;height:10px;border-radius:50%}}
.tooltip{{position:fixed;background:#1f2335;border:1px solid #292e42;border-radius:5px;padding:6px 10px;font-size:11px;color:#c0caf5;pointer-events:none;display:none;z-index:9999;max-width:240px}}
</style>
</head>
<body>
<div id="topbar">
  <h1>⬡ CodeFlow</h1>
  <div style="font-size:12px;color:#565f89">{root}</div>
  <div class="stats">
    <div>Files <span id="s-files">0</span></div>
    <div>Lines <span id="s-lines">0</span></div>
    <div>Edges <span id="s-edges">0</span></div>
    <div>Issues <span id="s-issues">0</span></div>
  </div>
</div>
<div id="controls">
  <input id="search" type="text" placeholder="Filter files…"/>
  <select id="lang-filter"><option value="">All Languages</option></select>
  <button id="btn-fit" title="Fit to screen">⊡ Fit</button>
  <button id="btn-deps" class="active" title="Show import edges">Imports</button>
  <button id="btn-security" title="Highlight security issues">⚠ Security</button>
  <button id="btn-health"   title="Highlight health scores">♥ Health</button>
  <button id="btn-reset"    title="Clear selection">✕ Clear</button>
  <span id="node-count" style="font-size:11px;color:#565f89;margin-left:auto"></span>
</div>
<div id="main">
  <div id="sidebar">
    <div id="sidebar-header">Files</div>
    <div id="sidebar-content"></div>
  </div>
  <div id="svg-area">
    <svg id="graph"></svg>
    <div id="legend">
      <div><div class="dot" style="background:#7aa2f7"></div> Import edge</div>
      <div><div class="dot" style="background:#9ece6a"></div> Call edge</div>
    </div>
    <div id="detail-panel"></div>
  </div>
</div>
<div class="tooltip" id="tooltip"></div>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const DATA = {graph_data};

const stats = DATA.stats;
document.getElementById('s-files').textContent  = stats.files;
document.getElementById('s-lines').textContent  = stats.lines.toLocaleString();
document.getElementById('s-edges').textContent  = stats.edges;
document.getElementById('s-issues').textContent = stats.security_issues;

// Populate language filter
const langs = [...new Set(DATA.nodes.map(n=>n.lang))].sort();
const lf = document.getElementById('lang-filter');
langs.forEach(l=>{{ const o=document.createElement('option');o.value=l;o.textContent=l;lf.appendChild(o); }});

// ── Sidebar ──
let selectedNode = null;
let filterText = '';
let filterLang = '';

function buildSidebar(nodes) {{
  const sc = document.getElementById('sidebar-content');
  sc.innerHTML = '';
  const visible = nodes.filter(n =>
    (filterText==='' || n.label.toLowerCase().includes(filterText)) &&
    (filterLang==='' || n.lang===filterLang)
  );
  document.getElementById('node-count').textContent = visible.length+' / '+DATA.nodes.length+' files';
  visible.sort((a,b)=>a.path.localeCompare(b.path)).forEach(n=>{{
    const el = document.createElement('div');
    el.className = 'file-item' + (selectedNode===n.id?' selected':'');
    el.innerHTML = `
      <div class="fname" title="${{n.path}}">${{n.label}}</div>
      <div class="fmeta">
        <span style="color:${{n.color}}">${{n.lang}}</span>
        <span>${{n.lines}} lines</span>
        <span class="grade grade-${{n.health.grade}}">${{n.health.grade}}</span>
        ${{n.security_issues.length>0?`<span style="color:#f7768e">⚠${{n.security_issues.length}}</span>`:''}}
      </div>`;
    el.addEventListener('click',()=>selectNode(n.id));
    sc.appendChild(el);
  }});
}}

document.getElementById('search').addEventListener('input', e=>{{
  filterText = e.target.value.toLowerCase();
  buildSidebar(DATA.nodes);
  updateVisibility();
}});
document.getElementById('lang-filter').addEventListener('change', e=>{{
  filterLang = e.target.value;
  buildSidebar(DATA.nodes);
  updateVisibility();
}});

// ── D3 Graph ──
const svg = d3.select('#graph');
const g   = svg.append('g');

svg.call(d3.zoom().scaleExtent([0.05,5]).on('zoom', e=>g.attr('transform',e.transform)));

const nodes = DATA.nodes.map(d=>Object.assign({{}},d));
const links = DATA.edges.map(d=>Object.assign({{}},d));

const simulation = d3.forceSimulation(nodes)
  .force('link',   d3.forceLink(links).id(d=>d.id).distance(d=>d.type==='import'?120:80).strength(0.5))
  .force('charge', d3.forceManyBody().strength(-180))
  .force('center', d3.forceCenter(0,0))
  .force('x',      d3.forceX(0).strength(0.04))
  .force('y',      d3.forceY(0).strength(0.04))
  .force('collide',d3.forceCollide(28));

const link = g.append('g').selectAll('.link')
  .data(links).enter().append('path')
  .attr('class',d=>'link '+d.type)
  .attr('marker-end',d=>d.type==='import'?'url(#arrow-import)':'url(#arrow-call)');

// Arrow markers
const defs = svg.append('defs');
[['import','#7aa2f7'],['call','#9ece6a']].forEach(([id,col])=>{{
  defs.append('marker').attr('id','arrow-'+id)
    .attr('viewBox','0 -5 10 10').attr('refX',22).attr('refY',0)
    .attr('markerWidth',6).attr('markerHeight',6).attr('orient','auto')
    .append('path').attr('d','M0,-5L10,0L0,5').attr('fill',col).attr('opacity',.7);
}});

const nodeG = g.append('g').selectAll('.node')
  .data(nodes).enter().append('g').attr('class','node')
  .call(d3.drag()
    .on('start',(e,d)=>{{if(!e.active)simulation.alphaTarget(.3).restart();d.fx=d.x;d.fy=d.y;}})
    .on('drag', (e,d)=>{{d.fx=e.x;d.fy=e.y;}})
    .on('end',  (e,d)=>{{if(!e.active)simulation.alphaTarget(0);d.fx=null;d.fy=null;}}));

nodeG.append('circle')
  .attr('r', d=>Math.max(8, Math.min(22, 6+d.lines/60)))
  .attr('fill',d=>d.color+'33')
  .attr('stroke',d=>d.color)
  .on('click',(_,d)=>selectNode(d.id))
  .on('mouseover',(e,d)=>showTooltip(e,d))
  .on('mousemove', e=>moveTooltip(e))
  .on('mouseout', ()=>hideTooltip());

nodeG.append('text')
  .text(d=>d.label.length>16?d.label.slice(0,14)+'…':d.label)
  .attr('dy','2.2em').attr('text-anchor','middle');

simulation.on('tick',()=>{{
  link.attr('d',d=>{{
    const dx=d.target.x-d.source.x, dy=d.target.y-d.source.y;
    const dr=Math.sqrt(dx*dx+dy*dy)*1.6;
    return `M${{d.source.x}},${{d.source.y}}A${{dr}},${{dr}} 0 0,1 ${{d.target.x}},${{d.target.y}}`;
  }});
  nodeG.attr('transform',d=>`translate(${{d.x}},${{d.y}})`);
}});

// ── Fit ──
function fitGraph() {{
  const svgEl = document.getElementById('graph');
  const w=svgEl.clientWidth, h=svgEl.clientHeight;
  const xs=nodes.map(n=>n.x||0), ys=nodes.map(n=>n.y||0);
  if(!xs.length)return;
  const minX=Math.min(...xs),maxX=Math.max(...xs),minY=Math.min(...ys),maxY=Math.max(...ys);
  const pad=60;
  const sc=Math.min((w-pad*2)/(maxX-minX+1),(h-pad*2)/(maxY-minY+1),3);
  const tx=w/2-sc*(minX+maxX)/2, ty=h/2-sc*(minY+maxY)/2;
  svg.transition().duration(500).call(
    d3.zoom().transform, d3.zoomIdentity.translate(tx,ty).scale(sc));
}}
document.getElementById('btn-fit').addEventListener('click',fitGraph);
simulation.on('end',()=>setTimeout(fitGraph,100));

// ── Selection ──
function selectNode(id){{
  selectedNode = id===selectedNode ? null : id;
  buildSidebar(DATA.nodes);
  updateHighlight();
  showDetail(id===selectedNode?id:null);
}}

function updateHighlight(){{
  if(!selectedNode){{
    nodeG.classed('dimmed',false).classed('highlighted',false);
    link.classed('dimmed',false).classed('highlighted',false);
    return;
  }}
  const connected = new Set([selectedNode]);
  links.forEach(l=>{{
    const s=typeof l.source==='object'?l.source.id:l.source;
    const t=typeof l.target==='object'?l.target.id:l.target;
    if(s===selectedNode)connected.add(t);
    if(t===selectedNode)connected.add(s);
  }});
  nodeG.classed('dimmed',d=>!connected.has(d.id)).classed('highlighted',d=>d.id===selectedNode);
  link.classed('dimmed',d=>{{
    const s=typeof d.source==='object'?d.source.id:d.source;
    const t=typeof d.target==='object'?d.target.id:d.target;
    return s!==selectedNode&&t!==selectedNode;
  }}).classed('highlighted',d=>{{
    const s=typeof d.source==='object'?d.source.id:d.source;
    const t=typeof d.target==='object'?d.target.id:d.target;
    return s===selectedNode||t===selectedNode;
  }});
}}

function updateVisibility(){{
  const visible = new Set(DATA.nodes
    .filter(n=>(filterText===''||n.label.toLowerCase().includes(filterText))&&(filterLang===''||n.lang===filterLang))
    .map(n=>n.id));
  nodeG.style('display',d=>visible.has(d.id)?null:'none');
  link.style('display',d=>{{
    const s=typeof d.source==='object'?d.source.id:d.source;
    const t=typeof d.target==='object'?d.target.id:d.target;
    return visible.has(s)&&visible.has(t)?null:'none';
  }});
}}

// ── Detail panel ──
function showDetail(id){{
  const dp = document.getElementById('detail-panel');
  if(!id){{dp.style.display='none';return;}}
  const n = DATA.nodes.find(x=>x.id===id);
  if(!n)return;
  const deps = links.filter(l=>{{
    const s=typeof l.source==='object'?l.source.id:l.source;
    return s===id;
  }}).map(l=>typeof l.target==='object'?l.target.id:l.target);
  const rdeps = links.filter(l=>{{
    const t=typeof l.target==='object'?l.target.id:l.target;
    return t===id;
  }}).map(l=>typeof l.source==='object'?l.source.id:l.source);
  const funcsHtml = n.functions.length
    ? '<div class="funcs-list">'+n.functions.map(f=>`<span title="line ${{f.line}}">${{f.name}}</span>`).join('')+'</div>' : '';
  dp.innerHTML = `
    <h3 title="${{n.path}}">${{n.label}}</h3>
    <div class="dp-row"><span class="dp-label">Language</span><span class="dp-val">${{n.lang}}</span></div>
    <div class="dp-row"><span class="dp-label">Lines</span><span class="dp-val">${{n.lines}}</span></div>
    <div class="dp-row"><span class="dp-label">Functions</span><span class="dp-val">${{n.functions.length}}</span></div>
    <div class="dp-row"><span class="dp-label">Classes</span><span class="dp-val">${{n.classes.length}}</span></div>
    <div class="dp-row"><span class="dp-label">Health</span><span class="dp-val"><span class="grade grade-${{n.health.grade}}">${{n.health.grade}}</span> ${{n.health.score}}/100</span></div>
    <div class="dp-row"><span class="dp-label">Imports</span><span class="dp-val">${{deps.length}} files</span></div>
    <div class="dp-row"><span class="dp-label">Imported by</span><span class="dp-val">${{rdeps.length}} files</span></div>
    ${{funcsHtml}}
    ${{n.security_issues.length?'<div class="sec-warn">⚠ '+n.security_issues.map(i=>`${{i.type}} (line ${{i.line}})`).join('<br>')+'</div>':''}}
  `;
  dp.style.display='block';
}}

// ── Modes ──
let showImports=true, showCalls=false, secMode=false, healthMode=false;

document.getElementById('btn-deps').addEventListener('click',()=>{{
  showImports=!showImports;
  document.getElementById('btn-deps').classList.toggle('active',showImports);
  link.filter(d=>d.type==='import').style('display',showImports?null:'none');
}});
document.getElementById('btn-security').addEventListener('click',()=>{{
  secMode=!secMode;
  document.getElementById('btn-security').classList.toggle('active',secMode);
  healthMode=false;
  document.getElementById('btn-health').classList.remove('active');
  nodeG.select('circle').attr('stroke',d=>{{
    if(secMode)return d.security_issues.length?'#f7768e':d.color+'55';
    return d.color;
  }});
}});
document.getElementById('btn-health').addEventListener('click',()=>{{
  healthMode=!healthMode;
  document.getElementById('btn-health').classList.toggle('active',healthMode);
  secMode=false;
  document.getElementById('btn-security').classList.remove('active');
  const gc={{'A':'#9ece6a','B':'#7aa2f7','C':'#e0af68','D':'#ff9e64','F':'#f7768e'}};
  nodeG.select('circle').attr('stroke',d=>healthMode?(gc[d.health.grade]||d.color):d.color);
}});
document.getElementById('btn-reset').addEventListener('click',()=>{{
  selectedNode=null;filterText='';filterLang='';
  document.getElementById('search').value='';
  document.getElementById('lang-filter').value='';
  buildSidebar(DATA.nodes);updateHighlight();updateVisibility();
  document.getElementById('detail-panel').style.display='none';
  secMode=healthMode=false;
  document.getElementById('btn-security').classList.remove('active');
  document.getElementById('btn-health').classList.remove('active');
  nodeG.select('circle').attr('stroke',d=>d.color);
}});

// ── Tooltip ──
const tooltip=document.getElementById('tooltip');
function showTooltip(e,d){{
  tooltip.innerHTML=`<b>${{d.label}}</b><br>${{d.lang}} · ${{d.lines}} lines · Health ${{d.health.grade}}`+(d.security_issues.length?`<br>⚠ ${{d.security_issues.length}} issue(s)`:'');
  tooltip.style.display='block';
  moveTooltip(e);
}}
function moveTooltip(e){{tooltip.style.left=(e.clientX+12)+'px';tooltip.style.top=(e.clientY+12)+'px';}}
function hideTooltip(){{tooltip.style.display='none';}}

// Initial build
buildSidebar(DATA.nodes);
</script>
</body>
</html>
"""


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="codeflow — local code architecture visualizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python codeflow.py .
  python codeflow.py ~/myproject -o arch.html --open
  python codeflow.py src/ -o out.html
""",
    )
    parser.add_argument("path", nargs="?", default=".", help="Directory to analyze (default: .)")
    parser.add_argument("-o", "--output", default="codeflow.html", help="Output HTML file (default: codeflow.html)")
    parser.add_argument("--open", action="store_true", help="Open result in browser")
    parser.add_argument("--no-calls", action="store_true", help="Skip call graph analysis")
    parser.add_argument("--json", action="store_true", help="Also dump raw JSON to stdout")
    args = parser.parse_args()

    path = os.path.abspath(args.path)
    if not os.path.isdir(path):
        print(f"Error: '{path}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing {path} …")
    data = walk(path, analyze_calls=not args.no_calls)

    s = data["stats"]
    print(f"  {s['files']} files  |  {s['lines']:,} lines  |  {s['edges']} edges  |  {s['security_issues']} security issues")

    if args.json:
        print(json.dumps(data, indent=2))

    title = os.path.basename(path)
    graph_json = json.dumps(data, separators=(",", ":"))
    html = HTML_TEMPLATE.replace("{title}", title)\
                        .replace("{root}", path)\
                        .replace("{graph_data}", graph_json)

    out = os.path.abspath(args.output)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  Output: {out}")

    if args.open:
        webbrowser.open(f"file://{out}")
        print("  Opened in browser.")


if __name__ == "__main__":
    main()
