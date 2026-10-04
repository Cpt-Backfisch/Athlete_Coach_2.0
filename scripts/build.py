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
    y-Achse: schneller = weiter oben."""
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
    y = lambda t: T + (t - lo) / (hi - lo) * ph          # schneller (kleiner) = oben

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
        return '<p class="sub">Noch keine Wettkämpfe eingetragen.</p>'
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
        blocks.append(f'<div class="disc"><div class="dh"><h3>{v["label"]}</h3>{badge}</div>'
                      f'{chart}<ul class="rl">{"".join(rows)}</ul></div>')
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
.disc{border-top:1px solid var(--border);padding-top:14px;margin-top:14px}
.disc:first-of-type{margin-top:4px}
.dh{display:flex;align-items:baseline;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:4px}
h3{font-size:15px;margin:0}
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
.pbx,.gx{display:inline-block;width:9px;height:9px;border-radius:50%;vertical-align:-1px;margin-left:4px}
.pbx{background:var(--pb)}.gx{border:2px dashed var(--pb)}
@media (max-width:480px){.rl li{grid-template-columns:1fr auto}.rl .rd{grid-column:1/-1}
 .rd em{display:inline;margin-left:8px}}
.tabs{position:sticky;top:0;z-index:5;display:flex;gap:4px;padding:4px;margin:0 0 16px;
 background:var(--card);border:1px solid var(--border);border-radius:12px}
.tabs a{flex:1;text-align:center;padding:8px 10px;border-radius:9px;font-size:14px;font-weight:600;
 color:var(--text-2);text-decoration:none;-webkit-tap-highlight-color:transparent}
.tabs a[aria-selected="true"]{background:var(--text);color:var(--bg)}
.js .panel{display:none}.js .panel.on{display:block}
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
</nav>

<div class="panel" id="p-training" data-panel="training">
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
</div>

<div class="panel" id="p-wettkaempfe" data-panel="wettkaempfe">
<section class="card">
 <h2>Wettkämpfe</h2>
 <p class="sub">Endzeiten je Disziplin – vergangene Rennen und geplante Starts</p>
 {{R_NEXT}}
 {{R_BLOCKS}}
 {{R_NOTE}}
</section>
</div>

<footer>Daten: Strava · aktualisiert {{BUILT}} Uhr</footer>
</main>
<div id="tip"></div>
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
