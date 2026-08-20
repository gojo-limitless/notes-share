#!/usr/bin/env python3
"""
render_note.py — Share a Bear note as a self-contained, Bear-styled HTML page.

Usage:
    python3 render_note.py "<note title or ID>" [--out DIR] [--no-index]

Reads the note via bearcli, renders markdown → HTML mirroring Bear's reader
(light theme, serif, tag pills, checkboxes, pygments code), inlines all
attachments as base64 data URIs, writes site/notes/<slug>.html, and rebuilds
the hub index. Prints the page's public URL.

Requires: bearcli (Bear 2.8+), python3 with `markdown` and `pygments`.
"""
import argparse
import base64
import html
import json
import mimetypes
import os
import re
import subprocess
import sys
import unicodedata
import urllib.parse
from datetime import datetime

import markdown
from pygments.formatters import HtmlFormatter
from pygments.styles import get_style_by_name

BEARCLI = os.environ.get("BEARCLI", "/usr/local/bin/bearcli")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_DIR = os.path.join(BASE_DIR, "site")
NOTES_DIR = os.path.join(SITE_DIR, "notes")
INDEX_JSON = os.path.join(SITE_DIR, "notes.json")

# ---------------------------------------------------------------- helpers

def run_bearcli(*args):
    p = subprocess.run([BEARCLI, *args], capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"bearcli error: {p.stderr.strip() or p.stdout.strip()}")
    return p.stdout

def bear_json(*args):
    return json.loads(run_bearcli(*args))

def slugify(title):
    """ASCII slug for URLs: 'The AI Shift — Plans 🚀' -> 'the-ai-shift-plans'."""
    s = unicodedata.normalize("NFKD", title)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9\s-]", "", s).strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    return re.sub(r"-{2,}", "-", s).strip("-") or "note"

def find_note(ref):
    """Resolve a title or ID to note metadata via bearcli list."""
    notes = bear_json("list", "--format", "json")
    if not isinstance(notes, list):
        notes = notes.get("notes", [])
    ref_l = ref.strip().lower()
    for n in notes:
        if n.get("id", "").lower() == ref_l:
            return n
    for n in notes:
        if n.get("title", "").strip().lower() == ref_l:
            return n
    # fuzzy: unique substring match on title
    hits = [n for n in notes if ref_l and ref_l in n.get("title", "").lower()]
    if len(hits) == 1:
        return hits[0]
    sys.exit(f"Note not found: {ref!r}")

# ---------------------------------------------------------------- preprocessing

TASK_RE = re.compile(r"^(\s*)[-*+] \[([ xX])\]\s+(.*)$")
WIKI_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
BARE_URL_RE = re.compile(r"(?<![\(\<\"'])(https?://[^\s\)\]\>\"']+)")
STRIKE_RE = re.compile(r"(?<!\w)~~([^~\n]+)~~(?!\w)")

def preprocess(content, wiki_map=None):
    """Bear-specific markdown → standard markdown, line by line."""
    wiki_map = wiki_map or {}
    out = []
    for line in content.split("\n"):
        m = TASK_RE.match(line)
        if m:
            indent, state, rest = m.groups()
            cb = '<input type="checkbox" disabled' + (" checked" if state in "xX" else "") + "> "
            out.append(f"{indent}- {cb}{rest}")
            continue
        def wiki_repl(m):
            target_title = m.group(1).split("/")[-1].strip()
            alias = (m.group(2) or target_title).strip()
            slug = wiki_map.get(target_title.lower())
            if slug:
                return f'[{html.escape(alias)}](notes/{slug}.html)'
            return html.escape(alias)
        line = WIKI_RE.sub(wiki_repl, line)
        line = STRIKE_RE.sub(lambda m: f"<del>{m.group(1)}</del>", line)
        line = BARE_URL_RE.sub(lambda m: f"<{m.group(1)}>", line)
        out.append(line)
    return "\n".join(out)

def inline_attachments(content, note_id, atts):
    """Replace ![](file.png) with base64 data URIs using attachment bytes."""
    by_name = {a["filename"]: a for a in atts}
    def repl(m):
        alt, target = m.group(1), urllib.parse.unquote(m.group(2))
        if target not in by_name:
            return m.group(0)
        p = subprocess.run(
            [BEARCLI, "attachments", "save", note_id, "--filename", target],
            capture_output=True)
        if p.returncode != 0:
            return m.group(0)
        mime = mimetypes.guess_type(target)[0] or "application/octet-stream"
        b64 = base64.b64encode(p.stdout).decode()
        return f'<img alt="{html.escape(alt or "")}" src="data:{mime};base64,{b64}">'
    return re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", repl, content)

# ---------------------------------------------------------------- rendering

PYGMENTS_CSS = HtmlFormatter(style=get_style_by_name("friendly")).get_style_defs(".highlight")

def render_html(title, tags, modified_at, body_html, pygments_css):
    tag_pills = ("<p class=\"tags\">" + "".join(
        f'<span class="tag">{html.escape(t.lstrip("#"))}</span>' for t in tags
    ) + "</p>") if tags else ""
    meta = ""
    if modified_at:
        try:
            d = datetime.fromisoformat(str(modified_at).replace("Z", "+00:00"))
            meta = d.strftime("%-d %b %Y")
        except Exception:
            meta = str(modified_at)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  --bg: #FBFBFA; --ink: #1F1F1F; --muted: #8A8A8A; --rule: #E8E6E1;
  --accent: #C6511B; --accent-soft: #FDEADC; --code-bg: #F5F4F1;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--bg); color: var(--ink);
  font-family: "New York", "Iowan Old Style", Georgia, "Times New Roman", serif;
  font-size: 17px; line-height: 1.65;
}}
main {{ max-width: 720px; margin: 0 auto; padding: 64px 32px 96px; }}
h1 {{ font-size: 32px; line-height: 1.25; margin: 0 0 8px; letter-spacing: -0.01em; }}
h2 {{ font-size: 24px; margin: 1.8em 0 0.5em; }}
h3 {{ font-size: 20px; margin: 1.6em 0 0.5em; }}
h4 {{ font-size: 17px; margin: 1.4em 0 0.4em; }}
h1, h2, h3, h4 {{ font-weight: 700; }}
p {{ margin: 0.9em 0; }}
a {{ color: var(--accent); text-decoration: underline; text-underline-offset: 2px; }}
a:hover {{ color: #8F3A10; }}
.meta {{ color: var(--muted); font-size: 13px; margin: 0 0 6px; }}
.tags {{ margin: 0 0 28px; }}
.tag {{
  display: inline-block; background: var(--accent-soft); color: #A34A10;
  font-family: -apple-system, "SF Pro Text", Helvetica, Arial, sans-serif;
  font-size: 12px; font-weight: 500; padding: 2px 10px; border-radius: 999px;
  margin-right: 6px; letter-spacing: 0.01em;
}}
hr {{ border: none; border-top: 1px solid var(--rule); margin: 2em 0; }}
ul, ol {{ padding-left: 1.5em; margin: 0.8em 0; }}
li {{ margin: 0.25em 0; }}
li.task {{ list-style: none; margin-left: -1.5em; }}
li.task input {{ accent-color: var(--accent); transform: scale(1.15); margin-right: 8px; }}
li.task input + br {{ display: none; }}
blockquote {{
  margin: 1em 0; padding: 2px 0 2px 16px;
  border-left: 3px solid #E0DCD4; color: #55524C;
}}
blockquote p {{ margin: 0.4em 0; }}
code {{
  font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 0.88em;
  background: var(--code-bg); padding: 2px 5px; border-radius: 4px;
}}
pre {{ background: var(--code-bg); border: 1px solid #EBE9E4; border-radius: 8px;
  padding: 14px 16px; overflow-x: auto; line-height: 1.5; }}
pre code {{ background: none; padding: 0; font-size: 13.5px; }}
.highlight {{ background: var(--code-bg); }}
table {{ border-collapse: collapse; margin: 1.2em 0; width: 100%; font-size: 0.95em; }}
th, td {{ border: 1px solid var(--rule); padding: 7px 12px; text-align: left; }}
th {{ background: #F3F1EC; font-weight: 600; }}
img {{ max-width: 100%; height: auto; border-radius: 6px; margin: 0.6em 0; }}
del {{ color: var(--muted); }}
.foot {{ margin-top: 3em; padding-top: 1em; border-top: 1px solid var(--rule);
  color: var(--muted); font-size: 12px; font-family: -apple-system, Helvetica, Arial, sans-serif; }}
</style>
{pygments_css}
</head>
<body>
<main>
{body_html}
{tag_pills}
<p class="foot">Shared from Bear · {html.escape(meta)}</p>
</main>
</body>
</html>
"""

def fmt_date(s):
    if not s:
        return ""
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d.strftime("%-d %b %Y")
    except Exception:
        return str(s)

def build_index():
    """Regenerate site/index.html + notes.json from notes/*.html metadata."""
    entries = []
    if os.path.exists(INDEX_JSON):
        entries = json.load(open(INDEX_JSON))
    entries.sort(key=lambda e: e.get("modified", ""), reverse=True)
    json.dump(entries, open(INDEX_JSON, "w"), indent=1)
    rows = []
    for e in entries:
        tags = "".join(
            f'<span class="tag">{html.escape(t.lstrip("#"))}</span>' for t in e.get("tags", []))
        rows.append(f'''<li><a href="notes/{html.escape(e['slug'])}.html">
        <span class="t">{html.escape(e['title'])}</span>
        <span class="d">{html.escape(fmt_date(e.get('modified','')))}</span>
        <span class="tags">{tags}</span></a></li>''')
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shared notes</title>
<style>
:root {{ --bg:#FBFBFA; --ink:#1F1F1F; --muted:#8A8A8A; --rule:#E8E6E1; --accent:#C6511B; --accent-soft:#FDEADC; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font-family:"New York", "Iowan Old Style", Georgia, serif; }}
main {{ max-width:680px; margin:0 auto; padding:64px 32px; }}
h1 {{ font-size:28px; margin:0 0 4px; }}
p.sub {{ color:var(--muted); margin:0 0 32px; }}
ul {{ list-style:none; padding:0; margin:0; }}
li {{ border-bottom:1px solid var(--rule); }}
a {{ display:flex; flex-wrap:wrap; align-items:baseline; gap:4px 12px; padding:14px 4px; text-decoration:none; color:var(--ink); }}
a:hover {{ background:#F5F3EF; }}
.t {{ font-size:17px; font-weight:600; }}
.d {{ color:var(--muted); font-size:12.5px; font-family:-apple-system, Helvetica, Arial, sans-serif; }}
.tags {{ display:block; width:100%; }}
.tag {{ display:inline-block; background:var(--accent-soft); color:#A34A10; font-family:-apple-system, Helvetica, Arial, sans-serif; font-size:11.5px; font-weight:500; padding:1px 9px; border-radius:999px; margin-right:6px; }}
</style></head><body><main>
<h1>Shared notes</h1>
<p class="sub">{len(entries)} note{'s' if len(entries)!=1 else ''}</p>
<ul>{''.join(rows)}</ul>
</main></body></html>"""
    with open(os.path.join(SITE_DIR, "index.html"), "w") as f:
        f.write(page)

# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Share a Bear note as Bear-styled HTML")
    ap.add_argument("note", help="Bear note title or ID")
    ap.add_argument("--out", default=NOTES_DIR, help="output dir (default: site/notes)")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    note = find_note(args.note)
    note_id = note["id"]

    content = bear_json("cat", note_id, "--format", "json")["content"]
    try:
        show = bear_json("show", note_id, "--fields", "all", "--format", "json")
    except SystemExit:
        show = note
    tags = list(dict.fromkeys(t.lstrip("#") for t in show.get("tags", []) if t))
    modified_at = show.get("modified_at") or show.get("modified") or note.get("modified_at", "")
    title = (note.get("title") or "").strip() or "Untitled"

    atts = bear_json("attachments", "list", note_id, "--format", "json")
    if not isinstance(atts, list):
        atts = []

    # map of already-shared note titles → slugs, for wiki-link resolution
    wiki_map = {}
    if os.path.exists(INDEX_JSON):
        for e in json.load(open(INDEX_JSON)):
            wiki_map[e.get("title", "").strip().lower()] = e.get("slug")

    body = preprocess(content, wiki_map)
    body = inline_attachments(body, note_id, atts)
    if not re.search(r"^#\s", body, re.M):          # no H1 in content → use note title
        body = f"# {title}\n\n" + body

    body_html = markdown.markdown(
        body, extensions=["extra", "codehilite", "smarty"],
        extension_configs={"codehilite": {"guess_lang": False, "css_class": "highlight"}})
    # task items: markdown may wrap our raw <input> — fix checkbox-only list items
    body_html = re.sub(
        r"<li><input type=\"checkbox\"([^>]*)>", r'<li class="task"><input type="checkbox"\1>',
        body_html)

    slug = slugify(title)
    if os.path.exists(os.path.join(args.out, f"{slug}.html")):
        other = json.load(open(INDEX_JSON)) if os.path.exists(INDEX_JSON) else []
        if any(e["slug"] == slug and e["id"] != note_id for e in other):
            slug = f"{slug}-{note_id[:6].lower()}"

    page = render_html(title, tags, modified_at, body_html, PYGMENTS_CSS)
    path = os.path.join(args.out, f"{slug}.html")
    with open(path, "w") as f:
        f.write(page)

    # update index metadata
    entries = json.load(open(INDEX_JSON)) if os.path.exists(INDEX_JSON) else []
    entries = [e for e in entries if e.get("id") != note_id]
    entries.append({"id": note_id, "title": title, "slug": slug,
                    "tags": tags, "modified": modified_at})
    json.dump(entries, open(INDEX_JSON, "w"), indent=1)
    build_index()

    print(f"Wrote {path}")
    print(f"Public URL: https://<your-user>.github.io/notes-share/{slug}.html")

if __name__ == "__main__":
    main()
