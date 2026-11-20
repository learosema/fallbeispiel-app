"""FastAPI-Backend: liefert das Frontend aus public/ und spielt die Fallbeispiele.

  GET  /api/scenarios   Liste der Fälle (ohne verborgene Fakten)
  POST /api/turn        Protokoll → Antwort der Simulation auf die letzte Äußerung
  POST /api/debrief     Protokoll → regelbasierte Checkliste
  POST /api/feedback    Protokoll → KI-Bewertung (Algorithmus + Patientensicht)

Umgebungsvariablen: siehe README.md (ACCESS_CODE, INTENT_*, JUDGE_*, LLM_*).
"""
from __future__ import annotations

import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import classifier, content, engine, evaluate, judge

PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"
NO_STORE = {"Cache-Control": "no-store"}


class Utterance(BaseModel):
    t: float = Field(ge=0, le=24 * 3600)
    text: str = Field(min_length=1, max_length=1000)


class RunRequest(BaseModel):
    scenario: str = Field(max_length=100)
    mode: Literal["minute", "full"] = "minute"
    callsign: str = Field(default="EVT1", min_length=1, max_length=40)
    dispatcher: str = Field(default="RotkreuzHamburg", min_length=1, max_length=60)
    log: list[Utterance] = Field(min_length=1, max_length=300)


def error(msg: str, status: int) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=status, headers=NO_STORE)


def check_access(x_access_code: str = Header(default="")) -> None:
    code = os.environ.get("ACCESS_CODE", "")
    if code and not hmac.compare_digest(x_access_code.encode(), code.encode()):
        raise HTTPException(401, "Zugangscode fehlt oder ist falsch.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    content.scenarios()  # Inhalte beim Start prüfen – Fehler sollen sofort auffallen
    if os.environ.get("PRELOAD_MODEL", "1") != "0":
        await run_in_threadpool(classifier.get)
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


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
    settings = engine.Settings(callsign=req.callsign.strip(), dispatcher=req.dispatcher.strip())
    return engine.replay(scenario, req.mode, settings, [u.model_dump() for u in req.log], classifier.get())


@app.get("/api/scenarios")
async def list_scenarios():
    return JSONResponse([s.meta for s in content.scenarios().values()], headers={"Cache-Control": "no-cache"})


@app.post("/api/turn", dependencies=[Depends(check_access)])
async def turn(req: RunRequest):
    run = await run_in_threadpool(_run, req)
    last = run.turns[-1]
    return JSONResponse({
        "lines": [{"who": l.who, "text": l.text} for l in last.lines],
        "ended": run.ended,
        "intents": [h.intent for h in last.hits],
    }, headers=NO_STORE)


@app.post("/api/debrief", dependencies=[Depends(check_access)])
async def debrief(req: RunRequest):
    run = await run_in_threadpool(_run, req)
    result = evaluate.evaluate(run)
    return JSONResponse({"result": result, "text": evaluate.as_text(result)}, headers=NO_STORE)


@app.post("/api/feedback", dependencies=[Depends(check_access)])
async def feedback(req: RunRequest):
    run = await run_in_threadpool(_run, req)
    result = evaluate.evaluate(run)
    try:
        text = await run_in_threadpool(judge.judge, run, result)
    except judge.JudgeError as exc:
        return error(f"KI-Bewertung fehlgeschlagen: {exc}", 502)
    return JSONResponse({"text": text or judge.fallback(result), "ai": text is not None, "provider": judge.provider()}, headers=NO_STORE)


@app.get("/sw.js", include_in_schema=False)
async def service_worker():
    return FileResponse(PUBLIC_DIR / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")
