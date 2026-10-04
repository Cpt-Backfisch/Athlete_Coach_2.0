# CLAUDE.md – Einstieg für jede Claude-Sitzung

**Athlete Coach 2.0**: öffentliches Trainings-Dashboard für Sebastian (Triathlet, Frankfurt) aus seinen
Strava-Daten. Ein täglicher Claude-Task holt neue Aktivitäten über den Strava-Connector, ein Script
filtert sie ins Repo, ein zweites baut `index.html`, GitHub Pages veröffentlicht. Kein Server, keine
Datenbank, keine API-Schlüssel.

## Zuerst lesen (je nach Aufgabe)

| Aufgabe | Datei |
|---|---|
| Was ist der Stand, was kommt als Nächstes? | `docs/STATUS.md` – **immer zuerst** |
| Wie hängt alles zusammen, warum so? | `docs/ARCHITEKTUR.md` |
| Dashboard aktualisieren („aktualisier mein Dashboard", täglicher Task) | `docs/UPDATE.md` – genau befolgen |
| Seite/Diagramme ändern oder erweitern | `docs/DESIGN.md` + `scripts/build.py` |

## Struktur

```
CLAUDE.md               dieser Einstieg
index.html              GENERIERT von scripts/build.py – nie von Hand bearbeiten
.nojekyll               GitHub Pages liefert Dateien 1:1 aus
data/activities.json    gefilterte Aktivitäten (eine pro Zeile), öffentlich
scripts/ingest.py       Strava-Antwort(en) → data/activities.json (Datenschutz-Filter, Duplikate)
scripts/build.py        data/activities.json → index.html (alle Berechnungen, SVG-Diagramme)
docs/                   Doku (STATUS, ARCHITEKTUR, UPDATE, DESIGN)
```

Lokal testen: `python3 scripts/build.py` und `index.html` im Browser öffnen bzw. per Playwright
screenshotten (Chromium unter `/opt/pw-browsers/chromium`).

## Feste Regeln

1. **Öffentliches Repo.** Niemals Secrets, Tokens, Strava-IDs, Aktivitätsnamen, Orte, GPS-Daten
   oder sonstige persönliche Details committen. Neue Datenfelder nur über `KEEP` in `ingest.py`
   und nach Rücksprache mit Sebastian.
2. **Zahlen rechnet das Script**, nicht Claude. Keine Werte von Hand in HTML oder Daten schreiben.
3. **Keine Abhängigkeiten:** nur Python-Standardbibliothek; die Seite lädt nichts Externes.
4. **`index.html` nie direkt bearbeiten** – immer `scripts/build.py` ändern und neu bauen.
5. **Daten-Updates** (täglicher Task / manuell): direkt auf `main` pushen, ohne Rückfrage (so entschieden).
6. **Änderungen an Code/Design/Doku:** erst Screenshot (hell + dunkel, Handy- + Desktop-Breite) zeigen
   und Sebastians OK einholen, dann auf `main` pushen. Commits logisch trennen.
7. **Am Ende jeder Arbeitssitzung `docs/STATUS.md` aktualisieren** (Stand, nächste Schritte,
   Entscheidungen ins Log). Architektur-Änderungen zusätzlich in `docs/ARCHITEKTUR.md`.
8. Die alte App (Repo `athlete-coach`) ist **nicht** Teil dieses Projekts und wird nicht angefasst.

## Zusammenarbeit mit Sebastian

- Deutsch. Er ist kein Entwickler: jeden Schritt kurz erklären (was und wofür), ohne Fachjargon-Lawine.
- Schwächen und Risiken zuerst; Konfidenz angeben (hoch/moderat/niedrig), Annahmen offenlegen.
- Er entscheidet auf hoher Ebene (Inhalte, Aussehen, Kosten, Datenschutz); technische Details entscheidet Claude
  und begründet sie kurz.
- Kopierfähige Prompts/Befehle immer als ein zusammenhängender Block.
- Modellwahl: Opus für Grundsatz-/Architekturfragen, Sonnet für Umsetzung – bei Wechsel kurz Bescheid geben.
- Bei langen Sitzungen vorschlagen, in einem neuen Chat weiterzumachen (Kontext = diese Dateien).

## Hintergrund (nur bei Bedarf)

- Saison-Ziel: Frankfurt Marathon 25.10.2026, Ziel 3:50. Halbmarathon-Bestzeit 1:38:57 (03/2026).
- Strava-Connector-Tools (nur lesen): `list_activities`, `get_activity_streams`, `get_activity_performance`,
  `get_athlete_zones`, `get_athlete_profile`, `get_gear`, `get_training_plan` u. a.
  Ein **geplanter Task** hat Zugriff auf Connector und Repo (getestet 04.10.2026).
