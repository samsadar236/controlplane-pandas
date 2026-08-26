"""Bias check (output-side).

Two tiers, honestly labelled:

  1. High-confidence (optional): if LLM Guard is installed, use its Bias
     output scanner. This is the recommended production path.
  2. Low-confidence fallback (always available): a transparent lexicon
     heuristic that flags a sensitive-group term appearing near a negative
     descriptor. It is intentionally simple and will miss subtle bias; it
     exists so the check always returns a signal and never silently passes.

For the grading vertical, the stronger output-side bias signal is
fairness.py (near-identical answers scored differently), which is
domain-native and does not depend on lexicons.

The lexicons below are small and illustrative, not exhaustive.
"""
from __future__ import annotations

import re

from . import result

_SENSITIVE = {
    "women", "woman", "men", "man", "girls", "boys", "female", "male",
    "black", "white", "asian", "hispanic", "latino", "latina", "arab",
    "jewish", "muslim", "christian", "hindu", "buddhist",
    "immigrant", "immigrants", "foreigner", "foreigners",
    "gay", "lesbian", "queer", "trans", "transgender",
    "disabled", "elderly", "old", "young",
}
_NEGATIVE = {
    "lazy", "stupid", "dumb", "inferior", "worse", "worst", "incompetent",
    "dishonest", "dangerous", "weak", "irrational", "aggressive",
    "untrustworthy", "less", "bad", "unfit", "incapable", "criminal",
    "greedy", "violent", "unintelligent", "naive",
}
_WINDOW = 6  # token window around a sensitive term


def _optional_llm_guard(text: str):
    try:
        from llm_guard.output_scanners import Bias
    except Exception:
        return None
    try:
        scanner = Bias()
        _sanitized, _valid, score = scanner.scan("", text)
        score = float(score)
        risk = "high" if score >= 0.75 else ("medium" if score >= 0.4 else "low")
        return result("bias", risk, score=score,
                      detail=f"llm_guard bias risk={score:.2f}")
    except Exception:
        return None


def _heuristic(text: str) -> dict:
    tokens = re.findall(r"[a-zA-Z']+", (text or "").lower())
    hits = []
    for i, tok in enumerate(tokens):
        if tok in _SENSITIVE:
            lo, hi = max(0, i - _WINDOW), min(len(tokens), i + _WINDOW + 1)
            near = [t for t in tokens[lo:hi] if t in _NEGATIVE]
            if near:
                hits.append({"term": tok, "near": near})
    if hits:
        return result(
            "bias", "medium", score=float(len(hits)),
            detail=("heuristic (low confidence): sensitive term near negative "
                    f"descriptor: {hits[:3]}"),
            evidence=hits,
        )
    return result("bias", "low", score=0.0,
                  detail="heuristic (low confidence): no obvious biased pattern")


def run(output: str, **_kwargs) -> dict:
    r = _optional_llm_guard(output or "")
    if r is not None:
        return r
    return _heuristic(output or "")


if __name__ == "__main__":
    failures = 0

    def check(label, cond):
        global failures
        print(f"[{'PASS' if cond else 'FAIL'}] {label}")
        if not cond:
            failures += 1

    r_bias = run("Women are worse at math than men.")
    check("biased sentence -> flagged (medium or high)", r_bias["flagged"])

    r_ok = run("The mitochondria is the powerhouse of the cell.")
    check("neutral sentence -> low risk", r_ok["risk"] == "low")

    print()
    if failures:
        print(f"SELF-TEST FAILED: {failures}")
        raise SystemExit(1)
    print("SELF-TEST PASSED: all cases correct")
