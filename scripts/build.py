#!/usr/bin/env python3
"""Dashboard-Seite aus data/activities.json bauen.

    python3 scripts/build.py

Schreibt index.html ins Repo-Wurzelverzeichnis (wird von GitHub Pages
ausgeliefert). Alle Zahlen werden HIER berechnet – nie von Hand oder von
Claude im Kopf. Nur Python-Standardbibliothek, keine Abhängigkeiten, keine
externen Skripte/CDNs auf der Seite.
"""
import html
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "activities.json"
OUT = ROOT / "index.html"
TZ = ZoneInfo("Europe/Berlin")

# Strava sport_type -> Kategorie. Reihenfolge = Stapel- und Farbreihenfolge
# (validierte Palette, siehe docs/DESIGN.md). Nicht umsortieren.
CATEGORIES = [
    ("run", "Laufen", {"Run", "TrailRun", "VirtualRun"}),
    ("bike", "Rad", {"Ride", "VirtualRide", "GravelRide", "MountainBikeRide",
                     "EBikeRide", "EMountainBikeRide", "Velomobile", "Handcycle"}),
    ("swim", "Schwimmen", {"Swim"}),
    ("hike", "Wandern & Gehen", {"Hike", "Walk"}),
    ("other", "Sonstiges", set()),  # alles andere
]
MONTHS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


def category(sport_type: str) -> str:
    for key, _, types in CATEGORIES:
        if sport_type in types:
            return key
    return "other"


def monthly_hours(acts: list, year: int) -> list:
    """[{month: 1..12, run: h, bike: h, ...}] für das Jahr, Bewegungszeit."""
    rows = [{"month": m, **{k: 0.0 for k, _, _ in CATEGORIES}} for m in range(1, 13)]
    for a in acts:
        d = datetime.fromisoformat(a["start_local"])
        if d.year != year or not a.get("moving_time_s"):
            continue
        rows[d.month - 1][category(a["sport_type"])] += a["moving_time_s"] / 3600
    return rows


def fmt_h(h: float) -> str:
    return f"{h:.1f}".replace(".", ",")


def stacked_bar_svg(rows: list, last_month: int, W: int = 720, H: int = 320, cls: str = "wide") -> str:
    """Gestapeltes Balkendiagramm als SVG. Zwei Varianten (breit/schmal), damit
    die Schrift auf dem Handy nicht mitschrumpft – CSS blendet eine davon aus."""
    rows = rows[:last_month]
    L, R, T, B = (40, 8, 12, 28) if W > 500 else (28, 4, 12, 26)
    pw, ph = W - L - R, H - T - B
    totals = [sum(r[k] for k, _, _ in CATEGORIES) for r in rows]
    ymax = max(totals + [1])
    step = 10 if ymax > 40 else 5
    top = (int(ymax // step) + 1) * step
    sx = pw / len(rows)
    bw = min(44, sx * 0.66)
    y = lambda v: T + ph - v / top * ph

    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="c1t" class="chart {cls}">']
    for v in range(0, top + 1, step):  # Gitter
        parts.append(f'<line class="grid" x1="{L}" x2="{W-R}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                     f'<text class="tick" x="{L-6}" y="{y(v)+4:.1f}" text-anchor="end">{v}</text>')
    for i, r in enumerate(rows):
        cx = L + sx * i + sx / 2
        x0 = cx - bw / 2
        base = 0.0
        segs = [(k, label, r[k]) for k, label, _ in CATEGORIES if r[k] > 0]
        for j, (k, label, v) in enumerate(segs):
            y1, y0 = y(base + v), y(base)
            gap = 2 if base > 0 else 0          # 2px Oberflächen-Abstand zwischen Segmenten
            h = max(y0 - y1 - gap, 0.5)
            last = j == len(segs) - 1
            tip = html.escape(f"{MONTHS[i]} · {label}: {fmt_h(v)} h")
            if last:  # 4px abgerundetes Datenende oben
                rr = min(4, h, bw / 2)
                d = (f"M{x0:.1f},{y1+h:.1f} V{y1+rr:.1f} Q{x0:.1f},{y1:.1f} {x0+rr:.1f},{y1:.1f} "
                     f"H{x0+bw-rr:.1f} Q{x0+bw:.1f},{y1:.1f} {x0+bw:.1f},{y1+rr:.1f} V{y1+h:.1f} Z")
                parts.append(f'<path class="seg s-{k}" d="{d}" data-tip="{tip}"/>')
            else:
                parts.append(f'<rect class="seg s-{k}" x="{x0:.1f}" y="{y1:.1f}" width="{bw:.1f}" '
                             f'height="{h:.1f}" data-tip="{tip}"/>')
            base += v
        if totals[i] > 0:
            parts.append(f'<text class="total" x="{cx:.1f}" y="{y(totals[i])-6:.1f}" '
                         f'text-anchor="middle">{fmt_h(totals[i])}</text>')
        parts.append(f'<text class="tick" x="{cx:.1f}" y="{H-8}" text-anchor="middle">{MONTHS[i]}</text>')
    parts.append(f'<line class="axis" x1="{L}" x2="{W-R}" y1="{y(0):.1f}" y2="{y(0):.1f}"/>')
    parts.append("</svg>")
    return "".join(parts)


def table_html(rows: list, last_month: int) -> str:
    head = "".join(f"<th>{l}</th>" for _, l, _ in CATEGORIES)
    body = []
    for r in rows[:last_month]:
        cells = "".join(f"<td>{fmt_h(r[k])}</td>" for k, _, _ in CATEGORIES)
        tot = sum(r[k] for k, _, _ in CATEGORIES)
        body.append(f"<tr><th>{MONTHS[r['month']-1]}</th>{cells}<td><b>{fmt_h(tot)}</b></td></tr>")
    sums = [sum(r[k] for r in rows[:last_month]) for k, _, _ in CATEGORIES]
    foot = "".join(f"<td>{fmt_h(s)}</td>" for s in sums)
    return (f"<table><thead><tr><th>Monat</th>{head}<th>Gesamt</th></tr></thead>"
            f"<tbody>{''.join(body)}</tbody><tfoot><tr><th>Summe</th>{foot}"
            f"<td><b>{fmt_h(sum(sums))}</b></td></tr></tfoot></table>")


def main() -> None:
    store = json.loads(DATA.read_text(encoding="utf-8"))
    acts = store["activities"]
    now = datetime.now(TZ)
    year = now.year
    rows = monthly_hours(acts, year)
    last_month = now.month
    total = sum(r[k] for r in rows for k, _, _ in CATEGORIES)
    n_year = sum(1 for a in acts if a["start_local"].startswith(str(year)))
    latest = acts[-1]["start_local"][:10] if acts else "–"
    latest_de = ".".join(reversed(latest.split("-"))) if acts else "–"
    legend = "".join(f'<li><span class="sw s-{k}"></span>{l}</li>' for k, l, _ in CATEGORIES)

    page = TEMPLATE
    for k, v in {
        "{{YEAR}}": str(year),
        "{{TOTAL}}": fmt_h(total),
        "{{COUNT}}": str(n_year),
        "{{LATEST}}": latest_de,
        "{{BUILT}}": now.strftime("%d.%m.%Y, %H:%M"),
        "{{LEGEND}}": legend,
        "{{CHART}}": stacked_bar_svg(rows, last_month)
        + stacked_bar_svg(rows, last_month, W=360, H=280, cls="narrow"),
        "{{TABLE}}": table_html(rows, last_month),
    }.items():
        page = page.replace(k, v)
    OUT.write_text(page, encoding="utf-8")
    print(f"build: index.html geschrieben ({n_year} Aktivitäten {year}, {fmt_h(total)} h)")


TEMPLATE = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Athlete Coach</title>
<meta name="robots" content="noindex">
<style>
:root{color-scheme:light;
 --bg:#fcfcfb;--card:#ffffff;--border:#e6e5e0;--text:#0b0b0b;--text-2:#52514e;--muted:#8a8984;
 --grid:#ecebe7;--axis:#c9c8c2;
 --run:#2a78d6;--bike:#eb6834;--swim:#1baf7a;--hike:#eda100;--other:#e87ba4}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
 --bg:#141413;--card:#1a1a19;--border:#2c2c2a;--text:#ffffff;--text-2:#c3c2b7;--muted:#8f8e86;
 --grid:#2a2a28;--axis:#4a4a46;
 --run:#3987e5;--bike:#d95926;--swim:#199e70;--hike:#c98500;--other:#d55181}}
:root[data-theme="dark"]{color-scheme:dark;
 --bg:#141413;--card:#1a1a19;--border:#2c2c2a;--text:#ffffff;--text-2:#c3c2b7;--muted:#8f8e86;
 --grid:#2a2a28;--axis:#4a4a46;
 --run:#3987e5;--bike:#d95926;--swim:#199e70;--hike:#c98500;--other:#d55181}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
 font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
 padding:max(20px,env(safe-area-inset-top)) 16px 40px}
main{max-width:760px;margin:0 auto}
header{display:flex;align-items:baseline;gap:6px;margin-bottom:20px}
.brand{font-weight:700;font-size:20px;letter-spacing:-.01em}
.brand i{color:#8e6fe0;font-style:normal}
.kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:16px}
.kpi{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:12px 14px}
.kpi b{display:block;font-size:24px;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.kpi span{color:var(--text-2);font-size:13px}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px}
h2{font-size:16px;margin:0 0 2px}
.sub{color:var(--text-2);font-size:13px;margin:0 0 12px}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;list-style:none;padding:0;margin:0 0 8px;font-size:13px;color:var(--text-2)}
.legend li{display:flex;align-items:center;gap:6px}
.sw{width:10px;height:10px;border-radius:3px;display:inline-block}
.chart{width:100%;height:auto;display:block;overflow:visible}
.chart.narrow{display:none}
@media (max-width:560px){.chart.wide{display:none}.chart.narrow{display:block}
 .chart.narrow .total{font-size:10px}.chart.narrow .tick{font-size:11px}}
.chart text{font-size:12px;fill:var(--muted);font-variant-numeric:tabular-nums}
.chart .total{fill:var(--text-2);font-weight:600}
.grid{stroke:var(--grid);stroke-width:1}.axis{stroke:var(--axis);stroke-width:1}
.seg{cursor:default}.seg:hover{opacity:.8}
.s-run{fill:var(--run);background:var(--run)}.s-bike{fill:var(--bike);background:var(--bike)}
.s-swim{fill:var(--swim);background:var(--swim)}.s-hike{fill:var(--hike);background:var(--hike)}
.s-other{fill:var(--other);background:var(--other)}
#tip{position:fixed;pointer-events:none;background:var(--text);color:var(--bg);font-size:13px;
 padding:5px 9px;border-radius:6px;opacity:0;transition:opacity .1s;white-space:nowrap;z-index:9}
details{margin-top:12px;font-size:13px}
summary{cursor:pointer;color:var(--text-2)}
.tw{overflow-x:auto}
table{border-collapse:collapse;width:100%;margin-top:8px;font-variant-numeric:tabular-nums}
th,td{padding:5px 8px;text-align:right;border-bottom:1px solid var(--border);white-space:nowrap}
th:first-child{text-align:left}thead th{color:var(--text-2);font-weight:600}
tfoot th,tfoot td{border-bottom:0;font-weight:600}
footer{color:var(--muted);font-size:12px;margin-top:20px;text-align:center}
@media (max-width:480px){.kpi{padding:10px}.kpi b{font-size:18px;white-space:nowrap}.kpi span{font-size:12px}.kpis{gap:8px}}
</style>
</head>
<body>
<main>
<header><span class="brand">athlete<i>.</i>coach</span></header>

<section class="kpis">
 <div class="kpi"><b>{{TOTAL}} h</b><span>Training {{YEAR}}</span></div>
 <div class="kpi"><b>{{COUNT}}</b><span>Einheiten {{YEAR}}</span></div>
 <div class="kpi"><b>{{LATEST}}</b><span>letzte Einheit</span></div>
</section>

<section class="card">
 <h2 id="c1t">Trainingsstunden pro Monat {{YEAR}}</h2>
 <p class="sub">Bewegungszeit nach Sportart, in Stunden</p>
 <ul class="legend">{{LEGEND}}</ul>
 {{CHART}}
 <details><summary>Als Tabelle anzeigen</summary><div class="tw">{{TABLE}}</div></details>
</section>

<footer>Daten: Strava · aktualisiert {{BUILT}} Uhr</footer>
</main>
<div id="tip"></div>
<script>
(function(){var t=document.getElementById('tip');
document.querySelectorAll('[data-tip]').forEach(function(el){
 el.addEventListener('pointermove',function(e){t.textContent=el.getAttribute('data-tip');
  t.style.opacity=1;var x=e.clientX+12,w=t.offsetWidth;if(x+w>innerWidth-8)x=e.clientX-w-12;
  t.style.left=x+'px';t.style.top=(e.clientY-34)+'px';});
 el.addEventListener('pointerleave',function(){t.style.opacity=0;});});})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
