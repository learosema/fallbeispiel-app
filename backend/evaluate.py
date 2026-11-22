"""Regelbasierte Auswertung: Checkliste nach SANmemo, Reihenfolge, Schlüsselmaßnahmen, Funkspruch.

Das Ergebnis ist deterministisch: gleiches Protokoll, gleiche Auswertung.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

import re

from .content import algorithm, intents
from .classifier import normalize
from .engine import REACTION, Run, applies, compact

OK, PARTIAL, MISSING, NA = "✅", "⚠️", "❌", "–"


def fmt(sec: float) -> str:
    sec = max(0, round(sec))
    return f"{sec // 60}:{sec % 60:02d}"


def _applies(cond: str | None, run: Run) -> bool:
    return applies(cond, run.scenario)


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
    if item.get("special") == "uebergabe":
        return out | check_handover(run)
    if item.get("special") == "team":
        return out | check_team(run)

    elements: list[Any] = list(item.get("all", [])) or list(item.get("of", []))
    for cond, extra in (item.get("extra") or {}).items():
        if _applies(cond, run):
            elements += extra
    # ausgeblendete Punkte gelten auch als Bestandteil anderer Punkte nicht (kein Wärmeerhalt im E, wo `skip: [waerme]`)
    for skipped, drop in (item.get("unless_skipped") or {}).items():
        if skipped in run.scenario.skip:
            elements = [el for el in elements if el not in drop]
    if "any" in item:
        anys = list(item["any"])
        for cond, more in (item.get("any_extra") or {}).items():
            if _applies(cond, run):
                anys += more
        elements = [anys]
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
    if meldung:
        # eine Meldung in mehreren Stücken zählt zusammen
        parts = infos[infos.index(meldung):]
        meldung = dict(meldung) | {k: any(p[k] for p in parts) for k in ("patient", "alter", "verdacht", "reaktion", "kommen")}
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
        if not meldung["reaktion"] and _applies("reaction_abnormal", run):
            problems.append("Auffällige Reaktion nicht genannt (z. B. „reagiert verzögert“, „verwirrt“, „bewusstlos“)")
        if not meldung["kommen"]:
            problems.append("Meldung nicht mit „kommen“ abgeschlossen")
    requested = {r.upper() for f in infos for r in f["resources"]}
    s = run.scenario
    # nach einer Verschlechterung kann mehr nötig werden (erst RTW, dann NEF dazu)
    escalated = [r for k, _ in run.fired for r in s.events[k].request if r not in s.request_required]
    lacking = [r for r in s.request_required if r not in requested]
    extra = [r for r in requested if r not in s.request_required + s.request_optional + escalated]
    if lacking:
        problems.append("Nachforderung unpassend: " + ", ".join(lacking) + " fehlt")
    late = sorted({r for r in escalated if r not in requested})
    if late:
        problems.append(", ".join(late) + " nach der Verschlechterung nicht nachgefordert")
    if extra:
        problems.append("nicht nötig nachgefordert: " + ", ".join(sorted(extra)))
    if run.state.get("funk_ermahnt"):
        problems.append("Gespräch nicht beendet – die Leitstelle musste auf Funkdisziplin hinweisen")
    if not any(f["ende_mit_rufname"] for f in infos):
        problems.append(f"Abschluss „{run.settings.callsign} Ende“ fehlt")
    return {
        "status": OK if not problems else PARTIAL,
        "note": "; ".join(problems),
        "quote": _quote(at, run),
        "at": (at, 0),
    }


# „Puls normal“ sagt nichts aus – besser: „Puls regelmäßig, gut tastbar, schnell“, „Rekap unter 2 s / verzögert“.
# „Normale Atmung“ bei der Atemkontrolle ist dagegen der Begriff des Algorithmus und wird nicht beanstandet.
_VAGUE = re.compile(r"\b(normal|unauffällig|ok|okay|in ordnung|passt)\b")
_VAGUE_TOPICS = re.compile(r"\bpuls|rekap|kapillar|nagelbett|kreislauf(?!stillstand)|\bhaut|hautfarbe|blutdruck|\brr\b|herzfrequenz|sättigung|spo2|atemfrequenz|\bwerte\b|vital")
# Embedding-Weg für Umschreibungen ohne Stichwort („Kreislauf im grünen Bereich“, „Blutdruck im Rahmen“):
# vage, wenn der Teilsatz den vagen Beispielen ähnlich genug und näher als konkreten Befunden und reinen
# Handlungen/Fragen ist. Vorher wird das Themenwort durch „wert“ ersetzt – sonst vergleicht das Modell vor
# allem „Puls“ mit „Puls“ statt „ist im Rahmen“ mit „gut tastbar“. Schwellen an Testsätzen gemessen
# (tests/test_embeddings.py): vage ≥ +0,03, konkret/Handlung ≤ −0,03.
VAGUE_MIN_SIM = 0.55
VAGUE_MARGIN = 0.0
# Handlungen („ich messe die Sättigung“, „messe den Puls“) und Verdachtsäußerungen teilen keinen Befund mit
_NOT_A_FINDING = re.compile(r"\b(messe|messen|misst|prüfe|prüfen|kontrolliere|kontrollieren|zähle|zählen|fühle|fühlen|taste|tasten"
                            r"|schaue|schauen|höre|hören|untersuche|untersuchen|bestimme|bestimmen|lege|legen|leuchte)\b"
                            r"|\b(verdacht|vermutlich|wahrscheinlich)\b")
_TOPIC_WORDS = re.compile(r"\b(der |die |das |den )?(puls\w*|rekap\w*|kapillar\w*|nagelbett\w*|kreislauf(?!stillstand)\w*|haut\w*|blutdruck\w*|rr|herzfrequenz|sättigung|spo2|atemfrequenz|werte|vitalwerte|vitalzeichen)\b")


def _mask(text: str) -> str:
    from .classifier import normalize

    return re.sub(r"\s+", " ", _TOPIC_WORDS.sub(" wert ", normalize(text))).strip()


def _prototypes(embedder) -> dict[str, Any]:
    if not hasattr(embedder, "_finding_protos"):
        groups = algorithm().get("finding_language") or {}
        embedder._finding_protos = {k: embedder.embed([_mask(x) for x in groups.get(k, [])])
                                    for k in ("vague", "concrete", "action") if groups.get(k)}
    return embedder._finding_protos


def is_vague(clause: str, embedder=None) -> bool:
    """Ist dieser Teilsatz ein nur als „normal“/„in Ordnung“ benannter Befund?"""
    from .classifier import normalize

    text = normalize(clause)
    if not _VAGUE_TOPICS.search(text):
        return False
    # Fragen und bloße Stichworte („Puls?“, „Rekap“) sind Untersuchungen, keine mitgeteilten Befunde
    if "?" in text or not re.sub(r"\b(der|die|das|den|und|mal|bitte|jetzt)\b|\W", "", _mask(text)).replace("wert", ""):
        return False
    if re.match(r"^\W*(wie|was|welche\w*|ist|sind|hat|haben|gibt)\b", text):
        return False
    if _VAGUE.search(text):
        return True
    if embedder is None or _NOT_A_FINDING.search(text):
        return False
    # Für kurze Reste („Puls unregelmäßig“, „auch die Haut“) ist der Embedding-Vergleich nicht verlässlich:
    # erst ab zwei Inhaltswörtern neben dem Themenwort („Blutdruck im Rahmen“, „Kreislauf im grünen Bereich“)
    if len([w for w in _mask(text).split() if w not in ("wert", "der", "die", "das", "den", "auch", "noch", "jetzt")]) < 2:
        return False
    protos = _prototypes(embedder)
    if "vague" not in protos:
        return False
    e = embedder.embed([_mask(text)])
    v = float((e @ protos["vague"].T).max())
    other = max((float((e @ protos[k].T).max()) for k in ("concrete", "action") if k in protos), default=0.0)
    return v >= VAGUE_MIN_SIM and v - other > VAGUE_MARGIN


def vague_findings(run: Run, embedder=None) -> list[str]:
    """Äußerungen, in denen ein Befund nur als „normal“/„unauffällig“ o. Ä. benannt wird."""
    out = []
    for t in run.turns:
        if t.funk:
            continue
        # „?“ bleibt am Teilsatz, damit Fragen als Fragen erkannt werden
        clauses = [c for c in re.split(r"(?<=\?)|[.,;!]|\bund\b", t.text.lower()) if c.strip()]
        if any(is_vague(c, embedder) for c in clauses):
            out.append(t.text.strip())
    return out


WRONG_CPR = {"hlw", "hlw_zaehlen", "hlw_30", "schock_ausloesen"}
REEVAL_INTENTS = ["puls", "spo2", "rr", "af_zaehlen", "atemkontrolle", "gcs", "orientierung", "bz", "rekap", "temperatur"]


def _blocks(text: str, blocks: list[dict[str, Any]], run: Run | None = None) -> list[str]:
    """Bausteine (label + patterns, optional min), die im Text fehlen. `if_intent`: nur, wenn der Intent vorkam."""
    missing = []
    for block in blocks:
        if block.get("if_intent") and (run is None or block["if_intent"] not in run.first):
            continue
        if block.get("only") and (run is None or not _applies(block["only"], run)):
            continue
        found = {p for p in block["patterns"] if re.search(p.replace("ß", "ss"), text)}
        if len(found) < block.get("min", 1):
            missing.append(block["label"])
    return missing


def check_team(run: Run) -> dict[str, Any]:
    """Teambesprechung: Welche Bausteine kamen in der (mehrteiligen) Besprechung vor?"""
    parts = [n for n, t in enumerate(run.turns) if t.team]
    if not parts:
        return {"status": MISSING, "note": ""}
    missing = _blocks(normalize(" ".join(run.turns[n].text for n in parts)), algorithm().get("team_talk", []), run)
    if not any(run.turns[n].team_closed for n in parts):
        missing.append("Abschlussfrage an den Kollegen („Siehst du das auch so?“)")
    return {"status": OK if not missing else PARTIAL, "note": ("Fehlt: " + "; ".join(missing)) if missing else "",
            "quote": _quote(parts[0], run), "at": (parts[0], 0)}


def check_handover(run: Run) -> dict[str, Any]:
    """Übergabe an den Rettungsdienst: Welche Bausteine (ISOBAR/SINNHAFT) kamen im gesamten Übergabetext vor?"""
    parts = [n for n, t in enumerate(run.turns) if t.handover]
    if not parts:
        if "uebergabe" in run.first:  # vor dem Eintreffen angesagt
            return {"status": PARTIAL, "note": "Übergabe angesagt, bevor der Rettungsdienst da war",
                    "quote": _quote(run.first["uebergabe"][0], run), "at": run.first["uebergabe"]}
        return {"status": MISSING, "note": ""}
    missing = _blocks(normalize(" ".join(run.turns[n].text for n in parts)), algorithm().get("handover", []), run)
    return {
        "status": OK if not missing else PARTIAL,
        "note": ("Fehlt: " + "; ".join(missing)) if missing else "",
        "quote": _quote(parts[0], run),
        "at": (parts[0], 0),
    }


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


def _since(run: Run, flag: str) -> Run | None:
    """Sicht auf den Einsatz ab dem Moment, in dem `flag` gesetzt wurde (None, wenn nie)."""
    if flag not in run.first_t:
        return None
    t0 = run.first_t[flag]
    first: dict[str, tuple[int, int]] = {}
    for n, turn in enumerate(run.turns):
        if turn.t < t0:
            continue
        for h in turn.hits:
            first.setdefault(h.intent, (n, h.pos))
    return replace(run, first=first)


def check_key_action(ka: dict[str, Any], run: Run) -> dict[str, Any]:
    item = {"id": "key", "label": ka["label"]} | {k: ka[k] for k in ("all", "any", "min", "of") if k in ka}
    if ka.get("after"):  # gilt erst ab einem Zeitpunkt im Einsatz (z. B. „sobald beatmet werden kann“)
        view = _since(run, ka["after"])
        if view is None:
            return {"id": "key", "label": ka["label"], "short": ka["label"], "status": NA, "note": "", "quote": "", "at": None,
                    "critical": bool(ka.get("critical"))}
        run = view
    out = check_item(item, run)
    out["critical"] = bool(ka.get("critical"))
    if out["status"] in (OK, PARTIAL) and out["at"]:
        n = out["at"][0]
        late = []
        for b in ka.get("before", []):
            # gleiche Äußerung zählt als rechtzeitig („Schock! Alle weg!“ ist ein Kommando)
            if b in run.first and run.first[b][0] < out["at"][0]:
                late.append(intents()[b].label)
        if late:
            out["status"] = PARTIAL
            out["note"] = "zu spät, erst nach: " + ", ".join(late[:3])
        if ka.get("within") is not None and run.turns[n].t > ka["within"]:
            out["status"] = PARTIAL
            out["note"] = (out["note"] + "; " if out["note"] else "") + f"erst nach {fmt(run.turns[n].t)} (Ziel: {fmt(ka['within'])})"
    return out


def _event_text(ev) -> str:
    """Was das Warnzeichen sagt, ohne Regieanweisungen („(zittert) Mir wird kalt“ → „Mir wird kalt“)."""
    parts = []
    for line in ev.variant.say:
        spoken = re.sub(r"\([^)]*\)", "", line.text).strip()
        parts.append(spoken or line.text.strip("() "))
    text = " ".join(parts)
    return text if len(text) <= 70 else text[:67].rstrip() + "…"


def check_warnings(run: Run) -> list[dict[str, Any]]:
    """Reaktion auf Warnzeichen: Kam nach dem Ereignis (Verschlechterung, „Mir wird kalt“) rechtzeitig eine der
    erwarteten Maßnahmen? Folgen mehrere Warnzeichen mit derselben Erwartung, zählt das erste, die weiteren
    stehen als Verlauf in der Notiz."""
    out: list[dict[str, Any]] = []
    by_expect: dict[frozenset[str], dict[str, Any]] = {}
    end_t = run.turns[-1].t if run.turns else 0.0
    for k, n in run.fired:
        ev = run.scenario.events[k]
        if not ev.expect or (run.ended_at is not None and n >= run.ended_at):
            continue  # nach dem Ende des Einsatzes kann niemand mehr reagieren
        key = frozenset(ev.expect["any"])
        if key in by_expect:  # gleiche Erwartung: nur Eskalation desselben Problems
            by_expect[key]["_later"].append(_event_text(ev))
            continue
        text = _event_text(ev)
        t0 = run.turns[n].t
        reaction = next((m for m in range(n + 1, len(run.turns))
                         if any(h.intent in key for h in run.turns[m].hits)), None)
        item = {"id": "warn", "label": ev.expect["label"] or f"Reaktion auf „{text}“", "short": text,
                "status": MISSING, "note": "", "quote": "", "at": None, "critical": False, "_later": []}
        if reaction is not None:
            delay = run.turns[reaction].t - t0
            item["at"] = (reaction, 0)
            item["quote"] = _quote(reaction, run)
            if delay <= ev.expect["within"]:
                item["status"] = OK
            else:
                item["status"] = PARTIAL
                item["note"] = f"erst nach {round(delay)} s (Ziel: {round(ev.expect['within'])} s)"
                item["improve"] = f"Auf „{text}“ schneller reagieren"
        elif end_t - t0 < ev.expect["within"]:
            continue  # Protokoll endet, bevor die Reaktionszeit um war – nicht bewerten
        else:
            expected = " / ".join(intents()[i].label for i in ev.expect["any"])
            item["note"] = "keine Reaktion – erwartet: " + expected
            item["improve"] = ev.expect["label"] or f"Auf „{text}“ reagieren: {expected}"
        by_expect[key] = item
        out.append(item)
    for item in out:
        later = item.pop("_later")
        if later and item["status"] != OK:
            item["note"] += "; danach: " + "; ".join(f"„{x}“" for x in later)
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


def evaluate(run: Run, embedder=None) -> dict[str, Any]:
    alg = algorithm()
    minute_def = alg["minute_conscious"] if run.scenario.conscious else alg["minute_unconscious"]
    minute = [check_item(it, run) for it in minute_def]
    sections = [{"title": "1. MINUTE", "items": minute}]
    full: list[dict[str, Any]] = []
    if run.mode == "full":
        full = [check_item(it, run) for it in alg["full"]]
        sections.append({"title": "xABCDE", "items": full})
    # Schlüsselmaßnahmen aus dem vollständigen ABCDE (phase: full, z. B. SAMPLER, BZ) zählen nicht in der 1. Minute
    keys = [check_key_action(ka, run) for ka in run.scenario.key_actions
            if run.mode == "full" or ka.get("phase", "minute") == "minute"]
    if keys:
        sections.append({"title": "SCHLÜSSELMASSNAHMEN", "items": keys})
    # Warnzeichen zählen nicht ins Urteil – die fehlende Maßnahme steht meist schon in Checkliste/Schlüsselmaßnahmen –,
    # werden aber als Verbesserung vorrangig genannt: Gerade hier korrigiert im Gespräch niemand.
    warnings = check_warnings(run)
    if warnings:
        sections.append({"title": "WARNZEICHEN", "items": warnings})

    # Tipps vom Kollegen (auf Nachfrage): Vermerk am Punkt und unter „Verbessern“, ändert das Urteil nicht.
    # Ein Tipp gibt es nur zu Punkten, die in dem Moment noch nicht vollständig erledigt waren.
    tipped = {t.tip for t in run.turns if t.tip}
    after_tip = []
    for it in minute + full:
        if it["id"] in tipped and it["status"] != NA:
            remark = "erst nach Tipp vom Kollegen" if it["status"] == OK else "trotz Tipp vom Kollegen"
            it["note"] = f"{it['note']}; {remark}" if it["note"] else remark[0].upper() + remark[1:]
            it["tipped"] = True
            if it["status"] == OK:
                after_tip.append(f"{it['short']} erst nach Tipp vom Kollegen")

    ordered = sorted((it for it in minute if it["at"] is not None and it["status"] != NA), key=lambda it: it["at"])
    # nicht für die Reihenfolge: „unordered“ (Reaktion fällt beim Ansprechen auf) und der frühe Funk, wo er gewollt ist
    free = {it["id"] for it in minute_def if it.get("unordered") or (it.get("special") == "funk" and run.scenario.funk_early)}
    wrong = _out_of_order([it if it["id"] not in free else it | {"at": None} for it in minute])
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

    if run.died_at is not None:
        verdict = "Nicht erfüllt"
    # HLW (oder Schock) bei jemandem, der wach ist bzw. normal atmet: schadet und ist ein schwerer Fehler –
    # auch wenn der Kollege sie gestoppt hat
    wrong_cpr = next((t for t in run.turns if WRONG_CPR & set(t.refused)), None)
    if wrong_cpr is not None:
        verdict = "Nicht erfüllt"
    total = run.turns[-1].t if run.turns else 0
    funk_end = next((t.t for t in run.turns if t.funk and t.funk["ende"]), None)
    time = f"Gesamtzeit {fmt(total)}" + (f", Funkspruch abgeschlossen nach {fmt(funk_end)}" if funk_end is not None else "")

    issues = sorted((it for it in relevant + warnings if it["status"] != OK),
                    key=lambda it: (0 if it.get("critical") else 1 if it["id"] == "warn" else 2, it["status"] != MISSING))
    vague = vague_findings(run, embedder)
    improve = [it.get("improve") or it["label"] + (f" ({it['note']})" if it["note"] else "") for it in issues][:4]
    improve += after_tip
    alone_s = sum((b if b is not None else total) - a for a, b in run.alone)
    course = []
    if run.died_at is not None:
        course.append(f"Patient verstorben nach {fmt(run.died_at)}")
    if wrong_cpr is not None:
        course.append(f"HLW bei wacher bzw. normal atmender Person versucht nach {fmt(wrong_cpr.t)} (vom Kollegen gestoppt)")
    if run.alone:
        course.append(f"Patient allein gelassen (insgesamt {fmt(alone_s)})")
    # Das Wichtigste zuerst: Tod und Alleinlassen stehen vor allem anderen
    front = []
    if run.died_at is not None:
        front.append(f"Der Patient ist nach {fmt(run.died_at)} verstorben – die lebensrettenden Maßnahmen kamen nicht rechtzeitig")
    if wrong_cpr is not None:
        front.append(f"HLW nur bei Bewusstlosigkeit ohne normale Atmung – hier wurde sie bei jemandem begonnen, der wach ist "
                     f"oder normal atmet („{_quote(run.turns.index(wrong_cpr), run)}“). Das kann schwer verletzen.")
    if run.alone:
        front.append("Patient nie allein lassen – einer bleibt immer da, Material holt der andere")
    improve = front + improve
    if vague:
        improve.append("Befunde konkret benennen statt „normal“ (z. B. „Puls regelmäßig, gut tastbar“, „Rekap unter 2 s“)")
    return {
        "verdict": verdict,
        "sections": sections,
        "order": [it["short"] for it in ordered],
        "deviations": deviations,
        "time": time,
        "praise": [it["label"] for it in relevant if it["status"] == OK][:3],
        "improve": improve,
        "vague": vague,
        "notes": run.scenario.notes,
        "course": course,
        "died_at": run.died_at,
    }


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
    if result.get("course"):
        lines.append("VERLAUF: " + "; ".join(result["course"]))
    if result.get("vague"):
        quotes = "; ".join(f"„{q}“" for q in result["vague"][:3])
        lines.append("BEFUNDSPRACHE: ungenau – " + quotes + ". Besser konkret: „Puls regelmäßig, gut/schlecht/nicht tastbar“, „Puls schnell“, „Rekap unter 2 s“ oder „Rekap verzögert“.")
    lines.append("ZEIT (nachrangig): " + result["time"])
    lines += ["", "GUT GEMACHT: " + ("; ".join(result["praise"]) or "–"),
              "VERBESSERN: " + ("; ".join(result["improve"]) or "nichts Wesentliches")]
    if result.get("notes"):
        lines += ["", "WORAUF ES IN DIESEM FALL ANKOMMT: " + " ".join(result["notes"].split())]
    return "\n".join(lines)


__all__ = ["evaluate", "as_text", "compact"]
