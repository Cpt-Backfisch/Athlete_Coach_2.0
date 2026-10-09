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
import math
import xml.etree.ElementTree as ET
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
# Jahresvergleich: kumulierte Trainingsstunden je Kalenderjahr (eine Linie pro Jahr)
# ---------------------------------------------------------------------------
CUM_FILTERS = [("all", "Gesamt"), ("run", "Laufen"), ("bike", "Rad"), ("swim", "Schwimmen")]


def cum_series(acts: list, today) -> dict:
    """{filter: {jahr: [kumulierte Stunden am Tagesende, bis heute bzw. 31.12.]}}."""
    years = sorted({int(a["start_local"][:4]) for a in acts if a.get("moving_time_s")})
    out = {f: {} for f, _ in CUM_FILTERS}
    for yr in years:
        if yr > today.year:
            continue
        jan1 = date(yr, 1, 1)
        ndays = (date(yr + 1, 1, 1) - jan1).days
        end = (today - jan1).days if yr == today.year else ndays - 1
        per = {f: [0.0] * ndays for f, _ in CUM_FILTERS}
        for a in acts:
            d = datetime.fromisoformat(a["start_local"]).date()
            if d.year != yr or not a.get("moving_time_s"):
                continue
            h = a["moving_time_s"] / 3600
            per["all"][(d - jan1).days] += h
            c = category(a["sport_type"])
            if c in per:
                per[c][(d - jan1).days] += h
        for f, _ in CUM_FILTERS:
            run, s = 0.0, []
            for i in range(end + 1):
                run += per[f][i]
                s.append(round(run, 2))
            out[f][yr] = s
    return out


def year_cls(yr: int, cur_year: int) -> str:
    """Farbe je Jahr: aktuelles Jahr y0 (Lila), Vorjahr y1 (Blau), dann y2 (Orange), y3 (Grün), älter grau."""
    age = cur_year - yr
    return f"y{age}" if 0 <= age <= 3 else "yx"


def year_len(yr: int) -> int:
    return (date(yr + 1, 1, 1) - date(yr, 1, 1)).days


def cum_svg(series: dict, f: str, cur_year: int, W: int = 720, H: int = 320, cls: str = "wide") -> str:
    """Liniendiagramm Jan–Dez, eine Linie pro Jahr. Aktuelles Jahr in Sportfarbe (Gesamt: --text),
    Vorjahre neutral; Endwerte direkt beschriftet, Fadenkreuz per Script."""
    L, R, T, B = (40, 76, 16, 28) if W > 500 else (32, 46, 16, 26)
    pw, ph = W - L - R, H - T - B
    ys = sorted(series)
    top = max([v for yr in ys for v in series[yr][-1:]] + [1])
    step = next(s for s in (5, 10, 20, 25, 50, 100, 200, 250, 500) if top / s <= 5)
    top = -(-top // step) * step
    y = lambda v: T + ph - v / top * ph
    ref = cur_year if cur_year in ys else (ys[-1] if ys else cur_year)
    nref = year_len(ref)
    x = lambda i, n: L + (i + 1) / n * pw
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="c3t" class="chart {cls} cy{' sel' if f == 'all' else ''}" '
             f'data-f="{f}" data-l="{L}" data-pw="{pw}" data-w="{W}">']
    for v in range(0, int(top) + 1, step):
        parts.append(f'<line class="grid" x1="{L}" x2="{L+pw}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                     f'<text class="tick" x="{L-6}" y="{y(v)+4:.1f}" text-anchor="end">{v}</text>')
    for m in range(12):
        a, b = month_span(ref, m)
        if m > 0:
            parts.append(f'<line class="mtick" x1="{x(a-1, nref):.1f}" x2="{x(a-1, nref):.1f}" '
                         f'y1="{y(0):.1f}" y2="{y(0)+4:.1f}"/>')
        if W > 500 or m % 2 == 0:
            parts.append(f'<text class="tick" x="{(x(a-1, nref)+x(b-1, nref))/2:.1f}" y="{H-8}" '
                         f'text-anchor="middle">{MONTHS[m]}</text>')
    parts.append(f'<line class="axis" x1="{L}" x2="{L+pw}" y1="{y(0):.1f}" y2="{y(0):.1f}"/>')
    # Vorjahre zuerst (darunter), aktuelles Jahr zuletzt (obenauf)
    order = [yr for yr in ys if yr != cur_year] + ([cur_year] if cur_year in ys else [])
    ends = []
    for yr in order:
        s, n = series[yr], year_len(yr)
        if not s:
            continue
        cur = yr == cur_year
        klass = f"cl {year_cls(yr, cur_year)}" + (" cur" if cur else "")
        d = f"M{L},{y(0):.1f} " + " ".join(f"L{x(i, n):.1f},{y(v):.1f}" for i, v in enumerate(s))
        parts.append(f'<path class="{klass}" d="{d}"/>')
        ends.append((yr, cur, x(len(s) - 1, n), y(s[-1]), s[-1]))
    # Beschriftungen rechts: Vorjahre am rechten Rand, aktuelles Jahr direkt neben dem Endpunkt
    # Schmal: zweizeilig (Jahr / Wert), damit es in den rechten Rand passt
    two = W <= 500
    gap = 28 if two else 14
    placed = []
    for yr, cur, ex, ey, v in sorted(ends, key=lambda e: e[3]):
        ty = ey + (0 if two else 4)
        for p in placed:  # Mindestabstand zu bereits gesetzten Labels mit ähnlichem x
            if abs(p[0] - (ex + 8)) < 70 and abs(ty - p[1]) < gap:
                ty = p[1] + gap
        placed.append((ex + 8, ty))
        if cur:
            parts.append(f'<circle class="dot cd {year_cls(yr, cur_year)}" cx="{ex:.1f}" cy="{ey:.1f}" r="4.5"/>')
        val = f"{fmt_h(v) if v < 100 else round(v)} h"
        lx = ex + 8
        body = (f'<tspan x="{lx:.1f}">{yr}</tspan><tspan x="{lx:.1f}" dy="13">{val}</tspan>' if two
                else f"{yr} · {val}")
        parts.append(f'<text class="lbl" x="{lx:.1f}" y="{ty:.1f}">{body}</text>')
    parts.append(f'<line class="xh" x1="0" x2="0" y1="{T}" y2="{y(0):.1f}"/>')
    parts.append(f'<rect class="xhit" x="{L}" y="{T}" width="{pw}" height="{ph}"/>')
    parts.append("</svg>")
    return "".join(parts)


def cum_table(series: dict, f: str) -> str:
    ys = sorted(series, reverse=True)
    head = "".join(f"<th>{yr}</th>" for yr in ys)
    body = []
    for m in range(12):
        cells, any_val = [], False
        for yr in ys:
            s = series[yr]
            last = month_span(yr, m)[1] - 1
            if month_span(yr, m)[0] < len(s):
                cells.append(f"<td>{fmt_h(s[min(last, len(s) - 1)])}</td>")
                any_val = True
            else:
                cells.append("<td>–</td>")
        if any_val:
            body.append(f"<tr><th>{MONTHS[m]}</th>{''.join(cells)}</tr>")
    return (f'<table data-f="{f}" class="ct{' sel' if f == 'all' else ''}"><thead><tr><th>Monatsende, h</th>{head}</tr></thead>'
            f"<tbody>{''.join(body)}</tbody></table>")


def cum_html(acts: list, today) -> str:
    data = cum_series(acts, today)
    cur = today.year
    btns = "".join(f'<button type="button" data-f="{f}" aria-pressed="{"true" if f == "all" else "false"}">'
                   f'{label}</button>' for f, label in CUM_FILTERS)
    charts = "".join(cum_svg(data[f], f, cur) + cum_svg(data[f], f, cur, W=360, H=280, cls="narrow")
                     for f, _ in CUM_FILTERS)
    tables = "".join(cum_table(data[f], f) for f, _ in CUM_FILTERS)
    nyears = len(data["all"])
    hint = ("" if nyears > 1 else
            '<p class="fine">Bisher liegen nur Daten für dieses Jahr vor – Vorjahres-Linien erscheinen '
            'nach dem Import älterer Strava-Daten.</p>')
    js = json.dumps({f: {str(k): v for k, v in data[f].items()} for f, _ in CUM_FILTERS},
                    separators=(",", ":")).replace("</", "<\\/")
    legend = "".join(f'<li><span class="ls {year_cls(yr, cur)}"></span>{yr}</li>'
                     for yr in sorted(data["all"], reverse=True))
    return (f'<div class="seg-f" role="group" aria-label="Sportart">{btns}</div>'
            f'<ul class="legend">{legend}</ul>'
            f'<div class="cyw">{charts}</div>'
            f'<details><summary>Als Tabelle anzeigen</summary><div class="tw">{tables}</div></details>'
            f'{hint}<script id="ydata" type="application/json">{js}</script>')


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
    if s["partner_pts"]:
        # Fairer Vergleich am Tag von Nicos letztem Stand, nicht mit Sebastians heutigem Wert
        li, lv = s["partner_pts"][-1]
        ci = min(li, e)
        gap = lv - s["me"][ci]
        when = date.fromordinal(date(s["year"], 1, 1).toordinal() + ci).strftime("%d.%m.")
        pn = html.escape(s["partner_name"])
        tiles.append((f"{'+' if gap >= 0 else '−'}{fmt_km(abs(gap))} km",
                      f"{pn} {'vor' if gap >= 0 else 'hinter'} dir<em>Stand {when}</em>"))
    cls = "mini m4" if len(tiles) == 4 else "mini"
    out = f'<div class="{cls}">' + "".join(f"<div><b>{a}</b><span>{b}</span></div>" for a, b in tiles) + "</div>"
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


# ---------------------------------------------------------------------------
# Wettkämpfe: Historie + geplante Starts je Disziplin, Bestzeit hervorgehoben
# ---------------------------------------------------------------------------
RACES = ROOT / "data" / "races.json"
DISCIPLINES = [  # Reihenfolge auf der Seite
    ("hm", "Halbmarathon"),
    ("marathon", "Marathon"),
    ("tri_kurz", "Triathlon Kurzdistanz"),
    ("tri_mittel", "Triathlon Mitteldistanz"),
    ("tri_lang", "Triathlon Langdistanz"),
    ("rad", "Radrennen"),
]


def parse_hms(s: str) -> int:
    parts = [int(p) for p in s.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, sec = parts
    return h * 3600 + m * 60 + sec


def fmt_hms(sec: int) -> str:
    sec = int(round(sec))
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def fmt_delta(sec: int) -> str:
    sec = int(round(abs(sec)))
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 \
        else f"{sec // 60}:{sec % 60:02d}"


def fmt_date(d) -> str:
    return d.strftime("%d.%m.%Y")


def countdown(d, today) -> str:
    n = (d - today).days
    if n == 0:
        return "heute"
    if n == 1:
        return "morgen"
    if n < 14:
        return f"in {n} Tagen"
    return f"in {n // 7} Wochen"


def race_data(cfg: dict, today) -> dict:
    """Je Disziplin: Ergebnisse, geplante Starts, Bestzeit. Alles hier gerechnet."""
    out = {}
    for key, label in DISCIPLINES:
        rs = []
        for r in cfg["races"]:
            if r["discipline"] != key:
                continue
            d = date.fromisoformat(r["date"])
            rs.append({"date": d, "name": r["name"], "source": r.get("source"),
                       "result": parse_hms(r["result"]) if r.get("result") else None,
                       "target_raw": r.get("target"), "beat": bool(r.get("beat"))})
        if not rs:
            continue
        rs.sort(key=lambda r: r["date"])
        past = [r for r in rs if r["result"] is not None]
        future = [r for r in rs if r["result"] is None and r["date"] >= today]
        pb = min(past, key=lambda r: (r["result"], r["date"])) if past else None
        for r in future:
            t = r["target_raw"]
            if t == "pb":
                r["target"] = pb["result"] if pb else None
                r["beat"] = True
                r["target_is_pb"] = True
            else:
                r["target"] = parse_hms(t) if t else None
                r["target_is_pb"] = False
        out[key] = {"label": label, "past": past, "future": future, "pb": pb}
    return out


def race_span(v: dict, today) -> tuple:
    """Zeitachse einer Disziplin: 1. Jan. des ersten Jahres … 31. Dez. des letzten Jahres (inkl. heute)."""
    ds = [r["date"] for r in v["past"] + v["future"]] + [today]
    return date(min(ds).year, 1, 1), date(max(ds).year + 1, 1, 1)


def race_svg(v: dict, span: tuple, today, W: int = 720, H: int = 132, cls: str = "wide") -> str:
    """Zeitstrahl einer Disziplin: Ergebnisse (Punkte), Bestzeit (PB), Zielzeiten (Ring, gestrichelt).
    y-Achse: schneller = weiter unten (wie eine normale Zeitachse)."""
    pts = [(r["date"], r["result"]) for r in v["past"]]
    tgts = [(r["date"], r["target"]) for r in v["future"] if r.get("target")]
    times = [t for _, t in pts + tgts]
    L, R, T, B = (46, 14, 34, 22) if W > 500 else (40, 10, 34, 22)
    pw, ph = W - L - R, H - T - B
    lo, hi = min(times), max(times)
    pad = max((hi - lo) * 0.15, 120)
    lo, hi = lo - pad, hi + pad
    step = next((s for s in (60, 120, 300, 600, 900, 1800, 3600, 7200) if (hi - lo) / s <= 4), 7200)
    t0, t1 = span
    days = (t1 - t0).days
    x = lambda d: L + (d - t0).days / days * pw
    y = lambda t: T + ph - (t - lo) / (hi - lo) * ph     # schneller (kleiner) = unten

    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" class="chart {cls} rc">']
    first = -(-int(lo) // step) * step
    for t in range(first, int(hi) + 1, step):
        lab = f"{t // 3600}:{t % 3600 // 60:02d}"
        parts.append(f'<line class="grid" x1="{L}" x2="{W-R}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>'
                     f'<text class="tick" x="{L-6}" y="{y(t)+4:.1f}" text-anchor="end">{lab}</text>')
    for yr in range(t0.year, t1.year):
        xa, xb = x(date(yr, 1, 1)), x(date(yr + 1, 1, 1))
        if yr > t0.year:
            parts.append(f'<line class="mtick" x1="{xa:.1f}" x2="{xa:.1f}" y1="{T+ph:.1f}" y2="{T+ph+4:.1f}"/>')
        nyears = t1.year - t0.year
        every = 1 if nyears <= (8 if W > 500 else 5) else (2 if nyears <= (16 if W > 500 else 10) else 3)
        if (t1.year - 1 - yr) % every == 0:
            parts.append(f'<text class="tick" x="{(xa+xb)/2:.1f}" y="{H-6}" text-anchor="middle">{yr}</text>')
    parts.append(f'<line class="axis" x1="{L}" x2="{W-R}" y1="{T+ph:.1f}" y2="{T+ph:.1f}"/>')
    if t0 <= today < t1:  # heute
        xt = x(today)
        parts.append(f'<line class="today" x1="{xt:.1f}" x2="{xt:.1f}" y1="12" y2="{T+ph:.1f}"/>'
                     f'<text class="tick" x="{xt + (4 if xt < W - R - 40 else -4):.1f}" y="10" text-anchor="{"start" if xt < W - R - 40 else "end"}">heute</text>')
    if len(pts) > 1:
        d = " ".join(f"{'M' if i == 0 else 'L'}{x(a):.1f},{y(b):.1f}" for i, (a, b) in enumerate(pts))
        parts.append(f'<path class="rline" d="{d}"/>')
    if pts and tgts:
        a, b = pts[-1]
        c, e = tgts[0]
        parts.append(f'<line class="rtgt" x1="{x(a):.1f}" y1="{y(b):.1f}" x2="{x(c):.1f}" y2="{y(e):.1f}"/>')
    pb = v["pb"]
    for r in v["past"]:
        is_pb = pb is r
        tip = html.escape(f"{fmt_date(r['date'])} · {r['name']}: {fmt_hms(r['result'])}"
                          + (" · Bestzeit" if is_pb else ""))
        parts.append(f'<circle class="rdot{" rpb" if is_pb else ""}" cx="{x(r["date"]):.1f}" '
                     f'cy="{y(r["result"]):.1f}" r="{6 if is_pb else 4}" data-tip="{tip}"/>')
    for r in v["future"]:
        if not r.get("target"):
            continue
        tip = html.escape(f"{fmt_date(r['date'])} · {r['name']}: Ziel "
                          f"{'unter ' if r['beat'] else ''}{fmt_hms(r['target'])}")
        parts.append(f'<circle class="rgoal" cx="{x(r["date"]):.1f}" cy="{y(r["target"]):.1f}" '
                     f'r="5" data-tip="{tip}"/>')
    if pb:  # Bestzeit direkt über dem Punkt beschriften
        px, py = x(pb["date"]), y(pb["result"])
        px = min(max(px, L + 40), W - R - 40)
        parts.append(f'<text class="rlbl" x="{px:.1f}" y="{py-11:.1f}" '
                     f'text-anchor="middle">PB {fmt_hms(pb["result"])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def races_html(rd: dict, today) -> str:
    if not rd:
        return '<section class="card"><p class="sub">Noch keine Wettkämpfe eingetragen.</p></section>'
    blocks = []
    for key, _ in DISCIPLINES:
        if key not in rd:
            continue
        v = rd[key]
        span = race_span(v, today)
        pb = v["pb"]
        badge = (f'<span class="pbb">Bestzeit <b>{fmt_hms(pb["result"])}</b>'
                 f'<i>{fmt_date(pb["date"])}</i></span>' if pb
                 else '<span class="pbb none">noch keine Bestzeit</span>')
        n_pts = len(v["past"]) + sum(1 for r in v["future"] if r.get("target"))
        chart = (race_svg(v, span, today) + race_svg(v, span, today, W=360, H=140, cls="narrow")
                 if n_pts >= 2 else "")
        rows = []
        for r in v["future"]:
            if r.get("target"):
                goal = (f"Ziel: neue PB (unter {fmt_hms(r['target'])})" if r["target_is_pb"]
                        else f"Ziel {'unter ' if r['beat'] else ''}{fmt_hms(r['target'])}")
            elif r["target_raw"] == "pb":
                goal = "Ziel: erste Bestzeit"
            else:
                goal = "Zielzeit offen"
            rows.append(f'<li class="up"><span class="rd">{fmt_date(r["date"])}'
                        f'<em>{countdown(r["date"], today)}</em></span>'
                        f'<span class="rn">{html.escape(r["name"])}</span>'
                        f'<span class="rt goal">{goal}</span></li>')
        for r in reversed(v["past"]):
            if pb is r:
                extra = '<em class="pbt">PB</em>'
            else:
                extra = f'<em>+{fmt_delta(r["result"] - pb["result"])}</em>'
            rows.append(f'<li><span class="rd">{fmt_date(r["date"])}</span>'
                        f'<span class="rn">{html.escape(r["name"])}</span>'
                        f'<span class="rt"><b>{fmt_hms(r["result"])}</b>{extra}</span></li>')
        n_past, n_fut = len(v["past"]), len(v["future"])
        meta = " · ".join(x for x in (
            f'{n_past} Rennen' if n_past else "",
            f'{n_fut} geplant' if n_fut else "") if x)
        blocks.append(f'<section class="card disc" id="d-{key}"><div class="dh"><div><h3>{v["label"]}</h3>'
                      f'<p class="dm">{meta}</p></div>{badge}</div>'
                      f'{chart}<ul class="rl">{"".join(rows)}</ul></section>')
    return "".join(blocks)


def next_race_html(rd: dict, today) -> str:
    fut = sorted((r for v in rd.values() for r in v["future"]), key=lambda r: r["date"])
    if not fut:
        return ""
    r = fut[0]
    return (f'<p class="note">Nächster Start: <b>{html.escape(r["name"])}</b> · '
            f'{fmt_date(r["date"])} · {countdown(r["date"], today)}</p>')


def races_note(cfg: dict) -> str:
    legend = '<span class="pbx"></span> Bestzeit · <span class="gx"></span> Zielzeit'
    watch = [f'{html.escape(r["name"])} {r["date"][:4]}' for r in cfg["races"]
             if r.get("result") and r.get("source") == "uhr"]
    pre = ""
    if watch:
        pre = ("Offizielle Endzeiten, Triathlon inkl. Wechsel. Zeit laut Uhr (Strava): "
               + ", ".join(watch) + ".<br>")
    return f'<p class="fine">{pre}{legend}</p>'


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


# ---------------------------------------------------------------- Woche

SPORT_DE = {
    "Run": "Lauf", "TrailRun": "Traillauf", "VirtualRun": "Laufband",
    "Ride": "Rad", "VirtualRide": "Rolle", "GravelRide": "Gravel", "MountainBikeRide": "MTB",
    "EBikeRide": "E-Bike", "EMountainBikeRide": "E-MTB", "Swim": "Schwimmen",
    "Hike": "Wandern", "Walk": "Gehen", "Workout": "Workout", "WeightTraining": "Krafttraining",
    "Yoga": "Yoga", "Squash": "Squash",
}
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def fmt_dur(sec: int) -> str:
    """3725 -> '1:02 h', 2738 -> '46 min'."""
    m = round(sec / 60)
    return f"{m // 60}:{m % 60:02d} h" if m >= 60 else f"{m} min"


def fmt_clock(sec: int) -> str:
    """3725 -> '1:02:05', 2738 -> '45:38'."""
    h, r = divmod(int(sec), 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_dist(a: dict) -> str:
    d = a.get("distance_m") or 0
    if d <= 0:
        return "–"
    if a["sport_type"] == "Swim":
        return f"{round(d):,} m".replace(",", ".")
    return f"{d / 1000:.1f} km".replace(".", ",")


def tempo(a: dict) -> tuple:
    """(Bezeichnung, Wert) passend zur Sportart, oder None ohne Distanz."""
    d, t = a.get("distance_m") or 0, a.get("moving_time_s") or 0
    if d <= 0 or t <= 0:
        return None
    cat = category(a["sport_type"])
    if a["sport_type"] == "Swim":
        p = round(t / (d / 100))
        return ("Pace", f"{p // 60}:{p % 60:02d} /100 m")
    if cat == "bike":
        return ("Ø Tempo", f"{d / t * 3.6:.1f} km/h".replace(".", ","))
    if cat in ("run", "hike"):
        p = round(t / (d / 1000))
        return ("Pace", f"{p // 60}:{p % 60:02d} /km")
    return None


def sport_name(a: dict) -> str:
    n = SPORT_DE.get(a["sport_type"], a["sport_type"])
    if category(a["sport_type"]) == "bike" and not (a.get("distance_m") or 0) > 0:
        n += " (indoor)"
    return n


def week_acts(acts: list, monday) -> list:
    from datetime import timedelta
    end = monday + timedelta(days=7)
    return [a for a in acts if monday <= datetime.fromisoformat(a["start_local"]).date() < end]


def week_html(acts: list, today) -> str:
    """Karte „Diese Woche": Summen + aufklappbare Liste der Einheiten (Mo–So)."""
    from datetime import timedelta
    mon = today - timedelta(days=today.weekday())
    sun = mon + timedelta(days=6)
    wk = sorted(week_acts(acts, mon), key=lambda a: a["start_local"])
    prev = week_acts(acts, mon - timedelta(days=7))
    t_wk = sum(a.get("moving_time_s") or 0 for a in wk)
    t_prev = sum(a.get("moving_time_s") or 0 for a in prev)
    run_km = sum((a.get("distance_m") or 0) for a in wk if category(a["sport_type"]) == "run") / 1000
    run_prev = sum((a.get("distance_m") or 0) for a in prev if category(a["sport_type"]) == "run") / 1000
    kw = mon.isocalendar()[1]
    head = (f'<h2>Diese Woche</h2><p class="sub">KW {kw} · {mon:%d.%m.} – {sun:%d.%m.%Y}</p>'
            f'<div class="mini">'
            f'<div><b>{len(wk)}</b><span>Einheiten</span><em>Vorwoche {len(prev)}</em></div>'
            f'<div><b>{fmt_dur(t_wk)}</b><span>Bewegungszeit</span><em>Vorwoche {fmt_dur(t_prev)}</em></div>'
            f'<div><b>{f"{run_km:.1f}".replace(".", ",")} km</b><span>Laufen</span>'
            f'<em>Vorwoche {f"{run_prev:.1f}".replace(".", ",")} km</em></div></div>')
    if not wk:
        return head + '<p class="note wk-empty">Noch keine Einheit in dieser Woche.</p>'
    # Zeitanteil je Sportart als dünner Balken
    split = []
    for k, label, _ in CATEGORIES:
        sec = sum(a.get("moving_time_s") or 0 for a in wk if category(a["sport_type"]) == k)
        if sec:
            split.append((k, label, sec))
    bar = "".join(f'<span class="s-{k}" style="flex:{sec}" data-tip="{label} {fmt_dur(sec)}"></span>'
                  for k, label, sec in split)
    keys = " · ".join(f'<span class="sw s-{k}"></span>{label} {fmt_dur(sec)}' for k, label, sec in split)
    items = []
    for a in wk:
        d = datetime.fromisoformat(a["start_local"])
        k = category(a["sport_type"])
        mv, el = a.get("moving_time_s") or 0, a.get("elapsed_time_s") or 0
        rows = [("Start", f"{d:%H:%M} Uhr"), ("Bewegungszeit", fmt_clock(mv))]
        if el > mv:
            rows.append(("Gesamtzeit", f"{fmt_clock(el)} <i>(Pause {fmt_clock(el - mv)})</i>"))
        if (a.get("distance_m") or 0) > 0:
            rows.append(("Distanz", fmt_dist(a)))
        tp = tempo(a)
        if tp:
            rows.append(tp)
        if (a.get("elevation_gain_m") or 0) > 0:
            rows.append(("Höhenmeter", f"{round(a['elevation_gain_m'])} m"))
        if t_wk:
            rows.append(("Anteil Woche", f"{round(mv / t_wk * 100)} %"))
        dl = "".join(f"<dt>{lbl}</dt><dd>{val}</dd>" for lbl, val in rows)
        items.append(
            f'<li><details class="wa"><summary>'
            f'<span class="wd">{WEEKDAYS[d.weekday()]} {d:%d.%m.}</span>'
            f'<span class="ws"><span class="sw s-{k}"></span>{html.escape(sport_name(a))}</span>'
            f'<span class="wv">{fmt_dist(a)}</span><span class="wv">{fmt_dur(mv)}</span>'
            f'</summary><dl>{dl}</dl></details></li>')
    return (head + f'<div class="wbar">{bar}</div><p class="wkeys">{keys}</p>'
            f'<ul class="wl">{"".join(items)}</ul>'
            '<p class="fine">Tippen für Details. Woche Mo–So, Zeiten = Bewegungszeit.</p>')


SPONSORS = ROOT / "data" / "sponsors.json"


def fmt_eur(v: float) -> str:
    """12,50 € bzw. 1.250 € (ganze Beträge ohne Nachkommastellen)."""
    if abs(v - round(v)) < 0.005:
        return f"{round(v):,}".replace(",", ".") + " €"
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def sponsors_html(cfg: dict) -> str:
    link = (cfg.get("paypal") or "").strip()
    if link.startswith("https://"):
        btn = (f'<a class="pp" href="{html.escape(link)}" target="_blank" rel="noopener">'
               'Mit PayPal unterstützen</a>')
    else:
        btn = '<p class="pp none">PayPal-Link folgt</p>'
    ents = sorted(cfg.get("entries", []), key=lambda e: e["date"], reverse=True)
    if not ents:
        return (btn + '<p class="note">Noch keine Sponsoren – der erste Beitrag erscheint hier mit Datum und Betrag.</p>')
    total = sum(float(e["amount"]) for e in ents)
    sums: dict = {}
    for e in ents:
        n = (e.get("name") or "").strip()
        if n:
            sums[n] = sums.get(n, 0.0) + float(e["amount"])
    stats = (f'<div class="mini"><div><b>{fmt_eur(total)}</b><span>gesamt</span></div>'
             f'<div><b>{len(ents)}</b><span>Beiträge</span></div>'
             f'<div><b>{len(sums) + sum(1 for e in ents if not (e.get("name") or "").strip())}</b>'
             '<span>Unterstützer</span></div></div>')
    top = sorted(sums.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    rank = ""
    if top:
        rank = ('<h4>Größte Sponsoren</h4><ol class="sl">' + "".join(
            f'<li><span class="sr">{i}</span><span class="sn">{html.escape(n)}</span>'
            f'<span class="sv">{fmt_eur(v)}</span></li>' for i, (n, v) in enumerate(top, 1)) + "</ol>")
    rows = "".join(
        f'<li><span class="sd">{fmt_date(date.fromisoformat(e["date"]))}</span>'
        f'<span class="sn">{html.escape((e.get("name") or "").strip() or "Anonym")}</span>'
        f'<span class="sv">{fmt_eur(float(e["amount"]))}</span></li>' for e in ents)
    return btn + stats + rank + f'<h4>Alle Beiträge</h4><ul class="sl">{rows}</ul>'


MARATHON_GPX = ROOT / "data" / "marathon_strecke.gpx"
MARATHON_MAP = ROOT / "data" / "marathon_karte.json"
MARATHON_PLAN = ROOT / "data" / "marathon_plan.json"
MARATHON_KM = 42.195


def haversine_km(a: tuple, b: tuple) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(d))


def parse_min(s: str) -> float:
    """'5:00' (min:ss) oder '3:37:00' (h:mm:ss) bzw. '10:10' (hh:mm) → Minuten."""
    p = [int(x) for x in s.split(":")]
    return p[0] * 60 + p[1] + p[2] / 60 if len(p) == 3 else p[0] + p[1] / 60


def fmt_pace(minutes: float) -> str:
    sec = round(minutes * 60)
    return f"{sec // 60}:{sec % 60:02d}"


def marathon_data() -> dict | None:
    """Offizielle Strecke + Plan → Daten für die Seite. Kilometer und Tempo rechnet das Script."""
    if not (MARATHON_GPX.exists() and MARATHON_MAP.exists() and MARATHON_PLAN.exists()):
        return None
    root = ET.parse(MARATHON_GPX).getroot()
    pts = [(float(e.get("lat")), float(e.get("lon"))) for e in root.iter()
           if e.tag.split("}")[-1] in ("rtept", "trkpt")]
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + haversine_km(a, b))
    scale = MARATHON_KM / cum[-1]  # GPX-Länge auf die offizielle Distanz normieren
    course = [[round(la, 5), round(lo, 5), round(c * scale, 3)] for (la, lo), c in zip(pts, cum)]
    plan = json.loads(MARATHON_PLAN.read_text(encoding="utf-8"))
    half = MARATHON_KM / 2
    p1 = parse_min(plan["pace_first_half"])
    total = parse_min(plan["target"])
    p2 = (total - p1 * half) / (MARATHON_KM - half)
    return {
        "plan": plan, "p1": p1, "p2": p2, "total": total, "start": parse_min(plan["start"]),
        "js": {"course": course, "map": {k: v for k, v in json.loads(MARATHON_MAP.read_text(encoding="utf-8")).items()
                                         if not k.startswith("_")},
               "places": plan["places"], "start": plan["start"], "date": plan["date"],
               "p1": p1, "p2": p2, "total": total, "km": MARATHON_KM, "block": plan["block"]},
    }


def marathon_html(md: dict | None) -> str:
    if not md:
        return '<section class="card"><h2>FFM-Marathon-Plan</h2><p class="sub">Keine Daten.</p></section>'
    pl = md["plan"]
    d = date.fromisoformat(pl["date"])
    half = md["p1"] * MARATHON_KM / 2
    return f"""<section class="card mcard">
 <h2>FFM-Marathon-Plan</h2>
 <p class="sub">{html.escape(pl["name"])} · {WEEKDAYS[d.weekday()]}., {fmt_date(d)} · {html.escape(pl["block"])} · Ziel {html.escape(pl["goal_text"])}</p>
 <div class="mclock" aria-live="polite">
  <b id="mTime">{html.escape(pl["start"])}</b>
  <div class="mwhere"><span id="mPlace">Start</span><em id="mMeta">km 0,0</em></div>
 </div>
 <div class="mseg" role="group" aria-label="Kartenausschnitt">
  <button type="button" data-v="all" aria-pressed="true">Ganze Strecke</button>
  <button type="button" data-v="city" aria-pressed="false">Innenstadt</button>
 </div>
 <div class="mmap"><svg id="mMap" viewBox="0 0 720 400" role="img" aria-label="Karte der Marathonstrecke mit Sebastians Position. Tippen auf die Strecke zeigt, wann er dort ist."></svg></div>
 <p class="fine mhint">Tipp auf die Strecke, um zu sehen, wann er dort vorbeikommt.</p>
 <noscript><p class="note">Die Karte braucht JavaScript.</p></noscript>
 <div class="mrange">
  <button type="button" class="mplay" id="mPlay" aria-label="Rennen abspielen"><svg viewBox="0 0 20 20"><path d="M5 3l12 7-12 7z"/></svg></button>
  <input type="range" id="mSlider" min="0" max="300" step="0.5" value="0" aria-label="Uhrzeit am Renntag">
 </div>
 <div class="mticks" id="mTicks"></div>
 <div class="mbtns">
  <button type="button" id="mNow">Jetzt (am Renntag)</button>
  <button type="button" data-go="start">Start</button>
  <button type="button" data-go="half">Halbmarathon</button>
  <button type="button" data-go="finish">Ziel</button>
 </div>
 <div class="mstart">
  <label for="mStart">Startzeit über der Linie</label>
  <div class="mstep">
   <button type="button" id="mMinus" aria-label="Eine Minute früher">−</button>
   <input id="mStart" type="text" value="{html.escape(pl["start"])}" inputmode="numeric" maxlength="5" autocomplete="off">
   <button type="button" id="mPlus" aria-label="Eine Minute später">+</button>
   <button type="button" id="mReset" class="mlink">Zurücksetzen</button>
  </div>
  <p class="fine" id="mStartNote">Geschätzt für {html.escape(pl["block"])}. Am Renntag auf die echte Startzeit stellen, dann verschiebt sich alles.</p>
 </div>
 <p class="fine">Tempo: {fmt_pace(md["p1"])} min/km bis zum Halbmarathon ({fmt_hms(round(half * 60))}), danach {fmt_pace(md["p2"])} min/km, Endzeit {html.escape(pl["target"])}. In der Nacht vor dem Rennen werden die Uhren eine Stunde zurückgestellt, alle Zeiten sind Winterzeit. Strecke: offizielle GPX-Datei des Veranstalters. Karte: Frankfurter Stadtteilgrenzen (Code for Germany), Main daraus abgeleitet, Wald und Parks vereinfacht. Live-Tracking am Renntag: <a href="https://www.frankfurt-marathon.com/">offizielle Marathon-App</a>.</p>
</section>"""


def marathon_js_data(md: dict | None) -> str:
    return json.dumps(md["js"] if md else None, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


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

    rcfg = json.loads(RACES.read_text(encoding="utf-8")) if RACES.exists() else {"races": []}
    rd = race_data(rcfg, now.date())

    scfg = (json.loads(SPONSORS.read_text(encoding="utf-8")) if SPONSORS.exists()
            else {"paypal": "", "entries": []})

    md = marathon_data()

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
        "{{WEEK}}": week_html(acts, now.date()),
        "{{CUM}}": cum_html(acts, now.date()),
        "{{C_YEAR}}": str(cs["year"]),
        "{{C_GOAL}}": fmt_km(cs["goal"]),
        "{{C_PARTNER}}": pname,
        "{{C_STATS}}": challenge_stats(cs),
        "{{C_LEGEND}}": c_legend,
        "{{C_CHART}}": challenge_svg(cs) + challenge_svg(cs, W=360, H=280, cls="narrow"),
        "{{C_TABLE}}": challenge_table(cs),
        "{{C_DATA}}": challenge_js_data(cs),
        "{{R_NEXT}}": next_race_html(rd, now.date()),
        "{{R_BLOCKS}}": races_html(rd, now.date()),
        "{{R_NOTE}}": races_note(rcfg),
        "{{S_BODY}}": sponsors_html(scfg),
        "{{M_BODY}}": marathon_html(md),
        "{{M_DATA}}": marathon_js_data(md),
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
<script>document.documentElement.classList.add('js')</script>
<style>
:root{color-scheme:light;
 --bg:#fcfcfb;--card:#ffffff;--border:#e6e5e0;--text:#0b0b0b;--text-2:#52514e;--muted:#8a8984;
 --grid:#ecebe7;--axis:#c9c8c2;
 --run:#2a78d6;--bike:#eb6834;--swim:#1baf7a;--hike:#eda100;--other:#e87ba4;--partner:#eb6834;--pb:#7d5bd9;
 --map-land:#f4f3ee;--map-line:#dfddd5;--map-water:#bcd7e8;--map-water-ink:#5b89a3;--map-green:#dde9d4;--map-green-ink:#6f8a62}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
 --bg:#141413;--card:#1a1a19;--border:#2c2c2a;--text:#ffffff;--text-2:#c3c2b7;--muted:#8f8e86;
 --grid:#2a2a28;--axis:#4a4a46;
 --run:#3987e5;--bike:#d95926;--swim:#199e70;--hike:#c98500;--other:#d55181;--partner:#d95926;--pb:#a48bea;
 --map-land:#21211f;--map-line:#34342f;--map-water:#1f3f52;--map-water-ink:#7fb0cc;--map-green:#1f3326;--map-green-ink:#7fa58c}}
:root[data-theme="dark"]{color-scheme:dark;
 --bg:#141413;--card:#1a1a19;--border:#2c2c2a;--text:#ffffff;--text-2:#c3c2b7;--muted:#8f8e86;
 --grid:#2a2a28;--axis:#4a4a46;
 --run:#3987e5;--bike:#d95926;--swim:#199e70;--hike:#c98500;--other:#d55181;--partner:#d95926;--pb:#a48bea;
 --map-land:#21211f;--map-line:#34342f;--map-water:#1f3f52;--map-water-ink:#7fb0cc;--map-green:#1f3326;--map-green-ink:#7fa58c}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
 font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
 padding:max(20px,env(safe-area-inset-top)) 16px 40px}
main{max-width:760px;margin:0 auto}
header{display:flex;align-items:baseline;gap:6px;margin-bottom:14px}
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
.mini.m4{grid-template-columns:repeat(4,1fr)}
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
.disc{margin-top:16px;border-top:4px solid var(--text)}
.dh{display:flex;align-items:flex-end;justify-content:space-between;gap:4px 10px;flex-wrap:wrap;
 margin:-2px 0 8px;padding-bottom:10px;border-bottom:1px solid var(--border)}
h3{font-size:21px;line-height:1.2;margin:0;letter-spacing:-.015em}
.dm{color:var(--muted);font-size:12px;margin:2px 0 0;font-variant-numeric:tabular-nums}
.pbb{font-size:13px;color:var(--text-2);font-variant-numeric:tabular-nums}
.pbb b{color:var(--pb);font-size:17px;margin:0 4px;letter-spacing:-.01em}
.pbb i{font-style:normal;color:var(--muted);font-size:12px}
.pbb.none{color:var(--muted)}
.rc{margin:2px 0 4px}
.rline{fill:none;stroke:var(--axis);stroke-width:1.5}
.rtgt{stroke:var(--pb);stroke-width:1.5;stroke-dasharray:4 4;opacity:.7}
.rdot{fill:var(--text-2);stroke:var(--card);stroke-width:2}
.rdot.rpb{fill:var(--pb)}
.rgoal{fill:var(--card);stroke:var(--pb);stroke-width:2;stroke-dasharray:3 2}
.today{stroke:var(--axis);stroke-width:1;stroke-dasharray:2 3}
.chart .rlbl{fill:var(--pb);font-weight:700}
.rl{list-style:none;margin:6px 0 0;padding:0;font-size:14px;font-variant-numeric:tabular-nums}
.rl li{display:grid;grid-template-columns:92px 1fr auto;gap:2px 10px;padding:6px 0;border-bottom:1px solid var(--border);align-items:baseline}
.rl li:last-child{border-bottom:0}
.rd{color:var(--text-2);font-size:13px}
.rd em{display:block;font-style:normal;color:var(--pb);font-weight:600;font-size:12px}
.rt{text-align:right;white-space:nowrap}
.rt em{font-style:normal;color:var(--muted);font-size:12px;margin-left:8px}
.rt em.pbt{color:var(--card);background:var(--pb);border-radius:4px;padding:1px 5px;font-weight:700}
.rt.goal{color:var(--text-2);font-size:13px}
.up .rn{font-weight:600}
.fine{color:var(--muted);font-size:12px;margin:12px 0 0}
.card .note+.fine{margin-top:0}
.pbx,.gx{display:inline-block;width:9px;height:9px;border-radius:50%;vertical-align:-1px;margin-left:4px}
.pbx{background:var(--pb)}.gx{border:2px dashed var(--pb)}
@media (max-width:480px){.rl li{grid-template-columns:1fr auto}.rl .rd{grid-column:1/-1}
 .rd em{display:inline;margin-left:8px}}
.wbar{display:flex;gap:2px;height:8px;border-radius:4px;overflow:hidden;margin:8px 0 6px}
.wkeys{color:var(--text-2);font-size:12px;margin:0 0 6px;font-variant-numeric:tabular-nums}
.wkeys .sw{margin:0 4px 0 2px}
.wl{list-style:none;margin:0;padding:0;font-variant-numeric:tabular-nums}
.wl li{border-bottom:1px solid var(--border)}.wl li:last-child{border-bottom:0}
.wa{margin:0;font-size:14px}
.wa summary{display:grid;grid-template-columns:62px 1fr auto 62px 10px;gap:10px;align-items:center;
 padding:9px 0;color:var(--text);list-style:none;-webkit-tap-highlight-color:transparent}
.wa summary::-webkit-details-marker{display:none}
.wa summary::after{content:"›";grid-column:5;color:var(--muted);font-size:18px;line-height:1;
 text-align:center;transform:rotate(90deg);transition:transform .15s}
.wa[open] summary::after{transform:rotate(-90deg)}
.mini em{display:block;font-style:normal;color:var(--muted);font-size:12px;white-space:nowrap}
@media (max-width:480px){.mini em{font-size:11px}.mini.m4{grid-template-columns:repeat(2,1fr);row-gap:10px}}
.wd{color:var(--text-2);font-size:13px;white-space:nowrap}.ws{display:flex;align-items:center;gap:8px;font-weight:600;min-width:0}
.wv{text-align:right;white-space:nowrap}
.wa dl{display:grid;grid-template-columns:auto 1fr;gap:4px 16px;margin:0 0 12px 72px;font-size:13px}
.wa dt{color:var(--text-2)}.wa dd{margin:0;text-align:right}.wa dd i{font-style:normal;color:var(--muted)}
@media (max-width:480px){.wa summary{grid-template-columns:62px 1fr auto auto 10px;gap:8px}
 .ws{gap:6px}
 .wa dl{margin-left:0;padding:4px 10px 0;border-left:2px solid var(--border)}}
.tabs{position:sticky;top:0;z-index:5;display:flex;gap:4px;padding:4px;margin:0 0 16px;
 background:var(--card);border:1px solid var(--border);border-radius:12px}
.tabs a{flex:1;text-align:center;padding:8px 10px;border-radius:9px;font-size:14px;font-weight:600;
 color:var(--text-2);text-decoration:none;-webkit-tap-highlight-color:transparent}
.tabs a[aria-selected="true"]{background:var(--text);color:var(--bg)}
.js .panel{display:none}.js .panel.on{display:block}
.seg-f{display:flex;gap:2px;padding:3px;margin:2px 0 10px;background:var(--bg);border:1px solid var(--border);border-radius:10px}
.seg-f button{flex:1;font:inherit;font-size:13px;font-weight:600;color:var(--text-2);background:none;border:0;
 border-radius:7px;padding:6px 4px;cursor:pointer;-webkit-tap-highlight-color:transparent}
.seg-f button[aria-pressed="true"]{background:var(--card);color:var(--text);box-shadow:0 0 0 1px var(--border)}
.cy:not(.sel),.ct:not(.sel){display:none!important}
.cl{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}.cl.cur{stroke-width:2.5}
.cl.y0{stroke:var(--pb)}.cl.y1{stroke:var(--run)}.cl.y2{stroke:var(--bike)}.cl.y3{stroke:var(--swim)}.cl.yx{stroke:var(--muted)}
.cd.y0{fill:var(--pb)}
.ls.y0{border-color:var(--pb)}.ls.y1{border-color:var(--run)}.ls.y2{border-color:var(--bike)}.ls.y3{border-color:var(--swim)}.ls.yx{border-color:var(--muted)}
#ptr{position:fixed;left:50%;top:0;z-index:20;transform:translate(-50%,-48px);display:flex;align-items:center;gap:8px;
 background:var(--text);color:var(--bg);font-size:13px;font-weight:600;padding:7px 14px;border-radius:18px;
 pointer-events:none;opacity:0;margin-top:env(safe-area-inset-top)}
#ptr i{display:inline-block;font-style:normal;transition:transform .15s}
#ptr.ready i{transform:rotate(180deg)}
#ptr.busy i{animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
html{overscroll-behavior-y:none}
.coach{display:block;width:100%;max-width:420px;height:auto;margin:4px auto 0;border-radius:10px}
.pp{display:block;text-align:center;font-weight:600;font-size:15px;padding:11px 14px;border-radius:10px;
 background:var(--text);color:var(--bg);text-decoration:none;margin:4px 0 14px}
.pp.none{background:none;color:var(--muted);border:1px dashed var(--border)}
h4{font-size:13px;color:var(--text-2);margin:16px 0 4px;font-weight:600}
.sl{list-style:none;margin:0;padding:0;font-size:14px;font-variant-numeric:tabular-nums}
.sl li{display:flex;gap:10px;align-items:baseline;padding:7px 0;border-bottom:1px solid var(--border)}
.sl li:last-child{border-bottom:0}
.sr{width:18px;color:var(--muted);font-weight:700}.sd{width:84px;color:var(--text-2);font-size:13px}
.sn{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.sv{font-weight:600;white-space:nowrap}
ol.sl li:first-child .sr,ol.sl li:first-child .sv{color:var(--pb)}
.mclock{display:grid;grid-template-columns:auto minmax(0,1fr);gap:0 14px;align-items:center;margin:4px 0 12px;
 padding:10px 14px;border-radius:10px;background:var(--text);color:var(--bg)}
.mclock b{font-size:44px;line-height:1;font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.mwhere{min-width:0;display:flex;flex-direction:column}
.mwhere span{font-size:17px;font-weight:700;line-height:1.3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mwhere em{font-style:normal;font-size:13px;line-height:1.35;opacity:.75;font-variant-numeric:tabular-nums;height:2.7em;overflow:hidden;
 display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
@media (max-width:480px){.mclock b{font-size:36px}.mwhere span{font-size:15px}.mwhere em{font-size:12px}}
.mseg{display:flex;gap:2px;padding:3px;margin:0 0 8px;background:var(--bg);border:1px solid var(--border);border-radius:10px}
.mseg button{flex:1;font:inherit;font-size:13px;font-weight:600;color:var(--text-2);background:none;border:0;
 border-radius:7px;padding:6px 4px;cursor:pointer;-webkit-tap-highlight-color:transparent}
.mseg button[aria-pressed="true"]{background:var(--card);color:var(--text);box-shadow:0 0 0 1px var(--border)}
.mmap{background:var(--map-land);border:1px solid var(--border);border-radius:10px;overflow:hidden}
.mmap svg{display:block;width:100%;height:auto;cursor:crosshair;touch-action:manipulation}
.mhint{margin:6px 0 12px}
.mrange{display:flex;align-items:center;gap:10px}
.mplay{flex:none;width:40px;height:40px;border-radius:50%;border:0;background:var(--pb);color:var(--card);cursor:pointer;display:grid;place-items:center}
.mplay svg{width:16px;height:16px;fill:currentColor}
#mSlider{flex:1;min-width:0;accent-color:var(--pb);height:30px;margin:0}
.mticks{display:flex;justify-content:space-between;color:var(--muted);font-size:12px;font-variant-numeric:tabular-nums;padding:0 0 0 50px}
.mbtns{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 0}
.mbtns button,.mstep button{font:inherit;font-size:13px;font-weight:600;color:var(--text);background:var(--bg);
 border:1px solid var(--border);border-radius:8px;padding:6px 10px;cursor:pointer}
.mstart{margin-top:14px;padding-top:12px;border-top:1px solid var(--border)}
.mstart label{display:block;font-size:13px;color:var(--text-2);margin-bottom:6px}
.mstep{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.mstep button{min-width:38px;font-size:16px;padding:5px 10px}
.mstep .mlink{min-width:0;font-size:13px}
#mStart{font:inherit;font-size:18px;font-weight:700;width:4.2em;text-align:center;padding:4px 6px;border:1px solid var(--border);
 border-radius:8px;background:var(--card);color:var(--text);font-variant-numeric:tabular-nums}
.mstart .fine{margin-top:6px}
.mcard .fine a{color:var(--text-2)}
.mcard button:focus-visible,#mStart:focus-visible,#mSlider:focus-visible{outline:2px solid var(--pb);outline-offset:2px}
.tabs a{white-space:nowrap}
@media (max-width:560px){.tabs{flex-wrap:wrap}.tabs a{flex:1 1 auto;padding:8px 6px;font-size:13px}}
@media (prefers-reduced-motion:reduce){.mpulse{display:none}}
footer{color:var(--muted);font-size:12px;margin-top:20px;text-align:center}
@media (max-width:480px){.mini b{font-size:16px}.kpi{padding:10px}.kpi b{font-size:18px;white-space:nowrap}.kpi span{font-size:12px}.kpis{gap:8px}}
</style>
</head>
<body>
<main>
<header><span class="brand">athlete<i>.</i>coach</span></header>

<nav class="tabs" role="tablist">
 <a href="#training" role="tab" data-tab="training" aria-selected="true">Training</a>
 <a href="#wettkaempfe" role="tab" data-tab="wettkaempfe" aria-selected="false">Wettkämpfe</a>
 <a href="#challenges" role="tab" data-tab="challenges" aria-selected="false">Challenges</a>
 <a href="#team" role="tab" data-tab="team" aria-selected="false">Team</a>
 <a href="#marathon" role="tab" data-tab="marathon" aria-selected="false">FFM-Marathon-Plan</a>
</nav>

<div class="panel" id="p-training" data-panel="training">
<section class="kpis">
 <div class="kpi"><b>{{TOTAL}} h</b><span>Training {{YEAR}}</span></div>
 <div class="kpi"><b>{{COUNT}}</b><span>Einheiten {{YEAR}}</span></div>
 <div class="kpi"><b>{{LATEST}}</b><span>letzte Einheit</span></div>
</section>

<section class="card">
 {{WEEK}}
</section>

<section class="card">
 <h2 id="c1t">Trainingsstunden pro Monat {{YEAR}}</h2>
 <p class="sub">Bewegungszeit nach Sportart, in Stunden</p>
 <ul class="legend">{{LEGEND}}</ul>
 {{CHART}}
 <details><summary>Als Tabelle anzeigen</summary><div class="tw">{{TABLE}}</div></details>
</section>

<section class="card">
 <h2 id="c3t">Trainingsstunden kumuliert – Jahresvergleich</h2>
 <p class="sub">Bewegungszeit seit 1. Januar, eine Linie pro Kalenderjahr</p>
 {{CUM}}
</section>
</div>

<div class="panel" id="p-wettkaempfe" data-panel="wettkaempfe">
<section class="card">
 <h2>Wettkämpfe</h2>
 <p class="sub">Endzeiten je Disziplin – vergangene Rennen und geplante Starts</p>
 {{R_NEXT}}
 {{R_NOTE}}
</section>
{{R_BLOCKS}}
</div>

<div class="panel" id="p-challenges" data-panel="challenges">
<section class="card">
 <h2 id="c2t">{{C_GOAL}}-km-Challenge {{C_YEAR}}</h2>
 <p class="sub">Gelaufene Kilometer kumuliert, mit {{C_PARTNER}}</p>
 {{C_STATS}}
 <ul class="legend">{{C_LEGEND}}</ul>
 {{C_CHART}}
 <details><summary>Als Tabelle anzeigen</summary><div class="tw">{{C_TABLE}}</div></details>
</section>
</div>

<div class="panel" id="p-team" data-panel="team">
<section class="card">
 <h2>Coach</h2>
 <p class="sub">Die Person hinter dem Plan</p>
 <img class="coach" src="assets/coach.jpg" width="900" height="1200" alt="Foto: Coach an der Laufstrecke">
</section>
<section class="card">
 <h2>Sponsoren</h2>
 <p class="sub">Wer das Training unterstützt</p>
 {{S_BODY}}
</section>
</div>

<div class="panel" id="p-marathon" data-panel="marathon">
{{M_BODY}}
</div>

<footer>Daten: Strava · aktualisiert {{BUILT}} Uhr</footer>
</main>
<div id="tip"></div>
<div id="ptr" aria-hidden="true"><i>↓</i><span>Zum Aktualisieren ziehen</span></div>
<script>
(function(){
var tabs=document.querySelectorAll('.tabs a'),ids=[].map.call(tabs,function(a){return a.dataset.tab;});
function show(id,scroll){if(ids.indexOf(id)<0)id=ids[0];
 tabs.forEach(function(a){a.setAttribute('aria-selected',a.dataset.tab===id?'true':'false');});
 document.querySelectorAll('.panel').forEach(function(p){p.classList.toggle('on',p.dataset.panel===id);});
 if(scroll)window.scrollTo(0,0);}
tabs.forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();
 history.replaceState(null,'','#'+a.dataset.tab);show(a.dataset.tab,true);});});
window.addEventListener('hashchange',function(){show(location.hash.slice(1),true);});
show(location.hash.slice(1),false);})();
</script>
<script>
(function(){ /* Filter Jahresvergleich */
document.querySelectorAll('.seg-f button').forEach(function(b){b.addEventListener('click',function(){
 var f=b.dataset.f;document.querySelectorAll('.seg-f button').forEach(function(x){x.setAttribute('aria-pressed',x===b?'true':'false');});
 document.querySelectorAll('.cy,.ct').forEach(function(el){el.classList.toggle('sel',el.dataset.f===f);});});});
var Y=JSON.parse(document.getElementById('ydata').textContent),t=document.getElementById('tip');
function h(v){return (v<100?v.toFixed(1).replace('.',','):Math.round(v))+' h';}
document.querySelectorAll('svg.cy').forEach(function(sv){
 var L=+sv.dataset.l,PW=+sv.dataset.pw,W=+sv.dataset.w,S=Y[sv.dataset.f],hit=sv.querySelector('.xhit'),xh=sv.querySelector('.xh');
 var ys=Object.keys(S).sort().reverse(),ref=+ys[0]||new Date().getFullYear(),nref=((ref%4===0&&ref%100!==0)||ref%400===0)?366:365;
 hit.addEventListener('pointermove',function(e){var r=sv.getBoundingClientRect(),k=r.width/W;
  var fr=((e.clientX-r.left)/k-L)/PW;fr=Math.max(0,Math.min(.9999,fr));var i=Math.floor(fr*nref);
  var xx=L+(i+1)/nref*PW;xh.setAttribute('x1',xx);xh.setAttribute('x2',xx);xh.style.opacity=1;
  var dt=new Date(ref,0,1+i),parts=[('0'+dt.getDate()).slice(-2)+'.'+('0'+(dt.getMonth()+1)).slice(-2)+'.'];
  ys.forEach(function(yr){var s=S[yr],n=((yr%4===0&&yr%100!==0)||yr%400===0)?366:365,j=Math.floor(fr*n);
   if(j<s.length)parts.push(yr+' '+h(s[j]));});
  t.textContent=parts.join(' · ');t.style.opacity=1;var x=e.clientX+12,w=t.offsetWidth;
  if(x+w>innerWidth-8)x=e.clientX-w-12;if(x<8)x=8;t.style.left=x+'px';t.style.top=(e.clientY-40)+'px';});
 hit.addEventListener('pointerleave',function(){t.style.opacity=0;xh.style.opacity=0;});});})();
</script>
<script>
(function(){ /* Zum Aktualisieren nach unten ziehen (Handy) */
if(!('ontouchstart' in window))return;
var el=document.getElementById('ptr'),lab=el.querySelector('span'),y0=null,x0=0,d=0,TH=80,busy=false;
function set(p){el.style.opacity=Math.min(1,p/40);el.style.transform='translate(-50%,'+(Math.min(p,TH*1.4)*0.7-48)+'px)';}
addEventListener('touchstart',function(e){if(busy||window.scrollY>0||e.touches.length!==1){y0=null;return;}
 y0=e.touches[0].clientY;x0=e.touches[0].clientX;d=0;},{passive:true});
addEventListener('touchmove',function(e){if(y0===null)return;d=e.touches[0].clientY-y0;
 if(d<20&&Math.abs(e.touches[0].clientX-x0)>Math.abs(d)){y0=null;set(0);return;}
 if(d<=0||window.scrollY>0){set(0);return;}
 if(e.cancelable)e.preventDefault();set(d);var ok=d>TH;el.classList.toggle('ready',ok);
 lab.textContent=ok?'Loslassen zum Aktualisieren':'Zum Aktualisieren ziehen';},{passive:false});
addEventListener('touchend',function(){if(y0===null)return;y0=null;
 if(d>TH){busy=true;el.classList.remove('ready');el.classList.add('busy');lab.textContent='Aktualisiere …';
  el.style.opacity=1;el.style.transform='translate(-50%,12px)';
  location.replace(location.pathname+'?t='+Date.now()+location.hash);}
 else{set(0);}d=0;});})();
</script>
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
<script id="mdata" type="application/json">{{M_DATA}}</script>
<script>
(function(){ /* FFM-Marathon-Plan: Karte, Rennuhr, Zeitregler, Startzeit */
var D=JSON.parse(document.getElementById('mdata').textContent);var svg=document.getElementById('mMap');
if(!D||!svg)return;
var C=D.course,MAP=D.map,L=D.km,H=L/2,P1=D.p1,P2=D.p2,TT=D.total,T0=600,NS='http://www.w3.org/2000/svg';
function $(id){return document.getElementById(id);}
function pad(n){return (n<10?'0':'')+n;}
function hhmm(m){m=Math.round(m);return pad(Math.floor(m/60)%24)+':'+pad(m%60);}
function dur(m){var s=Math.round(m*60);return Math.floor(s/3600)+':'+pad(Math.floor(s%3600/60));}
function durS(m){var s=Math.round(m*60);return Math.floor(s/3600)+':'+pad(Math.floor(s%3600/60))+':'+pad(s%60);}
function pace(p){var s=Math.round(p*60);return Math.floor(s/60)+':'+pad(s%60);}
function kmS(k){return k.toFixed(1).replace('.',',');}
function parseHM(s){var a=String(s).trim().split(':').map(Number);return (a.length===2&&!isNaN(a[0])&&!isNaN(a[1])&&a[1]<60)?a[0]*60+a[1]:null;}
var DEF=parseHM(D.start),ST=DEF;
try{var sv0=localStorage.getItem('mfp-start');if(sv0&&parseHM(sv0)!=null)ST=parseHM(sv0);}catch(e){}
function elapsed(d){return d<=H?P1*d:P1*H+P2*(d-H);}
function distAt(t){return t<=0?0:t>=TT?L:(t<=P1*H?t/P1:H+(t-P1*H)/P2);}
function posAt(km){var lo=0,hi=C.length-1;while(hi-lo>1){var mid=(lo+hi)>>1;if(C[mid][2]<km)lo=mid;else hi=mid;}
 var a=C[lo],b=C[hi],u=Math.max(0,Math.min(1,(km-a[2])/((b[2]-a[2])||1)));return [a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u];}
var S=[];for(var k=0;k<L;k+=0.05){var q0=posAt(k);S.push([k,q0[0],q0[1]]);}var qe=posAt(L);S.push([L,qe[0],qe[1]]);
var COS=Math.cos(50.1*Math.PI/180);
function distM(a,b,c,d){return Math.hypot((a-c)*111195,(b-d)*111195*COS);}
function placeAt(km){var n=D.places[0][1];D.places.forEach(function(p){if(km>=p[0])n=p[1];});return n;}
function passesNear(lat,lon,r){var runs=[],best=null;
 S.forEach(function(p){var d=distM(p[1],p[2],lat,lon);if(d<r){if(!best||d<best.d)best={d:d,km:p[0]};}else if(best){runs.push(best);best=null;}});
 if(best)runs.push(best);var out=[];
 runs.forEach(function(x){var l=out[out.length-1];if(l&&x.km-l.km<1){if(x.d<l.d)out[out.length-1]=x;}else out.push(x);});
 return out.map(function(x){return x.km;});}
/* Karte */
var W=720,Hh=400,view='all',vc=null,allCam=null,cityCam=null,lat0=50.105,lon0=8.62;
function proj(lat,lon){return [(lon-lon0)*COS,-(lat-lat0)];}
function camFor(pts,px,pt,pb){var xs=[],ys=[];pts.forEach(function(c){var p=proj(c[0],c[1]);xs.push(p[0]);ys.push(p[1]);});
 var x0=Math.min.apply(0,xs),x1=Math.max.apply(0,xs),y0=Math.min.apply(0,ys),y1=Math.max.apply(0,ys);
 var s=Math.min((W-2*px)/(x1-x0),(Hh-pt-pb)/(y1-y0));return {x:(x0+x1)/2,y:(y0+y1)/2-(pt-pb)/2/s,s:s};}
function cams(){allCam=camFor(C.concat([[50.1080,8.5370],[50.0990,8.7000]]),14,14,14);
 cityCam=camFor(C.filter(function(c){return c[2]<13.9||c[2]>35.8;}),18,18,18);vc=view==='all'?allCam:cityCam;}
function P(lat,lon){var p=proj(lat,lon);return [W/2+(p[0]-vc.x)*vc.s,Hh/2+(p[1]-vc.y)*vc.s];}
function pathD(pts,close){return pts.map(function(p,i){var q=P(p[0],p[1]);return (i?'L':'M')+q[0].toFixed(1)+' '+q[1].toFixed(1);}).join('')+(close?'Z':'');}
function el(t,a,txt){var e=document.createElementNS(NS,t);for(var k in a)e.setAttribute(k,a[k]);if(txt!=null)e.textContent=txt;return e;}
var clip=el('clipPath',{id:'mForest'}),clipP=el('path',{});clip.appendChild(clipP);var defs=el('defs',{});defs.appendChild(clip);
var gLand=el('rect',{x:0,y:0,fill:'var(--map-land)'}),gForest=el('g',{'clip-path':'url(#mForest)',fill:'var(--map-green)'}),
 gParks=el('g',{fill:'var(--map-green)',stroke:'var(--map-green)','stroke-width':6,'stroke-linejoin':'round'}),
 gDist=el('g',{fill:'none',stroke:'var(--map-line)','stroke-width':1}),
 gRiver=el('path',{fill:'none',stroke:'var(--map-water)','stroke-linecap':'round','stroke-linejoin':'round'}),
 gRiverL=el('text',{'font-size':13,'font-style':'italic',fill:'var(--map-water-ink)','text-anchor':'middle','letter-spacing':'2'},'Main'),
 gLab=el('g',{'font-weight':600,fill:'var(--muted)','letter-spacing':'1.2','text-anchor':'middle'}),
 gRoute=el('path',{fill:'none',stroke:'var(--axis)','stroke-width':4,'stroke-linecap':'round','stroke-linejoin':'round'}),
 gDone=el('path',{fill:'none',stroke:'var(--pb)','stroke-width':5,'stroke-linecap':'round','stroke-linejoin':'round'}),
 gKm=el('g',{'font-size':11,fill:'var(--text)'}),gLm=el('g',{'font-size':12,fill:'var(--text)'}),gTap=el('g',{}),gRun=el('g',{});
var pulse=el('circle',{r:16,fill:'var(--pb)',opacity:.25,'class':'mpulse'}),dot=el('circle',{r:8,fill:'var(--pb)',stroke:'var(--card)','stroke-width':3});
gRun.appendChild(pulse);gRun.appendChild(dot);
[defs,gLand,gForest,gParks,gDist,gRiver,gRiverL,gLab,gRoute,gDone,gKm,gLm,gTap,gRun].forEach(function(g){svg.appendChild(g);});
if(pulse.animate)pulse.animate([{r:10,opacity:.45},{r:22,opacity:0}],{duration:1600,iterations:Infinity});
function vis(s){return s.indexOf(view==='all'?'a':'c')>=0;}
var curKm=0,tap=null;
function draw(){
 gLand.setAttribute('width',W);gLand.setAttribute('height',Hh);clipP.setAttribute('d',pathD(MAP.forest_edge,true));
 gForest.innerHTML='';gDist.innerHTML='';gParks.innerHTML='';gLab.innerHTML='';gKm.innerHTML='';gLm.innerHTML='';
 MAP.districts.forEach(function(d){d.rings.forEach(function(r){var pd=pathD(r,true);gDist.appendChild(el('path',{d:pd}));
  if(MAP.forest_districts.indexOf(d.name)>=0)gForest.appendChild(el('path',{d:pd}));});});
 MAP.parks.forEach(function(r){gParks.appendChild(el('path',{d:pathD(r,true)}));});
 gRiver.setAttribute('d',pathD(MAP.river));gRiver.setAttribute('stroke-width',Math.max(6,170*vc.s/111195));
 var rl=view==='all'?P(50.0888,8.6290):P(50.1035,8.6745);gRiverL.setAttribute('x',rl[0]);gRiverL.setAttribute('y',rl[1]+(view==='all'?16:20));
 gLab.setAttribute('font-size',W<520?10:12);
 MAP.labels.filter(function(l){return vis(l[3]);}).forEach(function(l){var q=P(l[1],l[2]);gLab.appendChild(el('text',{x:q[0],y:q[1]},l[0].toUpperCase()));});
 MAP.green_labels.filter(function(l){return vis(l[3]);}).forEach(function(l){var q=P(l[1],l[2]);
  gLab.appendChild(el('text',{x:q[0],y:q[1],fill:'var(--map-green-ink)','font-style':'italic','font-weight':500,'letter-spacing':'.5'},l[0]));});
 gRoute.setAttribute('d',pathD(S.map(function(s){return [s[1],s[2]];})));
 var kms=view==='all'?[5,10,15,20,25,30,35,40]:[2,4,5,6,7,8,9,10,11,12,13,38,39,40];
 kms.forEach(function(k){var p=posAt(k),q=P(p[0],p[1]);
  gKm.appendChild(el('circle',{cx:q[0],cy:q[1],r:3.5,fill:'var(--card)',stroke:'var(--text)','stroke-width':1.5}));
  gKm.appendChild(el('text',{x:q[0]+5,y:q[1]-5,'font-weight':700},String(k)));});
 MAP.landmarks.filter(function(l){return vis(l[3])&&!(W<520&&view==='all'&&l[0]!=='Bf. Höchst');}).forEach(function(l){var q=P(l[1],l[2]);
  gLm.appendChild(el('rect',{x:q[0]-3.5,y:q[1]-3.5,width:7,height:7,fill:'var(--text)',transform:'rotate(45 '+q[0]+' '+q[1]+')'}));
  gLm.appendChild(el('text',{x:q[0]+8,y:q[1]+4,stroke:'var(--map-land)','stroke-width':3.5,'stroke-linejoin':'round',fill:'none'},l[0]));
  gLm.appendChild(el('text',{x:q[0]+8,y:q[1]+4},l[0]));});
 drawTap();drawRun();}
function drawRun(){if(!vc)return;var done=[];S.forEach(function(s){if(s[0]<=curKm)done.push([s[1],s[2]]);});var p=posAt(curKm);done.push(p);
 gDone.setAttribute('d',done.length>1?pathD(done):'');var q=P(p[0],p[1]);
 dot.setAttribute('cx',q[0]);dot.setAttribute('cy',q[1]);pulse.setAttribute('cx',q[0]);pulse.setAttribute('cy',q[1]);}
function drawTap(){gTap.innerHTML='';if(!tap)return;var q=P(tap.lat,tap.lon);
 gTap.appendChild(el('circle',{cx:q[0],cy:q[1],r:12,fill:'none',stroke:'var(--text)','stroke-width':2,'stroke-dasharray':'3 3'}));}
function size(force){var w=Math.round(svg.getBoundingClientRect().width);if(!w)return;
 var nh=Math.round(w*(view==='all'?(w<520?0.8:0.56):(w<520?1.05:0.62)));
 if(force||w!==W||nh!==Hh||!vc){W=w;Hh=nh;svg.setAttribute('viewBox','0 0 '+W+' '+Hh);cams();draw();}}
document.querySelectorAll('.mseg button').forEach(function(b){b.addEventListener('click',function(){view=b.dataset.v;
 document.querySelectorAll('.mseg button').forEach(function(x){x.setAttribute('aria-pressed',x===b?'true':'false');});size(true);});});
if(window.ResizeObserver)new ResizeObserver(function(){size(false);}).observe(svg);else addEventListener('resize',function(){size(false);});
/* Uhr und Regler */
var sl=$('mSlider');
$('mTicks').innerHTML='';[0,60,120,180,240,300].forEach(function(m){var s=document.createElement('span');s.textContent=hhmm(T0+m);$('mTicks').appendChild(s);});
function update(){var clock=T0+(+sl.value),t=clock-ST;curKm=distAt(t);$('mTime').textContent=hhmm(clock);var place,meta;
 if(t<0){place='Wartet im '+D.block;meta='Start in ca. '+Math.ceil(-t)+' Min.';}
 else if(t>=TT){place='Im Ziel';meta='Endzeit '+durS(TT)+' · seit '+Math.round(t-TT)+' Min. im Ziel';}
 else{place=placeAt(curKm);meta='km '+kmS(curKm)+' · Laufzeit '+dur(t)+' · '+pace(curKm<=H?P1:P2)+' min/km';}
 if(tap&&tap.passes.length>1&&t>=0&&t<TT){var i=-1;tap.passes.forEach(function(k,j){if(Math.abs(k-curKm)<0.15)i=j;});
  if(i>=0)meta+=' · '+(i+1)+'. von '+tap.passes.length+' Durchgängen, außerdem '+tap.passes.filter(function(_,j){return j!==i;}).map(function(k){return hhmm(ST+elapsed(k));}).join(', ');}
 $('mPlace').textContent=place;$('mMeta').textContent=meta;drawRun();}
function setClock(m,keep){if(!keep){tap=null;drawTap();}else drawTap();sl.value=Math.max(0,Math.min(300,m-T0));update();}
sl.addEventListener('input',function(){stop();tap=null;drawTap();update();});
document.querySelectorAll('.mbtns [data-go]').forEach(function(b){b.addEventListener('click',function(){stop();var g=b.dataset.go;
 setClock(g==='start'?ST:g==='half'?ST+elapsed(H):ST+TT);});});
svg.addEventListener('click',function(ev){var r=svg.getBoundingClientRect(),x=(ev.clientX-r.left)*W/r.width,y=(ev.clientY-r.top)*Hh/r.height,best=null;
 S.forEach(function(s){var q=P(s[1],s[2]),d=Math.hypot(q[0]-x,q[1]-y);if(!best||d<best.d)best={d:d,s:s};});
 if(!best||best.d>28){tap=null;drawTap();return;}var ps=passesNear(best.s[1],best.s[2],90);if(!ps.length)return;
 var idx=-1;ps.forEach(function(k,j){if(idx<0&&k>curKm+0.3)idx=j;});if(idx<0)idx=0;
 tap={lat:best.s[1],lon:best.s[2],passes:ps};stop();setClock(ST+elapsed(ps[idx]),true);});
function berlinNow(){try{var f=new Intl.DateTimeFormat('de-DE',{timeZone:'Europe/Berlin',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).formatToParts(new Date());
 var g=function(k){return +f.filter(function(x){return x.type===k;})[0].value;};return {d:g('year')+'-'+pad(g('month'))+'-'+pad(g('day')),m:g('hour')*60+g('minute')};}catch(e){return null;}}
var live=null,nb=$('mNow');
nb.addEventListener('click',function(){stop();var n=berlinNow();
 if(n&&n.d===D.date){setClock(n.m);clearInterval(live);live=setInterval(function(){var k=berlinNow();if(k)setClock(k.m);},30000);nb.textContent='Live aktiv';}
 else{nb.textContent='Erst am Renntag live';setTimeout(function(){nb.textContent='Jetzt (am Renntag)';},2500);}});
var raf=null,last=0,pb=$('mPlay');
function icon(play){pb.firstChild.innerHTML=play?'<path d="M5 3l12 7-12 7z"/>':'<path d="M5 3h3.5v14H5zM11.5 3H15v14h-3.5z"/>';pb.setAttribute('aria-label',play?'Rennen abspielen':'Pause');}
function stop(){if(raf){cancelAnimationFrame(raf);raf=null;}icon(true);}
function step(ts){var dt=last?ts-last:16;last=ts;var end=Math.min(300,ST+TT-T0+8),v=+sl.value+dt/1000*16;
 if(v>=end){sl.value=end;update();stop();return;}sl.value=v;update();raf=requestAnimationFrame(step);}
pb.addEventListener('click',function(){if(raf){stop();return;}clearInterval(live);tap=null;drawTap();
 if(+sl.value>=ST+TT-T0)sl.value=Math.max(0,ST-T0-3);
 if(matchMedia('(prefers-reduced-motion: reduce)').matches){setClock(ST+TT);return;}
 last=0;icon(false);raf=requestAnimationFrame(step);});
/* Startzeit */
var si=$('mStart');
function setStart(m){m=Math.max(T0-10,Math.min(T0+60,m));var sh=m-ST;ST=m;si.value=hhmm(m);
 try{localStorage.setItem('mfp-start',hhmm(m));}catch(e){}
 $('mStartNote').textContent=m===DEF?'Geschätzt für '+D.block+'. Am Renntag auf die echte Startzeit stellen, dann verschiebt sich alles.':'Startzeit angepasst. Im Ziel um ca. '+hhmm(m+TT)+' Uhr.';
 sl.value=Math.max(0,Math.min(300,+sl.value+sh));update();}
si.addEventListener('change',function(){var m=parseHM(si.value);if(m==null){si.value=hhmm(ST);return;}setStart(m);});
$('mMinus').addEventListener('click',function(){setStart(ST-1);});
$('mPlus').addEventListener('click',function(){setStart(ST+1);});
$('mReset').addEventListener('click',function(){setStart(DEF);});
size(true);si.value=hhmm(ST);setClock(ST+elapsed(6.0));
var n=berlinNow();if(n&&n.d===D.date&&n.m>=T0&&n.m<=T0+300)nb.click();})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
