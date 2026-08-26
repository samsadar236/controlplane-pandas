"""Deterministic grounding score via HHEM-2.1-Open. No API calls.

HHEM-2.1-Open (Vectara) is a small (~110M) classifier that scores how well
a hypothesis is supported by a premise, returning a probability in [0, 1].
Here: premise = the extracted claims (what the student actually wrote) plus
the rubric; hypothesis = the justification (the model's story about the
grade). A low score means the justification is not grounded in the claims,
which is a hallucination signal, computed with zero API cost.

It runs in the cascade BEFORE the LLM Critic. The gate (cascade.py) uses the
band to decide whether the Critic is needed at all, so most answers never
reach the LLM.

Dependencies: torch + transformers, which already arrive via
sentence-transformers (used by the plagiarism module), so this adds no new
heavy dependency. The first call downloads the model from Hugging Face
(a few hundred MB); after that it runs offline on CPU.

Graceful degradation: if the model cannot be loaded (offline, missing deps,
etc.), every function returns None / "unknown" and logs one warning. The
pipeline still runs; the gate treats "unknown" as borderline and routes to
the LLM Critic, so grounding is never a hard dependency.

Thresholds (settings.hhem_high_threshold / hhem_low_threshold) should be
calibrated on the eval set (Phase 3), not trusted as-is.
"""
from __future__ import annotations

import logging

from ..config import settings
from . import prompts

log = logging.getLogger(__name__)

_model = None
_load_failed = False


def _load_model():
    """Lazily load and cache the HHEM model. Returns None on any failure."""
    global _model, _load_failed
    if _model is not None:
        return _model
    if _load_failed:
        return None
    try:
        from transformers import AutoModelForSequenceClassification

        _model = AutoModelForSequenceClassification.from_pretrained(
            settings.hhem_model, trust_remote_code=True
        )
        log.info("HHEM grounding model loaded: %s", settings.hhem_model)
        return _model
    except Exception as e:  # ImportError, network, model repo errors, etc.
        _load_failed = True
        log.warning("HHEM grounding disabled (model unavailable): %s", e)
        return None


def grounding_score(premise: str, hypothesis: str) -> float | None:
    """Faithfulness of hypothesis given premise, in [0, 1]. None if unavailable."""
    if not getattr(settings, "hhem_enabled", True):
        return None
    if not premise or not hypothesis:
        return None
    model = _load_model()
    if model is None:
        return None
    try:
        maxc = int(getattr(settings, "hhem_max_chars", 4000) or 4000)
        pair = (premise[:maxc], hypothesis[:maxc])
        scores = model.predict([pair])
        val = scores[0]
        return float(val.item()) if hasattr(val, "item") else float(val)
    except Exception as e:
        log.warning("HHEM predict failed: %s", e)
        return None


def band(score: float | None) -> str:
    """Map a score to 'high' | 'borderline' | 'low' | 'unknown'."""
    if score is None:
        return "unknown"
    if score >= float(getattr(settings, "hhem_high_threshold", 0.7)):
        return "high"
    if score < float(getattr(settings, "hhem_low_threshold", 0.4)):
        return "low"
    return "borderline"


def build_premise(state: dict) -> str:
    """Premise = the extracted claims, plus the rubric as light context."""
    claims = state.get("claims", []) or []
    parts = [prompts.format_claims(claims)]
    criteria = state.get("criteria")
    if criteria:
        try:
            parts.append("Criteria:\n" + prompts.format_criteria(criteria))
        except Exception:
            pass
    return "\n\n".join(p for p in parts if p)


def build_hypothesis(state: dict) -> str:
    """Hypothesis = the justification, falling back to per-criterion reasoning."""
    just = (state.get("justification") or "").strip()
    if just and just != "(no justification generated)":
        return just
    pcs = state.get("per_criterion", []) or []
    return " ".join((pc.get("reasoning") or "") for pc in pcs).strip()


def score_answer(state: dict) -> dict:
    """Compute the grounding score + band for a GradingState-like dict."""
    premise = build_premise(state)
    hypothesis = build_hypothesis(state)
    s = grounding_score(premise, hypothesis)
    return {"grounding_score": s, "grounding_band": band(s)}


# ---------------------------------------------------------------------------
# Self-test: `python -m backend.grader.grounding` (or `python grounding.py`).
# The model path needs Hugging Face access; the banding + text construction
# are pure and always testable.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    failures = 0

    def check(label, cond):
        global failures
        print(f"[{'PASS' if cond else 'FAIL'}] {label}")
        if not cond:
            failures += 1

    # Banding logic (defaults: high>=0.7, low<0.4)
    check("band(0.92) == high", band(0.92) == "high")
    check("band(0.70) == high (inclusive)", band(0.70) == "high")
    check("band(0.55) == borderline", band(0.55) == "borderline")
    check("band(0.39) == low", band(0.39) == "low")
    check("band(None) == unknown", band(None) == "unknown")

    # Text construction
    state = {
        "claims": [
            {"step": 1, "content": "F(x) = x^2 + C", "concern": ""},
            {"step": 2, "content": "F(2) = 4 + C", "concern": ""},
        ],
        "criteria": [{"name": "Antiderivative", "points": 2, "conditions": "correct F(x)"}],
        "justification": "Claims 1 and 2 show the antiderivative and evaluation.",
        "per_criterion": [{"name": "Antiderivative", "awarded": 2, "max": 2,
                           "reasoning": "claims 1 and 2"}],
    }
    prem = build_premise(state)
    hyp = build_hypothesis(state)
    check("premise contains a claim", "F(x) = x^2 + C" in prem)
    check("premise contains rubric context", "Antiderivative" in prem)
    check("hypothesis uses the justification", hyp.startswith("Claims 1 and 2"))

    # Hypothesis fallback when justification is the placeholder
    state2 = dict(state, justification="(no justification generated)")
    check("hypothesis falls back to reasoning", build_hypothesis(state2) == "claims 1 and 2")

    # score_answer never crashes; returns a valid shape even with no model
    res = score_answer(state)
    check("score_answer returns both keys",
          set(res.keys()) == {"grounding_score", "grounding_band"})
    check("grounding_band is a valid value",
          res["grounding_band"] in {"high", "borderline", "low", "unknown"})
    print(f"    (grounding_band here = {res['grounding_band']}; "
          f"'unknown' is expected without Hugging Face access)")

    print()
    if failures:
        print(f"SELF-TEST FAILED: {failures} case(s) wrong")
        raise SystemExit(1)
    print("SELF-TEST PASSED: all cases correct")
