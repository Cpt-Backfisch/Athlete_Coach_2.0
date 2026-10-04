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
from datetime import date, datetime
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


# ---------------------------------------------------------------------------
# 1000-km-Lauf-Challenge (kumulierte Lauf-km, Soll-Linie, optional Partner)
# ---------------------------------------------------------------------------
CHALLENGE = ROOT / "data" / "challenge.json"
RUN_TYPES = CATEGORIES[0][2]  # Laufen = Run, TrailRun, VirtualRun


def fmt_km(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


def month_span(year: int, m: int) -> tuple:
    """(erster Tagesindex, erster Tagesindex des Folgemonats) für Monat m (0..11)."""
    jan1 = date(year, 1, 1)
    nxt = date(year + 1, 1, 1) if m == 11 else date(year, m + 2, 1)
    return (date(year, m + 1, 1) - jan1).days, (nxt - jan1).days


def challenge_series(acts: list, cfg: dict, today) -> dict:
    """Tageswerte (Stand jeweils am Tagesende) für Ich, Soll und Partner."""
    year, goal = cfg["year"], cfg["goal_km"]
    jan1 = date(year, 1, 1)
    ndays = (date(year + 1, 1, 1) - jan1).days
    if today.year < year:
        end = -1
    elif today.year > year:
        end = ndays - 1
    else:
        end = (today - jan1).days
    per_day = [0.0] * ndays
    for a in acts:
        d = datetime.fromisoformat(a["start_local"]).date()
        if d.year == year and a["sport_type"] in RUN_TYPES and a.get("distance_m"):
            per_day[(d - jan1).days] += a["distance_m"] / 1000
    me, run = [], 0.0
    for i in range(end + 1):
        run += per_day[i]
        me.append(round(run, 2))
    target = [goal * (i + 1) / ndays for i in range(ndays)]
    p = cfg.get("partner") or {}
    pts = sorted(((date.fromisoformat(e["date"]) - jan1).days, float(e["km_total"]))
                 for e in p.get("entries", []) if e["date"].startswith(str(year)))
    partner = [None] * ndays          # letzter bekannter Stand, nur bis zum letzten Eintrag
    for k, (idx, km) in enumerate(pts):
        stop = pts[k + 1][0] if k + 1 < len(pts) else idx + 1
        for i in range(idx, min(stop, ndays)):
            partner[i] = km
    return {"year": year, "goal": goal, "ndays": ndays, "end": end, "me": me,
            "target": target, "partner_name": p.get("name", "Partner"),
            "partner_pts": pts, "partner": partner}


def challenge_svg(s: dict, W: int = 720, H: int = 320, cls: str = "wide") -> str:
    L, R, T, B = (44, 12, 22, 28) if W > 500 else (36, 8, 22, 26)
    pw, ph = W - L - R, H - T - B
    n, goal = s["ndays"], s["goal"]
    top = goal
    for v in [*s["me"], *(km for _, km in s["partner_pts"])]:
        top = max(top, v)
    step = 200 if top <= 1000 else 250
    top = -(-top // step) * step
    x = lambda i: L + (i + 1) / n * pw      # Tagesende von Tag i (i = -1 → 1. Jan, 0 Uhr)
    y = lambda v: T + ph - v / top * ph
    yr = s["year"]

    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="c2t" class="chart {cls} cc" '
             f'data-l="{L}" data-pw="{pw}" data-w="{W}" data-t="{T}" data-b="{T+ph}">']
    for v in range(0, int(top) + 1, step):
        parts.append(f'<line class="grid" x1="{L}" x2="{W-R}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                     f'<text class="tick" x="{L-6}" y="{y(v)+4:.1f}" text-anchor="end">{fmt_km(v)}</text>')
    for m in range(12):
        a, b = month_span(yr, m)
        if m > 0:
            parts.append(f'<line class="mtick" x1="{x(a-1):.1f}" x2="{x(a-1):.1f}" '
                         f'y1="{y(0):.1f}" y2="{y(0)+4:.1f}"/>')
        if W > 500 or m % 2 == 0:
            parts.append(f'<text class="tick" x="{(x(a-1)+x(b-1))/2:.1f}" y="{H-8}" '
                         f'text-anchor="middle">{MONTHS[m]}</text>')
    parts.append(f'<line class="axis" x1="{L}" x2="{W-R}" y1="{y(0):.1f}" y2="{y(0):.1f}"/>')
    # Soll-Linie (linear 0 → Ziel)
    parts.append(f'<line class="tgt" x1="{L}" y1="{y(0):.1f}" x2="{x(n-1):.1f}" y2="{y(goal):.1f}"/>')
    parts.append(f'<text class="lbl" x="{x(n-1):.1f}" y="{y(goal)-8:.1f}" text-anchor="end">'
                 f'Soll {fmt_km(goal)} km</text>')
    # Partner
    if s["partner_pts"]:
        d = f"M{L},{y(0):.1f} " + " ".join(f"L{x(i):.1f},{y(v):.1f}" for i, v in s["partner_pts"])
        parts.append(f'<path class="ln ln-p" d="{d}"/>')
        for i, v in s["partner_pts"]:
            parts.append(f'<circle class="dot d-p" cx="{x(i):.1f}" cy="{y(v):.1f}" r="3.5"/>')
    # Ich
    if s["me"]:
        d = f"M{L},{y(0):.1f} " + " ".join(f"L{x(i):.1f},{y(v):.1f}" for i, v in enumerate(s["me"]))
        parts.append(f'<path class="ln ln-me" d="{d}"/>')
    # Endpunkte + direkte Beschriftung rechts daneben (dort ist bis Jahresende Platz);
    # zwei Beschriftungen halten mind. 15 px Abstand.
    ends = []
    if s["me"]:
        ends.append(("me", "Ich", s["end"], s["me"][-1]))
    if s["partner_pts"]:
        i, v = s["partner_pts"][-1]
        ends.append(("p", s["partner_name"], i, v))
    ends.sort(key=lambda e: -e[3])
    lx = max(x(i) for _, _, i, _ in ends) + 9 if ends else 0
    prev = None
    for k, name, i, v in ends:
        ty = y(v) + 4
        if prev is not None and ty - prev < 15:
            ty = prev + 15
        prev = ty
        parts.append(f'<circle class="dot d-{k}" cx="{x(i):.1f}" cy="{y(v):.1f}" r="4.5"/>')
        parts.append(f'<text class="lbl" x="{lx:.1f}" y="{ty:.1f}">{html.escape(name)} {fmt_km(v)}</text>')
    # Fadenkreuz (per Script bewegt)
    parts.append(f'<line class="xh" x1="0" x2="0" y1="{T}" y2="{y(0):.1f}"/>')
    parts.append(f'<rect class="xhit" x="{L}" y="{T}" width="{pw}" height="{ph}"/>')
    parts.append("</svg>")
    return "".join(parts)


def challenge_stats(s: dict) -> str:
    e, goal = s["end"], s["goal"]
    if e < 0:
        return '<p class="sub">Die Challenge hat noch nicht begonnen.</p>'
    me = s["me"][-1]
    soll = s["target"][e]
    diff = me - soll
    days_left = s["ndays"] - 1 - e
    sign = "+" if diff >= 0 else "−"
    tiles = [
        (f"{fmt_km(me)} km", "gelaufen"),
        (f"{fmt_km(soll)} km", "Soll heute"),
        (f"{sign}{fmt_km(abs(diff))} km", "vor dem Plan" if diff >= 0 else "hinter dem Plan"),
    ]
    out = '<div class="mini">' + "".join(f"<div><b>{a}</b><span>{b}</span></div>" for a, b in tiles) + "</div>"
    if me >= goal:
        note = f"Ziel erreicht – {fmt_km(me)} km."
    elif days_left > 0:
        per_week = (goal - me) / days_left * 7
        note = (f"Noch {fmt_km(goal - me)} km in {days_left} Tagen – "
                f"das sind {fmt_h(per_week)} km pro Woche.")
    else:
        note = f"Jahr vorbei – {fmt_km(goal - me)} km fehlen."
    if s["partner_pts"]:
        li, lv = s["partner_pts"][-1]
        d = date(s["year"], 1, 1).toordinal() + li
        note += (f" {html.escape(s['partner_name'])}: {fmt_km(lv)} km "
                 f"(Stand {date.fromordinal(d).strftime('%d.%m.')}).")
    else:
        note += f" {html.escape(s['partner_name'])}: noch keine Daten."
    return out + f'<p class="note">{note}</p>'


def challenge_table(s: dict) -> str:
    yr, e = s["year"], s["end"]
    has_p = bool(s["partner_pts"])
    head = "<th>Ich</th><th>Soll</th><th>Differenz</th>" + (
        f"<th>{html.escape(s['partner_name'])}</th>" if has_p else "")
    body = []
    for m in range(12):
        first, nxt = month_span(yr, m)
        last = nxt - 1
        i = min(last, e)
        if i < first:
            break
        me, soll = s["me"][i], s["target"][i]
        diff = me - soll
        cells = (f"<td>{fmt_km(me)}</td><td>{fmt_km(soll)}</td>"
                 f"<td>{'+' if diff >= 0 else '−'}{fmt_km(abs(diff))}</td>")
        if has_p:
            pv = next((v for j, v in reversed(s["partner_pts"]) if j <= i), None)
            cells += f"<td>{fmt_km(pv) if pv is not None else '–'}</td>"
        label = MONTHS[m] + (" (bisher)" if i < last else "")
        body.append(f"<tr><th>{label}</th>{cells}</tr>")
    return (f"<table><thead><tr><th>Monatsende, km</th>{head}</tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>")


def challenge_js_data(s: dict) -> str:
    d = {"y": s["year"], "n": s["ndays"], "g": s["goal"], "me": s["me"],
         "p": s["partner"] if s["partner_pts"] else None, "pn": s["partner_name"]}
    return json.dumps(d, separators=(",", ":")).replace("</", "<\\/")


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

    cfg = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    cs = challenge_series(acts, cfg, now.date())
    pname = html.escape(cs["partner_name"])
    c_legend = ('<li><span class="ls ls-me"></span>Ich</li>'
                + (f'<li><span class="ls ls-p"></span>{pname}</li>' if cs["partner_pts"] else "")
                + '<li><span class="ls ls-t"></span>Soll (linear)</li>')

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
        "{{C_YEAR}}": str(cs["year"]),
        "{{C_GOAL}}": fmt_km(cs["goal"]),
        "{{C_PARTNER}}": pname,
        "{{C_STATS}}": challenge_stats(cs),
        "{{C_LEGEND}}": c_legend,
        "{{C_CHART}}": challenge_svg(cs) + challenge_svg(cs, W=360, H=280, cls="narrow"),
        "{{C_TABLE}}": challenge_table(cs),
        "{{C_DATA}}": challenge_js_data(cs),
    }.items():
        page = page.replace(k, v)
    OUT.write_text(page, encoding="utf-8")
    print(f"build: index.html geschrieben ({n_year} Aktivitäten {year}, {fmt_h(total)} h, "
          f"Challenge {fmt_km(cs['me'][-1] if cs['me'] else 0)} km)")


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
 --run:#2a78d6;--bike:#eb6834;--swim:#1baf7a;--hike:#eda100;--other:#e87ba4;--partner:#eb6834}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
 --bg:#141413;--card:#1a1a19;--border:#2c2c2a;--text:#ffffff;--text-2:#c3c2b7;--muted:#8f8e86;
 --grid:#2a2a28;--axis:#4a4a46;
 --run:#3987e5;--bike:#d95926;--swim:#199e70;--hike:#c98500;--other:#d55181;--partner:#d95926}}
:root[data-theme="dark"]{color-scheme:dark;
 --bg:#141413;--card:#1a1a19;--border:#2c2c2a;--text:#ffffff;--text-2:#c3c2b7;--muted:#8f8e86;
 --grid:#2a2a28;--axis:#4a4a46;
 --run:#3987e5;--bike:#d95926;--swim:#199e70;--hike:#c98500;--other:#d55181;--partner:#d95926}
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
.card+.card{margin-top:16px}
.mini{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:4px 0 6px}
.mini div{border-left:2px solid var(--border);padding-left:10px}
.mini b{display:block;font-size:20px;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.mini span{color:var(--text-2);font-size:12px}
.note{color:var(--text-2);font-size:13px;margin:0 0 12px;font-variant-numeric:tabular-nums}
.ls{width:16px;height:0;border-top:2px solid;display:inline-block}
.ls-me{border-color:var(--run)}.ls-p{border-color:var(--partner)}.ls-t{border-top:2px dashed var(--muted)}
.ln{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.ln-me{stroke:var(--run)}.ln-p{stroke:var(--partner)}
.tgt{stroke:var(--muted);stroke-width:1.5;stroke-dasharray:5 4}
.dot{stroke:var(--card);stroke-width:2}.d-me{fill:var(--run)}.d-p{fill:var(--partner)}
.chart .lbl{fill:var(--text-2);font-weight:600}
.mtick{stroke:var(--axis);stroke-width:1}
.xh{stroke:var(--axis);stroke-width:1;opacity:0}.xhit{fill:transparent;cursor:crosshair}
tfoot th,tfoot td{border-bottom:0;font-weight:600}
footer{color:var(--muted);font-size:12px;margin-top:20px;text-align:center}
@media (max-width:480px){.mini b{font-size:16px}.kpi{padding:10px}.kpi b{font-size:18px;white-space:nowrap}.kpi span{font-size:12px}.kpis{gap:8px}}
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
 <h2 id="c2t">{{C_GOAL}}-km-Challenge {{C_YEAR}}</h2>
 <p class="sub">Gelaufene Kilometer kumuliert, mit {{C_PARTNER}}</p>
 {{C_STATS}}
 <ul class="legend">{{C_LEGEND}}</ul>
 {{C_CHART}}
 <details><summary>Als Tabelle anzeigen</summary><div class="tw">{{C_TABLE}}</div></details>
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
<script id="cdata" type="application/json">{{C_DATA}}</script>
<script>
(function(){var t=document.getElementById('tip');
document.querySelectorAll('[data-tip]').forEach(function(el){
 el.addEventListener('pointermove',function(e){t.textContent=el.getAttribute('data-tip');
  t.style.opacity=1;var x=e.clientX+12,w=t.offsetWidth;if(x+w>innerWidth-8)x=e.clientX-w-12;
  t.style.left=x+'px';t.style.top=(e.clientY-34)+'px';});
 el.addEventListener('pointerleave',function(){t.style.opacity=0;});});
var D=JSON.parse(document.getElementById('cdata').textContent);
function f(v){return Math.round(v).toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g,'.')+' km';}
document.querySelectorAll('svg.cc').forEach(function(sv){
 var L=+sv.dataset.l,PW=+sv.dataset.pw,W=+sv.dataset.w,h=sv.querySelector('.xhit'),xh=sv.querySelector('.xh');
 h.addEventListener('pointermove',function(e){var r=sv.getBoundingClientRect(),k=r.width/W;
  var i=Math.floor(((e.clientX-r.left)/k-L)/PW*D.n);i=Math.max(0,Math.min(D.n-1,i));
  var xx=L+(i+1)/D.n*PW;xh.setAttribute('x1',xx);xh.setAttribute('x2',xx);xh.style.opacity=1;
  var dt=new Date(D.y,0,1+i),s=('0'+dt.getDate()).slice(-2)+'.'+('0'+(dt.getMonth()+1)).slice(-2)+'.';
  var parts=[s];if(i<D.me.length)parts.push('Ich '+f(D.me[i]));
  if(D.p&&D.p[i]!=null)parts.push(D.pn+' '+f(D.p[i]));parts.push('Soll '+f(D.g*(i+1)/D.n));
  t.textContent=parts.join(' · ');t.style.opacity=1;var x=e.clientX+12,w=t.offsetWidth;
  if(x+w>innerWidth-8)x=e.clientX-w-12;if(x<8)x=8;t.style.left=x+'px';t.style.top=(e.clientY-40)+'px';});
 h.addEventListener('pointerleave',function(){t.style.opacity=0;xh.style.opacity=0;});});})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
