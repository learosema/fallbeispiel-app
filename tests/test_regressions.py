"""Datengetriebene Regressionstests aus tests/regressions.yaml (Regex- und Embedding-Classifier)."""
import os
from pathlib import Path

import pytest
import yaml

from backend import content, engine, evaluate
from backend.classifier import IntentClassifier

CASES = yaml.safe_load((Path(__file__).parent / "regressions.yaml").read_text(encoding="utf-8"))
IDS = [f"{i:02d}-{c['text'][:30]}" for i, c in enumerate(CASES)]


def check(clf, case):
    hits = {h.intent for h in clf.classify(case["text"])}
    for i in case.get("expect", []):
        assert i in hits, f"{case['text']!r}: {i} nicht erkannt (erkannt: {sorted(hits)})"
    for i in case.get("not", []):
        assert i not in hits, f"{case['text']!r}: {i} fälschlich erkannt (erkannt: {sorted(hits)})"
    if "reply" in case or "no_reply" in case or "vague" in case:
        s = content.scenarios()[case.get("scenario", "basis-sturz")]
        run = engine.replay(s, case.get("mode", "minute"), engine.Settings(), [{"t": 5, "text": case["text"]}], clf)
        reply = " ".join(l.text for l in run.turns[-1].lines)
        if "reply" in case:
            assert case["reply"] in reply, f"{case['text']!r}: Antwort {reply!r} enthält nicht {case['reply']!r}"
        if "no_reply" in case:
            assert case["no_reply"] not in reply, f"{case['text']!r}: Antwort {reply!r} enthält {case['no_reply']!r}"
        if "vague" in case:
            vague = bool(evaluate.vague_findings(run, getattr(clf, "embedder", None)))
            assert vague == case["vague"], f"{case['text']!r}: vage={vague}, erwartet {case['vague']}"


@pytest.fixture(scope="module")
def regex_clf():
    return IntentClassifier(use_embeddings=False)


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_regression_regex(regex_clf, case):
    if case.get("vague") is True and not evaluate._VAGUE.search(case["text"].lower()):
        pytest.skip("nur über Embeddings erkennbar")
    check(regex_clf, case)


@pytest.fixture(scope="module")
def emb_clf():
    if os.environ.get("INTENT_EMBEDDINGS") == "0":
        pytest.skip("Embeddings abgeschaltet")
    return IntentClassifier(use_embeddings=True)


@pytest.mark.parametrize("case", CASES, ids=IDS)
def test_regression_embeddings(emb_clf, case):
    check(emb_clf, case)
