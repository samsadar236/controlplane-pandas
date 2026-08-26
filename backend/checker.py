"""General 'check any output' entrypoint (T2.1).

`check_output` runs the policy-enabled checks (grounding, PII, bias) over any
AI output and returns a tiered decision. This is the generalisation of
GradeOps: the same checker that grades an exam answer can wrap a customer
chatbot answer, an internal copilot answer, or a decision-support answer,
with behaviour set by the use-case policy.

`decide_for_grade` maps the grading pipeline's OWN signals (HHEM band, rule
verdict, Critic verdict) into the same decision engine, so exam grades also
get an allow/edit/flag/block tier under a chosen policy.
"""
from __future__ import annotations

from . import checks
from .checks import bias_check, grounding_check, pii_check
from .decision import engine
from .policy import check_enabled, resolve_policy

_GRADE_BAND_TO_RISK = {"high": "low", "borderline": "medium", "low": "high", "unknown": "unknown"}


def check_output(use_case: str | None = None, *, output: str,
                 context: str = "", input: str = "", policy=None) -> dict:
    """Run the enabled checks over one AI output and return a tiered decision."""
    pol = resolve_policy(policy or use_case or "customer_support")
    results = []
    if check_enabled(pol, "grounding"):
        results.append(grounding_check.run(context, output))
    if check_enabled(pol, "pii"):
        results.append(pii_check.run(output))
    if check_enabled(pol, "bias"):
        results.append(bias_check.run(output))
    decision = engine.decide(results, pol)
    return {"use_case": pol.get("name"), "input_len": len(input or ""), **decision}


def decide_for_grade(grade: dict, policy) -> dict:
    """Map a grade_one_pass dict into a CheckResult + tiered decision."""
    pol = resolve_policy(policy)
    band = grade.get("grounding_band", "unknown")
    risk = _GRADE_BAND_TO_RISK.get(band, "unknown")
    # A hard rule failure or a failed Critic is a strong grounding problem.
    if not grade.get("deterministic_passed", True) or not grade.get("critic_passed", True):
        risk = "high"
    gres = checks.result(
        "grounding", risk,
        score=grade.get("grounding_score"),
        detail=grade.get("rule_summary", ""),
    )
    decision = engine.decide([gres], pol)
    return {"use_case": pol.get("name"), **decision}


if __name__ == "__main__":
    failures = 0

    def check(label, cond):
        global failures
        print(f"[{'PASS' if cond else 'FAIL'}] {label}")
        if not cond:
            failures += 1

    # A leaky, biased chatbot answer with no supporting context.
    out = check_output(
        use_case="customer_support",
        output="Sure! Contact John at john@acme.com or card 4111 1111 1111 1111. "
               "Frankly immigrants are lazy.",
        context="",
    )
    print(f"    customer_support tier={out['tier']} "
          f"reasons={[ (r['check'], r['risk'], r['action']) for r in out['reasons'] ]}")
    check("leaky answer under customer_support -> block (PII high)", out["tier"] == "block")
    check("pii reason present", any(r["check"] == "pii" for r in out["reasons"]))
    check("bias reason present", any(r["check"] == "bias" for r in out["reasons"]))

    # Same output, lenient internal policy -> not blocked (PII high -> edit).
    out2 = check_output(use_case="internal_knowledge",
                        output="card 4111 1111 1111 1111", context="")
    check("card under internal_knowledge -> edit (redact), not block",
          out2["tier"] == "edit")

    # decide_for_grade: a grounded grade allows; a rule-failed grade escalates.
    good_grade = {"grounding_band": "high", "deterministic_passed": True,
                  "critic_passed": True, "grounding_score": 0.9, "rule_summary": "ok"}
    bad_grade = {"grounding_band": "low", "deterministic_passed": False,
                 "critic_passed": False, "grounding_score": 0.1,
                 "rule_summary": "ungrounded_award"}
    check("good grade under decision_support -> allow",
          decide_for_grade(good_grade, "decision_support")["tier"] == "allow")
    check("bad grade under decision_support -> block",
          decide_for_grade(bad_grade, "decision_support")["tier"] == "block")

    print()
    if failures:
        print(f"SELF-TEST FAILED: {failures}")
        raise SystemExit(1)
    print("SELF-TEST PASSED: all cases correct")
