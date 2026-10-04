# Design-Regeln

Kurz und verbindlich. Neue Diagramme und Seitenteile folgen diesen Regeln, damit die Seite
einheitlich bleibt. Abweichungen nur nach Absprache mit Sebastian – dann hier nachtragen.

## Grundlagen

- **Mobile first:** primär iPhone/Safari, muss aber auch am Laptop gut aussehen. Jede Änderung in
  ~390 px **und** ~800 px Breite prüfen (Screenshot), jeweils hell **und** dunkel.
- **Hell/Dunkel** folgt der Systemeinstellung (`prefers-color-scheme`). Farben nur über die
  CSS-Variablen in `scripts/build.py` (`--bg`, `--card`, `--text`, `--run` …), nie Hex-Werte direkt im Markup.
- **Keine externen Ressourcen:** keine CDNs, Webfonts, Tracking, Bibliotheken. Systemschrift.
- **Marke:** Schriftzug „athlete**.**coach" mit Purple-Punkt `#8E6FE0` (aus der alten App übernommen).
- Zahlen mit `font-variant-numeric: tabular-nums`, deutsches Format (Komma, `03.10.2026`).

## Sportarten-Farben (validiert)

Feste Reihenfolge = Stapelreihenfolge. Die Palette ist auf Farbsehschwäche-Abstand geprüft;
**nicht umsortieren, keine Farben tauschen** ohne erneute Prüfung.

| Kategorie | Hell | Dunkel | Strava `sport_type` |
|---|---|---|---|
| Laufen | `#2a78d6` | `#3987e5` | Run, TrailRun, VirtualRun |
| Rad | `#eb6834` | `#d95926` | Ride, VirtualRide, GravelRide, MountainBikeRide, E(Mountain)BikeRide … |
| Schwimmen | `#1baf7a` | `#199e70` | Swim |
| Wandern & Gehen | `#eda100` | `#c98500` | Hike, Walk |
| Sonstiges | `#e87ba4` | `#d55181` | alles andere (Workout, Squash, …) |

Die Zuordnung steht im Code in `CATEGORIES` (`scripts/build.py`).

**Personen statt Sportarten** (Challenge-Grafik): Ich = `--run` (Blau), Partner = `--partner`
(gleiche Werte wie Rad-Orange – das validierte Blau/Orange-Paar), Soll = `--muted`, gestrichelt.

## Diagramme

- Dünne Balken, oben 4 px abgerundet, 2 px Abstand zwischen gestapelten Segmenten.
- Immer eine **Legende** (ab 2 Serien) und eine **Tabellen-Ansicht** („Als Tabelle anzeigen") –
  drei der hellen Farben haben wenig Kontrast zum Hintergrund, die Tabelle gleicht das aus.
- **Tooltip** beim Antippen/Überfahren eines Segments (`data-tip`-Attribut).
- Eine y-Achse pro Diagramm, nie zwei Skalen in einem Diagramm.
- Text (Werte, Achsen) in Textfarben, nie in der Serienfarbe.
- **Liniendiagramme:** 2 px Linien, Endpunkt als Punkt mit Ring in Kartenfarbe, Wert direkt rechts daneben
  beschriftet. Statt Einzel-Tooltips ein **Fadenkreuz** (`.xhit`/`.xh`), das alle Werte des Tages zeigt.
- Schmale Bildschirme bekommen eine eigene SVG-Variante (`cls="narrow"`), damit die Schrift lesbar bleibt.

## Wettkämpfe (Karte „Wettkämpfe")

- Eine Zeile pro Disziplin (Reihenfolge `DISCIPLINES` in `build.py`), nur Disziplinen mit Einträgen.
- **Bestzeit** in `--pb` (Lila, hell `#7d5bd9` / dunkel `#a48bea`, aus der Markenfarbe abgeleitet) –
  einzige Akzentfarbe der Karte, damit die PB sofort ins Auge fällt. Übrige Ergebnisse neutral (`--text-2`).
- Zeitstrahl je Disziplin (eigene Jahresachse je Disziplin, schneller = oben), nur ab 2 Zeitpunkten.
  Zielzeit = gestrichelter Ring + gestrichelte Linie vom letzten Ergebnis. „heute" als gepunktete Linie.
- Liste darunter: geplante Starts zuerst (mit Countdown in Wochen), dann Ergebnisse neueste zuerst mit Abstand zur PB.

## Navigation (Tabs)

- Eine Seite, oben ein klebender Umschalter mit Tabs („Training", „Wettkämpfe"). Aktiver Tab = gefüllt
  in `--text`. Neue Bereiche bekommen einen eigenen Tab statt die Seite zu verlängern (max. ~4 Tabs fürs Handy).
- Jeder Tab ist per Anker verlinkbar (`#training`, `#wettkaempfe`). Ohne JavaScript sind alle Bereiche untereinander sichtbar.
