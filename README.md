# Athlete Coach 2.0

Persönliches Trainings-Dashboard (Triathlon / Laufen) auf Basis von Strava-Daten.

**Architektur (Stand 04.10.2026, in Planung)**

- Ein geplanter Claude-Task ruft täglich neue Aktivitäten über den Strava-Connector ab.
- Die Daten werden gefiltert (nur Zahlen, keine Orte/Namen) und in diesem Repo gespeichert.
- Ein Script baut daraus die Dashboard-Seite.
- GitHub Pages veröffentlicht die Seite unter einem öffentlichen Link.

Ausführlich: [docs/ARCHITEKTUR.md](docs/ARCHITEKTUR.md)
