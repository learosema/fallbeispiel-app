"""Tests mit dem echten Embedding-Modell (lädt es beim ersten Mal herunter, ~470 MB).

Überspringen mit INTENT_EMBEDDINGS=0. Die Sätze hier kommen bewusst NICHT in den Beispielen
(content/intents.yaml, content/algorithm.yaml) vor – sie prüfen, ob Umschreibungen erkannt werden.
"""
import os

import pytest

from backend import evaluate
from backend.classifier import IntentClassifier

pytestmark = pytest.mark.skipif(os.environ.get("INTENT_EMBEDDINGS") == "0", reason="Embeddings abgeschaltet")


@pytest.fixture(scope="module")
def clf():
    return IntentClassifier(use_embeddings=True)


# ---------- Befundsprache ----------
# Gemessen mit maskiertem Themenwort: vage ≥ +0,03, konkret/Handlung ≤ −0,03 (Grenze bei 0).

VAGUE = [
    "puls ist unauffällig",
    "kreislauf im grünen bereich",
    "blutdruck ist im rahmen",
    "die vitalzeichen sind stabil",
    "haut schaut gut aus",
    "sättigung ist prima",
    pytest.param("puls fühlt sich gut an", marks=pytest.mark.xfail(reason="Grenzfall: Abstand −0,01, bewusst nicht in die Beispiele übernommen")),
    "die werte sind alle top",
]
CONCRETE_OR_ACTION = [
    "puls regelmäßig und kräftig",
    "rekap deutlich verlängert",
    "haut blass und feucht",
    "puls kaum tastbar",
    "wie ist der blutdruck",
    "ich taste den puls am handgelenk",
    "blutdruck hundertzehn zu siebzig",
    "sättigung liegt bei 92",
    "er atmet normal",
    "ich decke ihn zu",
]


@pytest.mark.parametrize("text", VAGUE)
def test_vague_paraphrase_is_flagged(clf, text):
    assert evaluate.is_vague(text, clf.embedder)


@pytest.mark.parametrize("text", CONCRETE_OR_ACTION)
def test_concrete_or_action_is_not_flagged(clf, text):
    assert not evaluate.is_vague(text, clf.embedder)


# ---------- Intent-Erkennung ----------

PARAPHRASES = [
    ("ich verschaffe mir einen überblick über die einsatzstelle", "lage_pruefen"),
    ("können sie mir erzählen wie es dazu kam", "was_passiert"),
    ("haben sie probleme beim atmen", "atmung_fragen"),
    ("sind sie sonst gesund", "sample_vorerkrankung"),
    ("wann haben sie zuletzt was zu sich genommen", "sample_mahlzeit"),
    ("haben sie sich sonst noch irgendwo verletzt", "bodycheck"),
    ("spüren sie wo ich sie berühre", "dms"),
]


@pytest.mark.parametrize("text,intent", PARAPHRASES)
def test_paraphrase_recognised(clf, text, intent):
    assert intent in {h.intent for h in clf.classify(text)}


@pytest.mark.parametrize("text", ["schönes wetter heute", "ich finde das alles sehr spannend"])
def test_small_talk_is_not_an_intent(clf, text):
    assert clf.classify(text) == []


@pytest.mark.parametrize("text", [
    "ich mache das jetzt mal so",
    pytest.param("können sie das bitte halten", marks=pytest.mark.xfail(reason="Grenzfall: Anweisung an den Patienten, landet bei „nicht aufstehen“")),
    "ich bin gleich wieder da", "okay alles klar",
    "ja genau", "na gut dann eben so", "warte mal eben", "ach so ist das", "hm ich weiß nicht genau",
])
def test_ambiguous_short_sentences_are_not_guessed(clf, text):
    """Liegen mehrere Intents gleichauf, lieber nachfragen als raten."""
    assert clf.classify(text) == [], [(h.intent, round(h.score, 2)) for h in clf.classify(text)]



@pytest.mark.parametrize("text,closing", [
    ("ist das für dich auch so", True),
    ("okay für dich", True),
    ("deine meinung", True),
    ("wir haben einen patienten männlich ende 60", False),
    ("kopfanprall", False),
    ("er hat sich den kopf gestoßen", False),
    ("wir brauchen rtw und nef", False),
])
def test_team_talk_closing_question_by_similarity(clf, text, closing):
    from backend import engine
    assert engine.TEAM_CLOSE.search(text) is None or closing  # nicht schon per Regex
    assert engine.is_team_close(text, clf) == closing
