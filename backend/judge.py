"""KI-Bewertung am Ende des Einsatzes: ganzer Dialog + regelbasierte Checkliste → Feedback.

JUDGE_PROVIDER:
  auto        claude-cli, wenn `claude` im PATH liegt, sonst none (Standard)
  claude-cli  `claude -p` (nutzt das eigene Claude-Abo, gut für lokale Tests)
  anthropic   Anthropic API (ANTHROPIC_API_KEY), Standardmodell claude-haiku-5-5
  openai      OpenAI-kompatible API (OPENAI_API_KEY, optional OPENAI_BASE_URL – z. B. Ollama)
  local       lokales Modell über transformers (LLM_MODEL)
  none        keine KI, nur die regelbasierte Auswertung
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

from .content import algorithm
from .engine import Run
from .evaluate import as_text, transcript

PROVIDER = os.environ.get("JUDGE_PROVIDER", "auto").strip().lower()
MODEL = os.environ.get("JUDGE_MODEL", "").strip()
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
TIMEOUT = float(os.environ.get("JUDGE_TIMEOUT", "180"))


def provider() -> str:
    if PROVIDER == "auto":
        return "claude-cli" if shutil.which(CLAUDE_BIN) else "none"
    return PROVIDER


SYSTEM = """Du bewertest ein Fallbeispiel-Training im Sanitätsdienst (DRK, Ausbildung). Eine Sanitäterin bzw. ein Sanitäter in Ausbildung hat per Sprache einen simulierten Einsatz durchgespielt. Patient, Kollege, Umstehende und Leitstelle wurden von einem regelbasierten System gespielt – bewerte nur die Äußerungen der Sanitäter:in, nicht die Simulation.

Bewerte zwei Dinge:
1. Wurde der Algorithmus (xABCDE nach DRK-SANmemo, siehe Referenz) eingehalten: vollständig, in der richtigen Reihenfolge, mit den richtigen Inhalten, kritische Probleme sofort behandelt? Zeit ist nachrangig.
   Achte auch auf die Befundsprache – aber nur bei Befunden, die die Sanitäter:in selbst mitteilt (z. B. in Teambesprechung, Funkspruch, Übergabe oder Zusammenfassungen). Fragen und angesagte Untersuchungen („Puls?“, „Rekap?“, „Ich messe den Blutdruck“) sind richtig so; die Werte liefert dann die Simulation. Mitgeteilte Befunde sollen konkret benannt werden („Puls regelmäßig, gut/schlecht/nicht tastbar“, „Puls schnell“, „Rekap unter 2 s“, „Rekap verzögert“, „Haut blass, kaltschweißig“) statt nur „normal“, „unauffällig“ oder „ok“. Ausnahme: „normale Atmung“ bei der Atemkontrolle Bewusstloser ist der Begriff des Algorithmus.
2. Wie hat sich der Patient behandelt gefühlt? Versetze dich in die betroffene Person: Hat man sich vorgestellt, sie ernst genommen, Maßnahmen angekündigt und erklärt, beruhigt, respektvoll und verständlich gesprochen, an Wärme und Würde gedacht? Bei Bewusstlosen: Wie würden Angehörige/Umstehende das Auftreten erleben?

Du bekommst eine automatisch erstellte Checkliste. Sie beruht auf Stichwort- und Intent-Erkennung und kann Umschreibungen übersehen oder Fehltreffer enthalten. Wo sie dem Gesprächsverlauf widerspricht, gilt der Gesprächsverlauf.

REFERENZ-ALGORITHMUS:
{reference}

Antworte auf Deutsch, nüchtern und wohlwollend, in du-Form, ohne Markdown-Sternchen und ohne Überschriften außer diesen. Nutze genau dieses Format:

ALGORITHMUS: <Erfüllt / Teilweise erfüllt / Nicht erfüllt>
<2–4 Sätze: Was lief nach Algorithmus, was fehlte oder kam in falscher Reihenfolge? Zitiere kurz, wo es hilft.>

PATIENTENSICHT: <2–4 Sätze aus Sicht der betroffenen Person, gern in Ich-Form, z. B. „Ich habe mich …“>

GUT GEMACHT: <1–2 Punkte>
VERBESSERN: <1–3 konkrete Punkte>"""


def build_prompt(run: Run, checklist: dict) -> tuple[str, str]:
    s = run.scenario
    system = SYSTEM.replace("{reference}", algorithm()["reference"].strip())
    notes = s.notes
    user = f"""FALL: {s.meta['title']} ({'nur 1. Minute' if run.mode == 'minute' else 'ganzer Fall'})
{s.meta['dispatch']}
{('HINWEISE ZUM FALL: ' + notes) if notes else ''}
Funkrufnamen: eigenes Team „{run.settings.callsign}“, Leitstelle „{run.settings.dispatcher}“.

AUTOMATISCHE CHECKLISTE:
{as_text(checklist)}

GESPRÄCHSVERLAUF (Nettozeit der Sanitäter:in in eckigen Klammern):
{transcript(run)}"""
    return system, user


class JudgeError(RuntimeError):
    pass


def _claude_cli(system: str, user: str) -> str:
    cmd = [CLAUDE_BIN, "-p", "--model", MODEL or "haiku", "--tools", "", "--system-prompt", system,
           "--no-session-persistence", "--output-format", "text"]
    try:
        # eigenes leeres Arbeitsverzeichnis, damit keine Projekt-Dateien (CLAUDE.md …) in den Kontext geraten
        with tempfile.TemporaryDirectory() as cwd:
            res = subprocess.run(cmd, input=user, capture_output=True, text=True, timeout=TIMEOUT, cwd=cwd)
    except FileNotFoundError as exc:
        raise JudgeError(f"`{CLAUDE_BIN}` nicht gefunden.") from exc
    except subprocess.TimeoutExpired as exc:
        raise JudgeError("Zeitüberschreitung bei `claude -p`.") from exc
    if res.returncode != 0:
        raise JudgeError(f"`claude -p` fehlgeschlagen: {(res.stderr or res.stdout).strip()[:300]}")
    return res.stdout


def _anthropic(system: str, user: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    try:
        msg = client.messages.create(
            model=MODEL or "claude-haiku-5-5",
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.AuthenticationError as exc:
        raise JudgeError("Anthropic: API-Key ungültig oder fehlt (ANTHROPIC_API_KEY).") from exc
    except anthropic.RateLimitError as exc:
        raise JudgeError("Anthropic: Rate-Limit erreicht, bitte später erneut versuchen.") from exc
    except anthropic.APIStatusError as exc:
        raise JudgeError(f"Anthropic: HTTP {exc.status_code}: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise JudgeError("Anthropic nicht erreichbar.") from exc
    if msg.stop_reason == "refusal":
        raise JudgeError("Anthropic: Anfrage abgelehnt.")
    return "".join(b.text for b in msg.content if b.type == "text")


def _openai(system: str, user: str) -> str:
    import openai

    client = openai.OpenAI()  # liest OPENAI_API_KEY und OPENAI_BASE_URL
    try:
        res = client.chat.completions.create(
            model=MODEL or "gpt-5-nano",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_completion_tokens=4000,
        )
    except openai.APIStatusError as exc:
        raise JudgeError(f"OpenAI-API: HTTP {exc.status_code}: {exc.message}") from exc
    except openai.APIConnectionError as exc:
        raise JudgeError("OpenAI-API nicht erreichbar.") from exc
    return res.choices[0].message.content or ""


def _local(system: str, user: str) -> str:
    from . import llm

    return llm.generate([{"role": "system", "content": system}, {"role": "user", "content": user}], 700)


PROVIDERS = {"claude-cli": _claude_cli, "anthropic": _anthropic, "openai": _openai, "local": _local}


def judge(run: Run, checklist: dict) -> str | None:
    """Liefert das KI-Feedback oder None, wenn keine KI konfiguriert ist."""
    p = provider()
    if p == "none":
        return None
    if p not in PROVIDERS:
        raise JudgeError(f"Unbekannter JUDGE_PROVIDER {p!r} (erlaubt: auto, {', '.join(PROVIDERS)}, none).")
    system, user = build_prompt(run, checklist)
    text = PROVIDERS[p](system, user).strip()
    if not text:
        raise JudgeError("Die KI hat keine Antwort geliefert.")
    return text


def fallback(checklist: dict) -> str:
    """Kurzer Feedback-Text aus der Checkliste, wenn keine KI verfügbar ist."""
    good = "; ".join(checklist["praise"]) or "–"
    better = "; ".join(checklist["improve"]) or "nichts Wesentliches"
    return f"GUT GEMACHT: {good}\nVERBESSERN: {better}\n\n(Keine KI-Bewertung konfiguriert – siehe JUDGE_PROVIDER.)"
