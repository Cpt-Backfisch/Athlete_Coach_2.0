# Dashboard-Update – Anleitung (Runbook)

Diese Anleitung befolgt der **tägliche Claude-Task** (21:59 Uhr) und jede Chat-Sitzung,
die „aktualisier mein Dashboard" ausführen soll. Der Task-Prompt verweist nur hierher –
**Ablauf ändern = diese Datei ändern**, nicht die Task-Einstellungen.

Ziel: neue Strava-Aktivitäten ins Repo übernehmen, Seite neu bauen, direkt auf `main` pushen.
Keine Rückfragen stellen – der Lauf ist unbeaufsichtigt.

## Schritte

1. **Repo bereitstellen**
   - Das Repo `Cpt-Backfisch/Athlete_Coach_2.0` ist in der Sitzung normalerweise schon geklont.
     Falls nicht: `add_repo` (owner `Cpt-Backfisch`, repo `Athlete_Coach_2.0`, access `push`) und wie beschrieben klonen.
   - Im Repo-Ordner: `git checkout main && git pull origin main`

2. **Startdatum bestimmen**
   ```bash
   python3 -c "import json,datetime as d;a=json.load(open('data/activities.json'))['activities'];print((d.date.fromisoformat(a[-1]['start_local'][:10])-d.timedelta(days=14)).isoformat()+'T00:00:00' if a else '2026-01-01T00:00:00')"
   ```
   (= 14 Tage vor der neuesten gespeicherten Aktivität; fängt nachträgliche Uploads ab.)

3. **Strava abfragen**
   - Strava-Tools per ToolSearch laden (Suche „strava"). Meldet der Server „noch verbindend", ~10 s warten und erneut versuchen (max. 3 Versuche).
   - `mcp__Strava__list_activities` mit `range_start` = Startdatum aus Schritt 2, `ordering` = `StartDateLocalAsc`, `first` = 100.
   - Solange `has_next_page` true ist: erneut mit `after` = `end_cursor`.

4. **Antworten unverändert speichern**
   - Jede Antwort **unverändert** als JSON-Datei ablegen: `/tmp/strava_1.json`, `/tmp/strava_2.json`, …
   - Nichts weglassen, umrechnen oder „aufräumen" – das Filtern macht das Script.

5. **Übernehmen und bauen**
   ```bash
   python3 scripts/ingest.py /tmp/strava_*.json
   python3 scripts/build.py
   ```
   Beide geben eine kurze Zusammenfassung aus (z. B. `ingest: 1 neu, 0 aktualisiert, 131 gesamt`).

6. **Prüfen vor dem Commit**
   - `git diff --stat` darf nur `data/activities.json` und `index.html` betreffen.
   - In `data/activities.json` dürfen **keine** Namen, Orte, IDs oder sonstigen Felder außer den sechs erlaubten stehen
     (`start_local, sport_type, distance_m, moving_time_s, elapsed_time_s, elevation_gain_m`).

7. **Committen und pushen – direkt auf `main`, kein Branch, kein Pull Request**
   ```bash
   git add data/activities.json index.html
   git commit -m "Update <JJJJ-MM-TT>: <Ausgabe von ingest>"
   git push origin main
   ```
   Wird der Push abgelehnt: `git pull --rebase origin main`, dann einmal erneut pushen.

## Regeln

- **Nur Daten aktualisieren.** In einem Update-Lauf keine Scripts, Doku oder das Design ändern.
- **Zahlen nie selbst rechnen oder abtippen** – alles kommt aus `ingest.py` / `build.py`.
- **Bei Fehlern nichts Halbfertiges committen.** Stattdessen kurz berichten (SendUserMessage), was fehlschlug,
  mit exakter Fehlermeldung. Der nächste Lauf holt verpasste Tage automatisch nach.
- Keine neuen Aktivitäten ist **kein** Fehler: trotzdem bauen und committen (der Zeitstempel zeigt, dass der Lauf lief).
