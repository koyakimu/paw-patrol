#!/usr/bin/env python3
"""Generate a static HTML site from the PAW Patrol episode database."""

import json
import os
from html import escape

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "site")


def load(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


CSS = """\
:root { --bg: #0f172a; --card: #1e293b; --border: #334155; --text: #e2e8f0;
        --muted: #94a3b8; --accent: #38bdf8; --red: #f87171; --green: #4ade80;
        --yellow: #facc15; }
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, 'Segoe UI', sans-serif; background: var(--bg);
       color: var(--text); line-height: 1.6; }
.container { max-width: 1100px; margin: 0 auto; padding: 1rem; }
h1 { font-size: 1.5rem; margin-bottom: .25rem; }
.subtitle { color: var(--muted); font-size: .9rem; margin-bottom: 1.5rem; }
nav { display: flex; gap: .5rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
nav a { color: var(--accent); background: var(--card); border: 1px solid var(--border);
        padding: .4rem .8rem; border-radius: .375rem; text-decoration: none; font-size: .85rem; }
nav a:hover, nav a.active { background: var(--accent); color: var(--bg); }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
         gap: .75rem; margin-bottom: 1.5rem; }
.stat { background: var(--card); border: 1px solid var(--border); border-radius: .5rem;
        padding: .75rem 1rem; }
.stat-value { font-size: 1.5rem; font-weight: 700; color: var(--accent); }
.stat-label { font-size: .8rem; color: var(--muted); }
table { width: 100%; border-collapse: collapse; font-size: .85rem; }
th { background: var(--card); position: sticky; top: 0; text-align: left;
     padding: .5rem .75rem; border-bottom: 2px solid var(--border); color: var(--muted);
     font-size: .75rem; text-transform: uppercase; letter-spacing: .05em; }
td { padding: .5rem .75rem; border-bottom: 1px solid var(--border); vertical-align: top; }
tr:hover td { background: rgba(56,189,248,.05); }
.rebroadcast { opacity: .6; }
.rebroadcast td:first-child::after { content: ' 再'; font-size: .7rem;
    background: var(--red); color: #fff; padding: .1rem .3rem; border-radius: .2rem;
    margin-left: .3rem; vertical-align: middle; }
.tag { font-size: .7rem; padding: .1rem .35rem; border-radius: .2rem; }
.tag-new { background: var(--green); color: #000; }
.tag-re { background: var(--red); color: #fff; }
.tag-ca { background: var(--accent); color: #000; }
.synopsis { color: var(--muted); font-size: .8rem; max-width: 400px; }
.truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 300px; display: block; }
footer { margin-top: 2rem; padding: 1rem 0; border-top: 1px solid var(--border);
         color: var(--muted); font-size: .75rem; text-align: center; }
@media (max-width: 768px) {
  table { font-size: .75rem; }
  td, th { padding: .4rem .5rem; }
  .stats { grid-template-columns: repeat(2, 1fr); }
}
"""


def page_template(title, nav_html, body, active=""):
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">
<h1>パウ・パトロール エピソード対応表</h1>
<p class="subtitle">TV Tokyo / U-NEXT / Canada 放送対応データベース</p>
{nav_html}
{body}
<footer>Generated from <a href="https://github.com/koyakimu/paw-patrol" style="color:var(--accent)">koyakimu/paw-patrol</a></footer>
</div>
</body>
</html>"""


def build_nav(active):
    links = [
        ("index.html", "放送リスト"),
        ("segments.html", "セグメント対応"),
        ("seasons.html", "シーズン情報"),
        ("rebroadcasts.html", "再放送一覧"),
    ]
    items = []
    for href, label in links:
        cls = ' class="active"' if href == active else ""
        items.append(f'<a href="{href}"{cls}>{label}</a>')
    return "<nav>" + "".join(items) + "</nav>"


# ── Page: broadcasts (index.html) ────────────────────────────────────────────

def build_index(broadcasts):
    total = broadcasts["total"]
    rebroadcasts = broadcasts["rebroadcasts"]
    unique = broadcasts["unique"]

    stats = f"""<div class="stats">
<div class="stat"><div class="stat-value">{total}</div><div class="stat-label">総放送回</div></div>
<div class="stat"><div class="stat-value">{unique}</div><div class="stat-label">ユニーク</div></div>
<div class="stat"><div class="stat-value">{rebroadcasts}</div><div class="stat-label">再放送</div></div>
</div>"""

    rows = []
    for b in broadcasts["broadcasts"]:
        cls = ' class="rebroadcast"' if b["is_rebroadcast"] else ""
        rb = ""
        if b["is_rebroadcast"]:
            rb = f' <span class="tag tag-re">= #{b["rebroadcast_of"]}</span>'

        ca = ""
        if b["canada_ids"]:
            ca = " ".join(f'<span class="tag tag-ca">{cid}</span>' for cid in b["canada_ids"])

        syn = ""
        if b.get("synopsis"):
            short = escape(b["synopsis"][:80]) + ("..." if len(b["synopsis"]) > 80 else "")
            syn = f'<span class="synopsis truncate" title="{escape(b["synopsis"])}">{short}</span>'

        rows.append(f"""<tr{cls}>
<td>#{b['number']}</td>
<td>{escape(b.get('air_date') or '')}</td>
<td>{escape(b['title'])}{rb}</td>
<td>{ca}</td>
<td>{syn}</td>
</tr>""")

    table = f"""<table>
<thead><tr><th>#</th><th>放送日</th><th>タイトル</th><th>カナダ版</th><th>あらすじ</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>"""

    return stats + table


# ── Page: segments ───────────────────────────────────────────────────────────

def build_segments_page(segments):
    mapped = segments["mapped_to_japan"]
    total = segments["total"]
    unmapped = total - mapped

    stats = f"""<div class="stats">
<div class="stat"><div class="stat-value">{total}</div><div class="stat-label">カナダ版セグメント</div></div>
<div class="stat"><div class="stat-value">{mapped}</div><div class="stat-label">日本放送済み</div></div>
<div class="stat"><div class="stat-value">{unmapped}</div><div class="stat-label">未放送</div></div>
</div>"""

    rows = []
    for s in segments["segments"]:
        ca = s["canada"]
        jp = s["japan"]
        jp_num = f'#{jp["broadcast_number"]}' if jp["broadcast_number"] else "-"
        jp_title = escape(jp["title"]) if jp["title"] else "-"

        rows.append(f"""<tr>
<td>{escape(s['id'])}</td>
<td>S{ca['season']}</td>
<td>{escape(ca['title'])}</td>
<td>{escape(ca.get('air_date') or '-')}</td>
<td>{jp_num}</td>
<td>{jp_title}</td>
</tr>""")

    table = f"""<table>
<thead><tr><th>ID</th><th>Season</th><th>カナダ版タイトル</th><th>CA放送日</th><th>TV Tokyo #</th><th>日本語タイトル</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>"""

    return stats + table


# ── Page: seasons ────────────────────────────────────────────────────────────

def build_seasons_page(seasons):
    body = ""

    # Canada
    body += "<h2 style='margin:1rem 0 .5rem'>カナダ版シーズン</h2>"
    rows = []
    for s in seasons["seasons"]["canada"]:
        rows.append(f"""<tr>
<td>Season {s['season']}</td>
<td>{s['episode_count']}</td>
<td>{s.get('first_air_date') or '-'}</td>
<td>{s.get('last_air_date') or '-'}</td>
</tr>""")
    body += f"""<table>
<thead><tr><th>シーズン</th><th>話数</th><th>開始日</th><th>終了日</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>"""

    # TV Tokyo
    body += "<h2 style='margin:1.5rem 0 .5rem'>テレビ東京シーズン</h2>"
    rows = []
    for s in seasons["seasons"]["tvtokyo"]:
        r = s["broadcast_range"]
        rows.append(f"""<tr>
<td>シーズン {s['season']}</td>
<td>#{r[0]} - #{r[1]}</td>
<td>{s.get('first_air_date') or '-'}</td>
<td>{s.get('last_air_date') or '-'}</td>
</tr>""")
    body += f"""<table>
<thead><tr><th>シーズン</th><th>放送回</th><th>開始日</th><th>終了日</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>"""

    return body


# ── Page: rebroadcasts ───────────────────────────────────────────────────────

def build_rebroadcasts_page(broadcasts):
    rebroadcasts = [b for b in broadcasts["broadcasts"] if b["is_rebroadcast"]]
    all_b = {b["number"]: b for b in broadcasts["broadcasts"]}

    stats = f"""<div class="stats">
<div class="stat"><div class="stat-value">{len(rebroadcasts)}</div><div class="stat-label">再放送回数</div></div>
</div>
<p style="color:var(--muted);font-size:.85rem;margin-bottom:1rem">
テレビ東京ではS4（2022年1月〜）以降、再放送にも新しい話数番号が振られています。
以下は同一タイトルの重複検出により特定された再放送です。
</p>"""

    rows = []
    for b in rebroadcasts:
        orig = all_b.get(b["rebroadcast_of"], {})
        rows.append(f"""<tr>
<td>#{b['number']}</td>
<td>{escape(b.get('air_date') or '')}</td>
<td>{escape(b['title'])}</td>
<td>#{b['rebroadcast_of']}</td>
<td>{escape(orig.get('air_date') or '')}</td>
</tr>""")

    table = f"""<table>
<thead><tr><th>再放送 #</th><th>再放送日</th><th>タイトル</th><th>初回 #</th><th>初回放送日</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>"""

    return stats + table


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Building static site...")
    os.makedirs(OUT_DIR, exist_ok=True)

    broadcasts = load("broadcasts.json")
    segments = load("segments.json")
    seasons = load("seasons.json")

    pages = [
        ("index.html", "放送リスト", build_index(broadcasts)),
        ("segments.html", "セグメント対応", build_segments_page(segments)),
        ("seasons.html", "シーズン情報", build_seasons_page(seasons)),
        ("rebroadcasts.html", "再放送一覧", build_rebroadcasts_page(broadcasts)),
    ]

    for filename, title, body in pages:
        nav = build_nav(filename)
        html = page_template(f"{title} - パウ・パトロール エピソード対応表", nav, body, filename)
        path = os.path.join(OUT_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  {filename}")

    print(f"\nDone! Site generated in {OUT_DIR}")


if __name__ == "__main__":
    main()
