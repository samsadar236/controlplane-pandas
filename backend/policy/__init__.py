"""Policy layer (T2.2): load per-use-case JSON policies.

Each policy names the use case, a latency budget, and per-check actions
mapped by risk band. The three built-in configs (customer_support,
internal_knowledge, decision_support) differ deliberately, which is the
brief's "one-size-fits-all fails" point made concrete.

Actions per risk band are one of: allow | edit | flag | block.
Risk bands a check can emit: high | medium | low | unknown.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_POLICY_DIR = Path(__file__).resolve().parent
_VALID_ACTIONS = {"allow", "edit", "flag", "block"}
_VALID_RISKS = {"high", "medium", "low", "unknown"}
_KNOWN_CHECKS = {"grounding", "pii", "bias"}


def available_policies() -> list[str]:
    return sorted(p.stem for p in _POLICY_DIR.glob("*.json"))


def _validate(policy: dict, name: str) -> dict:
    if "checks" not in policy or not isinstance(policy["checks"], dict):
        raise ValueError(f"policy '{name}' has no 'checks' object")
    for check, cfg in policy["checks"].items():
        actions = (cfg or {}).get("actions", {})
        for risk, action in actions.items():
            if risk not in _VALID_RISKS:
                raise ValueError(f"policy '{name}' check '{check}': unknown risk '{risk}'")
            if action not in _VALID_ACTIONS:
                raise ValueError(f"policy '{name}' check '{check}': unknown action '{action}'")
    return policy


@lru_cache(maxsize=32)
def load_policy(name: str) -> dict:
    """Load and validate a policy by name (filename stem)."""
    path = _POLICY_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"policy '{name}' not found in {_POLICY_DIR}. "
            f"Available: {', '.join(available_policies()) or '(none)'}"
        )
    policy = json.loads(path.read_text(encoding="utf-8"))
    return _validate(policy, name)


def resolve_policy(policy_or_name) -> dict:
    """Accept a policy dict or a name; return a validated policy dict."""
    if isinstance(policy_or_name, dict):
        return _validate(policy_or_name, policy_or_name.get("name", "inline"))
    return load_policy(str(policy_or_name))


def check_enabled(policy: dict, check: str) -> bool:
    cfg = (policy.get("checks") or {}).get(check)
    return bool(cfg and cfg.get("enabled", True))


if __name__ == "__main__":
    failures = 0

    def check(label, cond):
        global failures
        print(f"[{'PASS' if cond else 'FAIL'}] {label}")
        if not cond:
            failures += 1

    names = available_policies()
    print("    available:", names)
    check("three built-in policies present",
          {"customer_support", "internal_knowledge", "decision_support"}.issubset(set(names)))
    for n in ("customer_support", "internal_knowledge", "decision_support"):
        p = load_policy(n)
        check(f"{n} loads and validates", p.get("name") == n and "checks" in p)
        check(f"{n} enables grounding/pii/bias",
              all(check_enabled(p, c) for c in _KNOWN_CHECKS))
    try:
        load_policy("does_not_exist")
        check("missing policy raises", False)
    except FileNotFoundError:
        check("missing policy raises", True)

    print()
    if failures:
        print(f"SELF-TEST FAILED: {failures}")
        raise SystemExit(1)
    print("SELF-TEST PASSED: all cases correct")
