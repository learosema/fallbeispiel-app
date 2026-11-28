"""FastAPI-Backend: liefert das Frontend aus public/ und spielt die Fallbeispiele.

  GET  /api/scenarios   Liste der Fälle (ohne verborgene Fakten)
  POST /api/turn        Protokoll → Antwort der Simulation auf die letzte Äußerung
  POST /api/debrief     Protokoll → regelbasierte Auswertung
  POST /api/clip        Satz → URL des vorab vertonten Clips (für Texte, die das Frontend selbst vorliest)
  GET  /audio/<id>.mp3  Clip (vorab vertont aus audio/clips/, Leitstelle per Piper auf Zuruf)

Umgebungsvariablen: siehe README.md (INTENT_*, PRELOAD_MODEL, RATE_LIMIT, PIPER).
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from collections import OrderedDict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from functools import lru_cache

from . import classifier, content, engine, evaluate, solutions, speech, tts_piper

log = logging.getLogger(__name__)
PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"
NO_STORE = {"Cache-Control": "no-store"}
MAX_LOG_CHARS = 30_000  # ganzer Fall ≈ 15 000 Zeichen; begrenzt den Aufwand pro Anfrage


class Utterance(BaseModel):
    t: float = Field(ge=0, le=24 * 3600)
    text: str = Field(default="", max_length=1000)
    tick: bool = False  # Takt ohne Äußerung (fällige Ereignisse, z. B. AED-Analyse alle 2 Minuten)

    @model_validator(mode="after")
    def _text_or_tick(self):
        if not self.tick and not self.text.strip():
            raise ValueError("text fehlt")
        return self


class RunRequest(BaseModel):
    scenario: str = Field(max_length=100)
    mode: Literal["minute", "full"] = "minute"
    callsign: str = Field(default="EVT1", min_length=1, max_length=40)
    dispatcher: str = Field(default="RotkreuzHamburg", min_length=1, max_length=60)
    tips: bool = True   # Kollege gibt auf Nachfrage Tipps
    log: list[Utterance] = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def _log_size(self):
        if sum(len(u.text) for u in self.log) > MAX_LOG_CHARS:
            raise ValueError("Protokoll zu lang")
        return self


def error(msg: str, status: int) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=status, headers=NO_STORE)


class RateLimit:
    """Höchstens `limit` Aufrufe je Schlüssel (Client-IP) in `window` Sekunden – im Speicher, ein Prozess."""

    def __init__(self, limit: int, window: float):
        self.limit, self.window = limit, window
        self._calls: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> bool:
        if self.limit <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            if len(self._calls) > 10_000:  # abgelaufene Einträge aufräumen, damit der Speicher nicht wächst
                self._calls = {k: q for k, q in self._calls.items() if q and q[-1] > now - self.window}
            calls = self._calls.setdefault(key, deque())
            while calls and calls[0] <= now - self.window:
                calls.popleft()
            if len(calls) >= self.limit:
                return False
            calls.append(now)
            return True


# Jede Äußerung ist ein Aufruf, dazu Takte; ein zügiger Einsatz liegt bei ~20/min. Großzügig, weil sich eine
# Gruppe im selben WLAN eine IP teilt. Hinter dem Reverse Proxy ist die IP die echte (FORWARDED_ALLOW_IPS, Dockerfile).
api_limit = RateLimit(int(os.environ.get("RATE_LIMIT", "300")), 60)


# ---------- Sprachausgabe ----------
# Piper-Clips (Leitstelle) werden erst erzeugt, wenn der Browser sie abruft. Damit niemand beliebige Texte vertonen
# lässt, merkt sich der Server die Clips, die er in einer Antwort ausgeliefert hat (im Speicher, begrenzt).
_pending: OrderedDict[str, speech.Clip] = OrderedDict()
_pending_lock = threading.Lock()
PIPER_ON = tts_piper.enabled()


def audio_url(scenario_id: str | None, line: content.Line) -> str | None:
    c = speech.clip(scenario_id, line)
    if c is None:
        return None
    if c.voice.engine == "qwen":
        return f"/audio/{c.id}.mp3" if c.id in speech.available() else None
    if not PIPER_ON:
        return None
    with _pending_lock:
        _pending[c.id] = c
        _pending.move_to_end(c.id)
        while len(_pending) > 5000:
            _pending.popitem(last=False)
    return f"/audio/{c.id}.mp3"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    content.scenarios()  # Inhalte beim Start prüfen – Fehler sollen sofort auffallen
    speech.collect()     # Stimmen und Sprechfassung ebenso
    if PIPER_ON and os.environ.get("PRELOAD_MODEL", "1") != "0":
        models = {v.model for r in content.SPEAKERS if (v := speech.voice(None, r)) and v.engine == "piper"}

        def _load():
            for model in sorted(models):
                try:
                    tts_piper.preload(model)
                except Exception:  # ohne Netz o. ä.: dann eben Browserstimme
                    log.exception("Piper-Stimme %s nicht geladen", model)
        threading.Thread(target=_load, daemon=True).start()
    if os.environ.get("PRELOAD_MODEL", "1") != "0":
        await run_in_threadpool(classifier.get)
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def revalidate_static(request, call_next):
    """Statische Dateien immer beim Server nachfragen (ETag macht das billig).

    Ohne Cache-Control speichert der Browser sie nach eigenem Ermessen – und der Service Worker
    lädt über diesen HTTP-Cache, sodass nach Änderungen alte CSS/JS-Dateien ausgeliefert wurden.
    """
    response = await call_next(request)
    if request.method in ("GET", "HEAD") and not request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    if request.url.path.startswith("/api/") and not api_limit.hit(request.client.host if request.client else "?"):
        return JSONResponse({"error": "Zu viele Anfragen – bitte kurz warten."}, status_code=429,
                            headers=NO_STORE | {"Retry-After": "60"})
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def _invalid(_req, _exc):
    return error("Ungültige Anfrage.", 400)


@app.exception_handler(HTTPException)
async def _http(_req, exc: HTTPException):
    return error(str(exc.detail), exc.status_code)


def _run(req: RunRequest) -> engine.Run:
    scenario = content.scenarios().get(req.scenario)
    if scenario is None:
        raise HTTPException(404, "Unbekannter Fall.")
    settings = engine.Settings(callsign=req.callsign.strip(), dispatcher=req.dispatcher.strip(), tips=req.tips)
    return engine.replay(scenario, req.mode, settings, [u.model_dump() for u in req.log], classifier.get())


@app.get("/api/scenarios")
async def list_scenarios():
    return JSONResponse([{**s.meta, "dispatch_audio": audio_url(s.id, speech.dispatch_line(s))}
                         for s in content.scenarios().values()], headers={"Cache-Control": "no-cache"})


class ClipRequest(BaseModel):
    scenario: str | None = Field(default=None, max_length=100)
    who: str = Field(max_length=40)
    text: str = Field(max_length=1000)


@app.post("/api/clip")
async def find_clip(req: ClipRequest):
    """Nur Nachschlagen vorab vertonter Clips – hier wird nichts erzeugt."""
    if req.who not in content.SPEAKERS:
        raise HTTPException(400, "Unbekannter Sprecher.")
    c = speech.clip(req.scenario, content.Line(req.who, req.text))
    url = f"/audio/{c.id}.mp3" if c and c.voice.engine == "qwen" and c.id in speech.available() else None
    return JSONResponse({"audio": url}, headers={"Cache-Control": "no-cache"})


AUDIO_HEADERS = {"Cache-Control": "public, max-age=31536000, immutable"}  # Name = Hash des Inhalts


def _in_dir(base: Path, filename: str) -> Path | None:
    """Pfad zu filename in base – nur, wenn er nach dem Auflösen wirklich in base liegt."""
    root = os.path.realpath(base)
    full = os.path.realpath(os.path.join(root, filename))
    return Path(full) if full.startswith(root + os.sep) else None


@app.get("/audio/{name}", include_in_schema=False)
async def audio(name: str):
    m = re.fullmatch(r"([0-9a-f]{20})\.mp3", name)
    if not m:
        raise HTTPException(404, "Kein Clip.")
    cid = m[1]
    if (pre := speech.available().get(cid)) is not None:  # Pfad aus dem Verzeichnislisting, nicht aus der URL
        return FileResponse(pre, media_type="audio/mpeg", headers=AUDIO_HEADERS)
    with _pending_lock:
        c = _pending.get(cid)
    cached = _in_dir(tts_piper.CACHE_DIR, f"{cid}.mp3")
    have_cached = cached is not None and cached.is_file()
    if c is None and not have_cached:
        raise HTTPException(404, "Kein Clip.")
    try:
        path = cached if have_cached else await run_in_threadpool(tts_piper.render, c)
    except Exception:
        log.exception("Piper-Clip %s fehlgeschlagen", cid)
        raise HTTPException(503, "Clip gerade nicht verfügbar.")
    return FileResponse(path, media_type="audio/mpeg", headers=AUDIO_HEADERS)


@app.post("/api/turn")
async def turn(req: RunRequest):
    run = await run_in_threadpool(_run, req)
    last = run.turns[-1]
    return JSONResponse({
        "lines": [{"who": l.who, "text": l.text, "audio": audio_url(req.scenario, l)} for l in last.lines],
        "ended": run.ended,
        "next_event_at": run.next_event_at,
        "intents": [h.intent for h in last.hits],
    }, headers=NO_STORE)


@app.post("/api/debrief")
async def debrief(req: RunRequest):
    run = await run_in_threadpool(_run, req)
    result = evaluate.evaluate(run, classifier.get().embedder)
    return JSONResponse({"result": result, "text": evaluate.as_text(result)}, headers=NO_STORE)


@lru_cache
def _solution(sid: str) -> dict:
    # deterministisch: einmal nachspielen, dann aus dem Speicher (die Inhalte ändern sich nur mit einem Neustart)
    return solutions.transcript(sid, classifier.get(), classifier.get().embedder)


@app.get("/api/solutions")
async def list_solutions():
    """Musterlösungen – bewusst ohne Lösungsinhalt, die gibt es erst pro Fall (Spoiler)."""
    out = []
    for sid, s in content.scenarios().items():
        if sid in solutions.solutions():
            out.append({k: s.meta.get(k) for k in ("id", "group", "letter", "title", "teaser")})
    return JSONResponse(out, headers={"Cache-Control": "no-cache"})


@app.get("/api/solutions/{sid}")
async def get_solution(sid: str):
    if sid not in solutions.solutions() or sid not in content.scenarios():
        raise HTTPException(404, "Keine Musterlösung zu diesem Fall.")
    return JSONResponse(await run_in_threadpool(_solution, sid), headers={"Cache-Control": "no-cache"})


@app.get("/sw.js", include_in_schema=False)
async def service_worker():
    return FileResponse(PUBLIC_DIR / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")
