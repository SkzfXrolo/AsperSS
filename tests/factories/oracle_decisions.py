from __future__ import annotations

import factory


class OracleDecisionFactory(factory.DictFactory):
    action = "watch"
    score = 0.45
    confidence = 0.55
    reason = "heuristic baseline"
