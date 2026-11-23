"""Tests für Inhalte, Engine und Auswertung – mit reinem Regex-Classifier (schnell, ohne Modell-Download)."""
import re

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


def keys_of(res):
    return next(sec["items"] for sec in res["sections"] if sec["title"] == "SCHLÜSSELMASSNAHMEN")


def said(run, who=None):
    return [l.text for t in run.turns for l in t.lines if who is None or l.who == who]


# ---------- Inhalte ----------

def test_all_scenarios_load():
    sc = content.scenarios()
    assert len(sc) == 18
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
    run = play(clf, "basis-sturz", ["die blaue banane tanzt"])
    assert said(run) == [engine.FALLBACK.text]


def test_fallback_varies_but_starts_with_the_documented_question(clf):
    assert content.smalltalk().fallback[0] == engine.FALLBACK
    run = play(clf, "basis-sturz", ["die blaue banane tanzt"] * 2)
    replies = said(run, "Kollege")
    assert replies[0] == engine.FALLBACK.text and replies[1] != replies[0]


@pytest.mark.parametrize("text,reply", [
    ("danke", "Gerne"),
    ("okay", "Okay"),
    ("Moment bitte!", "Ansage"),
    ("Scheiße", "Schritt für Schritt"),
    ("was soll ich jetzt machen", "Einsatzstelle"),  # Tipp: erster offener Punkt ist die Lage
    ("gib mir mal das", "Was genau brauchst du"),
    ("schönes wetter heute", "Später"),
])
def test_smalltalk_gets_an_answer_but_no_intent(clf, text, reply):
    run = play(clf, "basis-sturz", [text])
    assert not run.turns[0].hits
    assert reply in " ".join(said(run))


def test_smalltalk_does_not_nod_off_unclear_actions(clf):
    # verankerte Muster: ein langer, nicht erkannter Satz bekommt weiter eine Rückfrage
    run = play(clf, "basis-sturz", ["okay ich mache jetzt das dings"])
    assert said(run) == [engine.FALLBACK.text]


def test_smalltalk_rotates_and_repeats(clf):
    run = play(clf, "basis-sturz", ["danke", "danke", "wie bitte"])
    replies = said(run)
    assert replies[0] != replies[1]
    assert replies[2] == replies[1]


def play_settings(clf, sid, lines, settings, mode="minute"):
    s = content.scenarios()[sid]
    return engine.replay(s, mode, settings, [{"t": 8 * (i + 1), "text": t} for i, t in enumerate(lines)], clf)


def test_tip_names_the_next_open_checklist_item(clf):
    run = play(clf, "basis-sturz", ["ist die einsatzstelle sicher", "hast du einen tipp"])
    assert run.turns[1].tip == "blutung"
    assert "Blutung" in said(run, "Kollege")[-1]


def test_no_tips_when_switched_off(clf):
    run = play_settings(clf, "basis-sturz", ["hast du einen tipp"], engine.Settings(tips=False))
    assert run.turns[0].tip is None
    assert "Leitung" in said(run)[0]


def test_tip_when_everything_is_done(clf):
    s = content.scenarios()["basis-sturz"]
    run = play(clf, "basis-sturz", ["was fehlt noch"])
    done = set(content.intents())  # alles erledigt
    assert engine.next_open(s, "minute", done) is None
    assert run.turns[0].tip == "lage"


def test_tips_do_not_reveal_the_breathing_finding():
    alg = content.algorithm()
    by_id = {it["id"]: it["tip"] for it in alg["minute_unconscious"]}
    assert by_id["seitenlage"] == by_id["hlw"]


def test_tips_are_noted_in_the_evaluation_but_keep_the_verdict(clf):
    steps = ["ist die einsatzstelle sicher", "ich ziehe handschuhe an", "hallo ich bin vom drk was ist passiert"]
    plain = evaluate.evaluate(play(clf, "basis-sturz", ["ist die einsatzstelle sicher", "hast du einen tipp", "ich prüfe auf bedrohliche blutungen"]))
    blut = next(i for sec in plain["sections"] for i in sec["items"] if i["id"] == "blutung")
    assert blut["status"] == evaluate.OK and "nach Tipp" in blut["note"]
    assert "Blutung erst nach Tipp vom Kollegen" in plain["improve"]
    other = evaluate.evaluate(play(clf, "basis-sturz", ["ist die einsatzstelle sicher", "okay", "ich prüfe auf bedrohliche blutungen"]))
    assert plain["verdict"] == other["verdict"]


def test_smalltalk_does_not_change_the_evaluation(clf):
    steps = ["ist die einsatzstelle sicher", "ich ziehe handschuhe an", "hallo ich bin vom drk was ist passiert"]
    plain = evaluate.evaluate(play(clf, "basis-sturz", steps))
    chatty = evaluate.evaluate(play(clf, "basis-sturz", ["okay", steps[0], "danke", steps[1], "moment", steps[2]], step=4))
    def keys(r):
        return [(i["label"], i["status"]) for sec in r["sections"] for i in sec["items"] if sec["title"] != "ZEITLEISTE"]
    assert keys(plain) == keys(chatty)


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
    assert said(run) == [content.smalltalk().team_ack[0].text]


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


COUNT_TO_30 = " ".join(str(i) for i in range(1, 31))


def test_reanimation_runs_until_rescue_service(clf):
    log = [
        {"t": 5, "text": "hallo hören sie mich"},
        {"t": 8, "text": "atemkontrolle keine normale atmung"},
        {"t": 10, "text": "notruf rtw und nef nachfordern"},
        {"t": 15, "text": "ich beginne sofort mit der herzdruckmassage"},
    ]
    run = replay_log(clf, "bw-reanimation", log)
    assert run.next_event_at == 30, "zuerst AED: 15 s nach HLW-Beginn"

    log.append({"t": 30, "text": "", "tick": True})
    run = replay_log(clf, "bw-reanimation", log)
    assert [l.text for l in run.turns[-1].lines] == [
        "AED ist dran.", "Patient nicht berühren! Herzrhythmus wird analysiert …", "Schock empfohlen. Blinkende Taste drücken."]

    # Zählen vor der Beatmungsbereitschaft: nur drücken, keine Beatmung
    log.append({"t": 35, "text": COUNT_TO_30})
    run = replay_log(clf, "bw-reanimation", log)
    assert not any("Beatmungen" in x for x in said(run))

    log.append({"t": 40, "text": "", "tick": True})
    run = replay_log(clf, "bw-reanimation", log)
    assert [l.text for l in run.turns[-1].lines] == ["Beutel mit Maske ist dran, Beatmung mit Raumluft möglich."]

    log.append({"t": 41, "text": COUNT_TO_30})
    run = replay_log(clf, "bw-reanimation", log)
    assert "(gibt zwei Beatmungen mit dem Beutel)" in [l.text for l in run.turns[-1].lines]

    # danach in dieser Reihenfolge: Absaugbereitschaft, Sauerstoff, Guedel-Tubus
    log += [{"t": 50, "text": "", "tick": True}, {"t": 60, "text": "", "tick": True}, {"t": 70, "text": "", "tick": True}]
    run = replay_log(clf, "bw-reanimation", log)
    setup = [x for x in said(run, "Kollege") if x in (
        "AED ist dran.", "Beutel mit Maske ist dran, Beatmung mit Raumluft möglich.", "Absaugbereitschaft hergestellt.",
        "Sauerstoff ist am Beutel angeschlossen.", "Guedel-Tubus liegt.")]
    assert setup == ["AED ist dran.", "Beutel mit Maske ist dran, Beatmung mit Raumluft möglich.",
                     "Absaugbereitschaft hergestellt.", "Sauerstoff ist am Beutel angeschlossen.", "Guedel-Tubus liegt."]

    # Schock, dann alle 2 Minuten erneut Analyse – kein ROSC
    log.append({"t": 72, "text": "Schock! Alle weg!"})
    for k in range(1, 4):
        log += [{"t": 30 + 120 * k, "text": "", "tick": True}, {"t": 32 + 120 * k, "text": "schock alle weg"}]
    run = replay_log(clf, "bw-reanimation", log)
    assert sum("Schock abgegeben" in x for x in said(run, "AED")) == 4
    assert not any("atmet wieder" in x or "Kein Schock" in x for x in said(run)), "ohne erweiterte Maßnahmen kein ROSC"

    # RTW + NEF kommen 8 Minuten nach der Nachforderung, danach keine Analysen mehr
    log += [{"t": 490, "text": "", "tick": True}, {"t": 500, "text": "übergabe: kollaps um 10 uhr, hlw seit 10:01, vier schocks"},
            {"t": 505, "text": "habt ihr noch fragen"}]
    run = replay_log(clf, "bw-reanimation", log)
    assert any(l.who == "Rettungsdienst" and "Notarzt" in l.text for l in run.turns[-3].lines)
    assert "weiter" in said(run, "Rettungsdienst")[-1]  # „… ihr drückt bitte weiter, bis wir so weit sind“
    assert run.ended and run.next_event_at is None

    res = evaluate.evaluate(replay_log(clf, "bw-reanimation", log, mode="full"))  # Zählen gehört zum ganzen Fall
    keys = {it["label"]: it for it in keys_of(res)}
    assert keys["Sicherheit beim Schock („Schock! Alle weg!“)"]["status"] == evaluate.OK
    assert keys["Sobald beatmet werden kann, laut bis 30 gezählt, dann 2 Beatmungen"]["status"] == evaluate.OK


@pytest.mark.parametrize("text", [
    COUNT_TO_30,
    "10 20 5 6 7 8 9 30",
    "zehn. zwanzig. fünf, sechs, sieben, acht, neun, dreißig",
    "einundzwanzig zweiundzwanzig ... achtundzwanzig neunundzwanzig dreißig",
])
def test_counting_to_30_variants(clf, text):
    intents = {h.intent for h in clf.classify(text)}
    assert {"hlw", "hlw_zaehlen", "hlw_30"} <= intents, intents


@pytest.mark.parametrize("text", ["blutdruck 130 zu 80", "um 9 30 ist er umgefallen", "sättigung 95 puls 110"])
def test_numbers_are_not_counting(clf, text):
    assert not {"hlw_zaehlen", "hlw_30"} & {h.intent for h in clf.classify(text)}


def test_counting_only_before_ventilation_is_not_enough(clf):
    log = [{"t": 5, "text": "ich beginne mit der herzdruckmassage"}, {"t": 10, "text": COUNT_TO_30},
           {"t": 20, "text": "", "tick": True}, {"t": 30, "text": "", "tick": True}, {"t": 60, "text": "ich drücke weiter"}]
    res = evaluate.evaluate(replay_log(clf, "bw-reanimation", log, mode="full"))
    key = next(it for it in keys_of(res) if "bis 30 gezählt" in it["label"])
    assert key["status"] == evaluate.MISSING


def test_no_rescue_service_without_request(clf):
    log = [{"t": 5, "text": "ich beginne mit der herzdruckmassage"}] + [{"t": 5 + 60 * k, "text": "", "tick": True} for k in range(1, 12)]
    run = replay_log(clf, "bw-reanimation", log)
    assert not any(l.who == "Rettungsdienst" for t in run.turns for l in t.lines)


def test_tick_without_due_event_says_nothing(clf):
    run = replay_log(clf, "basis-sturz", [{"t": 5, "text": "hallo"}, {"t": 6, "text": "", "tick": True}])
    assert run.turns[-1].lines == []


def test_next_event_at_points_to_deterioration(clf):
    run = play(clf, "basis-sturz", ["hallo"])
    assert run.next_event_at == 8 + engine.SILENCE_SECONDS  # erst meldet sich der Patient bei Stille …
    run = play(clf, "basis-sturz", ["hallo", "puls", "rekap", "hautfarbe", "decke"], step=10)
    assert run.next_event_at == 60  # … sonst „will nach Hause“ bei 60 s, Frieren bei 75 s
    run = play(clf, "basis-sturz", ["wir decken sie zu", "ich kläre sie auf, sie sollten ins krankenhaus"])
    assert run.next_event_at == 16 + engine.SILENCE_SECONDS


def test_rescue_service_arrives_and_handover_ends(clf):
    lines = ["evt eins fordere einen rtw nach"] + ["puls"] * 9 + ["übergabe an den rettungsdienst", "habt ihr noch fragen"]
    run = play(clf, "basis-sturz", lines, mode="full", step=60)
    assert any(l.who == "Rettungsdienst" for t in run.turns for l in t.lines)
    assert run.ended


# ---------- Auswertung ----------

GOOD_MINUTE = [
    "ist die lage sicher", "keine bedrohliche blutung", "hallo wir sind vom drk was ist passiert",
    "kollege bitte hws stabilisieren", "bekommen sie gut luft tut das atmen weh", "ich schaue auf die lippen",
    "hautfarbe puls rekap", "bauch becken oberschenkel", "ist ihnen kalt", "wir decken sie zu",
    "teambesprechung wir haben einen patienten männlich ende 60 wach reagiert angemessen",
    "kopfanprall", "schmerzen im nacken verdacht auf sht und hws trauma",
    "wir brauchen rtw und nef siehst du das auch so",
    "rotkreuzhamburg von evt eins kommen",
    "männlicher patient ende sechzig gestürzt wach und ansprechbar verdacht auf sht wir brauchen rtw und nef kommen",
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
    key = next(it for it in keys_of(res) if "Blutstillung" in it["label"])
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


def test_vague_finding_language_is_flagged(clf):
    run = play(clf, "basis-sturz", ["puls normal", "rekap unter zwei sekunden puls regelmäßig gut tastbar", "atmet er normal"])
    res = evaluate.evaluate(run)
    assert res["vague"] == ["puls normal"]
    assert "BEFUNDSPRACHE" in evaluate.as_text(res)
    assert any("konkret" in x for x in res["improve"])


def test_unconscious_normal_breathing_is_not_flagged(clf):
    res = evaluate.evaluate(play(clf, "bw-seitenlage", ["atemkontrolle er atmet normal"]))
    assert res["vague"] == []


# ---------- gemeldete fachliche Fehler ----------

@pytest.mark.parametrize("text,intent", [
    ("ich taste sie ab", "trauma_check"),
    ("ich taste ihn mal ab", "trauma_check"),
    ("rücken klopfen", "rueckenschlaege"),
    ("rücken klopen", "rueckenschlaege"),
    ("ich klopfe ihm kräftig auf den rücken", "rueckenschlaege"),
    ("ich schlage ihm fünfmal auf den rücken", "rueckenschlaege"),
    ("können sie mir erzählen wie es dazu kam", "was_passiert"),
])
def test_reported_phrases(clf, text, intent):
    intents = {h.intent for h in clf.classify(text)}
    assert intent in intents and "bz" not in intents, intents


def test_lying_on_back_is_not_back_blows(clf):
    assert "rueckenschlaege" not in {h.intent for h in clf.classify("wir legen ihn auf den rücken")}


@pytest.mark.parametrize("sid", ["a-bolus", "b-asthma", "bw-reanimation", "dom-fahrgeschaeft-kollaps"])
def test_blanket_not_expected_when_warm_and_awake_or_during_cpr(clf, sid):
    res = evaluate.evaluate(play(clf, sid, ["hallo"]))
    waerme = next(it for it in res["sections"][0]["items"] if it["id"] == "waerme")
    assert waerme["status"] == evaluate.NA


def test_blanket_still_expected_when_cold(clf):
    res = evaluate.evaluate(play(clf, "basis-sturz", ["hallo"]))
    waerme = next(it for it in res["sections"][0]["items"] if it["id"] == "waerme")
    assert waerme["status"] == evaluate.MISSING


# ---------- Abdeckung: jede Kombination aus Fall und Intent hat eine Antwort ----------

NO_REPLY_NEEDED = {"smalltalk", "funk_anruf", "funk_meldung", "funk_ende", "nachforderung"}


@pytest.mark.parametrize("sid", list(content.scenarios()))
def test_every_intent_has_an_answer(sid):
    s = content.scenarios()[sid]
    missing = [i for i in content.intents() if i not in NO_REPLY_NEEDED and engine.respond(s, i, dict(s.state)) is None]
    assert not missing, f"{sid}: keine Antwort auf {missing}"


def test_breathing_question_in_cpr_gives_breathing_finding(clf):
    for text in ["Atmung?", "Kollege, wie beurteilst du die Atmung?", "wie ist die atmung"]:
        run = play(clf, "bw-reanimation", [text])
        assert said(run) == ["Keine normale Atmung, nur vereinzelte schnappende Atemzüge. Haut blass-livide."], (text, said(run))


def test_patient_questions_to_unconscious_get_no_reaction(clf):
    run = play(clf, "bw-seitenlage", ["wo tut es ihnen weh"])
    assert said(run) == ["(keine Reaktion)"]


def test_no_sugar_for_unconscious(clf):
    run = play(clf, "bw-sommer", ["ich gebe ihm traubenzucker"])
    assert "nichts in den Mund" in said(run)[0]


@pytest.mark.parametrize("sid,expect", [("basis-sturz", "Achtundsechzig."), ("dom-fahrgeschaeft-kollaps", "Siebzehn."),
                                        ("bw-reanimation", "Anfang fünfzig")])
def test_age_question(clf, sid, expect):
    run = play(clf, sid, ["wie alt sind sie?"])
    assert [h.intent for h in run.turns[0].hits] == ["alter_fragen"]
    assert expect in said(run)[0]


@pytest.mark.parametrize("sid", list(content.scenarios()))
def test_situation_mentions_rough_age(clf, sid):
    lage = " ".join(said(play(clf, sid, ["wie ist die lage"])))
    assert re.search(r"älter|jung|jugendlich|mittleren alters|etwa (anfang|mitte|ende) \w+|etwa \w+zig", lage, re.I), lage


def test_rough_age_is_enough_for_radio(clf):
    run = play(clf, "basis-sturz", ["rotkreuzhamburg von evt eins kommen",
                                    "älterer mann gestürzt verdacht auf sht wir brauchen rtw kommen", "evt eins ende"])
    funk = next(it for it in evaluate.evaluate(run)["sections"][0]["items"] if it["id"] == "funk")
    assert "Alter" not in funk["note"], funk["note"]


def test_full_case_key_actions_not_checked_in_first_minute(clf):
    labels = [it["label"] for it in keys_of(evaluate.evaluate(play(clf, "basis-sturz", GOOD_MINUTE)))]
    assert "Blutverdünner erfragt" not in labels
    assert "Aufklärung, warum er nicht nach Hause gehen sollte" not in labels
    assert "Manuelle HWS-Stabilisierung nach Sturz mit Kopfanprall" in labels
    full = [it["label"] for it in keys_of(evaluate.evaluate(play(clf, "basis-sturz", GOOD_MINUTE, mode="full")))]
    assert "Blutverdünner erfragt" in full


def test_sampler(clf):
    assert "sample_risiko" in {h.intent for h in clf.classify("rauchen sie? gibt es herzkrankheiten in der familie?")}
    assert "sample_mahlzeit" in {h.intent for h in clf.classify("wann war der letzte stuhlgang")}
    lines = GOOD_MINUTE + ["was tut weh", "allergien", "medikamente", "vorerkrankungen", "wann zuletzt gegessen", "rauchen sie"]
    res = evaluate.evaluate(play(clf, "basis-sturz", lines, mode="full"))
    sampler = next(it for it in res["sections"][1]["items"] if it["id"] == "sample")
    assert sampler["status"] == evaluate.OK and sampler["label"].startswith("SAMPLER")


@pytest.mark.parametrize("text", ["Puls?", "Rekap?", "puls", "Puls und Rekap?", "wie ist der puls", "ist die haut blass?", "blutdruck bitte"])
def test_questions_and_examinations_are_not_vague(clf, text):
    run = play(clf, "basis-sturz", [text])
    assert evaluate.vague_findings(run) == [], text


def test_stated_vague_finding_still_flagged(clf):
    run = play(clf, "basis-sturz", ["Puls?", "kurze teambesprechung: puls normal, kreislauf ok"])
    assert evaluate.vague_findings(run) == ["kurze teambesprechung: puls normal, kreislauf ok"]


@pytest.mark.parametrize("text", ["Atmung?", "wie ist die atmung", "Kollege, wie beurteilst du die Atmung?", "ich beurteile die atmung"])
def test_breathing_assessment_gives_finding_for_conscious_patient(clf, text):
    run = play(clf, "basis-sturz", [text])
    assert [h.intent for h in run.turns[0].hits] == ["atmung_beurteilen"], text
    assert said(run) == ["Atmung ruhig und regelmäßig, ca. 16/min, keine Atemnot, er spricht in ganzen Sätzen."]


def test_breathing_question_goes_to_patient(clf):
    run = play(clf, "basis-sturz", ["bekommen sie gut luft?"])
    assert [h.intent for h in run.turns[0].hits] == ["atmung_fragen"]
    assert run.turns[0].lines[0].who == "Patient"


def test_breathing_question_to_unconscious_gets_no_reaction(clf):
    assert said(play(clf, "bw-seitenlage", ["bekommen sie gut luft?"])) == ["(keine Reaktion)"]


def test_breathing_assessment_counts_for_checklist(clf):
    res = evaluate.evaluate(play(clf, "basis-sturz", ["Atmung?", "tut das atmen weh", "lippen"]))
    atmung = next(it for it in res["sections"][0]["items"] if it["id"] == "atmung")
    assert atmung["status"] == evaluate.OK


@pytest.mark.parametrize("text,intent", [
    ("Kollege, versorge die Wunde", "wunde_versorgen"),
    ("Kollege, versorg bitte die Platzwunde", "wunde_versorgen"),
    ("Kollege, übernimm den Kopf", "hws_manuell"),
    ("kollege, kümmere dich um die blutung", "blutung_stillen"),
    ("kannst du bitte den Blutdruck messen", "rr"),
    ("miss mal den Blutzucker", "bz"),
    ("leg ihm bitte eine Decke drüber", "decke"),
    ("kannst du das bein schienen", "immobilisieren"),
])
def test_delegating_to_colleague(clf, text, intent):
    assert intent in {h.intent for h in clf.classify(text)}, text


@pytest.mark.parametrize("text,wrong", [("schau mal nach den pupillen", "sample_medikamente"),
                                        ("zähl mal die atemfrequenz", "hlw_details")])
def test_no_false_hits(clf, text, wrong):
    assert wrong not in {h.intent for h in clf.classify(text)}


def test_colleague_dresses_the_wound(clf):
    assert said(play(clf, "dom-krampf", ["Kollege, versorge die Wunde"])) == ["(versorgt die Platzwunde am Hinterkopf mit Kompresse und Verband)"]


def test_patient_can_be_persuaded(clf):
    # ohne Wissen um den Blutverdünner: erst Ablehnung, beim zweiten Anlauf Zustimmung
    run = play(clf, "basis-sturz", ["das sollte ein arzt abklären", "bitte lassen sie sich untersuchen"])
    assert "nur nach Hause" in said(run, "Patient")[0]
    assert "wenn Sie meinen" in said(run, "Patient")[-1]
    # mit Blutverdünner: sofort einsichtig
    run = play(clf, "basis-sturz", ["nehmen sie medikamente", "wegen des blutverdünners sollten sie ins krankenhaus"])
    assert "lass ich mich mitnehmen" in said(run, "Patient")[-1]


# ---------- Früher Funkspruch, Reaktion, Schlaganfall ----------

STROKE_FAST = [
    "ist die einsatzstelle sicher", "keine bedrohliche blutung", "hallo wir sind vom drk was ist passiert",
    "seit wann ist das so",
    "rotkreuzhamburg von evt eins kommen",
    "männlicher patient anfang siebzig wach reagiert verlangsamt sprache verwaschen symptombeginn 10:42 "
    "verdacht auf schlaganfall wir brauchen einen rtw kommen",
    "evt eins ende",
]
STROKE_REST = [
    "bekommen sie gut luft tut das atmen weh", "ich schaue auf die lippen", "hautfarbe puls rekap",
    "ist ihnen kalt", "kurze teambesprechung patient wach reagiert verlangsamt verdacht auf schlaganfall rtw ist alarmiert",
]


def test_early_radio_is_not_out_of_order_and_does_not_end_the_minute(clf):
    run = play(clf, "d-schlaganfall", STROKE_FAST)
    assert "1. Minute ist beendet" not in " ".join(said(run))
    res = evaluate.evaluate(play(clf, "d-schlaganfall", STROKE_FAST + STROKE_REST))
    assert not [d for d in res["deviations"] if "Reihe" in d], res["deviations"]
    key = next(k for k in keys_of(res) if "Früher Funkspruch" in k["label"])
    assert key["status"] == evaluate.OK


def test_early_radio_case_ends_minute_when_everything_is_done(clf):
    run = play(clf, "d-schlaganfall", STROKE_FAST + STROKE_REST)
    assert run.ended and "1. Minute ist beendet" in said(run)[-1]


def test_late_radio_still_ends_the_minute_in_normal_cases(clf):
    run = play(clf, "basis-sturz", ["rotkreuzhamburg von evt eins kommen", "älterer mann gestürzt rtw kommen", "evt eins ende"])
    assert run.ended


def test_tip_suggests_early_radio_once_the_problem_is_known(clf):
    run = play(clf, "d-schlaganfall", ["ist die einsatzstelle sicher", "hallo wir sind vom drk", "hast du einen tipp"])
    assert run.turns[-1].tip == "funk"
    run = play(clf, "basis-sturz", ["ist die einsatzstelle sicher", "hallo wir sind vom drk", "hast du einen tipp"])
    assert run.turns[-1].tip != "funk"


def test_reaction_counts_when_named_in_team_talk_or_radio(clf):
    res = evaluate.evaluate(play(clf, "basis-sturz", GOOD_MINUTE))
    items = {it["id"]: it for it in res["sections"][0]["items"]}
    assert items["neuro"]["status"] == evaluate.OK


def test_normal_reaction_need_not_be_named(clf):
    """Unauffällige Reaktion: gehört nicht in Teambesprechung/Funk (nur Auffälliges), Neurologie gilt mit dem Ansprechen."""
    lines = [l.replace(" wach reagiert angemessen", "").replace(" wach und ansprechbar", "") for l in GOOD_MINUTE]
    res = evaluate.evaluate(play(clf, "basis-sturz", lines))
    items = {it["id"]: it for it in res["sections"][0]["items"]}
    assert items["team"]["status"] == evaluate.OK, items["team"]["note"]
    assert "Reaktion" not in items["funk"]["note"]
    assert items["neuro"]["status"] == evaluate.OK


ABNORMAL_MINUTE = [
    "ist die lage sicher", "keine bedrohliche blutung", "hallo wir sind vom drk was ist passiert",
    "bekommen sie gut luft tut das atmen weh", "ich schaue auf die lippen", "hautfarbe puls rekap", "ist ihnen kalt",
    "wir legen eine decke um",
    "kurz zusammengefasst patientin weiblich mitte fünfzig kaltschweißig verdacht auf unterzucker wir brauchen einen rtw siehst du das auch so",
    "rotkreuzhamburg von evt eins kommen",
    "wir haben hier eine patientin weiblich mitte fünfzig verdacht auf unterzucker wir benötigen einen rtw kommen",
    "evt eins ende",
]


def test_abnormal_reaction_missing_in_team_talk_and_radio_is_noted(clf):
    res = evaluate.evaluate(play(clf, "d-hypo", ABNORMAL_MINUTE))
    items = {it["id"]: it for it in res["sections"][0]["items"]}
    assert items["team"]["status"] == evaluate.PARTIAL and "Reaktion" in items["team"]["note"]
    assert "Reaktion" in items["funk"]["note"]
    assert items["neuro"]["status"] == evaluate.MISSING


@pytest.mark.parametrize("sid, text", [
    ("basis-sturz", "Kurz zusammengefasst: Patient männlich, Ende sechzig. Sturz mit Kopfanprall, Nackenschmerzen. "
                    "Verdacht auf HWS-Trauma. Wir brauchen einen RTW. Siehst du das auch so?"),
    ("d-hypo", "Kurz zusammengefasst: Patientin weiblich, Mitte fünfzig, verwirrt, kaltschweißig. Verdacht auf Unterzucker. "
               "Wir brauchen einen RTW, ich messe gleich den Blutzucker. Siehst du das auch so?"),
])
def test_cheat_sheet_team_talk_examples_are_complete(clf, sid, text):
    """Die Beispiele im Spicker (public/spicker.html) ergeben eine vollständige Teambesprechung."""
    run = play(clf, sid, ["hallo wir sind vom drk", text])
    team = next(it for it in evaluate.evaluate(run)["sections"][0]["items"] if it["id"] == "team")
    assert team["status"] == evaluate.OK, team["note"]
    assert "bz" not in run.first   # während der Besprechung wird nichts ausgeführt


def test_orientation_is_not_part_of_the_first_minute():
    alg = content.algorithm()
    minute = [i for it in alg["minute_conscious"] for i in content._item_refs(it)]
    assert "orientierung" not in minute and "fast" not in minute
    d = next(it for it in alg["full"] if it["id"] == "d")
    assert d["extra"]["conscious"] == ["orientierung", "fast"]


def test_symptom_onset(clf):
    run = play(clf, "d-schlaganfall", ["seit wann ist das so"])
    assert [h.intent for h in run.turns[0].hits] == ["symptombeginn"] and "10:42" in said(run)[0]
    res = evaluate.evaluate(play(clf, "dom-krampf", ["seit wann krampft er"], mode="full"))
    assert next(k for k in keys_of(res) if k["label"] == "Anfallsdauer erfasst")["status"] == evaluate.OK


# ---------- Eskalation: allein lassen, Stille, Tod ----------

def replay_ticks(clf, sid, script, until=330, mode="minute"):
    """Wie der Browser: Äußerungen zu festen Zeiten, dazwischen Takte zu next_event_at."""
    s = content.scenarios()[sid]
    log, pending = [], sorted(script.items())
    while True:
        run = engine.replay(s, mode, engine.Settings(), log, clf) if log else None
        nxt = run.next_event_at if run else None
        if pending and (nxt is None or pending[0][0] <= nxt):
            t, text = pending.pop(0)
            log.append({"t": t, "text": text})
        elif nxt is not None and nxt <= until:
            log.append({"t": nxt, "text": "", "tick": True})
        else:
            return run


def test_untreated_extreme_bleeding_ends_in_death(clf):
    run = replay_ticks(clf, "x-kettensaege", {5: "hallo was ist passiert"})
    assert run.died_at == 270 and run.ended and engine.DIED.text in said(run)
    res = evaluate.evaluate(run)
    assert res["verdict"] == "Nicht erfüllt" and "verstorben" in res["improve"][0]
    after = engine.replay(content.scenarios()["x-kettensaege"], "minute", engine.Settings(),
                          [{"t": 5, "text": "hallo"}, {"t": 271, "text": "", "tick": True}, {"t": 280, "text": "puls"}], clf)
    assert said(after)[-1] == engine.AFTER_DEATH.text and not after.turns[-1].hits


def test_stopped_bleeding_prevents_death(clf):
    run = replay_ticks(clf, "x-kettensaege", {5: "starke blutung kollege tourniquet anlegen"})
    assert run.died_at is None and not run.state.get("bewusstlos")


def test_unconscious_during_case_does_not_talk(clf):
    run = replay_ticks(clf, "x-kettensaege", {5: "hallo", 160: "haben sie allergien"}, until=165)
    assert not run.state.get("verstorben") and run.state.get("bewusstlos")
    last = run.turns[-1] if run.turns[-1].text else run.turns[-2]
    assert all(l.who != "Patient" for l in last.lines), last.lines


def test_leaving_the_patient_alone(clf):
    run = replay_ticks(clf, "basis-sturz", {5: "hallo", 10: "wir holen kurz was aus dem auto", 60: "so wir sind wieder da"}, until=60)
    assert run.alone == [(10.0, 60.0)]
    calls = [l.text for t in run.turns[2:] for l in t.lines if l.who == "Patient"]
    assert calls, "der Patient meldet sich, wenn er allein ist"
    res = evaluate.evaluate(run)
    assert any("nie allein" in i for i in res["improve"]) and any("allein gelassen" in c for c in res["course"])


def test_doing_something_means_you_are_back(clf):
    run = play(clf, "basis-sturz", ["wir lassen sie kurz allein", "ich fühle den puls"])
    assert engine.BACK.text in said(run) and not run.state.get("allein") and run.alone[0][1] == 16


def test_colleague_stays_when_only_i_leave(clf):
    run = play(clf, "basis-sturz", ["ich gehe kurz zum auto"])
    assert "ich bleibe hier" in said(run)[0] and not run.state.get("allein")


def test_silence_makes_the_patient_speak_once(clf):
    run = replay_ticks(clf, "basis-sturz", {5: "hallo"}, until=59)
    silent = [t for t in run.turns if t.text == "" and any(l.who == "Patient" for l in t.lines)]
    assert len(silent) == 1 and silent[0].t == 35


def test_no_silence_lines_for_unconscious_patients(clf):
    run = replay_ticks(clf, "bw-seitenlage", {5: "hallo hören sie mich"}, until=59)
    assert all(l.who != "Patient" for t in run.turns[1:] for l in t.lines)


def test_open_radio_goes_to_dispatch_even_without_kommen(clf):
    run = play(clf, "x-kettensaege", [
        "rotkreuz hamburg von evt eins kommen",
        "wir haben hier einen patienten männlich und der hat eine kritische blutung",
        "etwa mitte vierzig wach reagiert angemessen verdacht auf arterielle blutung",
        "wir brauchen rtw und nef kommen", "evt eins ende",
    ])
    assert [t.lines[0].who for t in run.turns[1:4]] == ["Leitstelle"] * 3  # danach ggf. Verschlechterung des Falls
    assert said(run)[1] == "Verstanden." and "blutung_pruefen" not in run.first
    funk = next(it for it in evaluate.evaluate(run)["sections"][0]["items"] if it["id"] == "funk")
    assert funk["status"] == evaluate.OK, funk["note"]


def test_patient_sentence_leaves_a_forgotten_radio_call(clf):
    run = play(clf, "basis-sturz", ["rotkreuzhamburg von evt eins kommen", "älterer mann gestürzt rtw kommen", "ich fühle den puls"])
    assert run.turns[-1].lines[0].who == "Befund" and not run.state.get("funk_offen")
    assert said(run)[-1] == "EVT1 von RotkreuzHamburg, bitte Funkdisziplin, beenden Sie das Gespräch."
    run = play(clf, "basis-sturz", ["rotkreuzhamburg von evt eins kommen", "älterer mann gestürzt rtw kommen", "ich fühle den puls",
                                    "evt eins ende"])
    assert "funk_ende" in run.first
    funk = next(it for it in evaluate.evaluate(run)["sections"][0]["items"] if it["id"] == "funk")
    assert "Funkdisziplin" in funk["note"] and "Ende“ fehlt" not in funk["note"]


def test_radio_message_in_several_parts(clf):
    run = play(clf, "x-kettensaege", [
        "starke blutung kollege tourniquet anlegen",
        "rotkreuzhamburg von evt eins kommen",
        "patient männlich etwa mitte 40",
        "kritische schnittverletzung am oberschenkel tourniquet angelegt",
        "wach reagiert angemessen verdacht auf arterielle blutung",
        "wir brauchen einmal rtw nef kommen",
        "evt eins ende",
    ], step=3)
    replies = [t.lines[0].text for t in run.turns[2:6]]
    assert replies == ["Verstanden.", "Verstanden.", "Verstanden.", "RTW NEF kommt, verstanden."], replies
    funk = next(it for it in evaluate.evaluate(run)["sections"][0]["items"] if it["id"] == "funk")
    assert funk["status"] == evaluate.OK, funk["note"]


@pytest.mark.parametrize("text,requested", [
    ("wir brauchen einmal rtw nef kommen", True),
    ("wir benötigen einen rtw kommen", True),
    ("bitte rtw und notarzt kommen", True),
    ("einmal rtw kommen", True),
    ("rtw ist schon alarmiert kommen", False),
    ("der rettungsdienst ist informiert kommen", False),
])
def test_dispatch_confirms_resources_only_when_requested(clf, text, requested):
    run = play(clf, "basis-sturz", ["rotkreuzhamburg von evt eins kommen", "älterer mann gestürzt " + text])
    reply = said(run)[-1]
    assert ("kommt, verstanden" in reply) == requested, reply
    assert ("nachforderung" in run.first) == requested


def test_nef_becomes_necessary_after_deterioration(clf):
    first_call = {5: "rotkreuzhamburg von evt eins kommen",
                  8: "patientin mitte fünfzig verwirrt verdacht auf unterzucker wir brauchen einen rtw kommen", 11: "evt eins ende"}
    run = replay_ticks(clf, "d-hypo", first_call, until=260, mode="full")
    funk = next(it for it in evaluate.evaluate(run)["sections"][0]["items"] if it["id"] == "funk")
    assert "NEF nach der Verschlechterung nicht nachgefordert" in funk["note"]
    second = first_call | {250: "rotkreuzhamburg von evt eins kommen",
                           253: "patientin jetzt bewusstlos wir brauchen zusätzlich einen nef kommen", 256: "evt eins ende"}
    run = replay_ticks(clf, "d-hypo", second, until=260, mode="full")
    assert "NEF kommt, verstanden." in said(run)
    funk = next(it for it in evaluate.evaluate(run)["sections"][0]["items"] if it["id"] == "funk")
    assert "NEF" not in funk["note"], funk["note"]


def test_early_nef_is_fine_before_deterioration(clf):
    run = play(clf, "d-hypo", ["rotkreuzhamburg von evt eins kommen",
                               "patientin mitte fünfzig verwirrt wach verdacht auf unterzucker wir brauchen rtw und nef kommen", "evt eins ende"])
    funk = next(it for it in evaluate.evaluate(run)["sections"][0]["items"] if it["id"] == "funk")
    assert "NEF" not in funk["note"], funk["note"]



HANDOVER_SETUP = ["rotkreuzhamburg von evt eins kommen",
                  "älterer mann gestürzt wach verdacht auf sht wir brauchen einen rtw kommen", "evt eins ende"]


def _arrived(clf, extra, sid="basis-sturz"):
    log = [{"t": 3 * (i + 1), "text": x} for i, x in enumerate(HANDOVER_SETUP)]
    log.append({"t": 490, "text": "", "tick": True})  # Rettungsdienst ist da
    log += [{"t": 492 + 3 * i, "text": x} for i, x in enumerate(extra)]
    return engine.replay(content.scenarios()[sid], "full", engine.Settings(), log, clf)


def _handover_item(run):
    res = evaluate.evaluate(run)
    return next(it for sec in res["sections"] for it in sec["items"] if it["id"] == "uebergabe")


def test_handover_in_several_parts(clf):
    run = _arrived(clf, [
        "übergabe: herr petersen, ende sechzig, auf der nassen treppe gestürzt mit kopfanprall",
        "puls 78 regelmäßig, rr 145 zu 90, gcs 15, bz 112",
        "nimmt apixaban wegen vorhofflimmern, keine allergien",
        "wir haben die hws stabilisiert und ihn zugedeckt",
        "verdacht auf schädel-hirn-trauma unter blutverdünner",
        "habt ihr noch fragen",
    ])
    assert said(run, "Rettungsdienst")[1:5] == ["(nickt)"] * 4
    assert "übernehmen" in said(run, "Rettungsdienst")[-1] and run.ended
    assert not [h for t in run.turns if t.handover for h in t.hits if h.intent != "uebergabe"], "keine Maßnahmen während der Übergabe"
    item = _handover_item(run)
    assert item["status"] == evaluate.OK, item["note"]


def test_handover_missing_parts_are_named(clf):
    run = _arrived(clf, ["übergabe: älterer mann, gestürzt", "das wars"])
    item = _handover_item(run)
    assert item["status"] == evaluate.PARTIAL
    for part in ("Befunde", "Anamnese", "Maßnahmen", "Verdacht"):
        assert part in item["note"]


def test_rescue_service_takes_over_after_silence(clf):
    log = [{"t": 3 * (i + 1), "text": x} for i, x in enumerate(HANDOVER_SETUP)]
    log += [{"t": 490, "text": "", "tick": True}, {"t": 492, "text": "übergabe: älterer mann gestürzt"}]
    s = content.scenarios()["basis-sturz"]
    run = engine.replay(s, "full", engine.Settings(), log, clf)
    assert run.next_event_at == 492 + engine.HANDOVER_SILENCE
    run = engine.replay(s, "full", engine.Settings(), log + [{"t": run.next_event_at, "text": "", "tick": True}], clf)
    assert run.ended and "übernehmen" in said(run, "Rettungsdienst")[-1]



def test_team_talk_in_several_parts(clf):
    run = play(clf, "basis-sturz", [
        "teambesprechung", "wir haben einen patienten, männlich, ende 60", "kopfanprall",
        "schmerzen im nacken und po. verdacht auf hws-problem nach trauma", "wir brauchen rtw und nef. siehst du das auch so?",
    ])
    acks = {l.text for l in content.smalltalk().team_ack}
    assert all(t.lines[0].who == "Kollege" and t.lines[0].text in acks for t in run.turns[:4])
    assert said(run, "Kollege")[-1] in {l.text for l in content.smalltalk().team_agree}
    assert "nachforderung" not in run.first and "puls" not in run.first  # Besprechung, keine Handlung
    team = next(it for it in evaluate.evaluate(run)["sections"][0]["items"] if it["id"] == "team")
    assert "Reaktion" not in team["note"] and "Abschlussfrage" not in team["note"]   # Reaktion unauffällig: nicht nötig


@pytest.mark.parametrize("question", [
    "siehst du das auch so", "sehe ich das richtig", "bist du einverstanden", "was meinst du dazu", "stimmst du mir zu",
    "hast du noch was zu ergänzen", "passt das für dich", "sind wir uns da einig", "wie siehst du das",
])
def test_team_talk_closing_variants(clf, question):
    run = play(clf, "basis-sturz", ["kurze teambesprechung verdacht auf sht", question])
    assert run.turns[-1].team_closed, question


def test_team_talk_without_closing_question_is_noted(clf):
    run = play(clf, "basis-sturz", ["teambesprechung patient männlich ende 60 wach verdacht auf sht wir brauchen rtw", "hallo herr petersen"])
    team = next(it for it in evaluate.evaluate(run)["sections"][0]["items"] if it["id"] == "team")
    assert team["status"] == evaluate.PARTIAL and "Abschlussfrage" in team["note"]
    assert not run.turns[-1].team  # „Hallo …“ richtet sich an den Patienten


def test_colleague_speaks_after_early_radio_end(clf):
    run = play(clf, "x-kettensaege", ["starke blutung kollege tourniquet anlegen", "rotkreuzhamburg von evt eins kommen",
                                      "patient männlich mitte 40 wir brauchen rtw und nef kommen", "evt 1 ende", "evt 1 ende"])
    assert said(run, "Kollege")[-2] == engine.AFTER_FUNK[0].text
    assert said(run, "Kollege")[-1] == engine.FUNK_ALREADY_ENDED.text
    assert not run.ended


@pytest.mark.parametrize("text", ["Eva T1 Ende", "E V T 1 Ende", "evt 1 End", "efte eins ende", "Efau Tee eins Ende",
                                  "E Vau Tee 1 Ende", "evtl. 1 Ende", "eventuell eins ende"])
def test_misheard_callsign_still_ends_the_call(clf, text):
    run = play(clf, "basis-sturz", ["rotkreuzhamburg von evt eins kommen", "älterer mann gestürzt wir brauchen einen rtw kommen", text])
    assert "funk_ende" in run.first and run.ended
    funk = next(it for it in evaluate.evaluate(run)["sections"][0]["items"] if it["id"] == "funk")
    assert "Ende“ fehlt" not in funk["note"], funk["note"]


def test_sympathy_once_the_bolus_is_out_gets_a_spoken_answer(clf):
    run = play(clf, "a-bolus", ["fünf rückenschläge", "fünf oberbauchkompressionen", "das ist ja doof"])
    assert run.state.get("geloest") and said(run)[-1] == "(seufzt) Ja, das kann man wohl sagen."


def test_smalltalk_after_losing_consciousness_gets_no_reaction(clf):
    run = replay_ticks(clf, "a-bolus", {5: "hallo", 100: "oh das ist ja unglücklich"}, until=100)
    last = next(t for t in reversed(run.turns) if t.text)
    assert all(l.who != "Patient" for l in last.lines), last.lines


# ---------- Befinden („Geht es Ihnen besser?“): Betreuung, zählt nicht ----------

BETTER = {l.text for r in content.smalltalk().rules if r.id == "befinden" for l in r.better}


def test_feeling_better_only_after_a_measure(clf):
    run = play(clf, "basis-sturz", ["geht es ihnen besser", "ich lege ihnen eine decke um", "geht es ihnen jetzt besser"])
    assert not run.turns[0].hits and not run.turns[2].hits
    assert run.turns[0].lines[0].text not in BETTER
    assert run.turns[2].lines[0].text in BETTER


def test_asking_how_they_feel_again_is_care_not_anamnesis(clf):
    # erst Frage nach Beschwerden (zählt), danach dieselbe Frage = Befinden: keine Wiederholung der Beschwerden
    run = play(clf, "basis-sturz", ["wie fühlen sie sich", "ich lege ihnen eine decke um", "wie fühlen sie sich jetzt"])
    assert [h.intent for h in run.turns[0].hits] == ["beschwerden_fragen"]
    assert not run.turns[2].hits and run.turns[2].lines[0].text in BETTER


def test_feeling_better_follows_the_case(clf):
    run = play(clf, "x-kettensaege", ["geht es ihnen besser"])
    assert "blutet immer noch" in said(run)[-1]
    run = play(clf, "b-asthma", ["geht es ihnen besser", "ich gebe ihnen sauerstoff", "geht es ihnen besser"])
    assert "schüttelt den Kopf" in said(run)[0] and "besser" in said(run)[-1]


def test_feeling_better_unconscious_gets_no_reaction(clf):
    run = play(clf, "bw-seitenlage", ["geht es ihnen besser"])
    assert said(run) == ["(keine Reaktion)"]


@pytest.mark.parametrize("sid", list(content.scenarios()))
def test_no_patient_behaviour_after_losing_consciousness(clf, sid):
    # niemand lässt den Fall laufen und lässt den Patienten danach allein – nach dem Zusammensacken kommt nichts mehr vom Patienten
    run = replay_ticks(clf, sid, {5: "hallo", 400: "wir holen kurz was aus dem auto"}, until=480)
    for n, t in enumerate(run.turns):
        before = run.turns[:n]
        if any("bewusstlos" in (l.text) or "reagiert nicht mehr" in l.text for b in before for l in b.lines) and not t.text:
            assert all(l.who not in ("Patient",) and not l.text.startswith(("(Herr", "(Frau")) for l in t.lines), (sid, t.t, t.lines)


def test_chainsaw_pressure_bandage_first_then_tourniquet(clf):
    run = replay_ticks(clf, "x-kettensaege", {5: "starke blutung kollege druckverband anlegen", 30: "tourniquet anlegen"}, until=200)
    texts = said(run)
    assert any("durchgeblutet" in x for x in texts) and run.state.get("blutung_steht") and run.died_at is None
    keys = {k["label"]: k for k in keys_of(evaluate.evaluate(run))}
    assert keys["Erst Druckverband, Tourniquet erst wenn er nicht reicht"]["status"] == evaluate.OK
    assert keys["Blutung steht (Tourniquet, als der Druckverband durchgeblutet war)"]["status"] == evaluate.OK


def test_chainsaw_pressure_bandage_alone_is_not_enough(clf):
    run = replay_ticks(clf, "x-kettensaege", {5: "druckverband anlegen"}, until=330)
    assert run.died_at is not None


def test_chainsaw_tourniquet_without_bandage_is_noted(clf):
    res = evaluate.evaluate(play(clf, "x-kettensaege", ["tourniquet anlegen"]))
    key = next(k for k in keys_of(res) if k["label"].startswith("Erst Druckverband"))
    assert key["status"] == evaluate.MISSING


@pytest.mark.parametrize("text,intent", [
    ("ich lege einen druckverband an", "druckverband"), ("tourniquet anlegen", "tourniquet"),
    ("ich drücke die wunde fest ab", "abdruecken"), ("kollege kümmere dich um die blutung", "blutung_stillen"),
])
def test_bleeding_control_methods(clf, text, intent):
    hits = {h.intent for h in clf.classify(text)}
    assert intent in hits and "blutung_stillen" in hits and "wunde_versorgen" not in hits


def _chainsaw_handover(clf, handover):
    script = {5: "starke blutung kollege druckverband anlegen", 30: "tourniquet anlegen",
              40: "rotkreuzhamburg von evt eins kommen", 43: "patient männlich mitte vierzig wir brauchen rtw und nef kommen",
              46: "evt eins ende"}
    script |= {530 + 3 * i: x for i, x in enumerate(handover)}
    run = replay_ticks(clf, "x-kettensaege", script, until=560, mode="full")
    res = evaluate.evaluate(run)
    return next(it for sec in res["sections"] for it in sec["items"] if it["id"] == "uebergabe")


def test_handover_needs_tourniquet_time(clf):
    without = _chainsaw_handover(clf, ["übergabe: markus mitte vierzig, kettensäge ins bein, puls 112, rr 105 zu 65, "
                                       "keine allergien, tourniquet angelegt, verdacht auf arterielle blutung", "fragen?"])
    assert "Uhrzeit des Tourniquets" in without["note"]
    with_time = _chainsaw_handover(clf, ["übergabe: markus mitte vierzig, kettensäge ins bein, puls 112, rr 105 zu 65, "
                                         "keine allergien, tourniquet seit 10:47, verdacht auf arterielle blutung", "fragen?"])
    assert "Uhrzeit" not in with_time["note"], with_time["note"]


def test_handover_without_tourniquet_needs_no_time(clf):
    run = _arrived(clf, ["übergabe: herr petersen ende sechzig gestürzt, puls 78, gcs 15, nimmt apixaban, hws stabilisiert, "
                         "verdacht auf sht", "habt ihr noch fragen"])
    assert "Uhrzeit" not in _handover_item(run)["note"]


def test_note_the_time(clf):
    run = play(clf, "x-kettensaege", ["kollege merk dir die uhrzeit"])
    assert [h.intent for h in run.turns[0].hits] == ["uhrzeit_notieren"] and said(run) == ["(notiert die Uhrzeit)"]
    run = play(clf, "x-kettensaege", ["tourniquet anlegen", "schreib die uhrzeit auf das tourniquet"])
    assert any("10:47" in x for x in said(run))
    key = next(k for k in keys_of(evaluate.evaluate(run)) if k["label"] == "Uhrzeit auf das Tourniquet geschrieben")
    assert key["status"] == evaluate.OK
    run = play(clf, "dom-krampf", ["ich stoppe die zeit"])
    assert "uhrzeit_notieren" in run.first and said(run, "Kollege") != ["(notiert die Uhrzeit)"]


@pytest.mark.parametrize("text, closes", [
    ("Habt ihr noch Fragen?", True),
    ("Fragen?", True),
    ("Gibt es Rückfragen", True),
    ("Übernehmt ihr?", True),
    ("Das wär's", True),
    ("Das war alles", True),
    ("GCS 14, er wiederholt Fragen", False),
    ("Er hat uns viele Fragen gestellt", False),
])
def test_handover_close(text, closes):
    from backend.classifier import normalize
    assert bool(engine.HANDOVER_CLOSE.search(normalize(text))) == closes


@pytest.mark.parametrize("sid", [s for s, sc in content.scenarios().items() if sc.conscious] + ["bw-seitenlage", "bw-sommer"])
def test_no_cpr_on_awake_or_normally_breathing_patient(clf, sid):
    """HLW bei Wachen bzw. normal Atmenden: Der Kollege stoppt, sie zählt nicht, die Auswertung ist „Nicht erfüllt“."""
    run = play(clf, sid, ["hallo wir sind vom drk", "ich beginne mit der herzdruckmassage", "1 2 3 4 5 6 7 8 9 10 28 29 30"])
    replies = [l.text for l in run.turns[1].lines]
    assert any("Stopp" in r for r in replies), replies
    assert not any("Herzdruckmassage läuft" in l.text for t in run.turns for l in t.lines), "HLW darf nicht laufen"
    assert "hlw" not in run.first and "hlw" not in run.state or not run.state.get("hlw")
    res = evaluate.evaluate(run)
    assert res["verdict"] == "Nicht erfüllt"
    assert "HLW" in res["improve"][0]


@pytest.mark.parametrize("text", ["Er braucht keine Herzdruckmassage, er atmet ja.", "Keine Reanimation nötig, er ist wach.",
                                  "Wir müssen nicht reanimieren.", "Keine HLW, er atmet normal."])
def test_negated_cpr_is_not_cpr(clf, text):
    assert "hlw" not in {h.intent for h in clf.classify(text)}


def test_cpr_still_works_when_unconscious_without_breathing(clf):
    run = play(clf, "bw-reanimation", ["hallo hören sie mich", "atemkontrolle keine normale atmung", "ich beginne mit der herzdruckmassage"])
    assert "hlw" in run.first
    assert evaluate.evaluate(run)["course"] == [] or not any("HLW bei" in c for c in evaluate.evaluate(run)["course"])


@pytest.mark.parametrize("sid, at, allowed", [
    ("d-hypo", 245, False), ("c-gib", 335, False), ("e-unterkuehlung", 245, False), ("mil-alkohol", 305, False),
    ("x-kettensaege", 160, False),            # bewusstlos, atmet noch
    ("x-kettensaege", 215, True),             # Kreislaufstillstand
    ("a-bolus", 95, True),                    # bewusstlos mit Fremdkörper: HLW (ERC)
    ("b-asthma", 365, True), ("mil-pyro-asthma", 335, True),   # Schnappatmung
])
def test_cpr_only_when_unconscious_without_normal_breathing(clf, sid, at, allowed):
    """HLW-Indikation im Verlauf: bewusstlos UND keine normale Atmung – sonst stoppt der Kollege."""
    s = content.scenarios()[sid]
    log = [{"t": 2, "text": "hallo wir sind vom drk"}, {"t": at, "text": "", "tick": True},
           {"t": at + 1, "text": "ich beginne mit der herzdruckmassage"}]
    run = engine.replay(s, "full", engine.Settings(), log, clf)
    replies = [l.text for l in run.turns[-1].lines]
    if allowed:
        assert "hlw" in run.first and not any("Stopp" in r for r in replies), replies
    else:
        assert "hlw" not in run.first and any("normale Atmung" in r for r in replies), replies
        assert evaluate.evaluate(run)["verdict"] == "Nicht erfüllt"


@pytest.mark.parametrize("sid, at", [("b-asthma", 365), ("mil-pyro-asthma", 335), ("x-kettensaege", 215)])
def test_breathing_check_matches_gasping_state(clf, sid, at):
    s = content.scenarios()[sid]
    log = [{"t": 2, "text": "hallo"}, {"t": at, "text": "", "tick": True}, {"t": at + 1, "text": "atemkontrolle sehen hören fühlen"}]
    run = engine.replay(s, "full", engine.Settings(), log, clf)
    assert any("Keine normale Atmung" in l.text for l in run.turns[-1].lines)
