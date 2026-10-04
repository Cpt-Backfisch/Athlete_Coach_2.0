#!/usr/bin/env python3
"""Neue Strava-Aktivitäten in data/activities.json übernehmen.

Eingabe: eine oder mehrere JSON-Dateien mit der Antwort von
mcp__Strava__list_activities (Objekt mit "activities"-Liste) oder direkt eine
Liste von Aktivitäten im selben Format.

    python3 scripts/ingest.py /tmp/strava_page1.json [/tmp/strava_page2.json ...]

Datenschutz-Filter (öffentliches Repo!): Es werden NUR die Felder in KEEP
gespeichert. Strava-ID, Name, Beschreibung, Ort, GPS, Kudos usw. werden
verworfen. Schlüssel zur Duplikat-Erkennung ist die lokale Startzeit.

Nur Python-Standardbibliothek, keine Abhängigkeiten.
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "activities.json"

# Feld im Repo  <-  Pfad in der Strava-Antwort
KEEP = {
    "distance_m": "distance",
    "moving_time_s": "moving_time",
    "elapsed_time_s": "elapsed_time",
    "elevation_gain_m": "elevation_gain",
}


def clean(raw: dict) -> dict:
    s = raw.get("summary", {})
    out = {
        "start_local": raw["start_local"],
        "sport_type": raw["sport_type"],
    }
    for key, src in KEEP.items():
        v = s.get(src)
        if v is None:
            out[key] = None
        elif key.endswith("_s"):
            out[key] = int(round(float(v)))
        else:
            out[key] = round(float(v), 1)
    return out


def load_raw(path: str) -> list:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    return obj["activities"] if isinstance(obj, dict) else obj


def main(paths: list) -> None:
    store = {"updated_at": None, "activities": []}
    if DATA.exists():
        store = json.loads(DATA.read_text(encoding="utf-8"))
    by_key = {a["start_local"]: a for a in store["activities"]}

    added = updated = 0
    for p in paths:
        for raw in load_raw(p):
            a = clean(raw)
            old = by_key.get(a["start_local"])
            if old is None:
                added += 1
            elif old != a:
                updated += 1
            by_key[a["start_local"]] = a

    store["activities"] = sorted(by_key.values(), key=lambda a: a["start_local"])
    store["updated_at"] = datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec="seconds")
    DATA.parent.mkdir(exist_ok=True)
    # Eine Aktivität pro Zeile: kompakt und gut lesbare Git-Diffs
    lines = ",\n  ".join(json.dumps(a, ensure_ascii=False) for a in store["activities"])
    DATA.write_text(
        '{\n "updated_at": %s,\n "activities": [\n  %s\n ]\n}\n'
        % (json.dumps(store["updated_at"]), lines),
        encoding="utf-8",
    )
    print(f"ingest: {added} neu, {updated} aktualisiert, {len(store['activities'])} gesamt")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
