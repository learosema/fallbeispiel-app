"""FastAPI-Backend: liefert das Frontend aus public/ und beantwortet /api/chat mit einem lokalen LLM.

Umgebungsvariablen:
  LLM_MODEL        Hugging-Face-Modell-ID (Standard: Qwen/Qwen2.5-1.5B-Instruct)
  LLM_DEVICE       cpu | cuda (Standard: automatisch)
  LLM_TEMPERATURE  Standard: 0.7
  ACCESS_CODE      optional; der Browser sendet ihn als Header x-access-code
  PRELOAD_MODEL    "0" lädt das Modell erst bei der ersten Anfrage (Standard: beim Start)
"""
import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header
from fastapi.exceptions import RequestValidationError
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import llm

MAX_MESSAGES = 80
MAX_TOTAL_CHARS = 80_000
MAX_TOKENS_CAP = 1200
PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=MAX_MESSAGES)
    max_tokens: int | None = None


def error(msg: str, status: int) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=status, headers={"Cache-Control": "no-store"})


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.environ.get("PRELOAD_MODEL", "1") != "0":
        await run_in_threadpool(llm.load)
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.exception_handler(RequestValidationError)
async def _invalid(_req, _exc):
    return error("Ungültige Anfrage.", 400)


@app.post("/api/chat")
async def chat(req: ChatRequest, x_access_code: str = Header(default="")):
    code = os.environ.get("ACCESS_CODE", "")
    if code and not hmac.compare_digest(x_access_code.encode(), code.encode()):
        return error("Zugangscode fehlt oder ist falsch.", 401)

    if sum(len(m.content) for m in req.messages) > MAX_TOTAL_CHARS:
        return error("Anfrage zu groß.", 413)

    max_tokens = min(max(req.max_tokens or 300, 1), MAX_TOKENS_CAP)
    try:
        content = await run_in_threadpool(llm.generate, [m.model_dump() for m in req.messages], max_tokens)
    except Exception as exc:  # noqa: BLE001
        return error(f"Lokales Modell fehlgeschlagen: {exc}", 500)
    return JSONResponse({"content": content}, headers={"Cache-Control": "no-store"})


@app.get("/sw.js", include_in_schema=False)
async def service_worker():
    return FileResponse(PUBLIC_DIR / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")
