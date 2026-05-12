from __future__ import annotations

from argus_ai_oracle import PHRASES


def test_phrases_has_expected_buckets():
    for bucket in ("clean", "watch", "ss", "kick", "ban"):
        assert bucket in PHRASES


def test_each_bucket_has_at_least_50_non_empty_phrases():
    for bucket, phrases in PHRASES.items():
        assert isinstance(phrases, list)
        assert len(phrases) >= 50
        assert all(isinstance(p, str) and p.strip() for p in phrases)
