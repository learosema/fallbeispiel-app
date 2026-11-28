"""Sprachausgabe (backend/speech.py): Sprechfassung, Stimmenzuordnung und dass jeder gesprochene Satz vertont wird."""
import re
from pathlib import Path

import pytest

from backend import content, solutions, speech
from backend.classifier import IntentClassifier
from backend.content import Line

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("raw, said", [
    ("Puls 104, RR 140/85, SpO2 96 %.", "Puls 104, Blutdruck 140 zu 85, Sättigung 96 Prozent."),
    ("Wach, GCS 15, BZ 118 mg/dl.", "Wach, Glasgow 15, Blutzucker 118."),
    ("AF 30/min, Temperatur 35,9 °C.", "Atemfrequenz 30 pro Minute, Temperatur 35 Komma 9 Grad."),
    ("Der AED ist dran, ca. 2 Minuten.", "Der Defi ist dran, circa 2 Minuten."),
    ("Markus? MARKUS!", "Markus? Markus!"),
    ("Wir sind auf dem DOM.", "Wir sind auf dem Dom."),
    ("seit 10:42 Uhr", "seit 10 Uhr 42"),
    ("Um 10:42, ich hab", "Um 10 Uhr 42, ich hab"),
    ("Markus … wir sind im Wald …", "Markus... wir sind im Wald..."),
])
def test_sprechfassung_qwen(raw, said):
    assert speech.for_engine(raw, "qwen") == said


def test_piper_spells_callsign_and_abbreviations():
    said = speech.for_engine("EVT1 von RotkreuzHamburg, verstanden, RTW und NEF kommen.", "piper")
    assert said == "E Fau Te 1 von Rotkreuz Hamburg, verstanden, Er Te We und Neff kommen."


def test_spoken_narrates_actions_and_drops_stage_directions():
    assert speech.spoken(Line("Kollege", "(übernimmt die HWS)")) == ("Befund", "Kollege übernimmt die HWS")
    assert speech.spoken(Line("Befund", "(keine Reaktion)")) == ("Befund", "keine Reaktion")
    assert speech.spoken(Line("Umstehende", "(aufgelöst) Er ist umgefallen!")) == ("Umstehende", "Er ist umgefallen!")
    assert speech.spoken(Line("Befund", "Du triffst ein (Funkrufname EVT1). Los.")) == ("Befund", "Du triffst ein. Los.")


def test_voices():
    assert speech.voice(None, "Leitstelle").engine == "piper"
    assert speech.voice(None, "Kollege").engine == "qwen"
    assert speech.voice("basis-sturz", "Patient").scenario == "basis-sturz"
    assert speech.voice(None, "Patient") is None  # Patient braucht einen Fall


def test_clip_ids_are_stable_and_distinct():
    a = speech.clip("basis-sturz", Line("Patient", "Achtundsechzig."))
    b = speech.clip("basis-sturz", Line("Patient", "Achtundsechzig."))
    c = speech.clip("x-kettensaege", Line("Patient", "Achtundsechzig."))
    assert a == b and a.id != c.id and re.fullmatch(r"[0-9a-f]{20}", a.id)


def test_ui_lines_still_in_frontend():
    """Intro und Ergebnis liest das Frontend selbst vor – die vertonten Fassungen müssen zu public/app.js passen."""
    app = (ROOT / "public" / "app.js").read_text(encoding="utf-8")
    assert "Übe die 1. Minute nach SANmemo bis zum Funkspruch." in app
    assert "Beginne mit der 1. Minute, danach geht der Einsatz weiter." in app
    assert '"Algorithmus " + result.verdict + "."' in app


@pytest.fixture(scope="module")
def all_clip_ids():
    return {c.id for c in speech.collect()}


@pytest.mark.parametrize("sid", sorted(content.scenarios()))
def test_every_line_of_the_solutions_is_rendered(sid, all_clip_ids):
    """Was beim Durchspielen gesagt wird, muss in der Vertonungsliste stehen (sonst fiele es auf die Browserstimme)."""
    clf = IntentClassifier(use_embeddings=False)
    missing = []
    for mode in ("full", "minute"):
        run, _ = solutions.play(sid, clf, mode)
        for turn in run.turns:
            for line in turn.lines:
                c = speech.clip(sid, line)
                if c and c.voice.engine == "qwen" and c.id not in all_clip_ids:
                    missing.append(f"{line.who}: {line.text}")
    assert not missing, "nicht in speech.collect():\n" + "\n".join(sorted(set(missing)))
