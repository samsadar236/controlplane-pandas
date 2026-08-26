"""Similarity-as-fairness (T2.5).

Repurposes the existing plagiarism similarity engine as a grading-fairness
signal: two near-identical answers that received very different scores is a
grading-consistency (fairness) problem. This is domain-native output-side
bias detection for the grading vertical, at essentially zero extra cost,
since plagiarism.find_similar_pairs already produces the pairs.

Feed it the same pairs plus a {crop_id: score} map. Surface the flags in the
Audit view alongside the plagiarism similarity flags.
"""
from __future__ import annotations


def _default_gap(max_marks: float | None) -> float:
    # A gap of >= 25% of the max marks on near-identical answers is suspicious.
    if max_marks and max_marks > 0:
        return 0.25 * float(max_marks)
    return 1.0


def fairness_flags(pairs, scores: dict, *, score_gap: float | None = None,
                   max_marks: float | None = None) -> list[dict]:
    """Flag similar-answer pairs whose scores diverge.

    pairs:  iterable of (crop_a_id, crop_b_id, similarity)
    scores: {crop_id: score}
    """
    thresh = score_gap if score_gap is not None else _default_gap(max_marks)
    flags = []
    for a, b, sim in pairs or []:
        sa, sb = scores.get(a), scores.get(b)
        if sa is None or sb is None:
            continue
        gap = abs(float(sa) - float(sb))
        if gap >= thresh:
            flags.append({
                "crop_a": a,
                "crop_b": b,
                "similarity": round(float(sim), 4),
                "score_a": float(sa),
                "score_b": float(sb),
                "score_gap": round(gap, 4),
                "type": "grading_inconsistency",
            })
    flags.sort(key=lambda f: (f["score_gap"], f["similarity"]), reverse=True)
    return flags


if __name__ == "__main__":
    failures = 0

    def check(label, cond):
        global failures
        print(f"[{'PASS' if cond else 'FAIL'}] {label}")
        if not cond:
            failures += 1

    pairs = [(1, 2, 0.97), (3, 4, 0.93), (5, 6, 0.99)]
    scores = {1: 2.0, 2: 2.0, 3: 2.0, 4: 0.0, 5: 1.0, 6: 1.3}
    flags = fairness_flags(pairs, scores, max_marks=2.0)  # default gap = 0.5
    got = {(f["crop_a"], f["crop_b"]) for f in flags}
    check("identical-score pair (1,2) not flagged", (1, 2) not in got)
    check("divergent pair (3,4) flagged", (3, 4) in got)
    check("small-gap pair (5,6) gap 0.3 below 0.5 not flagged", (5, 6) not in got)
    check("flags sorted by gap desc", flags and flags[0]["crop_a"] == 3)

    tight = fairness_flags(pairs, scores, score_gap=0.25)
    check("tighter threshold 0.25 catches the (5,6) 0.3 gap",
          (5, 6) in {(f["crop_a"], f["crop_b"]) for f in tight})

    print()
    if failures:
        print(f"SELF-TEST FAILED: {failures}")
        raise SystemExit(1)
    print("SELF-TEST PASSED: all cases correct")
