"""PII / privacy check (output-side).

Deterministic regex baseline that always runs (no dependency, no model):
emails, US SSNs, IPv4, phone-like numbers, and credit-card numbers validated
with the Luhn checksum (so a random 16-digit string is not a false hit).

Optional upgrade: if Microsoft Presidio is installed, it is used for higher
recall (names, addresses, and more). Everything degrades gracefully.

Risk: high if a card or SSN is present; medium for email/phone/IP; low if none.
"""
from __future__ import annotations

import re

from . import result

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_IPV4 = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
)
_PHONE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s.\-]?)?(?:\(?\d{2,4}\)?[\s.\-]?){2,4}\d{2,4}(?!\d)")
_CARD_CANDIDATE = re.compile(r"\d(?:[ \-]?\d){12,18}")

_HIGH_TYPES = {"credit_card", "ssn", "us_ssn", "credit_card_number"}


def _luhn_ok(digits: str) -> bool:
    if len(digits) < 13:
        return False
    total, alt = 0, False
    for ch in reversed(digits):
        d = ord(ch) - 48
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def _find_cards(text: str) -> list[tuple[str, str]]:
    out = []
    for m in _CARD_CANDIDATE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            out.append(("credit_card", m.group().strip()))
    return out


def _regex_scan(text: str) -> list[tuple[str, str]]:
    ev: list[tuple[str, str]] = []
    ev += _find_cards(text)
    for m in _SSN.finditer(text):
        ev.append(("ssn", m.group()))
    for m in _EMAIL.finditer(text):
        ev.append(("email", m.group()))
    for m in _IPV4.finditer(text):
        ev.append(("ip", m.group()))
    captured = {v for _, v in ev}
    for m in _PHONE.finditer(text):
        val = m.group().strip()
        if len(re.sub(r"\D", "", val)) < 7:
            continue
        if any(val in c or c in val for c in captured):
            continue
        ev.append(("phone", val))
        captured.add(val)
    return ev


def _optional_presidio(text: str):
    try:
        from presidio_analyzer import AnalyzerEngine
    except Exception:
        return None
    try:
        results = AnalyzerEngine().analyze(text=text, language="en")
        return [(r.entity_type.lower(), text[r.start:r.end]) for r in results]
    except Exception:
        return None


def run(output: str) -> dict:
    text = output or ""
    ev = _optional_presidio(text)
    engine = "presidio" if ev is not None else "regex"
    if ev is None:
        ev = _regex_scan(text)

    if not ev:
        return result("pii", "low", score=0.0, detail=f"no PII detected ({engine})")

    types = {t for t, _ in ev}
    risk = "high" if types & _HIGH_TYPES else "medium"
    detail = f"{len(ev)} PII item(s) via {engine}: {sorted(types)}"
    return result("pii", risk, score=float(len(ev)), detail=detail, evidence=ev)


if __name__ == "__main__":
    failures = 0

    def check(label, cond):
        global failures
        print(f"[{'PASS' if cond else 'FAIL'}] {label}")
        if not cond:
            failures += 1

    r_clean = run("The derivative of x squared is two x.")
    check("clean text -> low risk", r_clean["risk"] == "low")

    r_card = run("Sure, charge card 4111 1111 1111 1111 for the order.")
    check("valid Luhn card -> high risk", r_card["risk"] == "high")
    check("card is in evidence",
          any(t == "credit_card" for t, _ in r_card["evidence"]))

    r_badcard = run("Order id 1234 5678 9012 3456 7 is pending.")  # fails Luhn
    check("non-Luhn digit run is NOT a card",
          not any(t == "credit_card" for t, _ in r_badcard["evidence"]))

    r_ssn = run("His SSN is 123-45-6789, please verify.")
    check("SSN -> high risk", r_ssn["risk"] == "high")

    r_email = run("Email me at alice@example.com about it.")
    check("email -> medium risk", r_email["risk"] == "medium")

    print()
    if failures:
        print(f"SELF-TEST FAILED: {failures}")
        raise SystemExit(1)
    print("SELF-TEST PASSED: all cases correct")
