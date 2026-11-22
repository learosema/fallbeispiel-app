"""Musterlösungen: je Fall ein Lauf, der im ganzen Fall „Erfüllt“ ergibt und den Patienten gut versorgt.

In `content/solutions/<id>.yaml` steht nur, was die Sanitäter:in sagt. Die Antworten der Simulation entstehen
hier durch Nachspielen mit der Engine – so passen sie immer zum aktuellen Stand des Falls. Ein Test
(tests/test_solutions.py) prüft, dass jede Lösung weiter „Erfüllt“ ergibt.

Aufbau einer Lösung:
    id: basis-sturz
    steps:
      - phase: Lage                       # Zwischenüberschrift
      - say: Ist die Einsatzstelle sicher?
        why: Erklärung, warum (optional)
        t: 120                            # Nettozeit in s (optional; sonst nach der Länge des vorigen Satzes)
      - wait: Rettungsdienst              # warten, bis jemand spricht (oder `until: 200` – bis zur Nettozeit);
                                          # Ereignisse laufen als Takte weiter
        meanwhile: [Sätze reihum, etwa alle `pause` s (Standard PAUSE)]
        pause: 4
        react: {"Schock empfohlen": "…"}  # nur in dieser Wartephase: auf eine Ansage sofort reagieren
    react: {"Schock empfohlen": "Schock! Alle weg!"}   # im ganzen Fall: auf jede solche Ansage einmal sofort reagieren
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from . import content, engine, evaluate

SOLUTIONS_DIR = content.CONTENT_DIR / "solutions"
PAUSE = 20.0   # Sekunden zwischen zwei `meanwhile`-Sätzen beim Warten


@lru_cache
def solutions() -> dict[str, dict[str, Any]]:
    out = {}
    for path in sorted(SOLUTIONS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        out[data["id"]] = data
    return out


def speaking_time(text: str) -> float:
    """Ungefähre Sprechdauer (Nettozeit) – gut 2 Wörter pro Sekunde, mindestens 3 s."""
    return max(3.0, round(len(text.split()) * 0.45, 1))


class _CachedClassifier:
    """Beim Nachspielen wird dieselbe Äußerung viele Male klassifiziert – das Ergebnis ist deterministisch."""

    def __init__(self, clf):
        self._clf = clf
        self._cache: dict[str, Any] = {}

    def classify(self, text):
        if text not in self._cache:
            self._cache[text] = self._clf.classify(text)
        return self._cache[text]

    def __getattr__(self, name):
        return getattr(self._clf, name)


def build_log(scenario, steps: list[dict[str, Any]], clf, mode: str = "full",
              settings: engine.Settings | None = None, react: dict[str, str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any] | None]]:
    """Protokoll wie im Browser: Äußerungen plus Takte (`tick`), sobald ein Ereignis fällig ist.

    Gibt das Protokoll und je Eintrag den zugehörigen Schritt zurück (None bei Takten)."""
    settings = settings or engine.Settings(tips=False)
    clf = _CachedClassifier(clf)
    log: list[dict[str, Any]] = []
    origin: list[dict[str, Any] | None] = []
    t = 0.0
    pending_phase = None
    react = dict(react or {})   # Ansage (Teiltext) → sofortige Reaktion, z. B. „Schock empfohlen“ → „Schock! Alle weg!“
    answered: dict[str, int] = {}

    def reaction(run, extra=None):
        """Reaktion auf eine Ansage, die öfter kam, als sie beantwortet wurde (jede Analyse genau einmal)."""
        for key, say in (react | (extra or {})).items():
            seen = sum(key in line.text for turn in run.turns for line in turn.lines)
            if seen > answered.get(key, 0):
                answered[key] = seen
                return say
        return None

    for step in steps:
        if "phase" in step and "say" not in step:
            pending_phase = step["phase"]
            continue
        if "wait" in step or "until" in step:
            # warten, bis jemand auftaucht (z. B. der Rettungsdienst): fällige Ereignisse als Takte einspielen und
            # zwischendurch die `meanwhile`-Sätze reihum (Betreuung, Kontrollen), etwa alle PAUSE Sekunden
            care = list(step.get("meanwhile") or [])
            local = dict(step.get("react") or {})   # Reaktionen nur für diese Wartephase (gehen den fallweiten vor)
            pause = float(step.get("pause", PAUSE))
            i = 0
            for _ in range(400):
                run = engine.replay(scenario, mode, settings, log, clf)
                if "wait" in step and any(line.who == step["wait"] for turn in run.turns for line in turn.lines):
                    break
                if "until" in step and t >= step["until"]:
                    break
                if run.ended:
                    raise ValueError(f"{scenario.id}: Einsatz endete beim Warten ({step})")
                due = reaction(run, local)
                if due:
                    at = log[-1]["t"] + 1.0
                    log.append({"t": at, "text": due})
                    origin.append({"say": due})
                    t = at + speaking_time(due)
                    continue
                nxt = run.next_event_at
                if care and (nxt is None or nxt > t + pause):
                    text = care[i % len(care)]
                    i += 1
                    log.append({"t": t + pause, "text": text})
                    origin.append({"say": text} | ({"phase": pending_phase} if pending_phase else {}))
                    pending_phase = None
                    t += pause + speaking_time(text)
                elif "until" in step and (nxt is None or nxt >= step["until"]):
                    t = max(t, float(step["until"]))
                    break
                elif nxt is not None:
                    log.append({"t": max(nxt, log[-1]["t"] + 0.5), "text": "", "tick": True})
                    origin.append(None)
                    t = max(t, log[-1]["t"])
                else:
                    raise ValueError(f"{scenario.id}: beim Warten passiert nichts mehr ({step})")
            else:
                raise ValueError(f"{scenario.id}: beim Warten passiert nichts mehr ({step})")
            t = log[-1]["t"] + 2.0
            continue
        target = float(step.get("t", t + 2.0))
        # fällige Ereignisse vorher als Takt einspielen (der Browser schickt sie zu next_event_at)
        while True:
            run = engine.replay(scenario, mode, settings, log, clf)
            if run.ended:
                return log, origin
            due = reaction(run)
            if due:
                at = log[-1]["t"] + 1.0
                log.append({"t": at, "text": due})
                origin.append({"say": due})
                t = max(t, at + speaking_time(due))
                target = max(target, t)
                continue
            nxt = run.next_event_at
            if nxt is None or nxt >= target or (log and nxt <= log[-1]["t"]):
                break
            log.append({"t": nxt, "text": "", "tick": True})
            origin.append(None)
        t = max(target, log[-1]["t"] + 0.5 if log else target)
        log.append({"t": t, "text": step["say"]})
        origin.append(step | ({"phase": pending_phase} if pending_phase else {}))
        pending_phase = None
        t += speaking_time(step["say"])
    return log, origin


def play(sid: str, clf, mode: str = "full") -> tuple[engine.Run, list[dict[str, Any] | None]]:
    scenario = content.scenarios()[sid]
    sol = solutions()[sid]
    log, origin = build_log(scenario, sol["steps"], clf, mode, react=sol.get("react"))
    run = engine.replay(scenario, mode, engine.Settings(tips=False), log, _CachedClassifier(clf))
    return run, origin


def transcript(sid: str, clf, embedder=None) -> dict[str, Any]:
    """Musterlösung für die Seite: Verlauf mit Antworten der Simulation und Auswertung."""
    scenario = content.scenarios()[sid]
    run, origin = play(sid, clf)
    entries: list[dict[str, Any]] = []
    for turn, step in zip(run.turns, origin):
        if step is not None:
            if step.get("phase"):
                entries.append({"phase": step["phase"]})
            entries.append({"who": "me", "text": turn.text, "t": round(turn.t), "why": step.get("why")})
        entries += [{"who": line.who, "text": line.text} for line in turn.lines]
    result = evaluate.evaluate(run, embedder)
    meta = scenario.meta
    return {
        "id": sid,
        "title": meta["title"],
        "group": meta.get("group"),
        "letter": meta.get("letter"),
        "dispatch": meta.get("dispatch"),
        "intro": solutions()[sid].get("intro"),
        "notes": scenario.notes,
        "key_actions": [ka["label"] for ka in scenario.key_actions],
        "verdict": result["verdict"],
        "entries": entries,
    }
