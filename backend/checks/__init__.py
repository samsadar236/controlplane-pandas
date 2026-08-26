"""Output checks. Every check's run(...) returns a uniform CheckResult:

    {check, risk, score, flagged, detail, evidence}

  risk: "high" | "medium" | "low" | "unknown"

The decision engine consumes only `check` and `risk`; the rest is for the
audit view. Kept dependency-free here so a single check can be imported and
tested in isolation.
"""
from __future__ import annotations

VALID_RISKS = ("high", "medium", "low", "unknown")


def result(check: str, risk: str, *, score=None, flagged=None,
           detail: str = "", evidence=None) -> dict:
    if risk not in VALID_RISKS:
        risk = "unknown"
    if flagged is None:
        flagged = risk in ("medium", "high")
    return {
        "check": check,
        "risk": risk,
        "score": score,
        "flagged": bool(flagged),
        "detail": detail,
        "evidence": evidence or [],
    }
