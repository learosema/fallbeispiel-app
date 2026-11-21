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
from .content import Line, Scenario, Variant, algorithm, intents, smalltalk

ARRIVAL_SECONDS = 480  # Rettungsdienst trifft ca. 8 Minuten nach der Nachforderung ein
FALLBACK = Line("Kollege", "Was genau machst du?")  # erste Rückfrage; weitere Varianten in content/smalltalk.yaml
TIP_DONE = Line("Kollege", "Von mir aus haben wir alles. Du entscheidest, wie es weitergeht.")
# Erkannt, aber der Fall hat keine Antwort: lieber nachfragen als einen Befund erfinden.
UNHANDLED = Line("Kollege", "Was genau meinst du?")

RESOURCES = [  # (Kürzel, Muster) in der Reihenfolge, in der die Leitstelle sie wiederholt
    ("RTW", r"\brtw\b|rettungswagen|rettungsdienst"),
    ("NEF", r"\bnef\b|notarzt|notärzt|notarzteinsatzfahrzeug"),
    ("KTW", r"\bktw\b|krankentransport"),
    ("Polizei", r"polizei|streife"),
    ("Feuerwehr", r"feuerwehr|\bhlf\b"),
]
# Reaktion/Bewusstsein in Teambesprechung oder Funkspruch genannt („wach, reagiert angemessen“, „bewusstlos“)
REACTION = re.compile(r"reagiert|reaktion|ansprechbar|\bwach\b|bewusstlos|bewusstsein|orientiert|verwirrt|somnolent"
                      r"|eingetrübt|eingetruebt|\bgcs\b|avpu|adäquat|adaequat|angemessen")
_NUMBERS = {"null": "0", "eins": "1", "zwei": "2", "drei": "3", "vier": "4", "fünf": "5", "fuenf": "5",
            "sechs": "6", "sieben": "7", "acht": "8", "neun": "9"}


class Classifier(Protocol):
    def classify(self, raw: str) -> list[Hit]: ...


@dataclass
class Settings:
    callsign: str = "EVT1"
    dispatcher: str = "RotkreuzHamburg"
    tips: bool = True   # Kollege gibt auf Nachfrage einen Tipp zum nächsten offenen Punkt der Checkliste


@dataclass
class Turn:
    t: float
    text: str
    hits: list[Hit]
    lines: list[Line]
    funk: dict[str, Any] | None = None
    unhandled: list[str] = field(default_factory=list)
    tip: str | None = None   # Checklisten-Punkt, zu dem der Kollege hier einen Tipp gegeben hat


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

def funk(text: str, s: Settings, state: dict[str, Any], mode: str,
         end_minute: bool = True) -> tuple[list[Hit], list[Line], dict[str, Any]] | None:
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
        "reaktion": bool(REACTION.search(t)),
    }
    hits: list[Hit] = []
    lines: list[Line] = []
    if anruf:
        hits.append(Hit("funk_anruf", 0, 1.0, "funk"))
        state["funk_offen"] = True
    if meldung:
        hits.append(Hit("funk_meldung", 1, 1.0, "funk"))
        if info["reaktion"]:
            hits.append(Hit("reaktion", 1, 1.0, "implied"))
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
        if mode == "minute" and end_minute and not state.get("_beendet"):
            lines.append(Line("Befund", "Die 1. Minute ist beendet. Du kannst die Auswertung starten."))
            state["_beendet"] = True
    if not lines and not ende:
        lines.append(Line("Leitstelle", "Wiederholen."))
    return hits, lines, info


# ---------- Smalltalk ----------

def smalltalk_rule(text: str):
    """Regel aus content/smalltalk.yaml für eine kurze Äußerung ohne fachliche Handlung (oder None)."""
    t = re.sub(r"[^\w\s]", " ", normalize(text))
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return None
    words = len(t.split())
    for rule in smalltalk().rules:
        if rule.max_words and words > rule.max_words:
            continue
        if any(p.search(t) for p in rule.patterns):
            return rule
    return None


# ---------- Tipps vom Kollegen ----------

def applies(cond: str | None, s: Scenario) -> bool:
    """Gilt eine `only`/`extra`-Bedingung aus algorithm.yaml für diesen Fall?"""
    return {
        None: True,
        "trauma": s.trauma,
        "bleeding": s.bleeding,
        "conscious": s.conscious,
        "unconscious": not s.conscious,
        "breathing_normal": not s.conscious and s.breathing == "normal",
        "breathing_abnormal": not s.conscious and s.breathing != "normal",
    }[cond]


def checklist(scenario: Scenario, mode: str) -> list[dict[str, Any]]:
    """Die Punkte der Checkliste in Reihenfolge: 1. Minute, im ganzen Fall danach xABCDE (ohne ausgeblendete)."""
    alg = algorithm()
    items = list(alg["minute_conscious"] if scenario.conscious else alg["minute_unconscious"])
    if mode == "full":
        items += alg["full"]
    return [it for it in items if it["id"] not in scenario.skip and applies(it.get("only"), scenario)]


def item_done(item: dict[str, Any], scenario: Scenario, done: set[str]) -> bool:
    """Vereinfachte Fassung von evaluate.check_item: Ist der Punkt vollständig erledigt?"""
    if item.get("special") == "funk":
        return "funk_meldung" in done and "funk_ende" in done
    if item.get("special") == "reevaluation":
        return "reevaluation" in done
    elements: list[Any] = list(item.get("all", [])) or list(item.get("of", []))
    for cond, extra in (item.get("extra") or {}).items():
        if applies(cond, scenario):
            elements += extra
    if "any" in item:
        elements = [list(item["any"])]
    need = item.get("min", len(elements))
    return sum(any(i in done for i in (el if isinstance(el, list) else [el])) for el in elements) >= need


def next_open(scenario: Scenario, mode: str, done: set[str]) -> dict[str, Any] | None:
    items = [it for it in checklist(scenario, mode) if not item_done(it, scenario, done)]
    if scenario.funk_early and any(i in done for i in scenario.funk_early):
        # kritisches Problem erkannt: jetzt zuerst funken
        items.sort(key=lambda it: it.get("special") != "funk")
    return items[0] if items else None


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
    said: dict[str, int] = {}  # Smalltalk-Regel bzw. Rückfrage → wie oft schon (für die Varianten reihum)

    def rotate(key: str, options: list[Line]) -> Line:
        k = said.get(key, 0)
        said[key] = k + 1
        return options[k % len(options)]

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
        f = None if tick else funk(text, settings, state, mode, end_minute=not scenario.funk_early)
        if tick:
            hits, info = [], None
        elif f:
            # Während eines Funkspruchs zählt nur der Funk – „Verdacht auf …“ ist dann keine Teambesprechung.
            hits, funk_lines, info = f
            lines += funk_lines
        else:
            hits, info = clf.classify(text), None
            team = next((h for h in hits if h.intent == "teambesprechung"), None)
            if team and REACTION.search(normalize(text)) and "reaktion" not in {h.intent for h in hits}:
                hits.append(Hit("reaktion", team.pos, 1.0, "implied"))
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
        if (mode == "minute" and scenario.funk_early and not state.get("_beendet") and "funk_ende" in first
                and next_open(scenario, mode, set(first)) is None):
            # früher Funk: Die 1. Minute endet erst, wenn alles erledigt ist (Auswertung geht jederzeit)
            state["_beendet"] = True
            lines.append(Line("Befund", "Die 1. Minute ist beendet. Du kannst die Auswertung starten."))
        if state.get("uebergeben") and not state.get("_beendet"):
            state["_beendet"] = True
            lines.append(Line("Befund", "Der Patient ist übergeben. Du kannst die Auswertung starten."))

        if state.get("_beendet") and ended_at is None:
            ended_at = n
        tip: str | None = None
        if not hits and not tick and f is None and (rule := smalltalk_rule(text)):
            # zählt nicht in die Auswertung: keine Treffer, nur eine Antwort (Tipps merkt sich die Auswertung)
            if rule.tip and settings.tips:
                item = next_open(scenario, mode, set(first))
                if item:
                    tip = item["id"]
                    lines = [Line("Kollege", item["tip"])] + lines
                else:
                    lines = [TIP_DONE] + lines
            elif rule.repeat:
                prev = next((tt.lines for tt in reversed(turns) if tt.lines), [])
                lines = list(prev or [Line("Kollege", "Es hat noch niemand etwas gesagt.")]) + lines
            elif rule.unconscious and not scenario.conscious:
                lines = [rotate(rule.id, rule.unconscious)] + lines
            else:
                lines = [rotate(rule.id, rule.say)] + lines
        if not hits and not lines and not tick:
            lines.append(rotate("_fallback", smalltalk().fallback))
        seen: set[Line] = set()
        lines = [Line(l.who, _fill(l.text, settings)) for l in lines]
        lines = [l for l in lines if not (l in seen or seen.add(l))]
        turns.append(Turn(t, text, hits, lines, info, unhandled, tip))

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
