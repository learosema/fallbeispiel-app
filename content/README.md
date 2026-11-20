# Inhalte

Alles, was die Simulation sagt und wie ausgewertet wird, steht hier in YAML. Code muss dafür nicht angefasst werden.
Nach Änderungen `uv run pytest` laufen lassen – die Tests prüfen u. a., dass jeder Fall die wichtigsten Befunde beantwortet.

## `intents.yaml` – was die Sanitäter:in tut

Jeder Intent ist ein Schritt („Puls“, „Decke“, „Rückenschläge“ …) mit

- `patterns`: Regex auf kleingeschriebenen Text (ß wird zu ss). Ein Treffer reicht. Spracheingaben kommen oft
  ohne Satzzeichen – Muster daher eher kurz halten.
- `examples`: Beispielsätze für die Embedding-Erkennung, falls kein Stichwort fällt („Frieren Sie?“ statt „kalt“).
- `default`: Antwort, wenn ein Fall selbst keine festlegt (typisch: Handgriffe des Kollegen).
- `implies` / `overrides` / `exclusive`: siehe Kommentar am Dateianfang.

## `algorithm.yaml` – wie ausgewertet wird

Checklisten für die 1. Minute (wach / bewusstlos) und den ganzen Fall, plus der Referenztext für die KI.

## `scenarios/*.yaml` – die Fälle

```yaml
id: basis-sturz              # eindeutig, Reihenfolge in der App = Dateiname
group: Grundlagen
letter: "1."
title: Sturz auf nasser Treppe
teaser: Kurzbeschreibung
dispatch: "Funkmeldung: …"   # wird vorgelesen
debrief_notes: >             # nur für die KI-Bewertung (Lösung, worauf es ankommt)
  …
conscious: true              # false → Checkliste „bewusstlos“
breathing: normal            # bei Bewusstlosigkeit: normal (Seitenlage) | abnormal (HLW)
trauma: true                 # HWS und Trauma-Check werden erwartet
bleeding: false              # bedrohliche Blutung → Blutstillung wird erwartet
request: {required: [RTW], optional: [NEF]}   # passende Nachforderung im Funkspruch
skip: [hws]                  # Checklistenpunkte, die hier nicht gelten („–“)
state: {geloest: false}      # Anfangszustand eigener Flags

responses:                   # Intent → Antwort
  puls:
    - Befund: Puls 78.       # einfache Form: Liste von Zeilen
  hautfarbe:                 # Varianten: die erste passende gilt
    - when: {decke: false}   # jeder erkannte Intent ist automatisch ein Flag (true, sobald er vorkam)
      say:
        - Befund: Haut kühl.
    - say:
        - Befund: Haut wird wärmer.
  heimlich:
    - when: {rueckenschlaege: true}
      say:
        - Befund: Der Fremdkörper löst sich.
      set: {geloest: true}   # eigene Flags setzen

events:                      # zeitgesteuert (Nettozeit der Sanitäter:in in Sekunden), feuern je einmal
  - at: 75
    when: {decke: false}
    say:
      - Patient: Mir wird kalt …
  - at: 60
    since: nachforderung     # relativ zum ersten Auftreten eines Intents
    say: [...]

key_actions:                 # fallspezifische Schlüsselmaßnahmen für die Auswertung
  - label: Blutstillung vor allem anderen
    any: [blutung_stillen]   # oder all: […] / min: n + of: […]
    critical: true           # fehlt sie, ist der Algorithmus „nicht erfüllt“
    within: 45               # sonst ⚠️ „erst nach …“
    before: [puls, atmung_fragen]   # sonst ⚠️ „zu spät“
```

Sprecher: `Patient`, `Kollege`, `Umstehende`, `Befund`, `Leitstelle`, `AED`, `Rettungsdienst`.
Text in Klammern ist Regieanweisung und wird angezeigt, aber nicht vorgelesen.
Enthält ein Text `: `, muss er in Anführungszeichen stehen: `- Befund: "Lage: sicher"`.

Die Leitstelle (Anruf, Meldung, „Ende“) und das Eintreffen des Rettungsdienstes ca. 8 Minuten nach der
Nachforderung übernimmt die Engine; `{callsign}` und `{dispatcher}` werden in Texten ersetzt.
