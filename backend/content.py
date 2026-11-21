"""Lädt Intents, Algorithmus-Checklisten und Fallbeispiele aus content/ (YAML) und prüft sie."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import yaml

CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"
SPEAKERS = ("Patient", "Kollege", "Umstehende", "Befund", "Leitstelle", "AED", "Rettungsdienst")


@dataclass(frozen=True)
class Line:
    who: str
    text: str


@dataclass
class Variant:
    say: list[Line]
    when: dict[str, Any] = field(default_factory=dict)
    set: dict[str, Any] = field(default_factory=dict)


@dataclass
class Intent:
    id: str
    label: str
    patterns: list[str]
    examples: list[str]
    default: list[Variant]
    implies: list[str]
    overrides: list[str]
    exclusive: bool = False
    fallback: list[str] = field(default_factory=list)       # hat der Fall keine Antwort, die dieser Intents nehmen
    unconscious: list[Variant] = field(default_factory=list)  # Antwort, wenn die Person bewusstlos ist   # wird er erkannt, entfallen alle anderen Intents der Äußerung


@dataclass
class Event:
    at: float
    since: str | None
    when: dict[str, Any]
    variant: Variant
    repeat: float | None = None   # Sekunden: feuert danach immer wieder, solange `when` passt
    expect: dict[str, Any] | None = None  # Warnzeichen: erwartete Reaktion {any: [...], within: s, label} für die Auswertung


@dataclass
class Scenario:
    id: str
    meta: dict[str, Any]        # group, letter, title, teaser, dispatch – geht an den Browser
    conscious: bool
    trauma: bool
    bleeding: bool
    breathing: str              # "normal" | "abnormal" (nur bei Bewusstlosigkeit relevant)
    request_required: list[str]
    request_optional: list[str]
    state: dict[str, Any]
    responses: dict[str, list[Variant]]
    events: list[Event]
    key_actions: list[dict[str, Any]]
    skip: list[str]
    notes: str = ""            # Lösungshinweise der Autor:innen, nicht für den Browser
    # Funkspruch früh absetzen (Schlaganfall, Reanimation …): sobald einer dieser Intents erledigt ist, schlägt der Kollege
    # den Funk als Nächstes vor; ein früher Funk ist nicht „außer der Reihe“, und „… Ende“ beendet die 1. Minute nicht
    funk_early: list[str] = field(default_factory=list)
    silence: list[Variant] | None = None  # was bei langer Stille gesagt wird (None = Standard, [] = nichts); Varianten mit when
    alone: list[Variant] | None = None    # Hilferufe, wenn der Patient allein gelassen wird (None = Standard, [] = nichts)


def _lines(raw: Any, where: str) -> list[Line]:
    if isinstance(raw, dict):
        raw = [raw]
    out = []
    for item in raw or []:
        if not isinstance(item, dict) or len(item) != 1:
            raise ValueError(f"{where}: jede Zeile braucht genau einen Sprecher, z. B. 'Patient: …' – bekommen: {item!r}")
        (who, text), = item.items()
        if who not in SPEAKERS:
            raise ValueError(f"{where}: unbekannter Sprecher {who!r} (erlaubt: {', '.join(SPEAKERS)})")
        out.append(Line(who, str(text).strip()))
    return out


def _variants(raw: Any, where: str) -> list[Variant]:
    """Akzeptiert entweder eine Liste von Zeilen oder eine Liste von Varianten mit say/when/set."""
    if raw is None:
        return []
    if isinstance(raw, dict) and ("say" in raw or "set" in raw):
        raw = [raw]
    if isinstance(raw, list) and raw and isinstance(raw[0], dict) and ("say" in raw[0] or "set" in raw[0] or "when" in raw[0]):
        return [Variant(_lines(v.get("say"), where), dict(v.get("when") or {}), dict(v.get("set") or {})) for v in raw]
    return [Variant(_lines(raw, where))]


@cache
def intents() -> dict[str, Intent]:
    data = yaml.safe_load((CONTENT_DIR / "intents.yaml").read_text(encoding="utf-8"))
    out: dict[str, Intent] = {}
    for iid, d in data.items():
        for p in d.get("patterns", []):
            re.compile(p)  # Fehler früh melden
        out[iid] = Intent(
            id=iid,
            label=d["label"],
            patterns=list(d.get("patterns", [])),
            examples=list(d.get("examples", [])),
            default=_variants(d.get("default"), f"intents.{iid}.default"),
            implies=list(d.get("implies", [])),
            overrides=list(d.get("overrides", [])),
            exclusive=bool(d.get("exclusive", False)),
            fallback=list(d.get("fallback", [])),
            unconscious=_variants(d.get("unconscious"), f"intents.{iid}.unconscious"),
        )
    for i in out.values():
        for ref in i.implies + i.overrides + i.fallback:
            if ref not in out:
                raise ValueError(f"intents.{i.id}: unbekannter Intent {ref!r}")
    return out


@dataclass
class SmalltalkRule:
    id: str
    patterns: list[re.Pattern]
    say: list[Line]                # Varianten, reihum
    repeat: bool = False           # vorige Antworten wiederholen („Wie bitte?“)
    max_words: int | None = None   # für nicht verankerte Muster
    tip: bool = False              # Bitte um Hilfe: Tipp zum nächsten offenen Punkt der Checkliste
    unconscious: list[Line] = field(default_factory=list)  # statt `say`, wenn die Person bewusstlos ist


@dataclass
class Smalltalk:
    rules: list[SmalltalkRule]
    fallback: list[Line]
    silence: list[Variant] = field(default_factory=list)  # Standard: wacher Patient bei langer Stille
    alone: list[Variant] = field(default_factory=list)    # Standard: Hilferufe, wenn allein gelassen


@cache
def smalltalk() -> Smalltalk:
    data = yaml.safe_load((CONTENT_DIR / "smalltalk.yaml").read_text(encoding="utf-8"))
    rules = []
    for rid, d in (data.get("rules") or {}).items():
        say = _lines(d.get("say"), f"smalltalk.{rid}.say")
        repeat = bool(d.get("repeat", False))
        if not say and not repeat:
            raise ValueError(f"smalltalk.{rid}: braucht say oder repeat")
        # wie im Classifier: Muster gelten für normalisierten Text (ß → ss), Groß/klein regelt re.I
        pats = [re.compile(p.replace("ß", "ss"), re.I) for p in d.get("patterns", [])]
        if not pats:
            raise ValueError(f"smalltalk.{rid}: keine patterns")
        unconscious = _lines(d.get("unconscious"), f"smalltalk.{rid}.unconscious")
        rules.append(SmalltalkRule(rid, pats, say, repeat, d.get("max_words"), bool(d.get("tip", False)), unconscious))
    fallback = _lines(data.get("fallback"), "smalltalk.fallback")
    if not fallback:
        raise ValueError("smalltalk.fallback: mindestens eine Rückfrage nötig")
    return Smalltalk(rules, fallback, _variants(data.get("silence"), "smalltalk.silence"), _variants(data.get("alone"), "smalltalk.alone"))


@cache
def algorithm() -> dict[str, Any]:
    data = yaml.safe_load((CONTENT_DIR / "algorithm.yaml").read_text(encoding="utf-8"))
    known = intents()
    for section in ("minute_conscious", "minute_unconscious", "full"):
        for item in data[section]:
            for ref in _item_refs(item):
                if ref not in known:
                    raise ValueError(f"algorithm.{section}.{item['id']}: unbekannter Intent {ref!r}")
            if not str(item.get("tip") or "").strip():
                raise ValueError(f"algorithm.{section}.{item['id']}: tip fehlt (was der Kollege auf Nachfrage sagt)")
    return data


def _item_refs(item: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("all", "any", "of"):
        for el in item.get(key, []):
            refs.extend(el if isinstance(el, list) else [el])
    return refs


EXPECT_WITHIN = 30.0  # Sekunden bis zur Reaktion auf ein Warnzeichen, wenn der Fall nichts anderes angibt


def _expect(e: dict[str, Any], when: dict[str, Any], known: dict[str, Intent], where: str) -> dict[str, Any] | None:
    """Erwartete Reaktion auf ein Ereignis. Ohne Angabe abgeleitet: Kommt das Ereignis, weil ein Intent fehlt
    (`when: {decke: false}`), ist genau dieser Intent die Reaktion. Ereignisse mit `since`/`repeat` (Abläufe wie
    der AED-Rhythmus) und `expect: false` werden nicht bewertet."""
    raw = e.get("expect")
    if raw is False:
        return None
    if raw is None:
        if e.get("since") or e.get("repeat"):
            return None
        derived = [k for k, v in when.items() if v is False and k in known]
        return {"any": derived, "within": EXPECT_WITHIN, "label": None} if derived else None
    if isinstance(raw, list):
        raw = {"any": raw}
    refs = list(raw.get("any") or [])
    if not refs:
        raise ValueError(f"{where}: any: [...] fehlt")
    for ref in refs:
        if ref not in known:
            raise ValueError(f"{where}: unbekannter Intent {ref!r}")
    return {"any": refs, "within": float(raw.get("within", EXPECT_WITHIN)), "label": raw.get("label")}


def _load_scenario(path: Path) -> Scenario:
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    sid = d["id"]
    known = intents()
    responses = {}
    for iid, raw in (d.get("responses") or {}).items():
        if iid not in known:
            raise ValueError(f"{path.name}: Antwort für unbekannten Intent {iid!r}")
        responses[iid] = _variants(raw, f"{path.name}.responses.{iid}")
    events = []
    flags = set(d.get("state") or {})
    for raw in list((d.get("responses") or {}).values()) + [d.get("events") or []]:
        for v in raw if isinstance(raw, list) else []:
            if isinstance(v, dict):
                flags |= set(v.get("set") or {})
    for n, e in enumerate(d.get("events") or []):
        if e.get("since") and e["since"] not in known and e["since"] not in flags:
            raise ValueError(f"{path.name}: events[{n}].since: weder Intent noch gesetztes Flag: {e['since']!r}")
        repeat = float(e["repeat"]) if e.get("repeat") else None
        if repeat is not None and repeat < 10:
            raise ValueError(f"{path.name}: events[{n}].repeat muss mindestens 10 Sekunden sein")
        when = dict(e.get("when") or {})
        events.append(Event(float(e["at"]), e.get("since"), when,
                            Variant(_lines(e.get("say"), f"{path.name}.events[{n}]"), {}, dict(e.get("set") or {})), repeat,
                            _expect(e, when, known, f"{path.name}: events[{n}].expect")))
    for ka in d.get("key_actions") or []:
        if ka.get("phase", "minute") not in ("minute", "full"):
            raise ValueError(f"{path.name}: key_actions {ka.get('label')!r}: phase muss minute oder full sein")
        if ka.get("after") and ka["after"] not in known and ka["after"] not in flags:
            raise ValueError(f"{path.name}: key_actions {ka.get('label')!r}: after: weder Intent noch Flag: {ka['after']!r}")
        for ref in _item_refs(ka) + list(ka.get("before", [])):
            if ref not in known:
                raise ValueError(f"{path.name}: key_actions {ka.get('label')!r}: unbekannter Intent {ref!r}")
    funk_early = list(d.get("funk_early") or [])
    for ref in funk_early:
        if ref not in known:
            raise ValueError(f"{path.name}: funk_early: unbekannter Intent {ref!r}")
    req = d.get("request") or {}
    return Scenario(
        id=sid,
        meta={k: d.get(k) for k in ("id", "group", "letter", "title", "teaser", "dispatch")} | {"group": d.get("group", "Grundlagen")},
        conscious=bool(d.get("conscious", True)),
        trauma=bool(d.get("trauma", False)),
        bleeding=bool(d.get("bleeding", False)),
        breathing=d.get("breathing", "normal"),
        request_required=[r.upper() for r in req.get("required", ["RTW"])],
        request_optional=[r.upper() for r in req.get("optional", [])],
        state=dict(d.get("state") or {}),
        responses=responses,
        events=events,
        key_actions=list(d.get("key_actions") or []),
        skip=list(d.get("skip") or []),
        notes=str(d.get("debrief_notes") or "").strip(),
        funk_early=funk_early,
        silence=_optional_lines(d, "silence", path.name),
        alone=_optional_lines(d, "alone", path.name),
    )


def _optional_lines(d: dict[str, Any], key: str, where: str) -> list[Variant] | None:
    """Zeilen reihum, wahlweise als Varianten mit when (die erste passende gilt, ihre Zeilen reihum)."""
    if key not in d:
        return None
    return [] if d[key] is False else _variants(d[key], f"{where}.{key}")


@cache
def scenarios() -> dict[str, Scenario]:
    out: dict[str, Scenario] = {}
    for path in sorted((CONTENT_DIR / "scenarios").glob("*.yaml")):  # Reihenfolge = Dateiname
        s = _load_scenario(path)
        if s.id in out:
            raise ValueError(f"{path.name}: doppelte id {s.id!r}")
        out[s.id] = s
    return out
