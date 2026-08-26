"""Deterministic grounding checks for the grader. No LLM, no network.

This runs BEFORE the LLM Critic in the cascade. It catches the failure
mode the Critic is meant to catch, but structurally and for free:

  1. ungrounded_award   : a criterion has awarded > 0 but cites no claim
  2. missing_claim      : a criterion cites a claim step that does not exist
  3. award_exceeds_max  : awarded is above the criterion's max
  4. award_negative     : awarded is below zero
  5. concern_claim_credited (warning): awarded > 0 while a cited claim was
     flagged by the Extractor as illegible / crossed_out / off_topic

Why this matters (and why it is not redundant with the LLM Critic):
  - An LLM judge shows authority bias: it tends to trust a citation like
    "claims 2 and 3 show F(x)" even when claim 2 or 3 does not exist or
    does not support the point. A string/number check cannot be fooled by
    a fabricated citation, so it is a reliable first gate.
  - It is deterministic and auditable: every decision is a rule with a
    reason, which is exactly what a governance/audit trail wants.
  - It costs no API calls, which protects the free-tier quota.

Citation sources, in priority order:
  - Structured: per_criterion[i]["claim_refs"] or ["supporting_claim_ids"]
    (a list of ints). Preferred if present — bullet-proof, no parsing.
  - Prose: parsed from per_criterion[i]["reasoning"], matching the format
    the Scorer prompt asks for, e.g. "claims 2 and 3 show F(x) correctly".

Claims are numbered by their "step" field (as produced by the Extractor).
"""
from __future__ import annotations

import re
from typing import Any, Iterable

# Small tolerance so floating-point sums do not trip award_exceeds_max.
_EPS = 1e-6

# Words that connect a run of claim numbers ("claims 2 and 3", "2 to 4").
_CONNECTORS = {"and", "or", "&", ",", "+", "to", "through", "thru", "-", "\u2013", "\u2014"}
_RANGE_WORDS = {"to", "through", "thru", "-", "\u2013", "\u2014"}
_TOKEN_RE = re.compile(r"\d+|[a-zA-Z]+|[^\w\s]", re.UNICODE)

# Anchors after which a run of claim numbers is expected.
_ANCHOR_RE = re.compile(r"\b(?:claims?|steps?)\b", re.IGNORECASE)
# Bracketed references like [2] or [2, 3].
_BRACKET_RE = re.compile(r"\[\s*(\d+(?:\s*[,\-\u2013]\s*\d+)*)\s*\]")

_FLAG_CONCERNS = {"illegible", "crossed_out", "off_topic"}


def _expand_numbers(fragment: str) -> set[int]:
    """Turn '2 3 - 5' into {2,3,4,5}; plain ints pass through."""
    nums: set[int] = set()
    # Ranges first: 'a - b'
    for rng in re.finditer(r"(\d+)\s*-\s*(\d+)", fragment):
        a, b = int(rng.group(1)), int(rng.group(2))
        if a <= b and (b - a) < 1000:
            nums.update(range(a, b + 1))
    # Remaining standalone ints (after removing range spans)
    no_ranges = re.sub(r"\d+\s*-\s*\d+", " ", fragment)
    for m in re.finditer(r"\d+", no_ranges):
        nums.add(int(m.group()))
    return nums


def _refs_from_tail(tail: str) -> set[int]:
    """Collect the contiguous run of claim numbers right after an anchor.

    Stops at the first real word that is not a connector, so
    "claims 2 and 3 show 5 steps" yields {2, 3}, not {2, 3, 5}.
    """
    frag_tokens: list[str] = []
    for tok in _TOKEN_RE.findall(tail):
        low = tok.lower()
        if tok.isdigit():
            frag_tokens.append(tok)
        elif low in _CONNECTORS:
            frag_tokens.append("-" if low in _RANGE_WORDS else " ")
        elif tok.isspace():
            continue
        else:
            break  # first non-connector word ends the reference run
    return _expand_numbers(" ".join(frag_tokens))


def parse_claim_refs(text: str) -> set[int]:
    """Best-effort extraction of cited claim step numbers from prose."""
    if not text:
        return set()
    refs: set[int] = set()
    # Anchored runs: "claim(s) N ...", "step(s) N ..."
    for m in _ANCHOR_RE.finditer(text):
        refs |= _refs_from_tail(text[m.end():])
    # Bracketed: "[2]", "[2, 3]"
    for m in _BRACKET_RE.finditer(text):
        refs |= _expand_numbers(m.group(1))
    return refs


def _structured_refs(pc: dict) -> set[int] | None:
    """Return structured refs if the Scorer provided them, else None."""
    for key in ("claim_refs", "supporting_claim_ids", "claim_ids"):
        val = pc.get(key)
        if isinstance(val, Iterable) and not isinstance(val, (str, bytes)):
            out: set[int] = set()
            for v in val:
                try:
                    out.add(int(v))
                except (TypeError, ValueError):
                    continue
            return out
    return None


def _valid_steps(claims: Iterable[dict]) -> set[int]:
    steps: set[int] = set()
    for c in claims or []:
        try:
            steps.add(int(c.get("step")))
        except (TypeError, ValueError):
            continue
    return steps


def _concern_by_step(claims: Iterable[dict]) -> dict[int, str]:
    out: dict[int, str] = {}
    for c in claims or []:
        try:
            step = int(c.get("step"))
        except (TypeError, ValueError):
            continue
        concern = (c.get("concern") or "").strip().lower()
        if concern:
            out[step] = concern
    return out


def verify_citations(claims: list[dict], per_criterion: list[dict]) -> dict:
    """Run the deterministic grounding checks.

    Returns:
        {
          "passed": bool,                 # True if no blocking violations
          "violations": [ {criterion, index, type, severity, detail} ],
          "n_checked": int,               # criteria with awarded > 0
          "n_criteria": int,
          "summary": str,                 # one-line, audit-friendly
        }
    Severity is "block" (fails the check) or "warn" (uncertainty signal only).
    """
    valid = _valid_steps(claims)
    concerns = _concern_by_step(claims)
    violations: list[dict] = []
    n_checked = 0

    for i, pc in enumerate(per_criterion or []):
        name = str(pc.get("name", f"criterion_{i}"))
        try:
            awarded = float(pc.get("awarded", 0) or 0)
        except (TypeError, ValueError):
            awarded = 0.0
        try:
            cmax = float(pc.get("max", 0) or 0)
        except (TypeError, ValueError):
            cmax = 0.0

        # Bounds checks apply regardless of citations.
        if awarded < -_EPS:
            violations.append(_v(name, i, "award_negative", "block",
                                 f"awarded={awarded} is below zero"))
        if awarded > cmax + _EPS:
            violations.append(_v(name, i, "award_exceeds_max", "block",
                                 f"awarded={awarded} exceeds max={cmax}"))

        if awarded <= _EPS:
            # No points awarded: nothing to ground.
            continue
        n_checked += 1

        structured = _structured_refs(pc)
        refs = structured if structured is not None else parse_claim_refs(pc.get("reasoning", ""))

        if not refs:
            violations.append(_v(name, i, "ungrounded_award", "block",
                                 "awarded > 0 but cites no claim in its reasoning"))
            continue

        missing = sorted(r for r in refs if r not in valid)
        if missing:
            violations.append(_v(name, i, "missing_claim", "block",
                                 f"cites claim(s) {missing} that do not exist "
                                 f"(valid steps: {sorted(valid) or 'none'})"))

        flagged = sorted(r for r in refs if concerns.get(r) in _FLAG_CONCERNS)
        if flagged:
            detail = ", ".join(f"{r}:{concerns[r]}" for r in flagged)
            violations.append(_v(name, i, "concern_claim_credited", "warn",
                                 f"awards points citing flagged claim(s) [{detail}]"))

    blocking = [v for v in violations if v["severity"] == "block"]
    passed = not blocking
    summary = _summarize(passed, violations, n_checked)
    return {
        "passed": passed,
        "violations": violations,
        "n_checked": n_checked,
        "n_criteria": len(per_criterion or []),
        "summary": summary,
    }


def check_state(state: dict) -> dict:
    """Convenience wrapper over a GradingState-like dict."""
    return verify_citations(state.get("claims", []) or [],
                            state.get("per_criterion", []) or [])


def _v(criterion: str, index: int, vtype: str, severity: str, detail: str) -> dict:
    return {"criterion": criterion, "index": index, "type": vtype,
            "severity": severity, "detail": detail}


def _summarize(passed: bool, violations: list[dict], n_checked: int) -> str:
    if not violations:
        return f"grounding OK ({n_checked} scored criteria, no issues)"
    blocks = sum(1 for v in violations if v["severity"] == "block")
    warns = sum(1 for v in violations if v["severity"] == "warn")
    verdict = "PASS" if passed else "FAIL"
    types = ", ".join(sorted({v["type"] for v in violations}))
    return f"grounding {verdict}: {blocks} blocking, {warns} warning ({types})"


def format_report(result: dict) -> str:
    """Multi-line human/audit-friendly rendering of a verify_citations result."""
    lines = [result.get("summary", "")]
    for v in result.get("violations", []):
        mark = "x" if v["severity"] == "block" else "!"
        lines.append(f"  [{mark}] {v['type']} @ '{v['criterion']}': {v['detail']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Self-test: run `python -m backend.grader.rules` (or `python rules.py`).
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    claims = [
        {"step": 1, "content": "Let F(x) = integral of f", "concern": ""},
        {"step": 2, "content": "F(x) = x^2 + C", "concern": ""},
        {"step": 3, "content": "scribble", "concern": "illegible"},
    ]

    cases = [
        (
            "valid: awarded points cite existing claims",
            [{"name": "Setup", "awarded": 2, "max": 2,
              "reasoning": "claims 1 and 2 show the antiderivative"}],
            True, set(),
        ),
        (
            "ungrounded: awarded > 0 with no citation",
            [{"name": "Setup", "awarded": 2, "max": 2,
              "reasoning": "looks correct overall"}],
            False, {"ungrounded_award"},
        ),
        (
            "missing claim: cites a step that does not exist",
            [{"name": "Final", "awarded": 1, "max": 1,
              "reasoning": "claim 4 gives the final value"}],
            False, {"missing_claim"},
        ),
        (
            "over max: awarded above the criterion max",
            [{"name": "Setup", "awarded": 3, "max": 2,
              "reasoning": "claims 1 and 2"}],
            False, {"award_exceeds_max"},
        ),
        (
            "warning only: credits an illegible claim but still passes",
            [{"name": "Setup", "awarded": 1, "max": 2,
              "reasoning": "claim 3 attempts the step"}],
            True, {"concern_claim_credited"},
        ),
        (
            "structured refs beat prose (bad prose, good ids)",
            [{"name": "Setup", "awarded": 2, "max": 2,
              "reasoning": "no numbers here", "claim_refs": [1, 2]}],
            True, set(),
        ),
        (
            "range + zero-award criterion ignored",
            [{"name": "Work", "awarded": 2, "max": 2, "reasoning": "claims 1-2 are correct"},
             {"name": "Bonus", "awarded": 0, "max": 1, "reasoning": "nothing shown"}],
            True, set(),
        ),
    ]

    failures = 0
    for label, per_criterion, want_pass, want_types in cases:
        res = verify_citations(claims, per_criterion)
        got_types = {v["type"] for v in res["violations"]}
        ok = (res["passed"] == want_pass) and want_types.issubset(got_types)
        status = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"[{status}] {label}")
        print(f"        passed={res['passed']} (want {want_pass}); "
              f"types={sorted(got_types) or '[]'} (want superset of {sorted(want_types) or '[]'})")
        if res["violations"]:
            for line in format_report(res).splitlines()[1:]:
                print(f"      {line}")

    print()
    if failures:
        print(f"SELF-TEST FAILED: {failures} case(s) wrong")
        raise SystemExit(1)
    print("SELF-TEST PASSED: all cases correct")
