"""Tests für Inhalte, Engine und Auswertung – mit reinem Regex-Classifier (schnell, ohne Modell-Download)."""
import pytest

from backend import content, engine, evaluate
from backend.classifier import IntentClassifier

# Diese Untersuchungen sollte jeder Fall selbst beantworten, statt auf „nichts Besonderes“ zurückzufallen.
CORE = ["lage_pruefen", "blutung_pruefen", "vorstellen", "puls", "spo2", "gcs", "bz", "decke", "hautfarbe"]
CORE_CONSCIOUS = ["was_passiert", "atmung_fragen", "zyanose", "rekap", "rr", "orientierung",
                  "sample_allergie", "sample_medikamente", "sample_vorerkrankung", "sample_mahlzeit", "bodycheck"]
CORE_UNCONSCIOUS = ["laut_ansprechen", "atemwege_freimachen", "atemkontrolle", "seitenlage"]


@pytest.fixture(scope="module")
def clf():
    return IntentClassifier(use_embeddings=False)


def play(clf, sid, lines, mode="minute", step=8):
    s = content.scenarios()[sid]
    log = [{"t": step * (i + 1), "text": t} for i, t in enumerate(lines)]
    return engine.replay(s, mode, engine.Settings(), log, clf)


def said(run, who=None):
    return [l.text for t in run.turns for l in t.lines if who is None or l.who == who]


# ---------- Inhalte ----------

def test_all_scenarios_load():
    sc = content.scenarios()
    assert len(sc) == 17
    for s in sc.values():
        assert s.meta["title"] and s.meta["dispatch"]
        assert "debrief_notes" not in s.meta and "responses" not in s.meta, "verborgene Fakten dürfen nicht in meta landen"


@pytest.mark.parametrize("sid", list(content.scenarios()))
def test_scenario_covers_core_findings(sid):
    s = content.scenarios()[sid]
    need = CORE + (CORE_CONSCIOUS if s.conscious else CORE_UNCONSCIOUS)
    missing = [i for i in need if i not in s.responses and not content.intents()[i].default]
    assert not missing, f"{sid}: keine Antwort für {missing}"


def test_regex_patterns_hit_their_examples(clf):
    """Jeder Intent mit Mustern sollte wenigstens eines seiner Beispiele per Regex erkennen."""
    misses = []
    for iid, it in content.intents().items():
        if not it.patterns or not it.examples:
            continue
        if not any(iid in {h.intent for h in clf.classify(ex)} for ex in it.examples):
            misses.append(iid)
    assert not misses, f"Muster greifen bei keinem Beispiel: {misses}"


# ---------- Engine ----------

def test_unrecognised_utterance_gets_fallback(clf):
    run = play(clf, "basis-sturz", ["schönes wetter heute"])
    assert said(run) == [engine.FALLBACK.text]


def test_state_dependent_response(clf):
    run = play(clf, "basis-sturz", ["ist ihnen kalt", "ich decke sie zu", "ist ihnen kalt"])
    replies = said(run, "Patient")
    assert "Ja, mir ist kalt" in replies[0]
    assert "Decke" in replies[-1]


def test_deterioration_event_fires_once(clf):
    run = play(clf, "basis-sturz", ["hallo"] * 12, step=15)
    assert sum("Mir wird richtig kalt" in x for x in said(run)) == 1


def test_teambesprechung_is_exclusive(clf):
    run = play(clf, "basis-sturz", ["kurz zusammengefasst sturz unter blutverdünner puls gut verdacht auf sht"])
    assert [h.intent for h in run.turns[0].hits] == ["teambesprechung"]
    assert said(run) == ["Verstanden."]


def test_funk_sequence_ends_first_minute(clf):
    run = play(clf, "basis-sturz", [
        "rotkreuzhamburg von evt eins kommen",
        "männlicher patient ende sechzig gestürzt verdacht auf sht wir brauchen rtw und nef kommen",
        "evt eins ende",
    ])
    assert said(run, "Leitstelle") == ["Hier RotkreuzHamburg.", "RTW NEF kommt, verstanden."]
    assert not run.turns[1].funk["ende"], "„Ende sechzig“ ist kein Funk-Ende"
    assert run.ended


def test_custom_callsigns(clf):
    s = content.scenarios()["basis-sturz"]
    log = [{"t": 5, "text": "Florian Hamburg von Rotkreuz 12-3 kommen"}]
    run = engine.replay(s, "minute", engine.Settings(callsign="Rotkreuz 12-3", dispatcher="Florian Hamburg"), log, clf)
    assert said(run, "Leitstelle") == ["Hier Florian Hamburg."]


def test_bleeding_control_changes_vitals(clf):
    run = play(clf, "x-kettensaege", ["ich lege sofort ein tourniquet an", "ich fühle den puls"])
    assert "112" in said(run, "Befund")[-1]


def test_untreated_bleeding_deteriorates(clf):
    run = play(clf, "x-kettensaege", ["hallo", "was ist passiert", "puls"], step=30)
    assert any("schwarz vor Augen" in x for x in said(run))


def test_bolus_needs_back_blows_and_heimlich(clf):
    run = play(clf, "a-bolus", ["fünf schläge zwischen die schulterblätter", "jetzt heimlich", "bekommen sie gut luft"])
    assert run.state["geloest"]
    assert said(run, "Patient")[-1] == "Jetzt geht's wieder."


def replay_log(clf, sid, log, mode="minute"):
    return engine.replay(content.scenarios()[sid], mode, engine.Settings(), log, clf)


def test_reanimation_cycle_reaches_rosc(clf):
    log = [
        {"t": 5, "text": "hallo hören sie mich"},
        {"t": 10, "text": "atemkontrolle keine normale atmung"},
        {"t": 15, "text": "ich beginne sofort mit der herzdruckmassage"},
    ]
    run = replay_log(clf, "bw-reanimation", log)
    assert any("Elektroden" in x for x in said(run)), "Kollege baut den AED von sich aus an"
    assert run.next_event_at == 30, "AED-Analyse 15 s nach Beginn der HLW"

    log.append({"t": 30, "text": "", "tick": True})
    run = replay_log(clf, "bw-reanimation", log)
    assert [l.text for l in run.turns[-1].lines] == [
        "AED ist dran.", "Patient nicht berühren! Herzrhythmus wird analysiert …", "Schock empfohlen. Blinkende Taste drücken."]

    log += [{"t": 40, "text": "", "tick": True}, {"t": 42, "text": "Schock! Alle weg!"}]
    run = replay_log(clf, "bw-reanimation", log)
    assert "Absaugbereitschaft hergestellt." in said(run, "Kollege")
    assert run.state["schocks"] == 1 and run.next_event_at is not None

    # zwei Minuten später die nächste Analyse, auch ohne dass jemand etwas sagt
    log += [{"t": 162, "text": "", "tick": True}, {"t": 165, "text": "schock alle weg"},
            {"t": 285, "text": "", "tick": True}]
    run = replay_log(clf, "bw-reanimation", log)
    assert run.state["schocks"] == 2 and run.state["rosc"]
    assert "Kein Schock empfohlen" in " ".join(said(run, "AED"))
    assert not any("wie tief" in x for x in said(run)), "Kollege fragt nicht nach HLW-Details"

    res = evaluate.evaluate(run)
    warn = next(it for it in res["sections"][-1]["items"] if "Sicherheit beim Schock" in it["label"])
    assert warn["status"] == evaluate.OK, "„Schock! Alle weg!“ in einer Äußerung ist rechtzeitig"
    assert "Sanitäter:in: " not in evaluate.transcript(run).splitlines()[-1], "Takte erscheinen ohne Äußerung"


def test_tick_without_due_event_says_nothing(clf):
    run = replay_log(clf, "basis-sturz", [{"t": 5, "text": "hallo"}, {"t": 6, "text": "", "tick": True}])
    assert run.turns[-1].lines == []


def test_next_event_at_points_to_deterioration(clf):
    run = play(clf, "basis-sturz", ["hallo"])
    assert run.next_event_at == 60  # „will nach Hause“ bei 60 s, Frieren bei 75 s
    run = play(clf, "basis-sturz", ["wir decken sie zu", "ich kläre sie auf, sie sollten ins krankenhaus"])
    assert run.next_event_at is None or run.next_event_at > 150


def test_rescue_service_arrives_and_handover_ends(clf):
    lines = ["evt eins fordere einen rtw nach"] + ["puls"] * 9 + ["übergabe an den rettungsdienst"]
    run = play(clf, "basis-sturz", lines, mode="full", step=60)
    assert any(l.who == "Rettungsdienst" for t in run.turns for l in t.lines)
    assert run.ended


# ---------- Auswertung ----------

GOOD_MINUTE = [
    "ist die lage sicher", "keine bedrohliche blutung", "hallo wir sind vom drk was ist passiert",
    "kollege bitte hws stabilisieren", "bekommen sie gut luft tut das atmen weh", "ich schaue auf die lippen",
    "hautfarbe puls rekap", "bauch becken oberschenkel", "wie heißen sie", "ist ihnen kalt", "wir decken sie zu",
    "kurze teambesprechung verdacht auf sht notarzt nötig",
    "rotkreuzhamburg von evt eins kommen",
    "männlicher patient ende sechzig gestürzt verdacht auf sht wir brauchen rtw und nef kommen",
    "evt eins ende",
]


def test_good_first_minute_is_fulfilled(clf):
    res = evaluate.evaluate(play(clf, "basis-sturz", GOOD_MINUTE))
    minute = res["sections"][0]["items"]
    assert all(it["status"] == evaluate.OK for it in minute), [(it["id"], it["note"]) for it in minute if it["status"] != evaluate.OK]
    assert not [d for d in res["deviations"] if "Reihe" in d]


def test_missing_and_out_of_order_steps(clf):
    lines = ["hallo was ist passiert", "ist die lage sicher", "puls"]
    res = evaluate.evaluate(play(clf, "basis-sturz", lines))
    items = {it["id"]: it for it in res["sections"][0]["items"]}
    assert items["hws"]["status"] == evaluate.MISSING
    assert items["kreislauf"]["status"] == evaluate.PARTIAL
    assert "Rekap" in items["kreislauf"]["note"]
    assert items["funk"]["status"] == evaluate.MISSING
    assert res["verdict"] == "Nicht erfüllt"


def test_funk_problems_are_reported(clf):
    res = evaluate.evaluate(play(clf, "x-kettensaege", ["rotkreuzhamburg von evt eins wir brauchen einen rtw kommen"]))
    funk = next(it for it in res["sections"][0]["items"] if it["id"] == "funk")
    assert funk["status"] == evaluate.PARTIAL
    for part in ("nicht auf „Hier", "NEF fehlt", "Ende"):
        assert part in funk["note"]


def test_critical_key_action_too_late(clf):
    res = evaluate.evaluate(play(clf, "x-kettensaege", ["ich fühle den puls", "tourniquet anlegen"], step=30))
    key = next(it for it in res["sections"][-1]["items"] if "Blutstillung" in it["label"])
    assert key["status"] == evaluate.PARTIAL and "zu spät" in key["note"]


def test_unconscious_checklist(clf):
    res = evaluate.evaluate(play(clf, "bw-seitenlage", [
        "lage sicher", "keine blutung", "hallo hören sie mich", "kopf überstrecken", "atemkontrolle sehen hören fühlen",
        "stabile seitenlage", "rettungsdecke",
    ]))
    items = {it["id"]: it["status"] for it in res["sections"][0]["items"]}
    assert items["seitenlage"] == evaluate.OK and items["atemkontrolle"] == evaluate.OK
    assert "hws" not in items and "hlw" in items and items["hlw"] == evaluate.NA


def test_full_mode_adds_abcde(clf):
    res = evaluate.evaluate(play(clf, "basis-sturz", GOOD_MINUTE + ["sättigung", "atemfrequenz", "lunge abhören"], mode="full"))
    titles = [s["title"] for s in res["sections"]]
    assert "xABCDE" in titles
    b = next(it for it in res["sections"][1]["items"] if it["id"] == "b")
    assert b["status"] == evaluate.OK


def test_transcript_contains_both_sides(clf):
    run = play(clf, "basis-sturz", ["hallo"])
    text = evaluate.transcript(run)
    assert "Sanitäter:in: hallo" in text and "Patient:" in text


def test_vague_finding_language_is_flagged(clf):
    run = play(clf, "basis-sturz", ["puls normal", "rekap unter zwei sekunden puls regelmäßig gut tastbar", "atmet er normal"])
    res = evaluate.evaluate(run)
    assert res["vague"] == ["puls normal"]
    assert "BEFUNDSPRACHE" in evaluate.as_text(res)
    assert any("konkret" in x for x in res["improve"])


def test_unconscious_normal_breathing_is_not_flagged(clf):
    res = evaluate.evaluate(play(clf, "bw-seitenlage", ["atemkontrolle er atmet normal"]))
    assert res["vague"] == []
