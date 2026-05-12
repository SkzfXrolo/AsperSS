from __future__ import annotations

from argus_ai_oracle import evaluate_hybrid
from argus_ai_trainer import EnsembleResult


def _evidence():
    return {
        "violations": [{"check_name": "reach", "level": "HIGH", "age_seconds": 1}],
        "current_score": 0.1,
    }


def test_hybrid_without_models_falls_back_to_heuristic():
    d = evaluate_hybrid(_evidence(), log_reg=None, knn=None, temporal=None)
    assert d.action in {"none", "watch", "ss", "kick", "ban"}
    assert "ensemble_components" not in d.evidence_used


def test_hybrid_with_broken_ensemble_degrades_with_tag(mocker):
    mocker.patch("argus_ai_oracle.evaluate", return_value=evaluate_hybrid(_evidence()))
    mocker.patch("argus_ai_trainer.ensemble_predict", side_effect=RuntimeError("boom"))
    d = evaluate_hybrid(_evidence(), log_reg=object())
    assert "ML degradado" in d.reasoning


def test_hybrid_uses_ensemble_when_available(mocker):
    fake = EnsembleResult(
        score=0.99,
        confidence=0.9,
        components={"heuristic": 0.2, "logreg": 0.8},
        component_scores={"heuristic": 0.2, "logreg": 0.99},
        top_features=[("f1", 1.2)],
        knn_neighbors=[],
        temporal_llr=0.0,
        skipped_reasons={},
        explanation="ok",
    )
    mocker.patch("argus_ai_trainer.ensemble_predict", return_value=fake)
    d = evaluate_hybrid(_evidence(), log_reg=object(), feature_vector=[0.1], sequence=["reach", "reach"])
    assert d.score == 0.99
    assert d.action in {"kick", "ban"}
    assert "ensemble_components" in d.evidence_used
