# Athlete Coach 2.0

Persönliches Trainings-Dashboard (Triathlon / Laufen) auf Basis von Strava-Daten.

**Dashboard:** https://cpt-backfisch.github.io/Athlete_Coach_2.0/

- Ein geplanter Claude-Task ruft täglich (ca. 22 Uhr) neue Aktivitäten über den Strava-Connector ab.
- `scripts/ingest.py` filtert sie (nur Zahlen, keine Orte/Namen/IDs) nach `data/activities.json`.
- `scripts/build.py` baut daraus `index.html`.
- GitHub Pages veröffentlicht die Seite unter einem öffentlichen Link.

| Doku | Inhalt |
|---|---|
| [docs/STATUS.md](docs/STATUS.md) | aktueller Stand, nächste Schritte, Entscheidungen |
| [docs/ARCHITEKTUR.md](docs/ARCHITEKTUR.md) | Aufbau, Datenfluss, Zugriffsrechte, Hosting |
| [docs/UPDATE.md](docs/UPDATE.md) | Ablauf des täglichen Updates |
| [docs/DESIGN.md](docs/DESIGN.md) | Gestaltungsregeln, Farben |
| [CLAUDE.md](CLAUDE.md) | Einstieg für Claude-Sitzungen |
