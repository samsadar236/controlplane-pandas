"""Composite uncertainty for the review queue (T1.4, Lane A).

Under Lane A the pipeline is deterministic and runs a single pass, so
variance across passes is ~0 and is not a useful confidence signal. This
module derives an uncertainty score in [0, 1] from the grade's EXTERNAL,
deterministic signals instead:

  - grounding faithfulness (HHEM score, or the band if no score)
  - the deterministic rule verdict (citation grounding)
  - the LLM Critic verdict (only present when the gate escalated)
  - justifier flags (hallucination_risk, ambiguous_evidence, etc.)

Higher uncertainty sorts to the FRONT of the review queue. Verbalised
self-confidence is deliberately NOT used: it is poorly calibrated.

`aggregate_passes` is a drop-in superset of grader.aggregate.aggregate_scores:
it returns the same keys (median, max_score, min_score, std_dev, n_passes)
plus `uncertainty`, so the review queue can sort on `uncertainty` while the
rest of the code keeps working. For the Lane B option (num_passes > 1) it
folds normalised score spread across passes into the uncertainty.
"""
from __future__ import annotations

import statistics

# Weights. Tuned so a fully-bad answer approaches 1.0; adjust on the eval set.
W_GROUNDING = 0.40   # weight on the faithfulness gap
W_RULE = 0.30        # deterministic rule check failed
W_CRITIC = 0.20      # LLM Critic failed (if it ran)
W_FLAG = 0.05        # per justifier flag
W_FLAG_CAP = 0.15    # cap on the flag contribution
W_SPREAD = 0.50      # weight on normalised score spread across passes (Lane B)

# Fallback grounding uncertainty when there is no numeric score.
_BAND_UNCERTAINTY = {"low": 1.0, "borderline": 0.6, "unknown": 0.5, "high": 0.0}


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def answer_uncertainty(grade: dict) -> float:
    """Uncertainty in [0, 1] for one graded answer. Higher = review first."""
    gs = grade.get("grounding_score")
    if gs is not None:
        try:
            g_component = 1.0 - _clamp(float(gs))
        except (TypeError, ValueError):
            g_component = _BAND_UNCERTAINTY.get(grade.get("grounding_band"), 0.5)
    else:
        g_component = _BAND_UNCERTAINTY.get(grade.get("grounding_band"), 0.5)

    u = W_GROUNDING * g_component
    if not grade.get("deterministic_passed", True):
        u += W_RULE
    if not grade.get("critic_passed", True):
        u += W_CRITIC
    n_flags = len([f for f in (grade.get("flags") or []) if f])
    u += min(n_flags * W_FLAG, W_FLAG_CAP)
    return round(_clamp(u), 4)


def uncertainty_components(grade: dict) -> dict:
    """Explainable breakdown for the audit view."""
    gs = grade.get("grounding_score")
    if gs is not None:
        try:
            g_component = 1.0 - _clamp(float(gs))
        except (TypeError, ValueError):
            g_component = _BAND_UNCERTAINTY.get(grade.get("grounding_band"), 0.5)
    else:
        g_component = _BAND_UNCERTAINTY.get(grade.get("grounding_band"), 0.5)
    n_flags = len([f for f in (grade.get("flags") or []) if f])
    return {
        "grounding": round(W_GROUNDING * g_component, 4),
        "rule": W_RULE if not grade.get("deterministic_passed", True) else 0.0,
        "critic": W_CRITIC if not grade.get("critic_passed", True) else 0.0,
        "flags": round(min(n_flags * W_FLAG, W_FLAG_CAP), 4),
    }


def aggregate_passes(passes: list[dict]) -> dict:
    """Drop-in superset of aggregate_scores, adding `uncertainty`.

    passes: list of grade_one_pass dicts (each has at least 'score', and
    ideally grounding_score / grounding_band / deterministic_passed /
    critic_passed / flags).
    """
    scores = [float(p.get("score", 0.0)) for p in passes if "score" in p]
    if not scores:
        return {
            "median": 0.0, "max_score": 0.0, "min_score": 0.0,
            "std_dev": 0.0, "n_passes": 0, "uncertainty": 1.0,
        }

    std = float(statistics.pstdev(scores)) if len(scores) > 1 else 0.0
    max_score = float(max(scores))

    per_pass_u = [answer_uncertainty(p) for p in passes if "score" in p]
    mean_u = statistics.mean(per_pass_u) if per_pass_u else 1.0

    # Lane B: disagreement across passes adds uncertainty (0 for a single pass).
    denom = max((float(p.get("max_score", 0.0)) for p in passes), default=0.0)
    norm_spread = (std / denom) if denom > 0 else 0.0
    uncertainty = round(_clamp(mean_u + W_SPREAD * norm_spread), 4)

    return {
        "median": float(statistics.median(scores)),
        "max_score": max_score,
        "min_score": float(min(scores)),
        "std_dev": std,
        "n_passes": len(scores),
        "uncertainty": uncertainty,
    }


# ---------------------------------------------------------------------------
# Self-test: `python confidence.py` (pure stdlib, no relative imports).
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    failures = 0

    def check(label, cond):
        global failures
        print(f"[{'PASS' if cond else 'FAIL'}] {label}")
        if not cond:
            failures += 1

    clean = {"score": 2, "max_score": 2, "grounding_score": 0.95,
             "deterministic_passed": True, "critic_passed": True, "flags": []}
    bad = {"score": 2, "max_score": 2, "grounding_score": 0.1,
           "deterministic_passed": False, "critic_passed": False,
           "flags": ["hallucination_risk", "ambiguous_evidence"]}
    mid = {"score": 1, "max_score": 2, "grounding_score": None,
           "grounding_band": "borderline", "deterministic_passed": True,
           "critic_passed": True, "flags": []}

    uc, ub, um = answer_uncertainty(clean), answer_uncertainty(bad), answer_uncertainty(mid)
    print(f"    clean={uc}  mid={um}  bad={ub}")
    check("clean answer is low uncertainty", uc < 0.15)
    check("bad answer is high uncertainty", ub > 0.85)
    check("mid (borderline, unknown score) is in between", uc < um < ub)
    check("uncertainty stays in [0,1]", all(0.0 <= x <= 1.0 for x in (uc, ub, um)))

    # aggregate_passes: single pass -> uncertainty == answer_uncertainty
    agg1 = aggregate_passes([clean])
    check("single-pass aggregate keeps std_dev 0", agg1["std_dev"] == 0.0)
    check("single-pass uncertainty matches answer_uncertainty",
          abs(agg1["uncertainty"] - uc) < 1e-6)
    check("aggregate exposes the legacy keys",
          {"median", "max_score", "min_score", "std_dev", "n_passes"}.issubset(agg1))

    # Lane B: two passes that disagree add spread
    p1 = dict(clean, score=2)
    p2 = dict(clean, score=0)
    agg2 = aggregate_passes([p1, p2])
    check("multi-pass disagreement raises uncertainty above the per-pass mean",
          agg2["uncertainty"] > answer_uncertainty(p1))

    # empty
    check("empty passes -> uncertainty 1.0", aggregate_passes([])["uncertainty"] == 1.0)

    print()
    if failures:
        print(f"SELF-TEST FAILED: {failures}")
        raise SystemExit(1)
    print("SELF-TEST PASSED: all cases correct")
