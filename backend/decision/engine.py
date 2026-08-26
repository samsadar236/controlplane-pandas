"""Tiered decision engine (T2.3).

Takes a list of CheckResults and a policy, returns the decision tier plus the
per-check reasons. The tier is the most severe action any enabled check
triggers, mapped from that check's risk band via the policy.

Tier order: allow < edit < flag < block.
"""
from __future__ import annotations

_TIER_ORDER = {"allow": 0, "edit": 1, "flag": 2, "block": 3}


def decide(results: list[dict], policy: dict) -> dict:
    checks_cfg = policy.get("checks", {}) or {}
    tier = "allow"
    reasons = []
    for r in results or []:
        cfg = checks_cfg.get(r.get("check"))
        if not cfg or not cfg.get("enabled", True):
            continue
        actions = cfg.get("actions", {}) or {}
        action = actions.get(r.get("risk"), actions.get("unknown", "flag"))
        reasons.append({
            "check": r.get("check"),
            "risk": r.get("risk"),
            "action": action,
            "detail": r.get("detail", ""),
        })
        if _TIER_ORDER.get(action, 0) > _TIER_ORDER[tier]:
            tier = action
    return {"tier": tier, "reasons": reasons, "results": results or []}


if __name__ == "__main__":
    failures = 0

    def check(label, cond):
        global failures
        print(f"[{'PASS' if cond else 'FAIL'}] {label}")
        if not cond:
            failures += 1

    # Inline minimal policies mirroring the shipped JSONs (grounding + pii + bias).
    cs = {"name": "customer_support", "checks": {
        "grounding": {"enabled": True, "actions": {"high": "block", "medium": "allow", "low": "allow", "unknown": "flag"}},
        "pii": {"enabled": True, "actions": {"high": "block", "medium": "edit", "low": "allow", "unknown": "flag"}},
        "bias": {"enabled": True, "actions": {"high": "flag", "medium": "flag", "low": "allow", "unknown": "allow"}},
    }}
    ik = {"name": "internal_knowledge", "checks": {
        "grounding": {"enabled": True, "actions": {"high": "flag", "medium": "allow", "low": "allow", "unknown": "allow"}},
        "pii": {"enabled": True, "actions": {"high": "edit", "medium": "allow", "low": "allow", "unknown": "allow"}},
        "bias": {"enabled": True, "actions": {"high": "flag", "medium": "allow", "low": "allow", "unknown": "allow"}},
    }}
    ds = {"name": "decision_support", "checks": {
        "grounding": {"enabled": True, "actions": {"high": "block", "medium": "flag", "low": "allow", "unknown": "flag"}},
        "pii": {"enabled": True, "actions": {"high": "block", "medium": "edit", "low": "allow", "unknown": "flag"}},
        "bias": {"enabled": True, "actions": {"high": "block", "medium": "flag", "low": "allow", "unknown": "flag"}},
    }}

    # Same input, three policies -> three different tiers.
    results = [
        {"check": "grounding", "risk": "medium"},
        {"check": "pii", "risk": "medium"},
        {"check": "bias", "risk": "low"},
    ]
    t_cs = decide(results, cs)["tier"]
    t_ik = decide(results, ik)["tier"]
    t_ds = decide(results, ds)["tier"]
    print(f"    customer_support={t_cs}  internal_knowledge={t_ik}  decision_support={t_ds}")
    check("customer_support -> edit (PII medium redacts)", t_cs == "edit")
    check("internal_knowledge -> allow (lenient)", t_ik == "allow")
    check("decision_support -> flag (grounding medium flags)", t_ds == "flag")

    # Most-severe wins.
    hi = [{"check": "pii", "risk": "high"}, {"check": "grounding", "risk": "low"}]
    check("high PII under customer_support -> block", decide(hi, cs)["tier"] == "block")

    # Disabled check is ignored.
    ik_no_bias = {"name": "x", "checks": dict(ik["checks"], bias={"enabled": False, "actions": {}})}
    check("disabled check is skipped",
          all(r["check"] != "bias" for r in decide(results, ik_no_bias)["reasons"]))

    # Unknown risk uses the 'unknown' action.
    unk = [{"check": "grounding", "risk": "unknown"}]
    check("unknown grounding under decision_support -> flag",
          decide(unk, ds)["tier"] == "flag")

    print()
    if failures:
        print(f"SELF-TEST FAILED: {failures}")
        raise SystemExit(1)
    print("SELF-TEST PASSED: all cases correct")
