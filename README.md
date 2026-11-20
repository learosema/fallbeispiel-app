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
uv run pytest                          # alles, inkl. Embedding-Modell
INTENT_EMBEDDINGS=0 uv run pytest      # schnell, nur Regex
```

Sätze, die in der Praxis falsch erkannt oder beantwortet wurden, gehören als Regressionstest in
`tests/regressions.yaml` – ein Eintrag pro Satz mit erwarteten (und verbotenen) Intents bzw. Antworten.

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

Die App läuft auf <http://localhost:8000> (nur von diesem Rechner aus erreichbar), Modelle landen im Volume `hf-cache`.
Im Container gibt es kein `claude`-CLI – für die KI-Bewertung dort `JUDGE_PROVIDER=anthropic` oder `openai` in `.env` setzen.

## Öffentlich betreiben

Die Simulation und die regelbasierte Checkliste sind für alle offen. Nur die KI-Bewertung kostet Geld und braucht
deshalb einen Login: Ohne Anmeldung gibt es nach dem Einsatz die Checkliste und einen Link „Anmelden und KI-Bewertung holen“,
der den Login in einem eigenen Fenster öffnet. Der laufende Einsatz bleibt dabei erhalten. Lokal gibt es keinen Login.

Den Login übernimmt [oauth2-proxy](https://oauth2-proxy.github.io/oauth2-proxy/), Caddy sorgt für HTTPS und schickt
nur `/api/feedback` und `/oauth2/*` durch den Proxy. Anmelden kann sich nur, wer in `deploy/emails.txt` steht.
Die Sitzung liegt im HttpOnly-Cookie von oauth2-proxy, die App selbst speichert nichts davon. Der API-Key für die KI bleibt
in `.env` auf dem Server.

```
                  ┌─ /api/feedback, /oauth2/* ──▶ oauth2-proxy ──▶ App   Login nötig, setzt X-Forwarded-Email
Browser ──HTTPS──▶ Caddy                                                  (KI-Bewertungen pro Person begrenzt)
                  └─ alles andere ─────────────────────────────▶ App   offen
```

1. Domain auf den Server zeigen lassen, Ports 80 und 443 freigeben.
2. OAuth-App anlegen – Google: Cloud Console → APIs & Dienste → Anmeldedaten → OAuth-Client-ID (Webanwendung);
   GitHub: Settings → Developer settings → OAuth Apps (dann `LOGIN_PROVIDER=github`).
   Weiterleitungs-URL: `https://<DOMAIN>/oauth2/callback`.
3. In `.env` setzen: `AUTH_HEADER=X-Forwarded-Email`, `DOMAIN`, `OAUTH2_PROXY_CLIENT_ID`, `OAUTH2_PROXY_CLIENT_SECRET`,
   `OAUTH2_PROXY_COOKIE_SECRET` und die KI-Einstellungen (siehe `.env.example`).
4. `cp deploy/emails.txt.example deploy/emails.txt` und die erlaubten Adressen eintragen.
5. `docker compose --profile public up -d --build`

Mit gesetztem `AUTH_HEADER` lehnt die App KI-Bewertungen ohne diesen Header ab (401). Der Header ist nur vertrauenswürdig,
solange die App ausschließlich über Caddy erreichbar ist (Caddy entfernt ihn, nur oauth2-proxy setzt ihn) – Port 8000
deshalb nie nach außen freigeben.
Bei der Anthropic- oder OpenAI-API zusätzlich ein monatliches Ausgabenlimit in deren Konsole setzen.

**Alternative Cloudflare Access:** Liegt die Domain bei Cloudflare, kann statt oauth2-proxy und Caddy ein Cloudflare-Tunnel
mit Access-Regel (Login per E-Mail-Code, bis 50 Personen kostenlos) vor der App stehen. Dann
`AUTH_HEADER=Cf-Access-Authenticated-User-Email` setzen und nur `docker compose up` starten. Die Anmeldung im Frontend
(`/oauth2/…`) ist auf oauth2-proxy zugeschnitten; mit Cloudflare Access am einfachsten die ganze Seite schützen.

## Weitere Einstellungen

Siehe `.env.example`.

| Variable                  | Standard                                                   | Bedeutung                                           |
|---------------------------|------------------------------------------------------------|-----------------------------------------------------|
| `AUTH_HEADER`             | leer                                                       | Header mit der angemeldeten Person (vom Login-Proxy); leer = KI-Bewertung ohne Login |
| `FEEDBACK_LIMIT`          | `20`                                                       | KI-Bewertungen pro Person und Stunde                |
| `INTENT_MODEL`            | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Embedding-Modell für die Intent-Erkennung        |
| `INTENT_THRESHOLD`        | `0.72`                                                     | Mindest-Ähnlichkeit für Embedding-Treffer           |
| `INTENT_EMBEDDINGS`       | `1`                                                        | `0` = nur Regex-Muster (kein Modell nötig)          |
| `PRELOAD_MODEL`           | `1`                                                        | `0` lädt den Classifier erst bei der ersten Anfrage |
| `JUDGE_TIMEOUT`           | `180`                                                      | Sekunden bis zum Abbruch der KI-Bewertung           |

PyTorch wird als CPU-Build installiert. Für eine NVIDIA-GPU den `pytorch-cpu`-Index in `pyproject.toml` entfernen.

## Hinweis

Alle Fälle sind frei erfunden und dienen nur der Ausbildung. Das DRK-SANmemo ist urheberrechtlich geschützt (© DRK)
und liegt nicht im Repository.
