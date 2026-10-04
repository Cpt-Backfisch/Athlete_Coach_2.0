# Athlete Coach 2.0 – Architektur

> Stand: 04.10.2026 · Status: **in Planung**, Grundsatzentscheidungen getroffen, noch nichts gebaut außer dieser Doku.
> Diese Datei ist die maßgebliche Beschreibung der Architektur. Bei Änderungen hier zuerst anpassen.

---

## 1. Auf einen Blick

Ein **Claude-Task** holt einmal täglich deine neuen Trainings aus **Strava**, speichert sie in diesem **GitHub-Repo**, ein **Script** baut daraus die Dashboard-Seite, und **GitHub Pages** stellt sie unter einem öffentlichen Link ins Netz. Du und deine Freunde öffnen denselben Link – ohne Login.

Es gibt **keinen eigenen Server, keine Datenbank, keine API-Schlüssel**. Laufende Kosten: 0 € (zusätzlich zu Claude Pro und Strava-Abo, die du ohnehin hast).

```mermaid
flowchart LR
    S["🏃 Strava<br/>(deine Aktivitäten)"]
    subgraph C["☁️ Claude (Pro-Abo)"]
        T["Geplanter Task<br/>täglich, automatisch"]
        CH["Chat<br/>manuell: 'aktualisier mein Dashboard'"]
    end
    subgraph G["🐙 GitHub – Repo Athlete_Coach_2.0 (öffentlich)"]
        D["data/activities.json<br/>(nur Zahlen)"]
        B["Build-Script"]
        W["Webseite<br/>(HTML)"]
    end
    P["🌐 GitHub Pages<br/>öffentlicher Link"]
    U["📱 Du & Freunde<br/>Browser, kein Login"]

    S -- "Strava-Connector<br/>(nur lesen)" --> T
    S -- "Strava-Connector" --> CH
    T -- "filtern + push" --> D
    CH -. "alternativ" .-> D
    D --> B --> W
    W -- "automatisch veröffentlicht" --> P
    P --> U
```

---

## 2. Welches Tool übernimmt was?

| Baustein | Aufgabe | Wer betreibt es |
|---|---|---|
| **Strava** | Quelle aller Trainingsdaten (Uhr → Strava wie bisher) | Strava (Abo nötig) |
| **Strava-Connector** | Gibt Claude Lesezugriff auf deine Strava-Daten. Kann nichts in Strava ändern. | Strava / Claude |
| **Claude-Task** („Routine") | Läuft nach Zeitplan in der Cloud: holt neue Aktivitäten, filtert sie, schreibt sie ins Repo, startet das Build-Script, pusht. Optional: kurzer Coach-Text. | Claude (Pro-Abo) |
| **Claude-Chat** | Dasselbe von Hand anstoßen; außerdem Coaching-Fragen und Weiterentwicklung der App | Claude |
| **GitHub-Repo** | Speichert Daten, Script und Webseite. Ist gleichzeitig das „Archiv" mit kompletter Änderungshistorie. | GitHub (kostenlos) |
| **Build-Script** | Rechnet aus `activities.json` die KPIs und erzeugt die HTML-Seite. Rechnet immer gleich – Claude rechnet die Zahlen **nicht** selbst. | liegt im Repo |
| **GitHub Pages** | Stellt die Webseite öffentlich ins Netz | GitHub (kostenlos) |

**Grundprinzip:** Claude ist nur der *Zulieferer* der Daten. Script, Daten und Seite funktionieren ohne Claude. Fällt Claude weg, kann man die Daten auch anders ins Repo bringen (siehe Abschnitt 7).

---

## 3. Informationsfluss Schritt für Schritt

1. **Du trainierst.** Die Aktivität landet wie gewohnt in Strava.
2. **Der Task startet** (geplant, z. B. täglich abends).
3. Er fragt über den Strava-Connector: *„Welche Aktivitäten gibt es seit dem letzten Lauf?"* – es werden nur **neue** geholt.
4. **Filter:** Pro Aktivität werden nur Zahlen gespeichert (Datum, Sportart, Distanz, Zeit, Höhenmeter, ggf. Puls). **Nicht** gespeichert: Ortsangaben, GPS-Strecken, Aktivitätsnamen, Beschreibungen. *(Genaue Feldliste wird mit den KPIs festgelegt.)*
5. Die neuen Einträge werden an `data/activities.json` angehängt.
6. Das **Build-Script** erzeugt die aktualisierte Webseite.
7. Der Task **committet und pusht** direkt auf `main`.
8. **GitHub Pages** veröffentlicht die neue Version automatisch (dauert meist 1–2 Minuten).
9. Wer den Link öffnet, sieht den neuen Stand.

---

## 4. Wie laufen Updates?

| Weg | Wann | Aufwand |
|---|---|---|
| **Automatisch** (Claude-Task) | nach Zeitplan, mind. 1× täglich (mehrmals möglich) | keiner |
| **Manuell im Chat** | jederzeit, z. B. direkt nach einem Wettkampf | ein Satz im Chat |

**Was passiert, wenn ein Lauf ausfällt?** (Connector antwortet nicht, Claude-Kontingent erschöpft, …) Nichts geht verloren: Der nächste Lauf holt alles seit dem **letzten erfolgreichen** Lauf nach. Die Seite ist dann nur einen Tag älter.

**Einen echten „Training fertig"-Auslöser gibt es nicht** – der Connector meldet sich nicht von selbst. Deshalb Zeitplan statt Echtzeit.

---

## 5. Wer hat welche Zugriffsrechte?

| Wer | Darf | Darf nicht |
|---|---|---|
| **Du** | alles (Repo, Task, Einstellungen) | – |
| **Claude-Task / Claude-Chat** | Strava **lesen**; nur **dieses eine Repo** lesen und beschreiben (über die Claude-GitHub-App, „Only select repositories") | Strava ändern; deine anderen Repos (z. B. die alte App) anfassen |
| **Freunde / alle Besucher** | Dashboard ansehen; Repo ansehen (ist öffentlich) | etwas ändern |

- Alles, was Claude ins Repo pusht, erscheint auf GitHub unter **deinem** Namen.
- Der Task läuft im Automatik-Modus, also **ohne Rückfragen**. Das ist gewollt.
- **Zugriff entziehen:** GitHub → Settings → Applications → Claude-App deinstallieren (GitHub) bzw. Strava-Connector in den Claude-Einstellungen trennen (Strava). Wirkt sofort.

**Wichtig – öffentlich heißt öffentlich:** Seite **und** Rohdaten im Repo sind für jeden einsehbar, der den Link kennt oder findet. Deshalb der Filter in Schritt 4.

---

## 6. Wie sehe ich das Dashboard? Wo liegt es? Wie sehen es Freunde?

- **Gehostet:** bei GitHub Pages, kostenlos.
- **Adresse (geplant):** `https://cpt-backfisch.github.io/Athlete_Coach_2.0/` – wird aktiv, sobald GitHub Pages eingeschaltet und die erste Seite gebaut ist.
- **Du:** Link im Browser öffnen. Tipp fürs iPhone: in Safari „Zum Home-Bildschirm" → wirkt wie eine App.
- **Freunde:** Du schickst ihnen den Link (z. B. per WhatsApp). Kein Konto, kein Login, keine App nötig.
- **Coaching-Fragen** („Wie war mein langer Lauf?", „Bin ich auf Kurs?") stellst du weiterhin direkt im Claude-Chat – dort hat Claude über den Connector Zugriff auf alle Details.

---

## 7. Abhängigkeiten & Ausfallszenarien

| Fällt weg | Folge | Ausweg |
|---|---|---|
| **Claude Pro** | Kein Task, kein Push aus Claude | Im kostenlosen Chat Daten abrufen lassen (Connector sollte verfügbar sein, nicht geprüft), Datei herunterladen und selbst ins Repo hochladen |
| **Strava-Abo** | Kein Connector | Strava-Datenexport (CSV) manuell ins Repo |
| **GitHub-Verbindung** läuft ab | Task überspringt Läufe bis zu 72 h, danach schaltet er sich ab | Neu verbinden, Task wieder einschalten |
| **Strava-Connector** wird geändert/eingestellt | Kein automatischer Abruf | Strava-API als Datenquelle nachrüsten (alte App hat Client-ID) |

Weil Daten, Script und Seite unabhängig von Claude sind, muss im Ernstfall nur der **Zulieferer** getauscht werden – nie die ganze App.

---

## 8. Kosten

| Dienst | Kosten |
|---|---|
| Claude Pro | bestehendes Abo; Task-Läufe zählen gegen das normale Nutzungskontingent (Lauf ≈ 1 Minute) |
| Strava | bestehendes Abo |
| GitHub + GitHub Pages | 0 € |
| **Zusätzlich** | **0 €** |

---

## 9. Entscheidungen & offene Punkte

**Entschieden**
- Datenquelle: Claude-Task über Strava-Connector, **keine** Strava-API
- Hosting: GitHub Pages, öffentlich, ohne Login – eine Seite für dich und Freunde
- Repo öffentlich, Rohdaten öffentlich (gefiltert) – akzeptiert
- Task pusht ohne Rückfrage direkt auf `main`
- Update mindestens 1× täglich, manuell jederzeit im Chat
- Kein GitHub-Actions-Workflow nötig (Pages liefert direkt aus dem Repo aus)

**Getestet**
- ✅ Geplanter Task kann Strava-Daten abrufen (04.10.2026, ohne Rückfragen)
- ✅ Push auf `main` aus einer Claude-Sitzung (04.10.2026)
- ⏳ Push auf `main` aus einem *geplanten* Task (Test läuft)

**Offen**
- Welche KPIs und Diagramme? → bestimmt auch die genaue Feldliste im Filter
- Coach-Text auf der Seite: ja/nein
- Strava-Nutzungsbedingungen: Ist die öffentliche Anzeige (aggregierter) Connector-Daten erlaubt? → vor Go-live prüfen
- Genaue Uhrzeit(en) des täglichen Tasks
- Ordnerstruktur und Technik der Seite (bewusst einfach halten)
