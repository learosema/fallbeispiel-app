# Fallbeispiel-App

Trainings-App für Fallbeispiele im Sanitätsdienst nach dem xABCDE-Schema (Fokus: die 1. Minute nach DRK-SANmemo).
Du sprichst (oder tippst), die App antwortet als Patient:in, Kollege, Umstehende und Leitstelle. Am Ende gibt es eine Auswertung.

## Architektur

```
Browser (public/)          Spracheingabe/-ausgabe, schickt bei jeder Äußerung das ganze Protokoll
   │
   ▼
FastAPI (backend/)
   ├─ classifier.py        Äußerung → Intents (Regex + Satz-Embeddings über transformers)
   ├─ engine.py            Expertensystem: Intents → hardcodierte Antworten je Fall, Zustände,
   │                       zeitliche Verschlechterung, Funkverkehr mit der Leitstelle
   ├─ evaluate.py          regelbasierte Checkliste (SANmemo), Reihenfolge, Schlüsselmaßnahmen
   └─ judge.py             KI-Bewertung am Ende: ganzer Dialog + Checkliste → Algorithmus + Patientensicht
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
uv run pytest
```

## KI-Bewertung

Nur die Auswertung am Ende nutzt ein Sprachmodell. Auswahl über `JUDGE_PROVIDER`:

| Provider     | Wofür                                                                 | Konfiguration                                        |
|--------------|-----------------------------------------------------------------------|------------------------------------------------------|
| `auto`       | Standard: `claude-cli`, falls `claude` im PATH liegt, sonst `none`     | –                                                    |
| `claude-cli` | lokaler Test über das eigene Claude-Abo (`claude -p`)                  | `JUDGE_MODEL` (Standard `haiku`)                     |
| `anthropic`  | Anthropic API                                                          | `ANTHROPIC_API_KEY`, `JUDGE_MODEL` (Standard `claude-haiku-5-5`) |
| `openai`     | OpenAI oder kompatible APIs (Ollama, vLLM, …)                          | `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `JUDGE_MODEL` (Standard `gpt-5-nano`) |
| `local`      | lokales Modell über transformers (auf CPU langsam und eher schwach)    | `LLM_MODEL`, `LLM_DEVICE`                            |
| `none`       | keine KI, nur die regelbasierte Checkliste                             | –                                                    |

Ohne KI bleibt die App voll benutzbar; die Checkliste erscheint immer sofort, das KI-Feedback wird nachgeladen.

## Mit Docker

```sh
docker compose up --build
```

Die App läuft auf <http://localhost:8000>, Modelle landen im Volume `hf-cache`.
Im Container gibt es kein `claude`-CLI – für die KI-Bewertung dort `JUDGE_PROVIDER=anthropic` oder `openai` in `.env` setzen.

## Weitere Einstellungen

Siehe `.env.example`.

| Variable                  | Standard                                                   | Bedeutung                                           |
|---------------------------|------------------------------------------------------------|-----------------------------------------------------|
| `ACCESS_CODE`             | leer                                                       | Zugangscode, wenn der Server öffentlich erreichbar ist |
| `INTENT_MODEL`            | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Embedding-Modell für die Intent-Erkennung        |
| `INTENT_THRESHOLD`        | `0.72`                                                     | Mindest-Ähnlichkeit für Embedding-Treffer           |
| `INTENT_EMBEDDINGS`       | `1`                                                        | `0` = nur Regex-Muster (kein Modell nötig)          |
| `PRELOAD_MODEL`           | `1`                                                        | `0` lädt den Classifier erst bei der ersten Anfrage |
| `JUDGE_TIMEOUT`           | `180`                                                      | Sekunden bis zum Abbruch der KI-Bewertung           |

PyTorch wird als CPU-Build installiert. Für eine NVIDIA-GPU den `pytorch-cpu`-Index in `pyproject.toml` entfernen.

## Hinweis

Alle Fälle sind frei erfunden und dienen nur der Ausbildung. Das DRK-SANmemo ist urheberrechtlich geschützt (© DRK)
und liegt nicht im Repository.
