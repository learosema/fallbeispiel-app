"""Expertensystem für den Einsatz: Intents → hardcodierte Antworten je Fallbeispiel.

Der Server ist zustandslos: Der Browser schickt bei jeder Äußerung das ganze Protokoll
(Text + Nettozeit). Die Engine spielt es deterministisch nach und liefert die Antwort auf
die letzte Äußerung. Dieselbe Wiederholung dient später als Grundlage der Auswertung.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from .classifier import Hit, normalize
from .content import Line, Scenario, Variant, intents

ARRIVAL_SECONDS = 480  # Rettungsdienst trifft ca. 8 Minuten nach der Nachforderung ein
FALLBACK = Line("Kollege", "Was genau machst du?")
# Erkannt, aber der Fall hat keine Antwort: lieber nachfragen als einen Befund erfinden.
UNHANDLED = Line("Kollege", "Was genau meinst du?")

RESOURCES = [  # (Kürzel, Muster) in der Reihenfolge, in der die Leitstelle sie wiederholt
    ("RTW", r"\brtw\b|rettungswagen|rettungsdienst"),
    ("NEF", r"\bnef\b|notarzt|notärzt|notarzteinsatzfahrzeug"),
    ("KTW", r"\bktw\b|krankentransport"),
    ("Polizei", r"polizei|streife"),
    ("Feuerwehr", r"feuerwehr|\bhlf\b"),
]
_NUMBERS = {"null": "0", "eins": "1", "zwei": "2", "drei": "3", "vier": "4", "fünf": "5", "fuenf": "5",
            "sechs": "6", "sieben": "7", "acht": "8", "neun": "9"}


class Classifier(Protocol):
    def classify(self, raw: str) -> list[Hit]: ...


@dataclass
class Settings:
    callsign: str = "EVT1"
    dispatcher: str = "RotkreuzHamburg"


@dataclass
class Turn:
    t: float
    text: str
    hits: list[Hit]
    lines: list[Line]
    funk: dict[str, Any] | None = None
    unhandled: list[str] = field(default_factory=list)


@dataclass
class Run:
    scenario: Scenario
    mode: str
    settings: Settings
    turns: list[Turn]
    state: dict[str, Any]
    first: dict[str, tuple[int, int]]       # Intent → (Äußerung, Position) des ersten Auftretens
    first_t: dict[str, float]
    ended: bool
    next_event_at: float | None = None      # Nettozeit, zu der das nächste Ereignis fällig wird (für den Takt im Browser)
    fired: list[tuple[int, int]] = field(default_factory=list)  # ausgelöste Ereignisse: (Index in scenario.events, Äußerung)
    ended_at: int | None = None             # Äußerung, mit der der Einsatz endete („1. Minute beendet“, Übergabe)


def compact(text: str) -> str:
    t = normalize(text)
    t = re.sub(r"\b(" + "|".join(_NUMBERS) + r")\b", lambda m: _NUMBERS[m.group(1)], t)
    return re.sub(r"[^a-z0-9äöü]", "", t)


def detect_resources(text: str) -> list[str]:
    t = normalize(text)
    return [name for name, pat in RESOURCES if re.search(pat, t)]


def _fill(text: str, s: Settings) -> str:
    return text.replace("{callsign}", s.callsign).replace("{dispatcher}", s.dispatcher)


def matches(when: dict[str, Any], state: dict[str, Any]) -> bool:
    for key, want in when.items():
        have = state.get(key, False)
        if isinstance(want, list):
            if have not in want:
                return False
        elif have != want:
            return False
    return True


def pick(variants: list[Variant], state: dict[str, Any]) -> Variant | None:
    return next((v for v in variants if matches(v.when, state)), None)


def respond(scenario: Scenario, iid: str, state: dict[str, Any]) -> Variant | None:
    """Antwort auf einen Intent, in dieser Reihenfolge:
    1. Antwort des Falls  2. bei Bewusstlosigkeit die allgemeine Antwort dafür („keine Reaktion“)
    3. Antwort des Falls auf einen Ausweich-Intent („Atmung?“ → Atemkontrolle)  4. Standardantwort des Intents."""
    cat = intents()
    it = cat[iid]
    v = pick(scenario.responses.get(iid, []), state)
    if v is None and not scenario.conscious:
        v = pick(it.unconscious, state)
    for alt in it.fallback:
        if v is not None:
            break
        v = pick(scenario.responses.get(alt, []), state)
    return v or pick(it.default, state)


# ---------- Funk ----------

def funk(text: str, s: Settings, state: dict[str, Any], mode: str) -> tuple[list[Hit], list[Line], dict[str, Any]] | None:
    t = normalize(text)
    c = compact(text)
    has_disp = compact(s.dispatcher) in c
    has_call = compact(s.callsign) in c
    kommen = bool(re.search(r"\bkommen\b", t))
    ende = bool(re.search(r"\bende\W*$", t)) and (has_call or state.get("funk_offen"))
    resources = detect_resources(text)
    in_funk = has_disp or (has_call and (kommen or ende)) or (state.get("funk_offen") and (kommen or ende or resources))
    if not in_funk:
        return None

    meldung = bool(resources) or bool(re.search(r"verdacht|patient|männlich|weiblich|\bmann\b|\bfrau\b|jahre|\bjahrig", t))
    anruf = has_disp and not (meldung and state.get("funk_offen"))
    info = {
        "text": text, "anruf": anruf, "beide_rufnamen": has_disp and has_call, "meldung": meldung,
        "resources": resources, "kommen": kommen, "ende": ende, "ende_mit_rufname": ende and has_call,
        "anruf_und_meldung_zusammen": anruf and meldung,
        "patient": bool(re.search(r"patient|männlich|weiblich|\bmann\b|\bfrau\b|junge|mädchen|kind|person", t)),
        # ungefähr reicht: „älterer Mann“, „junge Frau“, „mittleren Alters“, „Mitte vierzig“, „68“
        "alter": bool(re.search(r"\d+|jahre|\bjahrig|mitte|anfang|ende (zwanzig|dreißig|dreissig|vierzig|fünfzig|fuenfzig|sechzig|siebzig|achtzig)"
                                r"|\bält|\balt\b|\bjung|jugendlich|mittleren alters|senior|kind|säugling|erwachsen", t)),
        "verdacht": bool(re.search(r"verdacht|vermutlich|wahrscheinlich|\bv\s?a\b", t)),
    }
    hits: list[Hit] = []
    lines: list[Line] = []
    if anruf:
        hits.append(Hit("funk_anruf", 0, 1.0, "funk"))
        state["funk_offen"] = True
    if meldung:
        hits.append(Hit("funk_meldung", 1, 1.0, "funk"))
        if resources:
            hits.append(Hit("nachforderung", 2, 1.0, "funk"))
            lines.append(Line("Leitstelle", " ".join(resources) + " kommt, verstanden."))
        else:
            lines.append(Line("Leitstelle", "Verstanden."))
    elif anruf:
        lines.append(Line("Leitstelle", f"Hier {s.dispatcher}."))
    if ende:
        hits.append(Hit("funk_ende", 3, 1.0, "funk"))
        state["funk_offen"] = False
        if mode == "minute" and not state.get("_beendet"):
            lines.append(Line("Befund", "Die 1. Minute ist beendet. Du kannst die Auswertung starten."))
            state["_beendet"] = True
    if not lines and not ende:
        lines.append(Line("Leitstelle", "Wiederholen."))
    return hits, lines, info


# ---------- Wiederholung des Einsatzes ----------

def replay(scenario: Scenario, mode: str, settings: Settings, log: list[dict[str, Any]], clf: Classifier) -> Run:
    catalogue = intents()
    state: dict[str, Any] = dict(scenario.state)
    first: dict[str, tuple[int, int]] = {}
    first_t: dict[str, float] = {}
    fired: dict[int, int] = {}  # Ereignis → wie oft schon ausgelöst
    fired_log: list[tuple[int, int]] = []
    ended_at: int | None = None
    turns: list[Turn] = []

    def apply(v: Variant, t: float) -> None:
        state.update(v.set)
        for key, val in v.set.items():  # gesetzte Flags merken, damit Ereignisse `since: <flag>` nutzen können
            if val and key not in first_t:
                first_t[key] = t

    for n, entry in enumerate(log):
        t, text = float(entry.get("t", 0)), str(entry.get("text", ""))
        tick = bool(entry.get("tick"))  # Takt ohne Äußerung: nur die Zeit ist fortgeschritten
        lines: list[Line] = []
        unhandled: list[str] = []
        f = None if tick else funk(text, settings, state, mode)
        if tick:
            hits, info = [], None
        elif f:
            # Während eines Funkspruchs zählt nur der Funk – „Verdacht auf …“ ist dann keine Teambesprechung.
            hits, funk_lines, info = f
            lines += funk_lines
        else:
            hits, info = clf.classify(text), None
            for h in hits:
                if h.source == "implied":
                    continue
                v = respond(scenario, h.intent, state)
                if v is None:
                    unhandled.append(h.intent)
                    lines.append(UNHANDLED)
                    continue
                lines += v.say
                apply(v, t)
        for h in hits:
            state[h.intent] = True
            if h.intent not in first:
                first[h.intent] = (n, h.pos)
                first_t[h.intent] = t

        # zeitgesteuerte Ereignisse (Verschlechterung, Besserung, Eintreffen …)
        for k, ev in enumerate(scenario.events):
            due = _due(ev, fired.get(k, 0), first_t)
            if due is not None and t >= due and matches(ev.when, state):
                fired[k] = fired.get(k, 0) + 1
                fired_log.append((k, n))
                lines += ev.variant.say
                apply(ev.variant, t)
        if "nachforderung" in first_t and not state.get("rd_da") and t >= first_t["nachforderung"] + ARRIVAL_SECONDS:
            state["rd_da"] = True
            lines.append(Line("Rettungsdienst", "Hallo, Rettungsdienst. Was habt ihr?"))
        if state.get("uebergeben") and not state.get("_beendet"):
            state["_beendet"] = True
            lines.append(Line("Befund", "Der Patient ist übergeben. Du kannst die Auswertung starten."))

        if state.get("_beendet") and ended_at is None:
            ended_at = n
        if not hits and not lines and not tick:
            lines.append(FALLBACK)
        seen: set[Line] = set()
        lines = [Line(l.who, _fill(l.text, settings)) for l in lines]
        lines = [l for l in lines if not (l in seen or seen.add(l))]
        turns.append(Turn(t, text, hits, lines, info, unhandled))

    return Run(scenario, mode, settings, turns, state, first, first_t, bool(state.get("_beendet")),
               _next_event_at(scenario, state, fired, first_t, turns[-1].t if turns else 0.0), fired_log, ended_at)


def _due(ev, count: int, first_t: dict[str, float]) -> float | None:
    """Fälligkeit der nächsten Auslösung eines Ereignisses (None = nie mehr bzw. noch nicht absehbar)."""
    if count and not ev.repeat:
        return None
    if ev.since and ev.since not in first_t:
        return None
    return (first_t[ev.since] if ev.since else 0.0) + ev.at + count * (ev.repeat or 0)


def _next_event_at(scenario: Scenario, state: dict[str, Any], fired: dict[int, int], first_t: dict[str, float], now: float) -> float | None:
    """Wann wäre beim jetzigen Zustand das nächste Ereignis fällig? (None = keines)"""
    due: list[float] = []
    for k, ev in enumerate(scenario.events):
        d = _due(ev, fired.get(k, 0), first_t)
        if d is not None and matches(ev.when, state):
            due.append(d)
    if "nachforderung" in first_t and not state.get("rd_da"):
        due.append(first_t["nachforderung"] + ARRIVAL_SECONDS)
    later = [d for d in due if d > now]
    return min(later) if later else None
