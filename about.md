# Über dieses Projekt

Dies ist eine Trainings-App für Sanitäter:innen in Ausbildung (DRK): Fallbeispiele nach dem xABCDE-Schema durchspielen, mit
Fokus auf die **1. Minute nach DRK-SANmemo** – Lage, bedrohliche Blutung, Ansprechen, Schnellcheck, Teambesprechung,
Funkspruch. Man spricht (Web Speech API) oder tippt; die App antwortet als Patient:in, Kollege, Umstehende,
Leitstelle, AED und Rettungsdienst. Am Ende gibt es eine Auswertung. Modus „Ganzer Fall“ geht über die 1. Minute
hinaus bis zum vollständigen ABCDE, zur Reevaluation und zur Übergabe.

Stand: November 2026. Hauptbranch `main` (Gastmodus ist gemergt, PR #2); aktuelle Arbeit auf `feat/reverse-proxy-port` (Caddy raus, APP_PORT) und `feat/smalltalk-tips`.

## Wie es funktioniert

```
Browser (public/)  ── Protokoll [{t, text}] bei jeder Äußerung ──▶  FastAPI (backend/)
                   ◀── Antwortzeilen + next_event_at ──────────────   classifier → engine → evaluate
                                                                       Inhalte: content/*.yaml
```

- **Keine KI, keine Anmeldung, keine Datenhaltung.** Alles läuft deterministisch auf dem eigenen Server.
  Das einzige Modell ist ein kleines Satz-Embedding-Modell (`paraphrase-multilingual-MiniLM-L12-v2`, lokal über
  transformers) für die Intent-Erkennung.
- **Zustandslos:** Der Browser schickt bei jeder Äußerung das ganze Protokoll mit Nettozeit; der Server spielt es
  deterministisch nach (`engine.replay`). Dieselbe Wiederholung ist die Grundlage der Auswertung.
- **Nettozeit:** Die Zeit, in der die App antwortet oder vorliest, zählt nicht mit.
- **Takte:** Der Server meldet `next_event_at`; ist die Zeit erreicht, schickt der Browser einen Eintrag ohne Text
  (`tick: true`). So passieren Dinge auch, wenn niemand spricht (Patient kühlt aus, AED analysiert alle 2 Minuten).
- **Verborgene Fakten bleiben auf dem Server.** `/api/scenarios` liefert nur Titel, Teaser, Einsatzmeldung.

### Intent-Erkennung (`backend/classifier.py`, `content/intents.yaml`)

Eine Äußerung wird auf einen oder mehrere **Intents** abgebildet (rund 85, z. B. `puls`, `decke`, `rueckenschlaege`,
`hlw_30`). Reihenfolge der Positionen im Satz = Reihenfolge der Antworten.

1. **Regex-Muster** zuerst (präzise, auf kleingeschriebenem Text, ß → ss). Muster nie `.lower()`en – das machte aus
   `\W` ein `\w` (war ein echter Bug).
2. **Embeddings** nur für Teilsätze ohne Regex-Treffer, gegen die `examples` der Intents. Ein Treffer zählt nur bei
   Ähnlichkeit ≥ 0,72 **und** ≥ 0,05 Abstand zum zweitbesten Intent. Die Gruppe `smalltalk` („Okay“, „Moment“ …)
   konkurriert mit, wird aber nie selbst Treffer. Kurze Wortfenster sind aus (zu viele Fehltreffer).
3. `implies` / `overrides` / `exclusive` (nur bei Regex-Treffern) bereinigen das Ergebnis.

Leitlinie: **Lieber nachfragen als raten.** Wird nichts erkannt, fragt der Kollege nach („Was genau machst du?“, weitere
Varianten reihum). Davor greift `content/smalltalk.yaml`: kurze, mit `^…$` verankerte Sätze ohne Handlung („Danke“,
„Moment“, „Mist“, „Was soll ich machen?“, „Wie bitte?“ → wiederholt die letzte Antwort) bekommen eine passende Antwort
– ohne Intent, also ohne Einfluss auf die Auswertung. Mitgefühl an den Patienten („Oh, das ist ja unglücklich“,
„Das tut mir leid“) beantwortet der Patient selbst (bewusstlos: „keine Reaktion“), der Kollege bleibt still. Als
Beruhigen zählt es erst mit Ausblick („… wir kümmern uns jetzt um Sie“).

**Tipps auf Nachfrage** („Hast du einen Tipp?“, „Was fehlt noch?“, „Was soll ich machen?“): Der Kollege nennt den
ersten offenen Punkt der Checkliste (1. Minute, im ganzen Fall danach xABCDE) mit dem `tip`-Text aus
`content/algorithm.yaml`. Abschaltbar in den Einstellungen (Prüfungssituation). In der Auswertung steht am Punkt
„erst nach Tipp vom Kollegen“ und unter „Verbessern“; das Urteil ändert sich nicht. Tipps verraten keine
verborgenen Befunde (z. B. gleicher Tipp für Seitenlage und HLW).

### Antworten (`backend/engine.py`, `content/scenarios/*.yaml`)

Jeder Fall ist ein kleines Expertensystem: Intent → Antwortvarianten mit Bedingungen (`when`), Flags (`set`),
zeitgesteuerte `events` (`at`, `since`, `repeat`). Jeder erkannte Intent ist automatisch ein Flag.

Antwortsuche je Intent, in dieser Reihenfolge:

1. Antwort des Falls
2. bei Bewusstlosen die allgemeine `unconscious`-Antwort des Intents („(keine Reaktion)“, „nichts in den Mund“)
3. Antwort des Falls auf einen `fallback`-Intent („Atmung?“ beim Bewusstlosen → Atemkontrolle)
4. `default` des Intents
5. sonst fragt der Kollege nach – **niemals einen Befund erfinden** (früher kam pauschal „Dabei fällt nichts
   Besonderes auf“; ein Test prüft jetzt jede Kombination aus Fall × Intent).

Funkverkehr mit der Leitstelle (Anruf, Meldung, „… Ende“) und das Eintreffen des Rettungsdienstes ~8 Minuten nach
der Nachforderung übernimmt die Engine selbst. Rufnamen sind in den Einstellungen änderbar.

### Auswertung (`backend/evaluate.py`, `content/algorithm.yaml`)

- **Checkliste 1. Minute** (wach oder bewusstlos) und im ganzen Fall zusätzlich **xABCDE** inkl. SAMPLER,
  Reevaluation, Übergabe. Status ✅ / ⚠️ / ❌ / – (nicht relevant, z. B. `skip: [waerme]`).
- **Reihenfolge:** tatsächliche Abfolge; was nicht in die längste korrekt geordnete Folge passt, kam „außer der Reihe“.
- **Schlüsselmaßnahmen je Fall** mit `critical`, `within`, `before`, `after` und `phase` (`full` = nur im ganzen Fall).
- **Funkspruch:** beide Rufnamen, auf „Hier …“ gewartet, Patient (Geschlecht, ungefähres Alter), Verdacht,
  passende Nachforderung, „kommen“, „… Ende“.
- **Warnzeichen:** Wurde auf ein Ereignis (z. B. „Mir wird kalt“) rechtzeitig reagiert? Zählt nicht ins Urteil,
  steht aber oben bei „Verbessern“.
- **Befundsprache:** Mitgeteilte Befunde nur als „normal/ok/passt“ werden angemerkt (Regex + Embeddings mit
  maskiertem Themenwort).
- **„Worauf es in diesem Fall ankommt“** (`debrief_notes`) erscheint nach der Auswertung, nie vorher.

## Fachliche Regeln aus der Praxis

Diese Punkte kamen aus Rückmeldungen einer erfahrenen Sanitäterin und sind in Inhalten und Tests verankert.
Bitte nicht „wegoptimieren“ – im Zweifel nachfragen.

**Allgemein**

- **Befunde konkret benennen**, nicht „normal“: „Puls regelmäßig, gut/schlecht/nicht tastbar“, „Puls schnell“,
  „Rekap unter 2 s“ / „Rekap verzögert“. Die Fälle selbst formulieren ihre Befunde genauso.
- **Fragen sind keine Befunde:** „Puls?“, „Rekap?“ fragen Werte ab – das ist richtig und wird nicht angemerkt.
  „Normale Atmung“ bei der Atemkontrolle Bewusstloser ist der Begriff des Algorithmus und auch in Ordnung.
- **Atmung beurteilen ≠ Patienten fragen:** „Atmung?“ liefert einen Befund (Frequenz, Atemarbeit, Geräusche);
  „Bekommen Sie gut Luft?“ beantwortet der Patient.
- **Alter:** ungefähr reicht („älterer Mann“, „Mitte vierzig“); die Lagebeschreibung gibt es her.
- **SAMPLER** (Symptome, Allergien, Medikamente, Patientenvorgeschichte, Letzte Mahlzeit/Stuhlgang, Ereignis,
  Risikofaktoren) gehört ins **E** des ABCDE, **nicht** in die 1. Minute – z. B. „Blutverdünner erfragt“ ist `phase: full`.
- **Wärmeerhalt** nur, wo jemand auskühlen kann (Kälte, Nässe, Schock, Boden – auch im Sommer auf feuchtem Sand).
  Nicht bei wachen Patient:innen im Warmen (Restaurant, Wohnung) und **nicht während einer HLW**.
- **Der Kollege** führt aus, was man ansagt („Kollege, verbinde die Wunde“) – er reicht nicht nur Material.
  Fachliche Tipps gibt er **nur auf Nachfrage** (Entscheidung Lea, 21.11.2026: im echten Einsatz hilft man sich auch),
  ungefragt nie. Delegieren zählt in der Auswertung wie Selbermachen.
- **Material:** Auf den Rucksäcken sind Kühlpacks (Verbrennungen aber mit lauwarmem Wasser kühlen).

**Reanimation**

- **Kein ROSC.** Es wird durchreanimiert, bis RTW + NEF übernehmen (die haben z. B. Adrenalin). Ohne Nachforderung
  kommt niemand.
- **Der Kollege fragt nicht** nach Druckpunkt/Tiefe/Frequenz – er geht davon aus, dass es sitzt, und baut an:
  **AED → Beatmung (Beutel + Maske, Raumluft) → Absaugbereitschaft → Sauerstoff → ggf. Guedel-Tubus**,
  mit Ansagen wie „Absaugbereitschaft hergestellt“.
- **AED-Ansagen:** „Patient nicht berühren! Herzrhythmus wird analysiert …“ – dann „Schock empfohlen. Blinkende
  Taste drücken.“ (oder „Kein Schock empfohlen“). Darauf **„Schock! Alle weg!“** – ein Kommando, die Warnung in
  derselben Äußerung ist rechtzeitig. Alle 2 Minuten neu.
- **Wer drückt, zählt laut** – Pflicht, sobald beatmet werden kann. Kurzform „… 10 … 20 … 5, 6, 7, 8, 9, 30“
  oder „28, 29, 30“; dann 2 Beatmungen durch den Kollegen.

**Einzelne Fälle**

- **Sturz auf nasser Treppe:** Herr Petersen will nach Hause → Aufklärung (Kopfanprall unter Blutverdünner). Kennt
  man den Blutverdünner, willigt er sofort ein, sonst beim zweiten Anlauf.
- **Bolus:** Husten kann im Einzelfall noch möglich sein – „zum Husten auffordern“ bleibt eine (nicht kritische)
  Schlüsselmaßnahme. Eine Änderung in die andere Richtung wurde bewusst zurückgenommen.

## Wichtige Entscheidungen

| Entscheidung                                       | Warum                                                                                                                                                                                    |
| -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Netlify-Funktion → Python-Backend (FastAPI)        | eigener Server, lokale Modelle, verborgene Fakten bleiben serverseitig                                                                                                                   |
| Kein LLM-Rollenspiel, sondern Expertensystem       | kleine lokale Modelle (Qwen 0.5B/1.5B) hielten das Format nicht und waren auf CPU zu langsam (~50 s/Antwort)                                                                             |
| KI-Bewertung am Ende gebaut – und wieder ausgebaut | kostete Geld und brauchte deshalb Login; die regelbasierte Auswertung reicht. **Keine LLM-Aufrufe und keinen Login wieder einführen**; Auswertung stattdessen mit Heuristiken verbessern |
| Regex vor Embeddings, Abstand + Smalltalk-Gruppe   | Embeddings rieten bei kurzen Sätzen („ich taste sie ab“ → Blutzucker)                                                                                                                    |
| Themenwort maskieren bei der Befundsprache         | sonst verglich das Modell „Puls“ mit „Puls“ statt „ist im Rahmen“ mit „gut tastbar“                                                                                                      |
| Statische Dateien mit `Cache-Control: no-cache`    | der Service Worker lieferte sonst alte CSS/JS aus                                                                                                                                        |
| Barrierefreiheit                                   | semantisches HTML (fieldset/legend, h1–h3, Listen, `role="log"`/`status`), natives `<dialog>`, Fokusring bei Tastatur immer sichtbar, Fokus-Management, reduzierte Bewegung              |

## Arbeiten am Projekt

```sh
uv sync
uv run uvicorn backend.main:app --reload --reload-include '*.yaml'   # YAML-Änderungen ohne Neustart
uv run pytest                        # alles (~15 s, mit Embedding-Modell)
INTENT_EMBEDDINGS=0 uv run pytest    # schnell, nur Regex
```

- **Gemeldeter Fehler → Regressionstest** in [tests/regressions.yaml](tests/regressions.yaml): Satz, erwartete und
  verbotene Intents, erwartete Antwort. Läuft mit Regex und mit Embeddings.
- **Fälle ändern** = nur YAML, siehe [content/README.md](content/README.md). Die Tests prüfen Struktur, Abdeckung
  aller Intents je Fall und typische Abläufe.
- Wird ein Satz falsch verstanden: im Browser unter F12 → Netzwerk → `turn` zeigt `intents`, was erkannt wurde.
- Oberfläche, Inhalte und Doku sind auf Deutsch; Commit-Nachrichten auf Englisch.

### Hinweise für Claude-Sessions

- **Nie auf `main` pushen**; auf Feature-Branches arbeiten. Commits nur, wenn darum gebeten wird.
- **Mehrere Sessions arbeiten parallel** am Repo. Vor dem Commit `git status` lesen und **nur eigene Änderungen**
  committen.
- Den aktuellen Stand aus den Dateien lesen, nicht aus Erinnerung – Inhalte ändern sich oft.
- Fachliche Änderungen (Abläufe, Befunde, was „richtig“ ist) mit Lea abstimmen; die Regeln oben sind Praxiswissen.
- Keine Befunde erfinden, keine ungefragten Hinweise während des Einsatzes; Tipps nur auf Nachfrage (abschaltbar).
- Beim Ausprobieren im Browser: Chromium/Chrome headless + Playwright (`uv run --with playwright …`) funktioniert;
  Skripte von CDNs laden ist hier nicht erlaubt.

## Offene Punkte

- **Echte Sprachdaten fehlen.** Getestet wurde mit getippten bzw. ausgedachten Sätzen; was die Spracherkennung
  liefert (z. B. beim Zählen bis 30), ist ungeprüft. Idee: Durchläufe mit Einwilligung protokollieren und
  falsch erkannte Sätze in `regressions.yaml` übernehmen.
- **Bekannte Grenzfälle** (als `xfail` markiert): „Puls fühlt sich gut an“ (Befundsprache), „Können Sie das bitte
  halten“ (landet bei „nicht aufstehen“).
- **Fachlich gegenlesen:** Atembefunde (`atmung_beurteilen`) aller Fälle; Phase von Sauerstoffgabe und Kühlen
  (derzeit „ganzer Fall“); Decke bei „Verwirrte Person“ und „Pyro-Rauch“ (derzeit gefordert).
- Erzählte Handlungen sagen immer „Patient …“, auch bei Patientinnen.
