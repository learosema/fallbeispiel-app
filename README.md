# Fallbeispiel-App

Trainings-App für Fallbeispiele im Sanitätsdienst nach dem xABCDE-Schema (Fokus: die 1. Minute nach DRK-SANmemo).
Das Frontend (`public/`) ist eine PWA mit Spracheingabe und -ausgabe im Browser; das Python-Backend (`backend/`)
liefert die Seite aus und beantwortet `/api/chat` mit einem lokalen Sprachmodell über Hugging Face `transformers`.

## Lokal starten

Voraussetzung: [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run uvicorn backend.main:app --reload
```

Dann <http://localhost:8000> öffnen. Beim ersten Start wird das Modell heruntergeladen (~3 GB für das Standardmodell).

## Mit Docker

```sh
docker compose up --build
```

Die App läuft auf <http://localhost:8000>, Modelle landen im Volume `hf-cache`.

## Konfiguration

Umgebungsvariablen (siehe `.env.example`, für Docker in `.env` eintragen):

| Variable          | Standard                       | Bedeutung                                             |
|-------------------|--------------------------------|-------------------------------------------------------|
| `LLM_MODEL`       | `Qwen/Qwen2.5-1.5B-Instruct`   | Hugging-Face-Modell-ID                                |
| `LLM_DEVICE`      | automatisch (`cuda` oder `cpu`)| Rechengerät                                           |
| `LLM_TEMPERATURE` | `0.7`                          | Sampling-Temperatur                                   |
| `ACCESS_CODE`     | leer                           | Zugangscode, wenn der Server öffentlich erreichbar ist|
| `PRELOAD_MODEL`   | `1`                            | `0` lädt das Modell erst bei der ersten Anfrage       |

PyTorch wird als CPU-Build installiert. Für eine NVIDIA-GPU den `pytorch-cpu`-Index in `pyproject.toml` entfernen.

## Hinweis

Das DRK-SANmemo ist urheberrechtlich geschützt (© DRK) und liegt nicht im Repository.
