# Status & nächste Schritte

> Zuletzt aktualisiert: 04.10.2026. Diese Datei am Ende jeder Arbeitssitzung aktualisieren
> (was erledigt wurde, was als Nächstes kommt, neue Entscheidungen).

## Aktueller Stand

- ✅ Architektur entschieden und getestet → [`ARCHITEKTUR.md`](ARCHITEKTUR.md)
- ✅ Daten 2026 importiert: 130 Aktivitäten (01.01.–03.10.2026) in `data/activities.json`
- ✅ `scripts/ingest.py` (Datenschutz-Filter) und `scripts/build.py` (Seite bauen)
- ✅ Erste Seite: KPI-Kacheln + **Testgrafik** „Trainingsstunden pro Monat 2026 nach Sportart"
- ✅ **1000-km-Challenge 2026** mit Nico (Chef): kumulierte Lauf-km, lineare Soll-Linie, Nicos Linie,
  Stand/Soll/Differenz und nötige km pro Woche. Nicos Stände pflegt Sebastian per Chat → [`CHALLENGE.md`](CHALLENGE.md)
- ✅ **„Diese Woche"** im Tab Training (über der Monatsgrafik): Wochensummen mit Vorwochenvergleich und
  aufklappbare Liste aller Einheiten. Offen: mehr Details (Puls/Watt/Kadenz) bräuchten neue Felder in `KEEP` → erst nach Sebastians OK
- ✅ **Menü-Tabs** „Training", „Wettkämpfe", „Challenges" (eine Seite, Umschalten per Tab, Link-Anker `#training`, `#wettkaempfe`, `#challenges`)
- ✅ **Wettkämpfe-Tab**: alle Rennen seit 2015 und geplante Starts je Disziplin, Bestzeit hervorgehoben, Countdown in Wochen.
  Daten in `data/races.json` (offizielle Zeiten aus dem Athletenprofil; nur Eschborn–Frankfurt 2026 laut Uhr)
- ⏳ Ersten Stand von Nico eintragen (bisher keine Daten → seine Linie ist noch ausgeblendet)
- ✅ Täglicher Task „athlete.coach Dashboard-Update", 21:59 Uhr, folgt [`UPDATE.md`](UPDATE.md)
- ⏳ **GitHub Pages einschalten** (Sebastian, einmalig): Repo → Settings → Pages → Source *Deploy from a branch* → Branch `main`, Ordner `/ (root)` → Save.
  Danach erreichbar unter `https://cpt-backfisch.github.io/Athlete_Coach_2.0/`
- ⏳ Ersten automatischen Lauf (heute 21:59) am nächsten Tag prüfen: neuer Commit „Update …" von Claude im Repo?

## Nächste Schritte (Vorschlag, Reihenfolge offen)

1. **KPIs & Inhalte festlegen** – was soll die Seite zeigen? Ideen aus der alten App:
   Wochenumfang/Wochenziel, Sportverteilung, Jahresvergleich (benötigt Daten 2024/2025 → Backfill),
   Countdown zum nächsten Wettkampf, Lauf-km kumuliert, Verlauf langer Läufe.
2. **Coach-Text** oben auf der Seite: ja/nein? (Der Task könnte 2–3 Sätze schreiben; wäre der einzige
   Teil, den Claude statt des Scripts erzeugt – Regeln dafür vorher festlegen.)
3. **Wettkämpfe:** nach jedem Rennen Ergebnis in `data/races.json` (und im Athletenprofil) eintragen.
   Nächstes Rennen: Frankfurt Marathon 25.10.2026, Ziel unter 3:37:34. Zielzeiten Kraichgau/Ironman bewusst offen.
4. **Historische Daten** 2024/2025 nachladen (einmaliger Backfill über den Connector, gleicher Ablauf wie UPDATE.md mit früherem Startdatum).
5. Optional: Icon/Logo für „Zum Home-Bildschirm".

## Bekannte Einschränkungen

- Gelöschte Strava-Aktivitäten werden nicht automatisch entfernt (nur Hinzufügen/Aktualisieren).
- Kein Echtzeit-Update: Seite ist max. ~1 Tag alt (oder manuell im Chat aktualisieren).
- Indoor-Radfahrten haben in Strava oft Distanz 0 – für Stunden egal, für km-Auswertungen beachten.

## Entscheidungs-Log

| Datum | Entscheidung |
|---|---|
| 04.10.2026 | Neuaufbau als „App 2.0" in neuem Repo; alte App (`athlete-coach`) bleibt unangetastet |
| 04.10.2026 | Datenquelle Strava-Connector via Claude-Task, keine Strava-API, kein Server, keine DB |
| 04.10.2026 | Hosting GitHub Pages, öffentlich ohne Login; Repo inkl. gefilterter Rohdaten öffentlich |
| 04.10.2026 | Öffentliche Anzeige der Strava-Daten von Sebastian geprüft und freigegeben |
| 04.10.2026 | Task täglich 21:59 Uhr, pusht ohne Rückfrage direkt auf `main` |
| 04.10.2026 | Python-Standardbibliothek only; statisches HTML ohne externe Ressourcen |
| 04.10.2026 | 1000-km-Challenge: zählt Run, TrailRun, VirtualRun (Laufband); nicht Gehen/Wandern |
| 04.10.2026 | Nico mit Namen und km öffentlich auf der Seite – mit Nico abgestimmt |
| 04.10.2026 | Athletenprofil aus der Claude-App als `docs/ATHLETENPROFIL.md` ins Repo übernommen (ohne Marathon-Trainingsplan) |
| 04.10.2026 | Wettkämpfe in `data/races.json` von Hand gepflegt (Strava markiert Rennen nicht verlässlich). Rennnamen öffentlich; Patrick-Vergleich nicht auf der Seite. Marathon 2015 bleibt drin |
| 04.10.2026 | Athletenprofil (`docs/ATHLETENPROFIL.md`) darf im öffentlichen Repo liegen – von Sebastian bestätigt |
| 04.10.2026 | Seite in Tabs „Training" / „Wettkämpfe" / „Challenges" aufgeteilt, damit man nicht ewig scrollt; 1000-km-Challenge liegt unter „Challenges" |
| 04.10.2026 | „Diese Woche": Woche Mo–So zum Build-Datum; Details nur aus vorhandenen Feldern (keine neuen Strava-Felder) |
| 04.10.2026 | Nicos Daten manuell (`data/challenge.json`), weil der Strava-Connector nur Sebastians Konto liest |
