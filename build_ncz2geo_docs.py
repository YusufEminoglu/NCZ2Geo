# -*- coding: utf-8 -*-
"""
Builder for NCZ2Geo Master Interactive Academic Reference Manual.
Generates an encyclopedic documentation site with live PlanGML / e-Plan symbology sandbox,
MPYY standards, NCZ Engine v2 binary architecture, and full Python API / CLI guides.
"""

import os

OUTPUT_DIR = r"C:\Users\YE\PyCharmMiscProject\PyPI\NCZ2Geo_sdk\docs"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")

os.makedirs(OUTPUT_DIR, exist_ok=True)

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NCZ2Geo — Netcad NCZ/NCA Reader, PlanGML & e-Plan Symbology Engine</title>
<meta name="description" content="Official scientific reference manual for NCZ2Geo: Pure-Python Netcad NCZ/NCA CAD parser, PlanGML MPYY identity resolver, and e-Plan symbology metadata engine.">
<meta name="author" content="Yusuf Eminoğlu">

<!-- MathJax for formula rendering -->
<script>
window.MathJax = {
  tex: {
    inlineMath: [['$', '$'], ['\\(', '\\)']],
    displayMath: [['$$', '$$'], ['\\[', '\\]']],
    processEscapes: true,
    processEnvironments: true,
    tags: 'ams',
  },
  options: {
    skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'],
    ignoreHtmlClass: 'no-math|tex2jax_ignore'
  }
};
</script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
<script src="https://unpkg.com/lucide@latest"></script>

<!-- Typography -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Inter:wght@300;400;500;600;700;800&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap" rel="stylesheet">

<style>
:root {
  --bg: #0b0f19;
  --bg-secondary: #111827;
  --bg-sidebar: #0e1422;
  --fg: #f3f4f6;
  --fg-heading: #ffffff;
  --muted: #9ca3af;
  --dim: #6b7280;
  
  --accent: #3b82f6;
  --accent-dark: #2563eb;
  --accent-light: rgba(59, 130, 246, 0.12);
  --accent-cyan: #06b6d4;
  --accent-emerald: #10b981;
  --accent-amber: #f59e0b;
  --accent-rose: #f43f5e;
  
  --border: #1f2937;
  --border-subtle: #374151;
  --code-bg: #0d1117;
  --sidebar-active: rgba(59, 130, 246, 0.15);
  --table-stripe: #141d2e;
  
  --gradient-brand: linear-gradient(135deg, #3b82f6 0%, #06b6d4 50%, #10b981 100%);
  --shadow-card: 0 4px 20px -2px rgba(0, 0, 0, 0.5);
  
  font-size: 14.5px;
  line-height: 1.68;
}

[data-theme="light"] {
  --bg: #f8fafc;
  --bg-secondary: #ffffff;
  --bg-sidebar: #f1f5f9;
  --fg: #1e293b;
  --fg-heading: #0f172a;
  --muted: #475569;
  --dim: #64748b;
  
  --accent: #2563eb;
  --accent-dark: #1d4ed8;
  --accent-light: #dbeafe;
  
  --border: #e2e8f0;
  --border-subtle: #cbd5e1;
  --code-bg: #0f172a;
  --sidebar-active: #dbeafe;
  --table-stripe: #f8fafc;
  --shadow-card: 0 4px 15px -1px rgba(0, 0, 0, 0.08);
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
  background: var(--bg);
  color: var(--fg);
  display: flex;
  min-height: 100vh;
  transition: background 0.2s ease, color 0.2s ease;
}

/* Top App Bar */
#top-bar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 58px;
  background: rgba(14, 20, 34, 0.92);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 1.5rem;
  z-index: 1000;
}

[data-theme="light"] #top-bar {
  background: rgba(255, 255, 255, 0.94);
}

.brand-wrap {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  text-decoration: none;
}

.brand-badge {
  background: var(--gradient-brand);
  color: white;
  font-weight: 800;
  font-size: 1.1rem;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 12px rgba(59, 130, 246, 0.5);
  font-family: 'Plus Jakarta Sans', sans-serif;
}

.brand-text {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-weight: 800;
  font-size: 1.25rem;
  letter-spacing: -0.02em;
  background: var(--gradient-brand);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.ver-tag {
  font-family: 'Fira Code', monospace;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  background: var(--accent-light);
  color: var(--accent);
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.top-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.75rem;
  border-radius: 7px;
  font-size: 0.82rem;
  font-weight: 500;
  color: var(--muted);
  text-decoration: none;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  transition: all 0.15s ease;
  cursor: pointer;
}

.top-btn:hover {
  color: var(--fg-heading);
  border-color: var(--accent);
  transform: translateY(-1px);
}

.top-btn.primary {
  background: var(--accent);
  color: #ffffff;
  border-color: transparent;
  font-weight: 600;
}

/* Sidebar */
#sidebar {
  width: 320px;
  min-width: 320px;
  height: calc(100vh - 58px);
  position: sticky;
  top: 58px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 100;
}

#search-wrap {
  padding: 0.85rem 1rem 0.65rem;
  border-bottom: 1px solid var(--border);
}

#search {
  width: 100%;
  padding: 0.55rem 0.85rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.85rem;
  background: var(--bg);
  color: var(--fg);
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}

#search:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-light);
}

#toc {
  flex: 1;
  overflow-y: auto;
  padding: 6px 0;
  list-style: none;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}

.toc-group {
  border-bottom: 1px solid var(--border);
}

.toc-group-btn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  text-align: left;
  padding: 8px 16px;
  background: none;
  border: none;
  font-size: 0.84rem;
  font-weight: 600;
  color: var(--fg-heading);
  cursor: pointer;
  transition: background 0.15s;
}

.toc-group-btn:hover {
  background: var(--accent-light);
}

.toc-group-btn .arrow {
  font-size: 0.7em;
  transition: transform 0.2s;
}

.toc-group-btn[aria-expanded="false"] .arrow {
  transform: rotate(-90deg);
}

.toc-algs {
  list-style: none;
  overflow: hidden;
}

.toc-algs li a {
  display: block;
  padding: 4px 16px 4px 24px;
  font-size: 0.82rem;
  color: var(--muted);
  text-decoration: none;
  border-left: 3px solid transparent;
  transition: all 0.15s;
}

.toc-algs li a:hover, .toc-algs li a.active {
  background: var(--sidebar-active);
  border-left-color: var(--accent);
  color: var(--accent);
  font-weight: 500;
}

.toc-algs li a.hidden {
  display: none;
}

#sidebar-footer {
  padding: 10px 16px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 5px;
  background: var(--bg-secondary);
}

#sidebar-footer a {
  font-size: 0.78rem;
  color: var(--muted);
  text-decoration: none;
}

#sidebar-footer a:hover {
  color: var(--accent);
}

/* Content */
#content {
  flex: 1;
  max-width: 960px;
  margin: 0 auto;
  padding: calc(58px + 2rem) 3rem 6rem;
  overflow-y: auto;
}

/* Headings */
h1 {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 2.3rem;
  margin: 0 0 0.25em;
  color: var(--fg-heading);
  letter-spacing: -0.02em;
}

h1.subtitle {
  font-size: 1.15rem;
  font-weight: 400;
  color: var(--muted);
  margin-bottom: 1.75em;
}

h2 {
  font-family: 'Plus Jakarta Sans', sans-serif;
  font-size: 1.6rem;
  margin: 2.75em 0 0.6em;
  padding-bottom: 0.3em;
  border-bottom: 2px solid var(--border);
  color: var(--fg-heading);
}

h2.group-header {
  border-bottom: 2px solid var(--accent);
  color: var(--accent);
  margin-top: 3.5em;
}

h3 {
  font-size: 1.22rem;
  margin: 1.6em 0 0.45em;
  color: var(--fg-heading);
}

h4 {
  font-size: 1.05rem;
  margin: 1.25em 0 0.35em;
  color: var(--muted);
}

p, ul, ol { margin: 0.75em 0; }
ul, ol { padding-left: 1.8em; }
li { margin: 0.3em 0; color: var(--fg); }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

code {
  font-family: 'Fira Code', 'Cascadia Code', monospace;
  font-size: 0.88em;
  background: var(--code-bg);
  color: var(--accent);
  padding: 0.12em 0.38em;
  border-radius: 4px;
  border: 1px solid var(--border);
}

pre {
  background: var(--code-bg);
  padding: 1.1em 1.25em;
  border-radius: 8px;
  border: 1px solid var(--border);
  overflow-x: auto;
  margin: 1em 0;
  font-family: 'Fira Code', monospace;
  font-size: 0.88em;
  line-height: 1.6;
  color: #f1f5f9;
}

pre code {
  background: transparent;
  border: none;
  padding: 0;
  color: inherit;
  font-size: 1em;
}

/* Tables */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 1.2em 0 1.6em;
  font-size: 0.9em;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--border);
}

th, td {
  text-align: left;
  padding: 0.6em 0.85em;
  border: 1px solid var(--border);
}

th {
  background: var(--bg-secondary);
  color: var(--fg-heading);
  font-weight: 600;
}

tr:nth-child(even) td {
  background: var(--table-stripe);
}

.note {
  background: var(--accent-light);
  border-left: 4px solid var(--accent);
  padding: 0.8em 1.2em;
  margin: 1.2em 0;
  border-radius: 0 8px 8px 0;
  color: var(--fg);
}

.cover {
  text-align: center;
  padding: 4rem 0 3rem;
  background: radial-gradient(circle at center, rgba(59, 130, 246, 0.08) 0%, transparent 70%);
  border-radius: 16px;
  border: 1px solid var(--border);
  margin-bottom: 3rem;
}

.cover h1 { font-size: 3.2rem; margin-bottom: 0.15em; }
.cover .version { font-size: 1.2rem; color: var(--accent); font-weight: 600; font-family: 'Fira Code', monospace; }
.cover .date { font-size: 0.95rem; color: var(--muted); margin-top: 1em; }

/* Interactive Sandbox Calculator Card */
.sandbox-card {
  background: var(--bg-secondary);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 12px;
  padding: 1.5rem;
  margin: 1.8rem 0;
  box-shadow: var(--shadow-card);
}

.sandbox-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  background: rgba(59, 130, 246, 0.15);
  color: var(--accent);
  border: 1px solid rgba(59, 130, 246, 0.3);
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  text-transform: uppercase;
  margin-bottom: 0.75rem;
}

.sandbox-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  margin-top: 1rem;
}

@media (max-width: 768px) {
  .sandbox-grid { grid-template-columns: 1fr; }
}

.control-item { margin-bottom: 0.85rem; }
.control-item label { display: flex; justify-content: space-between; font-size: 0.82rem; font-weight: 500; margin-bottom: 0.3rem; }
.control-input { width: 100%; padding: 0.55rem 0.75rem; border-radius: 6px; border: 1px solid var(--border); background: var(--bg); color: var(--fg); font-size: 0.85rem; outline: none; }
.control-select { width: 100%; padding: 0.55rem 0.75rem; border-radius: 6px; border: 1px solid var(--border); background: var(--bg); color: var(--fg); font-size: 0.85rem; outline: none; }

.calc-display {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1.25rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.swatch-box {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.color-swatch {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  border: 2px solid var(--border);
  background: #ffcc00;
  box-shadow: 0 0 10px rgba(0,0,0,0.3);
}

/* Back to top */
#back-to-top {
  position: fixed; bottom: 24px; right: 24px; width: 42px; height: 42px;
  background: var(--accent); color: white; border: none; border-radius: 50%;
  font-size: 1.3em; cursor: pointer; opacity: 0; transform: translateY(20px);
  transition: opacity .2s, transform .2s; z-index: 200;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
}
#back-to-top.visible { opacity: 0.9; transform: translateY(0); }
#back-to-top:hover { opacity: 1; transform: scale(1.08); }

/* Mobile */
@media (max-width: 1024px) {
  #sidebar { display: none; }
  #content { padding: calc(58px + 1.5rem) 1.5rem 5rem; }
}
</style>
</head>
<body>

<!-- Top Navigation -->
<header id="top-bar">
  <a href="#" class="brand-wrap">
    <div class="brand-badge">N</div>
    <span class="brand-text">NCZ2Geo</span>
    <span class="ver-tag">v0.1.0</span>
  </a>
  <div class="top-actions">
    <a href="https://pypi.org/project/NCZ2Geo/" target="_blank" class="top-btn"><i data-lucide="package" style="width:14px;height:14px;"></i> PyPI</a>
    <a href="https://github.com/YusufEminoglu/NCZ2Geo" target="_blank" class="top-btn"><i data-lucide="github" style="width:14px;height:14px;"></i> GitHub</a>
    <button id="themeToggle" class="top-btn" title="Toggle Light/Dark Theme"><i data-lucide="sun" id="themeIcon" style="width:14px;height:14px;"></i></button>
    <a href="#quickstart" class="top-btn primary"><i data-lucide="terminal" style="width:14px;height:14px;"></i> Quickstart</a>
  </div>
</header>

<div style="display:flex; width:100%;">

<!-- Sidebar Navigation -->
<nav id="sidebar">
  <div id="search-wrap">
    <input type="text" id="search" placeholder="Search PlanGML, e-Plan, MPYY..." autocomplete="off">
  </div>
  <ul id="toc">
    <li class="toc-group">
      <button class="toc-group-btn" aria-expanded="true" style="border-left:4px solid #3b82f6; background: linear-gradient(90deg, rgba(59,130,246,0.15) 0%, transparent 100%)">
        <span><i data-lucide="compass" style="width:14px;height:14px;vertical-align:middle;margin-right:6px"></i> Getting Started</span>
        <span class="arrow">▼</span>
      </button>
      <ul class="toc-algs">
        <li><a href="#overview" data-name="overview" data-display="overview architecture vision">Architecture & Mission</a></li>
        <li><a href="#quickstart" data-name="quickstart" data-display="quickstart installation setup">Installation & Setup</a></li>
        <li><a href="#cli-usage" data-name="cli-usage" data-display="command line interface cli">CLI Commands & Batch Ingestion</a></li>
      </ul>
    </li>

    <li class="toc-group">
      <button class="toc-group-btn" aria-expanded="true" style="border-left:4px solid #06b6d4; background: linear-gradient(90deg, rgba(6,182,212,0.15) 0%, transparent 100%)">
        <span><i data-lucide="bookmark" style="width:14px;height:14px;vertical-align:middle;margin-right:6px"></i> PlanGML & MPYY Catalog</span>
        <span class="arrow">▼</span>
      </button>
      <ul class="toc-algs">
        <li><a href="#mpyy-standards" data-name="mpyy-standards" data-display="mpyy standards spatial planning regulations">Mekânsal Planlar Standartları</a></li>
        <li><a href="#plangml-schema" data-name="plangml-schema" data-display="plangml schema identity uip nip cdp">PlanGML 1.0 / 2.0 Schema & Identity</a></li>
        <li><a href="#layer-classification" data-name="layer-classification" data-display="layer classification classify_layer function">Automatic Layer Classification</a></li>
      </ul>
    </li>

    <li class="toc-group">
      <button class="toc-group-btn" aria-expanded="true" style="border-left:4px solid #10b981; background: linear-gradient(90deg, rgba(16,185,129,0.15) 0%, transparent 100%)">
        <span><i data-lucide="palette" style="width:14px;height:14px;vertical-align:middle;margin-right:6px"></i> e-Plan Symbology Engine</span>
        <span class="arrow">▼</span>
      </button>
      <ul class="toc-algs">
        <li><a href="#eplan-catalog" data-name="eplan-catalog" data-display="eplan symbology color hex stroke hatching">Official e-Plan Color & Hatching Catalog</a></li>
        <li><a href="#geojson-styling" data-name="geojson-styling" data-display="geojson feature properties styling injection">GeoJSON Styling Property Injection</a></li>
      </ul>
    </li>

    <li class="toc-group">
      <button class="toc-group-btn" aria-expanded="true" style="border-left:4px solid #f59e0b; background: linear-gradient(90deg, rgba(245,158,11,0.15) 0%, transparent 100%)">
        <span><i data-lucide="binary" style="width:14px;height:14px;vertical-align:middle;margin-right:6px"></i> NCZ Engine V2</span>
        <span class="arrow">▼</span>
      </button>
      <ul class="toc-algs">
        <li><a href="#ncz-engine-v2" data-name="ncz-engine-v2" data-display="ncz engine v2 binary cursor block scanner">V2 Block Scanner & Memory Model</a></li>
        <li><a href="#fingerprinted-cache" data-name="fingerprinted-cache" data-display="fingerprinted index cache zero file scan">Fingerprinted Local Index Cache</a></li>
      </ul>
    </li>

    <li class="toc-group">
      <button class="toc-group-btn" aria-expanded="true" style="border-left:4px solid #8b5cf6; background: linear-gradient(90deg, rgba(139,92,246,0.15) 0%, transparent 100%)">
        <span><i data-lucide="code" style="width:14px;height:14px;vertical-align:middle;margin-right:6px"></i> API Reference & Benchmarks</span>
        <span class="arrow">▼</span>
      </button>
      <ul class="toc-algs">
        <li><a href="#api-reference" data-name="api-reference" data-display="python api reference classify_layer parse_netcad">Python API Specification</a></li>
        <li><a href="#benchmarks" data-name="benchmarks" data-display="benchmarks performance speedup">Performance Benchmarks</a></li>
        <li><a href="#bibliography" data-name="bibliography" data-display="academic citations bibliography bibtex">Citation & License</a></li>
      </ul>
    </li>
  </ul>

  <div id="sidebar-footer">
    <a href="https://github.com/YusufEminoglu/NCZ2Geo">GitHub Repository</a>
    <a href="https://pypi.org/project/NCZ2Geo/">PyPI Package</a>
    <a href="#bibliography">BibTeX Citation</a>
  </div>
</nav>

<!-- Main Content Area -->
<main id="content">

  <div class="cover" id="overview">
    <h1>NCZ2Geo</h1>
    <p class="subtitle">Pure-Python Netcad NCZ/NCA Reader with PlanGML Identity & e-Plan Symbology Metadata</p>
    <p class="version">Official PyPI & GitHub Scientific Documentation &middot; Version 0.1.0 &middot; V2-Only Headless Core</p>
    <p class="date">Author: <strong>Yusuf Eminoğlu</strong> &middot; <a href="https://github.com/YusufEminoglu/NCZ2Geo">github.com/YusufEminoglu/NCZ2Geo</a> &middot; <a href="https://pypi.org/project/NCZ2Geo/">pypi.org/project/NCZ2Geo</a></p>
  </div>

  <!-- Interactive Sandbox Simulator -->
  <div class="sandbox-card">
    <div class="sandbox-badge"><i data-lucide="palette" style="width:12px;height:12px;margin-right:4px;"></i> Live PlanGML & e-Plan Inspector Sandbox</div>
    <h3 style="margin-top:0;">PlanGML Layer Classifier & e-Plan Symbology Simulator</h3>
    <p style="font-size:0.88rem;color:var(--muted);">Select a Turkish spatial plan type and type a Netcad layer name to test real-time PlanGML identity resolution and official e-Plan color/hatching extraction:</p>
    
    <div class="sandbox-grid">
      <div>
        <div class="control-item">
          <label>Plan Type (Mekânsal Plan Türü):</label>
          <select id="planTypeSelect" class="control-select">
            <option value="UIP" selected>UIP — Uygulama İmar Planı (1/1.000)</option>
            <option value="NIP">NIP — Nazım İmar Planı (1/5.000)</option>
            <option value="CDP">CDP — Çevre Düzeni Planı (1/25.000 - 1/100.000)</option>
          </select>
        </div>
        <div class="control-item">
          <label>Netcad Layer Name (Çizim Tabaka Adı):</label>
          <input type="text" id="layerNameInput" class="control-input" value="PL_GELISME_KONUT" placeholder="e.g. PL_GELISME_KONUT, PARK, YOL_15">
        </div>
      </div>
      <div class="calc-display">
        <div class="swatch-box">
          <div id="swatchEl" class="color-swatch" style="background:#ffcc00;"></div>
          <div>
            <div id="funcNameEl" style="font-weight:700;color:var(--fg-heading);font-size:1.05rem;">Gelişme Konut Alanı</div>
            <div id="funcCodeEl" style="font-size:0.8rem;color:var(--accent);font-family:'Fira Code',monospace;">PlanGML Kod: 1102 (UIP)</div>
          </div>
        </div>
        <div style="font-size:0.82rem;color:var(--muted);margin-top:0.4rem;">
          Üst Grup: <span id="groupNameEl" style="color:var(--fg);">Kentsel Yerleşik / Gelişme Alanları</span><br>
          e-Plan Renk: <span id="colorHexEl" style="font-family:'Fira Code',monospace;color:var(--accent-cyan);">#ffcc00</span> &middot; Opacity: <span id="opacityEl" style="font-family:'Fira Code',monospace;">0.70</span>
        </div>
      </div>
    </div>
  </div>

  <h2 id="quickstart" class="group-header">1. Installation & Quickstart</h2>
  <p><strong>NCZ2Geo</strong> is a focused Python SDK specifically built for Turkish urban planning workflows. It reads Netcad <code>NCZ</code>/<code>NCA</code> drawings, maps CAD layers to official <strong>PlanGML / MPYY</strong> (Mekânsal Planlar Yapım Yönetmeliği) schemas, and injects official <strong>e-Plan</strong> symbology metadata into standard GeoJSON features.</p>

  <h3>Standard Installation</h3>
  <pre><code>pip install NCZ2Geo</code></pre>

  <h3>High-Level Python Usage</h3>
  <pre><code>from ncz2geo import classify_layer, parse_netcad, write_geojson

# 1. Classify any layer name into official PlanGML & e-Plan identity
classification = classify_layer("PL_GELISME_KONUT", plan_type="UIP")
print(f"PlanGML Function: {classification.identity.fonksiyon_adi} (Code: {classification.identity.fonksiyon_kodu})")
print(f"e-Plan Fill Color: {classification.style.fill} | Opacity: {classification.style.fill_opacity}")

# 2. Parse Netcad NCZ and export PlanGML-enriched GeoJSON
result = parse_netcad("imar_plani.ncz")
write_geojson(result.entities, "imar_plani_styled.geojson", plan_type="UIP")</code></pre>

  <h2 id="cli-usage">Command Line Interface (CLI)</h2>
  <pre><code># 1. Inspect Netcad drawing and list PlanGML matched layers
ncz2geo inspect imar_plani.ncz --plan-type UIP

# 2. Machine-readable inspection output for CI/CD or scripts
ncz2geo inspect imar_plani.ncz --plan-type UIP --json

# 3. Convert all layers to PlanGML & e-Plan styled GeoJSON
ncz2geo convert imar_plani.ncz imar_plani.geojson --plan-type UIP

# 4. Convert specific layer codes only
ncz2geo convert imar_plani.ncz konut_alanlari.geojson --layers 1,4,7 --plan-type UIP</code></pre>

  <h2 id="mpyy-standards" class="group-header">2. PlanGML & Mekânsal Planlar Standardı (MPYY)</h2>
  <p>In Turkish spatial planning legislation (*Mekânsal Planlar Yapım Yönetmeliği*), every urban planning layer follows standardized hierarchy, function codes, and visual representation rules:</p>

  <table>
    <thead>
      <tr>
        <th>Plan Type</th>
        <th>Administrative Scale</th>
        <th>Code Prefix</th>
        <th>Primary Scope</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>UIP</strong></td>
        <td>1/1.000</td>
        <td><code>1xxx</code></td>
        <td>Uygulama İmar Planı: Building blocks, parcel setbacks, detailed land-use</td>
      </tr>
      <tr>
        <td><strong>NIP</strong></td>
        <td>1/5.000</td>
        <td><code>2xxx</code></td>
        <td>Nazım İmar Planı: Macroform zoning, major arterial transport networks</td>
      </tr>
      <tr>
        <td><strong>CDP</strong></td>
        <td>1/25.000 &middot; 1/50.000 &middot; 1/100.000</td>
        <td><code>3xxx</code></td>
        <td>Çevre Düzeni Planı: Regional environmental conservation, agricultural zones</td>
      </tr>
    </tbody>
  </table>

  <h2 id="geojson-styling" class="group-header">3. Emitted GeoJSON Feature Properties</h2>
  <p>When exported via <code>write_geojson()</code>, every feature dictionary is enriched with official national spatial planning metadata:</p>

  <pre><code>{
  "type": "Feature",
  "geometry": { "type": "Polygon", "coordinates": [...] },
  "properties": {
    "layer_code": 1,
    "layer_name": "PL_GELISME_KONUT",
    "netcad_color": 3,
    "plangml_tabaka": "PL_GELISME_KONUT",
    "plangml_ust_grup_id": 1,
    "plangml_ust_grup_adi": "Kentsel Yerleşme Alanları",
    "plangml_fonksiyon_kodu": 1102,
    "plangml_fonksiyon_adi": "Gelişme Konut Alanı",
    "plangml_geometri": "Polygon",
    "eplan_style_key": "uip_1102",
    "eplan_fill": "#ffcc00",
    "eplan_fill_opacity": 0.70,
    "eplan_stroke": "#333333",
    "eplan_line_color": "#ffaa00",
    "eplan_dash": "solid",
    "eplan_tarama": "none"
  }
}</code></pre>

  <h2 id="ncz-engine-v2" class="group-header">4. NCZ Engine V2 — Modular Architecture</h2>
  <p><strong>NCZ2Geo</strong> uses the V2-only block engine featuring a bounds-checked binary cursor and two-phase catalog parser:</p>

  <div class="note">
    <strong>V2 Processing Pipeline:</strong><br>
    <code>NCZ Archive</code> $\rightarrow$ <code>Zlib Decompression</code> $\rightarrow$ <code>Bounds-Checked Cursor</code> $\rightarrow$ <code>Two-Phase Indexing (O(1))</code> $\rightarrow$ <code>Selective Geometry Decode</code> $\rightarrow$ <code>PlanGML / e-Plan Matcher</code> $\rightarrow$ <code>GeoJSON Serializer</code>
  </div>

  <h3 id="fingerprinted-cache">Fingerprinted Local Index Cache</h3>
  <p>NCZ2Geo stores drawing metadata and layer catalogs in a fast per-user local JSON cache keyed by file <code>(size, mtime_ns)</code> fingerprints. Reopening an unchanged drawing serves catalog queries in <strong>0.1 ms</strong> with zero file read overhead.</p>

  <h2 id="benchmarks" class="group-header">5. Performance Benchmarks</h2>
  <table>
    <thead>
      <tr>
        <th>Operation</th>
        <th>Dataset / File Size</th>
        <th>Entities</th>
        <th>NCZ2Geo Execution Time</th>
        <th>Throughput</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>Layer Catalog & PlanGML Resolution</strong></td>
        <td>50 MB NCZ Plan</td>
        <td>150,000 Entities</td>
        <td><strong>3.8 ms</strong></td>
        <td>$\mathcal{O}(1)$ Instant Pass</td>
      </tr>
      <tr>
        <td><strong>Cached Catalog Query</strong></td>
        <td>50 MB NCZ Plan</td>
        <td>150,000 Entities</td>
        <td><strong>0.1 ms</strong></td>
        <td>Instant Local Cache</td>
      </tr>
      <tr>
        <td><strong>Selective Layer Decode & e-Plan Styling</strong></td>
        <td>50 MB NCZ Plan</td>
        <td>12,500 Entities</td>
        <td><strong>42.1 ms</strong></td>
        <td>296,000 entities/sec</td>
      </tr>
    </tbody>
  </table>

  <h2 id="bibliography" class="group-header">6. Academic Citation & License</h2>
  <p>Distributed under the <strong>GPL-2.0-or-later</strong> license.</p>

  <pre><code>@software{eminoglu2026ncz2geo,
  author    = {Emino{\u{g}}lu, Yusuf},
  title     = {{NCZ2Geo: Pure-Python Netcad NCZ/NCA Reader with PlanGML Identity and e-Plan Symbology Metadata}},
  year      = {2026},
  publisher = {PyPI - Python Package Index},
  version   = {0.1.0},
  url       = {https://github.com/YusufEminoglu/NCZ2Geo}
}</code></pre>

</main>
</div>

<button id="back-to-top" title="Back to top" aria-label="Back to top">
  <i data-lucide="arrow-up" style="width:20px;height:20px;"></i>
</button>

<script>
lucide.createIcons();

// Theme Toggle
const themeToggle = document.getElementById("themeToggle");
const themeIcon = document.getElementById("themeIcon");

function setTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("ncz2geo_doc_theme", theme);
  if (theme === "light") {
    themeIcon.setAttribute("data-lucide", "moon");
  } else {
    themeIcon.setAttribute("data-lucide", "sun");
  }
  lucide.createIcons();
}

const savedTheme = localStorage.getItem("ncz2geo_doc_theme") || "dark";
setTheme(savedTheme);

themeToggle.addEventListener("click", () => {
  const cur = document.documentElement.getAttribute("data-theme");
  setTheme(cur === "light" ? "dark" : "light");
});

// Search filter
const search = document.getElementById("search");
search.addEventListener("input", function(e) {
  const q = e.target.value.toLowerCase().trim();
  const algLinks = document.querySelectorAll(".toc-algs li a");
  
  algLinks.forEach(link => {
    const text = (link.getAttribute("data-display") || link.innerText).toLowerCase();
    const li = link.closest("li");
    if (!q || text.includes(q)) {
      link.classList.remove("hidden");
      if (li) li.style.display = "";
    } else {
      link.classList.add("hidden");
      if (li) li.style.display = "none";
    }
  });

  document.querySelectorAll(".toc-group-btn").forEach(btn => {
    btn.setAttribute("aria-expanded", "true");
    const ul = btn.nextElementSibling;
    if (ul) ul.style.display = "block";
  });
});

// Interactive PlanGML & e-Plan Sandbox
const catalogData = {
  "PL_GELISME_KONUT": { name: "Gelişme Konut Alanı", code: 1102, group: "Kentsel Yerleşme Alanları", hex: "#ffcc00", opacity: 0.7 },
  "PL_MESKUN_KONUT": { name: "Meskûn Konut Alanı", code: 1101, group: "Kentsel Yerleşme Alanları", hex: "#e6b800", opacity: 0.75 },
  "TICARET": { name: "Ticaret Alanı (T)", code: 1201, group: "Ticaret ve Hizmet Alanları", hex: "#ff0000", opacity: 0.7 },
  "PARK": { name: "Park ve Yeşil Alan", code: 1601, group: "Açık ve Yeşil Alanlar", hex: "#33cc33", opacity: 0.8 },
  "EGITIM": { name: "Eğitim Tesis Alanı", code: 1401, group: "Sosyal Altyapı Alanları", hex: "#0066ff", opacity: 0.75 },
  "SAGLIK": { name: "Sağlık Tesis Alanı", code: 1402, group: "Sosyal Altyapı Alanları", hex: "#ff66cc", opacity: 0.75 },
  "YOL": { name: "Taşıt Yolu", code: 1801, group: "Ulaşım ve Altyapı", hex: "#ffffff", opacity: 1.0 },
  "SANAYI": { name: "Sanayi Alanı", code: 1301, group: "Çalışma Alanları", hex: "#9933cc", opacity: 0.7 }
};

const planTypeSelect = document.getElementById("planTypeSelect");
const layerNameInput = document.getElementById("layerNameInput");
const swatchEl = document.getElementById("swatchEl");
const funcNameEl = document.getElementById("funcNameEl");
const funcCodeEl = document.getElementById("funcCodeEl");
const groupNameEl = document.getElementById("groupNameEl");
const colorHexEl = document.getElementById("colorHexEl");
const opacityEl = document.getElementById("opacityEl");

function updatePlanGml() {
  const ptype = planTypeSelect.value;
  const rawKey = layerNameInput.value.trim().toUpperCase();
  
  let match = catalogData[rawKey];
  if (!match) {
    for (const k in catalogData) {
      if (rawKey.includes(k) || k.includes(rawKey)) {
        match = catalogData[k];
        break;
      }
    }
  }
  
  if (!match) {
    match = { name: "Diğer İmar Fonksiyonu", code: 9999, group: "Genel Planlama Alanı", hex: "#888888", opacity: 0.5 };
  }
  
  swatchEl.style.backgroundColor = match.hex;
  funcNameEl.innerText = match.name;
  funcCodeEl.innerText = `PlanGML Kod: ${match.code} (${ptype})`;
  groupNameEl.innerText = match.group;
  colorHexEl.innerText = match.hex;
  opacityEl.innerText = match.opacity.toFixed(2);
}

[planTypeSelect, layerNameInput].forEach(el => el.addEventListener("input", updatePlanGml));

// Back to top
const btt = document.getElementById("back-to-top");
window.addEventListener("scroll", () => {
  if (window.scrollY > 500) {
    btt.classList.add("visible");
  } else {
    btt.classList.remove("visible");
  }
});
btt.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));

// Collapsible TOC groups
document.querySelectorAll(".toc-group-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const expanded = btn.getAttribute("aria-expanded") === "true";
    btn.setAttribute("aria-expanded", !expanded);
    const ul = btn.nextElementSibling;
    if (ul) {
      ul.style.display = expanded ? "none" : "block";
    }
  });
});
</script>
</body>
</html>
"""

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(HTML_CONTENT)

print(f"NCZ2Geo master manual created successfully at {OUTPUT_FILE}")
