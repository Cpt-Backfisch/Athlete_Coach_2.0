# 1000-km-Challenge – Nicos Stand eintragen

Sebastian und Nico (sein Chef) wollen 2026 je 1000 km laufen. Sebastians km kommen automatisch aus
Strava. Nicos km kann der Connector nicht lesen – sie werden **von Hand** gepflegt.

**Auslöser im Chat**, z. B.: „Nico steht am 12.10. bei 715 km"

## Ablauf

1. Repo auf aktuellem Stand: `git checkout main && git pull origin main`
2. In `data/challenge.json` unter `partner.entries` einen Eintrag anhängen, chronologisch sortiert:
   `{"date": "2026-10-12", "km_total": 715}`
   - `km_total` = **Jahressumme** bis zu diesem Tag (nicht die km seit dem letzten Eintrag).
   - Gleiches Datum schon vorhanden → Wert ersetzen statt doppelt eintragen.
   - Wert kleiner als der vorige Eintrag → kurz bei Sebastian nachfragen (Tippfehler?).
3. `python3 scripts/build.py`
4. `git diff --stat` darf nur `data/challenge.json` und `index.html` zeigen.
5. Committen und direkt auf `main` pushen (Daten-Update, keine Rückfrage nötig):
   `git commit -am "Challenge: Nico <Datum> <km> km" && git push origin main`

## Regeln

- Was zählt: Laufen (Run, Trail Run, Laufband). Gehen/Wandern zählt nicht – gilt für beide.
- Nur Datum + km speichern, keine weiteren Angaben zu Nico (öffentliches Repo).
- Neues Jahr: `year` und ggf. `goal_km` anpassen, `entries` leeren.
