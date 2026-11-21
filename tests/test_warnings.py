"""Reaktion auf Warnzeichen (Ereignisse mit erwarteter Maßnahme) und „Worauf es ankommt“ in der Auswertung."""
import pytest

from backend import content, engine, evaluate
from backend.classifier import IntentClassifier

FUNK = ["rotkreuzhamburg von evt1 kommen",
        "patient männlich ende sechzig verdacht auf hws verletzung wir brauchen einen rtw kommen",
        "evt1 ende"]


@pytest.fixture(scope="module")
def clf():
    return IntentClassifier(use_embeddings=False)


def run_at(clf, sid, timed, mode="minute"):
    """timed: [(Sekunde, Text)]; Text None = Takt ohne Äußerung."""
    log = [{"t": t, "text": "", "tick": True} if text is None else {"t": t, "text": text} for t, text in timed]
    return engine.replay(content.scenarios()[sid], mode, engine.Settings(), log, clf)


def warnings(run):
    sec = next((s for s in evaluate.evaluate(run)["sections"] if s["title"] == "WARNZEICHEN"), None)
    return sec["items"] if sec else []


def cold(run):
    return next(w for w in warnings(run) if "kalt" in w["label"])


def test_no_reaction_to_warning_sign(clf):
    run = run_at(clf, "basis-sturz", [(10, "hallo"), (80, "puls"), (160, "rekap"), (200, "hautfarbe")])
    w = cold(run)
    assert w["status"] == evaluate.MISSING
    assert "keine Reaktion" in w["note"]
    assert "Er zittert deutlich" in w["note"]  # die Eskalation steht als Verlauf dabei, nicht als eigener Punkt
    assert sum("kalt" in x["label"] or "zittert" in x["label"] for x in warnings(run)) == 1


def test_timely_reaction(clf):
    run = run_at(clf, "basis-sturz", [(10, "hallo"), (80, "puls"), (95, "rettungsdecke drüber")])
    w = cold(run)
    assert w["status"] == evaluate.OK and "decke" in w["quote"]


def test_late_reaction(clf):
    run = run_at(clf, "basis-sturz", [(10, "hallo"), (80, "puls"), (130, "rettungsdecke drüber")])
    w = cold(run)
    assert w["status"] == evaluate.PARTIAL and "erst nach 50 s" in w["note"]


def test_warning_right_before_the_end_is_not_judged(clf):
    run = run_at(clf, "basis-sturz", [(10, "hallo"), (80, "puls"), (90, "rekap")])
    assert not any("kalt" in w["label"] for w in warnings(run))


def test_warning_after_first_minute_ended_is_ignored(clf):
    run = run_at(clf, "basis-sturz", [(10, "hallo"), (20, FUNK[0]), (30, FUNK[1]), (40, FUNK[2]), (80, None), (200, None)])
    assert run.ended_at == 3
    assert not any("kalt" in w["label"] for w in warnings(run))


def test_explicit_expectation_with_label(clf):
    run = run_at(clf, "a-bolus", [(10, "hallo"), (45, "husten sie mal"), (50, "rückenschläge")])
    w = next(w for w in warnings(run) if "blau" in w["label"])
    assert w["status"] == evaluate.OK


def test_warnings_do_not_change_the_verdict_but_lead_the_improvements(clf):
    run = run_at(clf, "basis-sturz", [(10, "hallo"), (80, "puls"), (160, "rekap"), (200, "hautfarbe")])
    res = evaluate.evaluate(run)
    assert any("kalt" in x for x in res["improve"][:3])


def test_process_events_are_not_warnings():
    """AED-Rhythmus, Kollege baut an …: Ereignisse mit `since` brauchen keine Reaktion."""
    s = content.scenarios()["bw-reanimation"]
    assert all(e.expect is None for e in s.events if e.since)
    assert s.events[0].expect["any"] == ["hlw"]  # Schnappatmung wird seltener → HLW


def test_every_expectation_names_known_intents():
    known = content.intents()
    for s in content.scenarios().values():
        for e in s.events:
            if e.expect:
                assert e.expect["any"] and all(i in known for i in e.expect["any"]), s.id


def test_unknown_intent_in_expect_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="unbekannter Intent"):
        content._expect({"expect": ["gibtsnicht"]}, {}, content.intents(), "x")


def test_case_notes_follow_the_evaluation(clf):
    run = run_at(clf, "basis-sturz", [(10, "hallo")])
    text = evaluate.as_text(evaluate.evaluate(run))
    assert "WORAUF ES IN DIESEM FALL ANKOMMT: Herr Petersen (68)" in text
    assert text.index("VERBESSERN") < text.index("WORAUF ES")
