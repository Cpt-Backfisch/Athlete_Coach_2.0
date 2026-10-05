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
 --run:#2a78d6;--bike:#eb6834;--swim:#1baf7a;--hike:#eda100;--other:#e87ba4;--partner:#eb6834;--pb:#7d5bd9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
 --bg:#141413;--card:#1a1a19;--border:#2c2c2a;--text:#ffffff;--text-2:#c3c2b7;--muted:#8f8e86;
 --grid:#2a2a28;--axis:#4a4a46;
 --run:#3987e5;--bike:#d95926;--swim:#199e70;--hike:#c98500;--other:#d55181;--partner:#d95926;--pb:#a48bea}}
:root[data-theme="dark"]{color-scheme:dark;
 --bg:#141413;--card:#1a1a19;--border:#2c2c2a;--text:#ffffff;--text-2:#c3c2b7;--muted:#8f8e86;
 --grid:#2a2a28;--axis:#4a4a46;
 --run:#3987e5;--bike:#d95926;--swim:#199e70;--hike:#c98500;--other:#d55181;--partner:#d95926;--pb:#a48bea}
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
@media (max-width:480px){.mini em{font-size:11px}}
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
</body>
</html>
"""

if __name__ == "__main__":
    main()
