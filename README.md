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

Die App ist ohne Anmeldung nutzbar: Simulation und Auswertung laufen komplett auf dem eigenen Server, ohne KI und
ohne kostenpflichtige Dienste. Davor steht nur Caddy für HTTPS (Zertifikat von Let's Encrypt, automatisch erneuert).

```
Browser ──HTTPS──▶ Caddy (Ports 80/443) ──▶ App (Port 8000, nur für Caddy und den Server selbst erreichbar)
```

### Voraussetzungen

- Linux-Server mit Docker und Compose-Plugin ab 2.24 (`docker compose version`)
- eine (Sub-)Domain, deren A/AAAA-Eintrag auf den Server zeigt (`dig +short fallbeispiel.example.org`)
- Ports 80 und 443 von außen erreichbar und frei (kein anderer Webserver darauf)
- mindestens 2–3 GB RAM (PyTorch und Embedding-Modell) und ca. 5 GB Platz; der erste Build dauert einige Minuten

### 1. Code holen

```sh
git clone https://github.com/learosema/fallbeispiel-app.git
cd fallbeispiel-app
```

### 2. Domain eintragen

```sh
echo "DOMAIN=fallbeispiel.example.org" > .env
```

Weitere Einstellungen sind optional (siehe `.env.example` und [Weitere Einstellungen](#weitere-einstellungen)).

### 3. Starten

```sh
docker compose --profile public up -d --build
docker compose --profile public logs -f        # Strg+C beendet nur die Anzeige
```

Beim ersten Start lädt die App das Embedding-Modell (~470 MB) ins Volume `hf-cache`. Bis sie bereit ist
(„Application startup complete“ im Log), antwortet Caddy mit 502. Spätere Starts gehen schnell.

### 4. Prüfen

- `https://<DOMAIN>` öffnen, einen Fall spielen, die Auswertung starten.
- Im Log von Caddy steht `certificate obtained successfully`.
- Von außen ist Port 8000 **nicht** erreichbar: `curl http://<DOMAIN>:8000` muss scheitern.

### Aktualisieren

```sh
git pull && docker compose --profile public up -d --build
```

Nach dem Update laden Browser die neue Version beim nächsten Öffnen (der Service Worker fragt immer zuerst beim Server nach).

### Betrieb

- **Neustarts:** Alle Container laufen mit `restart: unless-stopped` und kommen nach einem Server-Neustart von selbst
  wieder, solange Docker beim Booten startet (`systemctl enable docker`).
- **Überlast:** Jede Anfrage spielt den ganzen Einsatz nach und rechnet ggf. Embeddings. Die App begrenzt deshalb die
  API-Aufrufe pro Client-IP (`RATE_LIMIT`, Standard 300 pro Minute, ein zügiger Einsatz braucht ~20). Teilen sich viele
  Leute eine IP (Lehrgang im selben WLAN) und erscheint „Zu viele Anfragen“, den Wert in `.env` erhöhen und
  `docker compose --profile public up -d` ausführen. Die Grenze gilt pro Prozess und beginnt nach einem Neustart neu.
- **Client-IP:** Die App übernimmt sie aus `X-Forwarded-For`, das Caddy setzt. Das ist nur sicher, solange Port 8000
  nicht nach außen offen ist – in `docker-compose.yml` deshalb `127.0.0.1:8000:8000` lassen.
- **Daten:** Die App speichert nichts. Das Einsatzprotokoll liegt nur im Browser und wird bei jeder Äußerung mitgeschickt.
  Im Log der App stehen nur Zugriffszeilen (Client-IP, Pfad, Status), keine Inhalte; Caddy schreibt ohne `log`-Direktive
  keine Zugriffslogs.
- **Logs:** `docker compose --profile public logs --tail 100 app` bzw. `caddy`.

### Fehlersuche

| Symptom                                   | Ursache / Abhilfe                                                                 |
|-------------------------------------------|-----------------------------------------------------------------------------------|
| Kein Zertifikat, Browser warnt            | DNS zeigt noch nicht auf den Server oder Port 80/443 ist zu (Firewall, Cloud-Sicherheitsgruppe). Caddy versucht es selbst erneut. |
| 502 Bad Gateway                           | App startet noch (Modell-Download) oder ist abgestürzt: `logs app`                |
| App wird beendet, `Killed` im Log         | zu wenig RAM – Swap anlegen oder größeren Server nehmen                           |
| „Zu viele Anfragen – bitte kurz warten.“  | `RATE_LIMIT` erhöhen (siehe Betrieb)                                              |

## Weitere Einstellungen

Siehe `.env.example`.

| Variable                  | Standard                                                   | Bedeutung                                           |
|---------------------------|------------------------------------------------------------|-----------------------------------------------------|
| `INTENT_MODEL`            | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Embedding-Modell für die Intent-Erkennung        |
| `INTENT_THRESHOLD`        | `0.72`                                                     | Mindest-Ähnlichkeit für Embedding-Treffer           |
| `INTENT_EMBEDDINGS`       | `1`                                                        | `0` = nur Regex-Muster (kein Modell nötig)          |
| `RATE_LIMIT`              | `300`                                                      | API-Aufrufe pro Client-IP und Minute, `0` = aus     |
| `PRELOAD_MODEL`           | `1`                                                        | `0` lädt den Classifier erst bei der ersten Anfrage |

PyTorch wird als CPU-Build installiert. Für eine NVIDIA-GPU den `pytorch-cpu`-Index in `pyproject.toml` entfernen.

## Hinweis

Alle Fälle sind frei erfunden und dienen nur der Ausbildung. Das DRK-SANmemo ist urheberrechtlich geschützt (© DRK)
und liegt nicht im Repository.
