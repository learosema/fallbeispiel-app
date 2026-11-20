"""Regelbasierte Auswertung: Checkliste nach SANmemo, Reihenfolge, Schlüsselmaßnahmen, Funkspruch.

Das Ergebnis ist deterministisch und dient als Faktengrundlage für die KI-Bewertung
(und als Fallback, wenn keine KI konfiguriert ist).
"""
from __future__ import annotations

from typing import Any

from .content import algorithm, intents
from .engine import Run, compact

OK, PARTIAL, MISSING, NA = "✅", "⚠️", "❌", "–"


def fmt(sec: float) -> str:
    sec = max(0, round(sec))
    return f"{sec // 60}:{sec % 60:02d}"


def _applies(cond: str | None, run: Run) -> bool:
    s = run.scenario
    return {
        None: True,
        "trauma": s.trauma,
        "bleeding": s.bleeding,
        "conscious": s.conscious,
        "unconscious": not s.conscious,
        "breathing_normal": not s.conscious and s.breathing == "normal",
        "breathing_abnormal": not s.conscious and s.breathing != "normal",
    }[cond]


def _label(el: str | list[str]) -> str:
    cat = intents()
    return " / ".join(cat[i].label for i in el) if isinstance(el, list) else cat[el].label


def _first(el: str | list[str], run: Run) -> tuple[int, int] | None:
    opts = el if isinstance(el, list) else [el]
    found = [run.first[i] for i in opts if i in run.first]
    return min(found) if found else None


def _quote(turn_idx: int, run: Run) -> str:
    text = run.turns[turn_idx].text.strip()
    return text if len(text) <= 90 else text[:87] + "…"


def check_item(item: dict[str, Any], run: Run) -> dict[str, Any]:
    out = {"id": item["id"], "label": item["label"], "short": item.get("short", item["label"]), "status": NA, "note": "", "quote": "", "at": None}
    if item["id"] in run.scenario.skip or not _applies(item.get("only"), run):
        return out
    if item.get("special") == "funk":
        return out | check_funk(run)
    if item.get("special") == "reevaluation":
        return out | check_reevaluation(run)

    elements: list[Any] = list(item.get("all", [])) or list(item.get("of", []))
    for cond, extra in (item.get("extra") or {}).items():
        if _applies(cond, run):
            elements += extra
    if "any" in item:
        elements = [list(item["any"])]
    need = item.get("min", len(elements))

    firsts = [(el, _first(el, run)) for el in elements]
    done = [(el, f) for el, f in firsts if f]
    missing = [el for el, f in firsts if not f]
    if len(done) >= need:
        out["status"] = OK
    elif done:
        out["status"] = PARTIAL
    else:
        out["status"] = MISSING
    if missing and out["status"] == PARTIAL:  # bei ❌ ist das Label selbst schon die Aussage
        out["note"] = "Fehlt: " + ", ".join(_label(m) for m in missing)
    if done:
        at = min(f for _, f in done)
        out["at"] = at
        out["quote"] = _quote(at[0], run)
    return out


def check_funk(run: Run) -> dict[str, Any]:
    calls = [t for t in run.turns if t.funk]
    if not calls:
        return {"status": MISSING, "note": "Kein Funkspruch an die Leitstelle."}
    at = next(i for i, t in enumerate(run.turns) if t.funk)
    infos = [t.funk for t in calls]
    anruf = next((f for f in infos if f["anruf"]), None)
    meldung = next((f for f in infos if f["meldung"]), None)
    problems: list[str] = []
    if not anruf:
        problems.append("Anruf der Leitstelle fehlt")
    elif not anruf["beide_rufnamen"]:
        problems.append(f"Anruf ohne beide Rufnamen („{run.settings.dispatcher} von {run.settings.callsign}, kommen“)")
    if anruf and anruf["anruf_und_meldung_zusammen"]:
        problems.append("nicht auf „Hier …“ der Leitstelle gewartet")
    if not meldung:
        problems.append("keine Meldung abgesetzt")
    else:
        if not (meldung["patient"] and meldung["alter"]):
            problems.append("Patient (Geschlecht, ungefähres Alter) fehlt")
        if not meldung["verdacht"]:
            problems.append("Verdachtsdiagnose fehlt")
        if not meldung["kommen"]:
            problems.append("Meldung nicht mit „kommen“ abgeschlossen")
    requested = {r.upper() for f in infos for r in f["resources"]}
    s = run.scenario
    lacking = [r for r in s.request_required if r not in requested]
    extra = [r for r in requested if r not in s.request_required + s.request_optional]
    if lacking:
        problems.append("Nachforderung unpassend: " + ", ".join(lacking) + " fehlt")
    if extra:
        problems.append("nicht nötig nachgefordert: " + ", ".join(sorted(extra)))
    if not any(f["ende_mit_rufname"] for f in infos):
        problems.append(f"Abschluss „{run.settings.callsign} Ende“ fehlt")
    return {
        "status": OK if not problems else PARTIAL,
        "note": "; ".join(problems),
        "quote": _quote(at, run),
        "at": (at, 0),
    }


REEVAL_INTENTS = ["puls", "spo2", "rr", "af_zaehlen", "atemkontrolle", "gcs", "orientierung", "bz", "rekap", "temperatur"]


def check_reevaluation(run: Run) -> dict[str, Any]:
    if "reevaluation" in run.first:
        n, _ = run.first["reevaluation"]
        return {"status": OK, "quote": _quote(n, run), "at": run.first["reevaluation"]}
    counts: dict[str, list[int]] = {}
    for n, t in enumerate(run.turns):
        for h in t.hits:
            if h.intent in REEVAL_INTENTS:
                counts.setdefault(h.intent, []).append(n)
    repeated = [(i, ns[1]) for i, ns in counts.items() if len(set(ns)) > 1]
    if repeated:
        i, n = min(repeated, key=lambda x: x[1])
        return {"status": OK, "note": f"{intents()[i].label} wiederholt", "quote": _quote(n, run), "at": (n, 0)}
    return {"status": MISSING, "note": "Keine erneute Kontrolle nach den Maßnahmen."}


def check_key_action(ka: dict[str, Any], run: Run) -> dict[str, Any]:
    item = {"id": "key", "label": ka["label"]} | {k: ka[k] for k in ("all", "any", "min", "of") if k in ka}
    out = check_item(item, run)
    out["critical"] = bool(ka.get("critical"))
    if out["status"] in (OK, PARTIAL) and out["at"]:
        n = out["at"][0]
        late = []
        for b in ka.get("before", []):
            if b in run.first and run.first[b] < out["at"]:
                late.append(intents()[b].label)
        if late:
            out["status"] = PARTIAL
            out["note"] = "zu spät, erst nach: " + ", ".join(late[:3])
        if ka.get("within") is not None and run.turns[n].t > ka["within"]:
            out["status"] = PARTIAL
            out["note"] = (out["note"] + "; " if out["note"] else "") + f"erst nach {fmt(run.turns[n].t)} (Ziel: {fmt(ka['within'])})"
    return out


def _out_of_order(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Schritte, die nicht in die längste korrekt geordnete Folge passen."""
    seq = [(i, it) for i, it in enumerate(items) if it["at"] is not None and it["status"] != NA]
    seq.sort(key=lambda x: x[1]["at"])
    idx = [i for i, _ in seq]
    # längste aufsteigende Teilfolge (O(n²) reicht hier)
    best = [1] * len(idx)
    prev = [-1] * len(idx)
    for a in range(len(idx)):
        for b in range(a):
            if idx[b] < idx[a] and best[b] + 1 > best[a]:
                best[a], prev[a] = best[b] + 1, b
    keep: set[int] = set()
    k = max(range(len(idx)), key=lambda x: best[x]) if idx else -1
    while k >= 0:
        keep.add(k)
        k = prev[k]
    return [seq[p][1] for p in range(len(seq)) if p not in keep]


def evaluate(run: Run) -> dict[str, Any]:
    alg = algorithm()
    minute_def = alg["minute_conscious"] if run.scenario.conscious else alg["minute_unconscious"]
    minute = [check_item(it, run) for it in minute_def]
    sections = [{"title": "1. MINUTE", "items": minute}]
    full: list[dict[str, Any]] = []
    if run.mode == "full":
        full = [check_item(it, run) for it in alg["full"]]
        sections.append({"title": "xABCDE", "items": full})
    keys = [check_key_action(ka, run) for ka in run.scenario.key_actions]
    if keys:
        sections.append({"title": "SCHLÜSSELMASSNAHMEN", "items": keys})

    ordered = sorted((it for it in minute if it["at"] is not None and it["status"] != NA), key=lambda it: it["at"])
    wrong = _out_of_order(minute)
    deviations = [f"{it['short']} kam außer der Reihe" for it in wrong]
    deviations += [f"{it['short']} fehlt" for it in minute if it["status"] == MISSING]

    relevant = [it for it in minute + full + keys if it["status"] != NA]
    ok = sum(it["status"] == OK for it in relevant)
    critical_missing = [k for k in keys if k["critical"] and k["status"] == MISSING]
    if relevant and ok == len(relevant) and not wrong:
        verdict = "Erfüllt"
    elif critical_missing or not relevant or ok / len(relevant) < 0.5:
        verdict = "Nicht erfüllt"
    else:
        verdict = "Teilweise erfüllt"

    total = run.turns[-1].t if run.turns else 0
    funk_end = next((t.t for t in run.turns if t.funk and t.funk["ende"]), None)
    time = f"Gesamtzeit {fmt(total)}" + (f", Funkspruch abgeschlossen nach {fmt(funk_end)}" if funk_end is not None else "")

    issues = sorted((it for it in relevant if it["status"] != OK), key=lambda it: (not it.get("critical"), it["status"] != MISSING))
    return {
        "verdict": verdict,
        "sections": sections,
        "order": [it["short"] for it in ordered],
        "deviations": deviations,
        "time": time,
        "praise": [it["label"] for it in relevant if it["status"] == OK][:3],
        "improve": [it["label"] + (f" ({it['note']})" if it["note"] else "") for it in issues][:4],
    }


def transcript(run: Run) -> str:
    out = []
    for t in run.turns:
        out.append(f"[{fmt(t.t)}] Sanitäter:in: {t.text}")
        out += [f"        {l.who}: {l.text}" for l in t.lines]
    return "\n".join(out)


def as_text(result: dict[str, Any]) -> str:
    lines = [f"ALGORITHMUS: {result['verdict']}", ""]
    for sec in result["sections"]:
        lines.append(sec["title"])
        for it in sec["items"]:
            extra = " – ".join(x for x in (it["note"], f"„{it['quote']}“" if it["quote"] else "") if x)
            lines.append(f"{it['status']} {it['label']}" + (f": {extra}" if extra else ""))
        lines.append("")
    lines.append("TATSÄCHLICHE REIHENFOLGE: " + (" → ".join(result["order"]) or "–"))
    lines.append("ABWEICHUNGEN: " + ("; ".join(result["deviations"]) or "keine"))
    lines.append("ZEIT (nachrangig): " + result["time"])
    return "\n".join(lines)


__all__ = ["evaluate", "transcript", "as_text", "compact"]
