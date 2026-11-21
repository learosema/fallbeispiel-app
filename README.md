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
ohne kostenpflichtige Dienste. Für HTTPS steht ein Reverse Proxy davor, der auf dem Server ohnehin läuft – unten
am Beispiel nginx mit einem Zertifikat von Let's Encrypt (certbot).

```
Browser ──HTTPS──▶ nginx ──▶ App (127.0.0.1:8000, von außen nicht erreichbar)
```

### Voraussetzungen

- Linux-Server mit Docker und Compose-Plugin ab 2.24 (`docker compose version`), nginx und certbot
- eine (Sub-)Domain, deren A- und ggf. AAAA-Eintrag auf den Server zeigt (`dig +short fallbeispiel.example.org A`
  bzw. `AAAA` – Let's Encrypt bevorzugt IPv6, ein veralteter AAAA-Eintrag lässt die Prüfung scheitern)
- mindestens 2–3 GB RAM (PyTorch und Embedding-Modell) und ca. 5 GB Platz; der erste Build dauert einige Minuten

### 1. App starten

```sh
git clone https://github.com/learosema/fallbeispiel-app.git
cd fallbeispiel-app
docker compose up -d --build
docker compose logs -f        # Strg+C beendet nur die Anzeige
```

Beim ersten Start lädt die App das Embedding-Modell (~470 MB) ins Volume `hf-cache`. Bis sie bereit ist
(„Application startup complete“ im Log), antwortet nginx mit 502. Spätere Starts gehen schnell.
Eine `.env` ist nicht nötig; Einstellungen siehe `.env.example` und [Weitere Einstellungen](#weitere-einstellungen).
Ist Port 8000 auf dem Server schon belegt, z. B. `APP_PORT=8402` in `.env` setzen und in der nginx-Config unten
`proxy_pass http://127.0.0.1:8402;` eintragen. `docker-compose.yml` selbst nicht ändern – sonst gibt es Konflikte beim
`git pull`, und ein Port ohne `127.0.0.1:` wäre von außen offen (Docker umgeht dabei auch `ufw`).

### 2. Zertifikat holen

Zuerst nur HTTP, damit Let's Encrypt die Domain prüfen kann (`/etc/nginx/sites-available/fallbeispiel`):

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name fallbeispiel.example.org;

    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 301 https://$host$request_uri; }
}
```

```sh
sudo ln -s ../sites-available/fallbeispiel /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot certonly --webroot -w /var/www/html -d fallbeispiel.example.org --deploy-hook "systemctl reload nginx"
```

Der `--deploy-hook` lädt nginx nach jeder automatischen Verlängerung neu. Ist in `/etc/letsencrypt/cli.ini` schon ein
anderes Verfahren eingestellt, dasselbe nehmen (sonst: „Too many flags setting configurators“).

### 3. HTTPS einrichten

In dieselbe Datei:

```nginx
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;                       # nginx < 1.25.1: stattdessen „listen 443 ssl http2;“
    server_name fallbeispiel.example.org;

    ssl_certificate     /etc/letsencrypt/live/fallbeispiel.example.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/fallbeispiel.example.org/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host              $host;
        proxy_set_header X-Forwarded-For   $remote_addr;   # überschreiben, nicht anhängen (siehe unten)
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```sh
sudo nginx -t && sudo systemctl reload nginx
sudo certbot renew --dry-run
```

Das Zertifikat gilt sofort. Meldet der Browser einen falschen Namen, liefert nginx noch ein anderes Zertifikat aus
(Block fehlt oder nicht neu geladen) – prüfen mit
`echo | openssl s_client -connect <DOMAIN>:443 -servername <DOMAIN> 2>/dev/null | openssl x509 -noout -subject`.

**Warum `$remote_addr`:** Das Rate-Limit braucht die echte Client-IP. Die App nimmt den ersten Eintrag aus
`X-Forwarded-For`; das übliche `$proxy_add_x_forwarded_for` hängt nur an, damit könnte jeder eine beliebige IP
vorschicken. Steht vor nginx noch ein Proxy (z. B. Cloudflare), zusätzlich `set_real_ip_from` und `real_ip_header`
setzen, sonst teilen sich alle dessen IP.

**Andere Proxys:** Caddy (`reverse_proxy 127.0.0.1:8000`) und Traefik überschreiben `X-Forwarded-For` von selbst,
solange keine vertrauenswürdigen Proxys (`trusted_proxies` bzw. `trustedIPs`) eingestellt sind. Läuft der Proxy in
einem Docker-Container, erreicht er `127.0.0.1:8000` des Servers nicht. Dann die App in sein Netzwerk hängen und ihn
auf `http://fallbeispiel-app:8000` zeigen lassen, z. B. mit einer `docker-compose.override.yml`
(wird von `docker compose` automatisch gelesen):

```yaml
services:
  app:
    ports: !reset []           # kein Port auf dem Server mehr nötig
    networks:
      default:
      proxy:
        aliases: [fallbeispiel-app]   # eindeutiger Name im gemeinsamen Netz („app“ gibt es dort oft mehrfach)
networks:
  proxy:
    external: true
    name: <Netzwerk des Proxys>
```

### 4. Prüfen

- `https://<DOMAIN>` öffnen, einen Fall spielen, die Auswertung starten.
- Im Log der App (`docker compose logs app`) steht bei den Aufrufen deine echte IP – nicht `127.0.0.1` oder `172.…`.
  Sonst setzt der Proxy `X-Forwarded-For` nicht, und alle teilen sich ein Rate-Limit.
- Von außen ist Port 8000 **nicht** erreichbar: `curl http://<DOMAIN>:8000` muss scheitern.

### Aktualisieren

```sh
git pull && docker compose up -d --build
```

Nach dem Update laden Browser die neue Version beim nächsten Öffnen (der Service Worker fragt immer zuerst beim Server nach).

### Betrieb

- **Neustarts:** Alle Container laufen mit `restart: unless-stopped` und kommen nach einem Server-Neustart von selbst
  wieder, solange Docker beim Booten startet (`systemctl enable docker`).
- **Überlast:** Jede Anfrage spielt den ganzen Einsatz nach und rechnet ggf. Embeddings. Die App begrenzt deshalb die
  API-Aufrufe pro Client-IP (`RATE_LIMIT`, Standard 300 pro Minute, ein zügiger Einsatz braucht ~20). Teilen sich viele
  Leute eine IP (Lehrgang im selben WLAN) und erscheint „Zu viele Anfragen“, den Wert in `.env` erhöhen und
  die App mit `docker compose up -d` neu starten. Die Grenze gilt pro Prozess und beginnt nach einem Neustart neu.
- **Client-IP:** Die App übernimmt sie aus `X-Forwarded-For` (`FORWARDED_ALLOW_IPS=*`). Das ist nur sicher, solange
  Port 8000 nicht nach außen offen ist – in `docker-compose.yml` deshalb `127.0.0.1:8000:8000` lassen – und der Proxy
  den Header überschreibt (siehe 3.).
- **Daten:** Die App speichert nichts. Das Einsatzprotokoll liegt nur im Browser und wird bei jeder Äußerung mitgeschickt.
  Im Log der App stehen nur Zugriffszeilen (Client-IP, Pfad, Status), keine Inhalte. Was dein Proxy protokolliert,
  regelt seine eigene Konfiguration.
- **Logs:** `docker compose logs --tail 100 app`

### Fehlersuche

| Symptom                                   | Ursache / Abhilfe                                                                 |
|-------------------------------------------|-----------------------------------------------------------------------------------|
| certbot: Prüfung fehlgeschlagen           | DNS (auch AAAA) zeigt nicht auf den Server, Port 80 ist zu, oder ein anderer `server`-Block fängt die Anfrage ab. Test: Datei nach `/var/www/html/.well-known/acme-challenge/test` legen und per `curl http://<DOMAIN>/.well-known/acme-challenge/test` abrufen |
| Browser: falscher Name im Zertifikat      | nginx liefert ein anderes Zertifikat aus – 443-Block fehlt oder nginx nicht neu geladen (siehe 3.) |
| Alle bekommen schnell „Zu viele Anfragen“ | Proxy gibt die Client-IP nicht weiter – im App-Log steht überall dieselbe IP (siehe 3. Prüfen) |
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
| `APP_PORT`                | `8000`                                                     | Port auf dem Server (nur `127.0.0.1`), für den Proxy |
| `RATE_LIMIT`              | `300`                                                      | API-Aufrufe pro Client-IP und Minute, `0` = aus     |
| `FORWARDED_ALLOW_IPS`     | `*` (im Docker-Image)                                      | Absender, deren `X-Forwarded-For` gilt (uvicorn)    |
| `PRELOAD_MODEL`           | `1`                                                        | `0` lädt den Classifier erst bei der ersten Anfrage |

PyTorch wird als CPU-Build installiert. Für eine NVIDIA-GPU den `pytorch-cpu`-Index in `pyproject.toml` entfernen.

## Hinweis

Alle Fälle sind frei erfunden und dienen nur der Ausbildung. Das DRK-SANmemo ist urheberrechtlich geschützt (© DRK)
und liegt nicht im Repository.
