"""Musterlösungen (content/solutions): Jede ergibt im ganzen Fall und in der 1. Minute „Erfüllt“.

Ändert sich ein Fall, die Erkennung oder die Auswertung so, dass eine Lösung nicht mehr aufgeht, schlägt dieser Test
an – dann die Lösung anpassen (oder die Änderung überdenken). Läuft mit reinem Regex-Classifier und, wenn verfügbar,
mit Embeddings wie in der App.
"""
import os

import pytest

from backend import content, evaluate, solutions
from backend.classifier import IntentClassifier

SIDS = sorted(content.scenarios())
FALLBACKS = ("Was genau machst du?", "Wie meinst du das?", "sag es bitte konkreter", "Sag es mir genauer", "Was genau kontrollierst du?")


def classifiers():
    yield pytest.param(False, id="regex")
    yield pytest.param(True, id="embeddings", marks=pytest.mark.skipif(
        os.environ.get("INTENT_EMBEDDINGS") == "0", reason="Embeddings abgeschaltet"))


@pytest.fixture(scope="module", params=list(classifiers()))
def clf(request):
    return IntentClassifier(use_embeddings=request.param)


def test_every_scenario_has_a_solution():
    assert sorted(solutions.solutions()) == SIDS


@pytest.mark.parametrize("mode", ["full", "minute"])
@pytest.mark.parametrize("sid", SIDS)
def test_solution_is_fulfilled(clf, sid, mode):
    run, origin = solutions.play(sid, clf, mode)
    res = evaluate.evaluate(run, clf.embedder)
    open_items = [(sec["title"], it["label"], it["note"]) for sec in res["sections"] for it in sec["items"]
                  if it["status"] not in (evaluate.OK, evaluate.NA)]
    assert res["verdict"] == "Erfüllt", open_items or res["deviations"]
    assert not open_items, open_items
    assert run.died_at is None and not run.alone
    assert run.ended, "Lösung endet nicht mit dem Ende des Einsatzes (1. Minute bzw. Übergabe)"
    assert not res["vague"], res["vague"]


@pytest.mark.parametrize("sid", SIDS)
def test_solution_is_understood(clf, sid):
    """Kein Satz der Lösung führt zur Rückfrage des Kollegen – eine Musterlösung muss verstanden werden."""
    run, origin = solutions.play(sid, clf)
    asked = [t.text for t, step in zip(run.turns, origin)
             if step is not None and any(f in line.text for line in t.lines for f in FALLBACKS)]
    assert not asked, asked


def test_transcript_has_lines_and_phases(clf):
    tr = solutions.transcript("basis-sturz", clf, clf.embedder)
    assert tr["verdict"] == "Erfüllt"
    assert any("phase" in e for e in tr["entries"])
    assert any(e.get("who") == "Rettungsdienst" for e in tr["entries"])
    assert tr["notes"] and tr["key_actions"]
