from __future__ import annotations

from argus_ai_trainer import TemporalPatternDetector


def test_repeated_violation_pattern_scores_high():
    t = TemporalPatternDetector()
    for _ in range(30):
        t.observe(["killaura_no_swing", "reach", "killaura_multi"], label=1.0)
    for _ in range(30):
        t.observe(["chat_spam", "cmd_spam", "chat_spam"], label=0.0)
    out = t.score_sequence(["killaura_no_swing", "reach", "killaura_multi"])
    assert out["score"] > 0.7


def test_random_pattern_scores_lower_than_cheater_pattern():
    t = TemporalPatternDetector()
    for _ in range(20):
        t.observe(["killaura_no_swing", "reach", "killaura_multi"], label=1.0)
        t.observe(["chat_spam", "cmd_spam", "chat_spam"], label=0.0)
    strong = t.score_sequence(["killaura_no_swing", "reach", "killaura_multi"])
    randomish = t.score_sequence(["reach", "chat_spam", "speed"])
    assert strong["score"] >= randomish["score"]


def test_new_player_or_short_sequence_returns_neutral():
    t = TemporalPatternDetector()
    assert t.score_sequence([])["score"] == 0.5
    assert t.score_sequence(["reach"])["score"] == 0.5


def test_reset_on_new_instance():
    t1 = TemporalPatternDetector()
    t1.observe(["reach", "killaura_multi"], label=1.0)
    t2 = TemporalPatternDetector()
    assert t2.samples_observed == 0
