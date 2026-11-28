# Kurzbefehle für die Entwicklung – `make` allein zeigt die Übersicht.
# Unter der Haube läuft alles über uv (https://docs.astral.sh/uv/).

PORT ?= 8000
HOST ?= 127.0.0.1
UV   := $(shell command -v uv 2>/dev/null)

.DEFAULT_GOAL := help
.PHONY: help install serve test test-fast docker check-uv voices-cast audio-status
TTS_PY := .venv-tts/bin/python

help: ## diese Übersicht
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-10s %s\n", $$1, $$2}'
	@echo ""
	@echo "  Port ändern: make serve PORT=8080"

check-uv:
ifeq ($(UV),)
	@echo "uv fehlt. Installieren: curl -LsSf https://astral.sh/uv/install.sh | sh" && exit 1
endif

install: check-uv ## Abhängigkeiten installieren (macht serve/test auch automatisch)
	uv sync

serve: check-uv ## App lokal starten, lädt bei Code- und YAML-Änderungen neu → http://localhost:8000
	@echo "→ http://localhost:$(PORT)  (Beenden mit Strg+C; der erste Start lädt das Embedding-Modell)"
	uv run uvicorn backend.main:app --host $(HOST) --port $(PORT) --reload --reload-include '*.yaml'

test: check-uv ## alle Tests (inkl. Embedding-Modell, ~15 s)
	uv run pytest

test-fast: check-uv ## schnelle Tests, nur Regex
	INTENT_EMBEDDINGS=0 uv run pytest

docker: ## wie auf dem Server: im Docker-Container bauen und starten
	docker compose up --build

voices-cast: ## Stimmen casten: Referenzclips nach audio/voices (siehe tools/tts/README.md)
	$(TTS_PY) tools/tts/cast.py

audio-status: ## wie viele vertonte Clips fehlen
	uv run python tools/tts/render.py --status
