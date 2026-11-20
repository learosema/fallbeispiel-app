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
    exclusive: bool = False   # wird er erkannt, entfallen alle anderen Intents der Äußerung


@dataclass
class Event:
    at: float
    since: str | None
    when: dict[str, Any]
    variant: Variant


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
    notes: str = ""            # Hinweise nur für die KI-Bewertung, nicht für den Browser


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
        )
    for i in out.values():
        for ref in i.implies + i.overrides:
            if ref not in out:
                raise ValueError(f"intents.{i.id}: unbekannter Intent {ref!r}")
    return out


@cache
def algorithm() -> dict[str, Any]:
    data = yaml.safe_load((CONTENT_DIR / "algorithm.yaml").read_text(encoding="utf-8"))
    known = intents()
    for section in ("minute_conscious", "minute_unconscious", "full"):
        for item in data[section]:
            for ref in _item_refs(item):
                if ref not in known:
                    raise ValueError(f"algorithm.{section}.{item['id']}: unbekannter Intent {ref!r}")
    return data


def _item_refs(item: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("all", "any", "of"):
        for el in item.get(key, []):
            refs.extend(el if isinstance(el, list) else [el])
    return refs


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
        events.append(Event(float(e["at"]), e.get("since"), dict(e.get("when") or {}),
                            Variant(_lines(e.get("say"), f"{path.name}.events[{n}]"), {}, dict(e.get("set") or {}))))
    for ka in d.get("key_actions") or []:
        for ref in _item_refs(ka) + list(ka.get("before", [])):
            if ref not in known:
                raise ValueError(f"{path.name}: key_actions {ka.get('label')!r}: unbekannter Intent {ref!r}")
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
    )


@cache
def scenarios() -> dict[str, Scenario]:
    out: dict[str, Scenario] = {}
    for path in sorted((CONTENT_DIR / "scenarios").glob("*.yaml")):  # Reihenfolge = Dateiname
        s = _load_scenario(path)
        if s.id in out:
            raise ValueError(f"{path.name}: doppelte id {s.id!r}")
        out[s.id] = s
    return out
