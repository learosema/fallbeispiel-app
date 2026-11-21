# Fallbeispiel-App

Trainings-App für Fallbeispiele im Sanitätsdienst nach dem xABCDE-Schema (Fokus: die 1. Minute nach DRK-SANmemo).
Du sprichst (oder tippst), die App antwortet als Patient:in, Kollege, Umstehende und Leitstelle. Am Ende gibt es eine regelbasierte Auswertung – ohne KI und ohne Login.

## Architektur

```
Browser (public/)          Spracheingabe/-ausgabe, schickt bei jeder Äußerung das ganze Protokoll
   │
   ▼
FastAPI (backend/)
   ├─ classifier.py        Äußerung → Intents (Regex + Satz-Embeddings über transformers)
   ├─ engine.py            Expertensystem: Intents → hardcodierte Antworten je Fall, Zustände,
   │                       zeitliche Verschlechterung, Funkverkehr mit der Leitstelle
   └─ evaluate.py          regelbasierte Auswertung: Checkliste (SANmemo), Reihenfolge, Schlüsselmaßnahmen,
                           Funkspruch, Befundsprache
content/                   Intents, Checklisten, Fallbeispiele (YAML) – siehe content/README.md
```

Der Server ist zustandslos: Er spielt das Protokoll bei jeder Anfrage deterministisch nach.
Die verborgenen Fakten der Fälle bleiben auf dem Server.

## Lokal starten

Voraussetzung: [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run uvicorn backend.main:app --reload
```

Dann <http://localhost:8000> öffnen. Beim ersten Start wird das Embedding-Modell für die Intent-Erkennung
heruntergeladen (~470 MB).

Tests:

```sh
uv run pytest                          # alles, inkl. Embedding-Modell
INTENT_EMBEDDINGS=0 uv run pytest      # schnell, nur Regex
```

Sätze, die in der Praxis falsch erkannt oder beantwortet wurden, gehören als Regressionstest in
`tests/regressions.yaml` – ein Eintrag pro Satz mit erwarteten (und verbotenen) Intents bzw. Antworten.

## Mit Docker

```sh
docker compose up --build
```

Die App läuft auf <http://localhost:8000> (nur von diesem Rechner aus erreichbar), Modelle landen im Volume `hf-cache`.

## Öffentlich betreiben

Die App braucht keinen Login: Simulation und Auswertung laufen komplett auf dem eigenen Server, es gibt keine
kostenpflichtigen Dienste dahinter. Caddy davor sorgt für HTTPS.

```
Browser ──HTTPS──▶ Caddy ──▶ App (Port 8000, nur lokal erreichbar)
```

### Voraussetzungen

- Linux-Server mit Docker und Compose-Plugin ab 2.24 (`docker compose version`)
- eine (Sub-)Domain, deren A/AAAA-Eintrag auf den Server zeigt
- Ports 80 und 443 offen und frei (kein anderer Webserver darauf)
- mindestens 2–3 GB RAM (PyTorch und Embedding-Modell); der erste Build dauert einige Minuten

### Einrichten

```sh
git clone git@github.com:learosema/fallbeispiel-app.git
cd fallbeispiel-app
echo "DOMAIN=fallbeispiel.example.org" > .env
docker compose --profile public up -d --build
docker compose --profile public logs -f        # Caddy holt das Zertifikat
```

Dann `https://<DOMAIN>` öffnen.

### Aktualisieren

```sh
git pull && docker compose --profile public up -d --build
```

## Weitere Einstellungen

Siehe `.env.example`.

| Variable                  | Standard                                                   | Bedeutung                                           |
|---------------------------|------------------------------------------------------------|-----------------------------------------------------|
| `INTENT_MODEL`            | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Embedding-Modell für die Intent-Erkennung        |
| `INTENT_THRESHOLD`        | `0.72`                                                     | Mindest-Ähnlichkeit für Embedding-Treffer           |
| `INTENT_EMBEDDINGS`       | `1`                                                        | `0` = nur Regex-Muster (kein Modell nötig)          |
| `PRELOAD_MODEL`           | `1`                                                        | `0` lädt den Classifier erst bei der ersten Anfrage |

PyTorch wird als CPU-Build installiert. Für eine NVIDIA-GPU den `pytorch-cpu`-Index in `pyproject.toml` entfernen.

## Hinweis

Alle Fälle sind frei erfunden und dienen nur der Ausbildung. Das DRK-SANmemo ist urheberrechtlich geschützt (© DRK)
und liegt nicht im Repository.
