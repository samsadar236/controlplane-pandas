"""Grounding check for the general checker (context vs output).

Reuses the HHEM model from grader.grounding, but with the general framing:
premise = the retrieved context/source, hypothesis = the AI's output. Low
faithfulness = high hallucination risk. If there is no context, or the model
is unavailable, risk is "unknown" (the decision engine routes that per policy).

Band -> risk is inverted: faithful (high band) is low risk.
"""
from __future__ import annotations

from ..grader import grounding
from . import result

_BAND_TO_RISK = {"high": "low", "borderline": "medium", "low": "high", "unknown": "unknown"}


def run(context: str, output: str) -> dict:
    score = grounding.grounding_score(context or "", output or "")
    band = grounding.band(score)
    risk = _BAND_TO_RISK.get(band, "unknown")
    if score is None:
        detail = "grounding not available (no context or model unloaded); needs review"
    else:
        detail = f"faithfulness={score:.3f} (band {band})"
    return result("grounding", risk, score=score, detail=detail)
