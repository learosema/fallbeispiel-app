"""Sprachausgabe: welcher Satz mit welcher Stimme, in welcher Sprechfassung und unter welchem Clip-Namen.

Gemeinsame Grundlage für den Server (Clip-URL pro Antwortzeile) und für tools/tts (Casting und Vertonung).
Stimmen und Ersetzungsregeln stehen in content/voices.yaml, die Stimmen für Patient/Umstehende im jeweiligen Fall.

Clip-Namen sind ein Hash aus Stimme und gesprochenem Text: Ändert sich ein Text oder eine Stimmbeschreibung, entsteht ein
neuer Name, und der alte Clip wird einfach nicht mehr benutzt (tools/tts/render.py --prune räumt auf).
"""
from __future__ import annotations

import dataclasses
import hashlib
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Iterable, Iterator

import yaml

from . import content
from .content import Line, Scenario

ROOT = Path(__file__).resolve().parent.parent
AUDIO_DIR = ROOT / "audio"
CLIPS_DIR = AUDIO_DIR / "clips"     # vorab vertont, im Repo: <id>.mp3
VOICES_DIR = AUDIO_DIR / "voices"   # Referenzclips aus dem Casting: <key>.wav + <key>.txt
FORMAT = "1"  # hochzählen, wenn sich etwas an der Vertonung ändert, das alle Clips betrifft

# Wörter in Großbuchstaben, die gesprochen ein Wort sind (nicht buchstabiert, nicht „gerufen“)
WORDS = {"NEF": "Neff", "DOM": "Dom"}
LETTERS = {"A": "A", "B": "Be", "C": "Ze", "D": "De", "E": "E", "F": "Eff", "G": "Ge", "H": "Ha", "I": "I", "J": "Jott",
           "K": "Ka", "L": "El", "M": "Em", "N": "En", "O": "O", "P": "Pe", "Q": "Ku", "R": "Er", "S": "Ess", "T": "Te",
           "U": "U", "V": "Fau", "W": "We", "X": "Ix", "Y": "Üpsilon", "Z": "Zett", "Ä": "Ä", "Ö": "Ö", "Ü": "Ü"}


@dataclass(frozen=True)
class Voice:
    key: str            # Dateiname der Referenz bzw. Teil des Clip-Hashes, z. B. "kollege-3fa2c1"
    role: str
    engine: str         # "qwen" (vorab vertont) | "piper" (auf dem Server, auf Zuruf)
    design: str = ""    # Beschreibung für Qwen VoiceDesign
    model: str = ""     # Piper-Stimme
    filter: str = ""    # z. B. "funk-leicht"
    scenario: str = ""  # leer = gilt in allen Fällen


@dataclass(frozen=True)
class Clip:
    id: str
    voice: Voice
    text: str           # Sprechfassung, so wird es gesprochen


def _h(s: str, n: int = 6) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:n]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


@cache
def config() -> dict[str, Any]:
    data = yaml.safe_load((content.CONTENT_DIR / "voices.yaml").read_text(encoding="utf-8"))
    rules = []
    for n, rule in enumerate(data.get("sprechfassung") or []):
        if not (isinstance(rule, list) and len(rule) == 2):
            raise ValueError(f"voices.yaml: sprechfassung[{n}] braucht [Regex, Ersatz]")
        rules.append((re.compile(rule[0]), rule[1]))
    data["_rules"] = rules
    for role in data.get("roles") or {}:
        if role not in content.SPEAKERS:
            raise ValueError(f"voices.yaml: unbekannte Rolle {role!r}")
    return data


@cache
def _scenario_voices() -> dict[str, dict[str, str]]:
    """voices: aus den Fällen. Eigenes Laden, damit content.Scenario unverändert bleibt."""
    out = {}
    for path in sorted((content.CONTENT_DIR / "scenarios").glob("*.yaml")):
        d = yaml.safe_load(path.read_text(encoding="utf-8"))
        v = d.get("voices") or {}
        for role in v:
            if role not in ("Patient", "Umstehende", "reference"):
                raise ValueError(f"{path.name}: voices: nur Patient, Umstehende und reference, nicht {role!r}")
        for role in v.get("reference") or {}:
            if role not in v:
                raise ValueError(f"{path.name}: voices.reference.{role}: dafür gibt es keine Stimme")
        out[d["id"]] = v
    return out


def voice(scenario_id: str | None, role: str) -> Voice | None:
    if role in ("Patient", "Umstehende"):
        design = _scenario_voices().get(scenario_id or "", {}).get(role)
        if not design:
            return None
        return Voice(f"{scenario_id}.{_slug(role)}-{_h(design)}", role, "qwen", design=design, scenario=scenario_id or "")
    d = (config().get("roles") or {}).get(role)
    if not d:
        return None
    if d.get("engine") == "piper":
        model, flt = d["model"], d.get("filter", "")
        return Voice(f"{_slug(role)}-piper-{_h(model + flt)}", role, "piper", model=model, filter=flt)
    return Voice(f"{_slug(role)}-{_h(d['design'])}", role, "qwen", design=d["design"])


def spoken(line: Line) -> tuple[str, str] | None:
    """Was vorgelesen wird und von wem (wie bisher im Frontend):
    - eine reine Handlung in Klammern erzählt der Befund: „Kollege: (übernimmt die HWS)“ → „Kollege übernimmt die HWS“
    - Tonangaben neben gesprochenem Text entfallen: „(aufgelöst) Er ist umgefallen!“ → „Er ist umgefallen!“
    """
    text = re.sub(r"[*_#`]", "", line.text.strip())
    action = re.fullmatch(r"\(([^)]*)\)\.?", text)
    if action:
        return ("Befund", action[1] if line.who == "Befund" else f"{line.who} {action[1]}")
    text = re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", "", text)).strip()
    text = re.sub(r"\s+([.,!?;:…])", r"\1", text).strip('"').strip()  # „ein (…).“ → „ein.“
    return (line.who, text) if re.search(r"\w", text) else None


def _spell(word: str) -> str:
    return " ".join(LETTERS.get(ch.upper(), ch) for ch in word)


def for_engine(text: str, engine: str) -> str:
    """Sprechfassung. Qwen liest Buchstaben-Abkürzungen englisch → ausschreiben (Regeln aus voices.yaml).
    Piper buchstabiert deutsch korrekt → nur buchstabieren lassen, wo es sonst ein Wort läse („EVT1“ → „E Fau Te 1“)."""
    text = re.sub(r"([a-zäöü])([A-ZÄÖÜ][a-zäöü])", r"\1 \2", text)  # „RotkreuzHamburg“ → „Rotkreuz Hamburg“ (nicht „SpO2“)
    if engine == "qwen":
        for rx, repl in config()["_rules"]:
            text = rx.sub(repl, text)
        # Übrige Großbuchstaben-Wörter sind Rufe („MARKUS!“) oder Wörter („DOM“) – normal schreiben
        text = re.sub(r"\b[A-ZÄÖÜ]{2,}\b", lambda m: WORDS.get(m[0], m[0].capitalize()), text)
    else:
        text = re.sub(r"\b([A-ZÄÖÜ]{2,4})(\d*)\b",
                      lambda m: (WORDS.get(m[1]) or _spell(m[1])) + (f" {m[2]}" if m[2] else ""), text)
    return re.sub(r"\s+", " ", text).strip()


def clip(scenario_id: str | None, line: Line) -> Clip | None:
    sp = spoken(line)
    if sp is None:
        return None
    role, text = sp
    v = voice(scenario_id, role)
    if v is None:
        return None
    text = for_engine(text, v.engine)
    return Clip(_h(f"{FORMAT}|{v.key}|{text}", 20), v, text)


# ---------- Alle Sätze, die vorkommen können (fürs Vorab-Vertonen) ----------

# Texte, die das Frontend selbst vorliest (public/app.js); ein Test prüft, dass es sie dort noch gibt
UI_LINES = [
    Line("Befund", "Du triffst mit deinem Kollegen ein. Übe die 1. Minute nach SANmemo bis zum Funkspruch."),
    Line("Befund", "Du triffst mit deinem Kollegen ein. Beginne mit der 1. Minute, danach geht der Einsatz weiter."),
] + [Line("Befund", f"Algorithmus {v}.") for v in ("Erfüllt", "Teilweise erfüllt", "Nicht erfüllt")]


def dispatch_line(scenario: Scenario) -> Line:
    return Line("Befund", re.sub(r"^Einsatzmeldung:\s*", "Einsatzmeldung: ", scenario.meta.get("dispatch", "")))


def _walk(obj: Any, seen: set[int] | None = None) -> Iterator[Line]:
    seen = set() if seen is None else seen
    if id(obj) in seen:
        return
    seen.add(id(obj))
    if isinstance(obj, Line):
        yield obj
    elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            yield from _walk(getattr(obj, f.name), seen)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k == "tip" and isinstance(v, str):  # Tipps des Kollegen in algorithm.yaml
                yield Line("Kollege", v.strip())
            else:
                yield from _walk(v, seen)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for v in obj:
            yield from _walk(v, seen)


def _engine_literals() -> Iterator[Line]:
    """Feste Sätze im Code (Line("Wer", "Text") in backend/*.py)."""
    for path in sorted((ROOT / "backend").glob("*.py")):
        for who, text in re.findall(r'Line\("(\w+)",\s*"((?:[^"\\]|\\.)*)"\)', path.read_text(encoding="utf-8")):
            if who in content.SPEAKERS and "{" not in text:
                yield Line(who, text)


def collect() -> list[Clip]:
    """Alle vorab zu vertonenden Clips (nur Qwen-Stimmen), eindeutig nach id."""
    common = list(_walk([content.smalltalk(), content.intents(), content.algorithm()])) + list(_engine_literals()) + UI_LINES
    out: dict[str, Clip] = {}
    for sid, s in content.scenarios().items():
        for line in [dispatch_line(s), *_walk(s), *common]:
            c = clip(sid, line)
            if c and c.voice.engine == "qwen":
                out.setdefault(c.id, c)
    return list(out.values())


def voices_in_use(clips: Iterable[Clip]) -> list[Voice]:
    seen: dict[str, Voice] = {}
    for c in clips:
        seen.setdefault(c.voice.key, c.voice)
    return list(seen.values())


def reference_text(v: Voice, max_chars: int = 220) -> str:
    """Referenzsatz fürs Casting: echte Zeilen der Rolle aus dem eigenen Fall (längste zuerst), sonst der Satz aus
    voices.yaml. Die Referenz prägt Klang und Stimmung aller geklonten Sätze – deshalb nur fallspezifische Zeilen."""
    fixed = (config().get("reference") or {}).get(v.role)
    if v.scenario == "" and fixed:
        return for_engine(fixed, v.engine)
    own_ref = (_scenario_voices().get(v.scenario, {}).get("reference") or {}).get(v.role)
    if own_ref:  # im Fall vorgegeben (voices: reference: Patient: …)
        return for_engine(own_ref, v.engine)
    s = content.scenarios().get(v.scenario)
    own_clips = [c for c in (clip(v.scenario, l) for l in _walk(s)) if c and c.voice.key == v.key] if s else []
    # Was beim Casting stört: Fremdwörter ziehen die ganze Stimme ins Englische („Steak“, „Spray“), Fragen und „…“
    # geben ihr eine steigende Satzmelodie. Solche Zeilen nur nehmen, wenn es nichts anderes gibt.
    avoid = re.compile(r"\b(" + "|".join(map(re.escape, config().get("reference_avoid") or [])) + r")", re.I) \
        if config().get("reference_avoid") else None

    def badness(t: str) -> int:
        pauses = t.count("…") + t.count("...")
        return (10 if avoid and avoid.search(t) else 0) + 3 * t.count("?") + pauses - (t.rstrip()[-1:] in ".!" and not t.endswith("..."))

    own = sorted({c.text for c in own_clips if len(c.text) > 25}, key=lambda t: (badness(t), -len(t)))
    out, said = "", set()
    for t in own:
        sentences = {x.strip() for x in re.split(r"(?<=[.!?])\s+", t) if x.strip()}
        # Wiederholung auch bei ähnlichen Sätzen („Keine Ahnung.“ / „Keine Ahnung, ich …“): erste zwei Wörter vergleichen
        starts = {" ".join(re.findall(r"\w+", x.lower())[:2]) for x in sentences}
        if len(out) + len(t) + 1 > max_chars or sentences & said or starts & said:
            continue  # zu lang oder wiederholt sich
        if out and avoid and avoid.search(t):
            continue  # Fremdwörter nur, wenn es sonst gar nichts gibt
        if out and "?" in t:
            continue  # Fragen färben die Satzmelodie – nur, wenn es nichts anderes gibt
        if len(out) >= 80 and badness(t) > 0:
            break  # genug sauberes Material – Fragen/„…“ nicht noch dazunehmen
        out = f"{out} {t}".strip()
        said |= sentences | starts
    return out or for_engine(fixed or "Hallo, hier bin ich.", v.engine)


@cache
def available() -> dict[str, Path]:
    """Vorab vertonte Clips, die da sind: id → Datei. Der Server nimmt Pfade nur von hier, nie aus der Anfrage."""
    return {p.stem: p for p in CLIPS_DIR.glob("*.mp3")} if CLIPS_DIR.is_dir() else {}
