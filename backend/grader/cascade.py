"""The deterministic gate of the cascade.

`verifier_node` runs the two cheap, deterministic checks (citation rules +
HHEM grounding) and records their results. No LLM call happens here.

`gate_router` then decides whether the LLM Critic is needed at all:
  - hard rule failure  -> END   (reason already known; do not spend an LLM call)
  - any warning        -> Critic (get a semantic opinion)
  - grounding "high"    -> END   (confident grounded; skip the LLM)
  - otherwise          -> Critic (borderline / low / unknown)

This is the cost lever: on a clean or clearly-broken answer the pipeline
never reaches the LLM, which protects both latency and the free-tier quota.
The Critic, when it does run, uses the "critic" role (a different model than
the Scorer) to avoid self-preference bias.

verifier_node sets a PROVISIONAL critic verdict from the rule check so the
grade output is meaningful even when the gate skips the LLM Critic. If the
Critic runs, it overrides these fields.
"""
from __future__ import annotations

from . import grounding, rules
from .state import GradingState


def verifier_node(state: GradingState) -> dict:
    rule_result = rules.verify_citations(
        state.get("claims", []) or [],
        state.get("per_criterion", []) or [],
    )
    g = grounding.score_answer(state)
    provisional_passed = rule_result["passed"] and g["grounding_band"] != "low"
    return {
        "rule_result": rule_result,
        "rule_summary": rule_result["summary"],
        "grounding_score": g["grounding_score"],
        "grounding_band": g["grounding_band"],
        "deterministic_passed": provisional_passed,
        # Provisional critic verdict (overridden if the LLM Critic runs).
        "critic_passed": rule_result["passed"],
        "critic_feedback": "" if rule_result["passed"] else rule_result["summary"],
    }


def gate_decision(state: GradingState) -> str:
    """Pure, testable gate. Returns 'critic' or 'end'."""
    rr = state.get("rule_result") or {}
    if not rr.get("passed", True):
        return "end"  # hard deterministic fail: reason known, skip the LLM
    violations = rr.get("violations", []) or []
    if any(v.get("severity") == "warn" for v in violations):
        return "critic"
    if state.get("grounding_band") == "high":
        return "end"  # confident grounded: skip the LLM
    return "critic"   # borderline / low / unknown -> LLM Critic


def gate_router(state: GradingState):
    """LangGraph-facing conditional edge (maps to the 'critic' node or END)."""
    from langgraph.graph import END

    return "critic" if gate_decision(state) == "critic" else END


# ---------------------------------------------------------------------------
# Self-test: `python -m backend.grader.cascade` (or `python cascade.py`).
# gate_decision is pure (no LangGraph); verifier_node exercises rules +
# grounding (grounding degrades to "unknown" without model access).
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    failures = 0

    def check(label, cond):
        global failures
        print(f"[{'PASS' if cond else 'FAIL'}] {label}")
        if not cond:
            failures += 1

    block = {"passed": False, "violations": [
        {"type": "ungrounded_award", "severity": "block", "detail": ""}], "summary": "x"}
    warn = {"passed": True, "violations": [
        {"type": "concern_claim_credited", "severity": "warn", "detail": ""}], "summary": "x"}
    clean = {"passed": True, "violations": [], "summary": "ok"}

    check("hard rule fail -> end",
          gate_decision({"rule_result": block, "grounding_band": "high"}) == "end")
    check("warning -> critic (even if grounding high)",
          gate_decision({"rule_result": warn, "grounding_band": "high"}) == "critic")
    check("clean + high grounding -> end (skip LLM)",
          gate_decision({"rule_result": clean, "grounding_band": "high"}) == "end")
    check("clean + borderline -> critic",
          gate_decision({"rule_result": clean, "grounding_band": "borderline"}) == "critic")
    check("clean + low -> critic",
          gate_decision({"rule_result": clean, "grounding_band": "low"}) == "critic")
    check("clean + unknown grounding -> critic (safe default)",
          gate_decision({"rule_result": clean, "grounding_band": "unknown"}) == "critic")
    check("missing rule_result -> critic (safe default)",
          gate_decision({}) == "critic")

    # verifier_node end to end on a synthetic state
    state = {
        "claims": [{"step": 1, "content": "F(x)=x^2+C", "concern": ""}],
        "per_criterion": [{"name": "Setup", "awarded": 2, "max": 2,
                           "reasoning": "claim 1 gives F(x)"}],
        "justification": "Claim 1 gives the antiderivative.",
        "criteria": [{"name": "Setup", "points": 2, "conditions": "F(x) correct"}],
    }
    out = verifier_node(state)
    expected_keys = {"rule_result", "rule_summary", "grounding_score",
                     "grounding_band", "deterministic_passed",
                     "critic_passed", "critic_feedback"}
    check("verifier_node returns all expected keys", expected_keys.issubset(out.keys()))
    check("verifier_node provisional critic_passed matches clean rule check",
          out["critic_passed"] is True)
    check("verifier_node grounding_band valid",
          out["grounding_band"] in {"high", "borderline", "low", "unknown"})

    print()
    if failures:
        print(f"SELF-TEST FAILED: {failures} case(s) wrong")
        raise SystemExit(1)
    print("SELF-TEST PASSED: all cases correct")
