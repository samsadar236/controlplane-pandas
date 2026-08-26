"""Generate a labelled grading eval set (T3.2).

Two paths:

  1. Synthetic (default, no dependencies, always runs): builds valid, gold
     graded answers with claims, criteria, and correct per-criterion scores.
     These are the "clean" (negative) class for the checker evaluation and
     the ground truth for scorer agreement. Deterministic given --seed.

  2. Giskard RAGET (optional): if `giskard` is installed and an LLM key is
     set, generate question/reference/context triples from a knowledge base.
     Kept as a documented function; it needs network + keys, so the synthetic
     path is the runnable default that unblocks scripts/eval.py immediately.

Each record (one JSON object per line):
    {
      "id": str, "question": str, "max_marks": float,
      "criteria": [ {name, points, conditions, ...} ],
      "claims":   [ {step, content, concern} ],          # what the student wrote
      "gold_per_criterion": [ {name, awarded, max, reasoning, claim_refs} ]
    }

Usage:
    python scripts/make_eval_set.py --out data/eval/set.jsonl --n 12 --seed 7
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


# Base problems: each has claims (numbered by step) and criteria whose points
# are grounded in specific claims. gold_per_criterion is the correct grading.
_BASES = [
    {
        "question": "Find the antiderivative F(x) of f(x)=2x and evaluate F(2)-F(0).",
        "max_marks": 3.0,
        "criteria": [
            {"name": "Antiderivative", "points": 1.0, "conditions": "F(x)=x^2 (+C)"},
            {"name": "Evaluation", "points": 1.0, "conditions": "F(2)-F(0)=4"},
            {"name": "Constant handled", "points": 1.0, "conditions": "constant cancels or noted"},
        ],
        "claims": [
            {"step": 1, "content": "F(x) = x^2 + C", "concern": ""},
            {"step": 2, "content": "F(2) = 4 + C, F(0) = C", "concern": ""},
            {"step": 3, "content": "F(2) - F(0) = 4", "concern": ""},
        ],
        "gold": [
            {"name": "Antiderivative", "awarded": 1.0, "max": 1.0,
             "reasoning": "claim 1 gives F(x)=x^2+C", "claim_refs": [1]},
            {"name": "Evaluation", "awarded": 1.0, "max": 1.0,
             "reasoning": "claims 2 and 3 evaluate the difference to 4", "claim_refs": [2, 3]},
            {"name": "Constant handled", "awarded": 1.0, "max": 1.0,
             "reasoning": "claim 2 shows C cancels", "claim_refs": [2]},
        ],
    },
    {
        "question": "Differentiate g(x)=x^3 and give g'(2).",
        "max_marks": 2.0,
        "criteria": [
            {"name": "Derivative", "points": 1.0, "conditions": "g'(x)=3x^2"},
            {"name": "Value", "points": 1.0, "conditions": "g'(2)=12"},
        ],
        "claims": [
            {"step": 1, "content": "g'(x) = 3x^2", "concern": ""},
            {"step": 2, "content": "g'(2) = 3*4 = 12", "concern": ""},
        ],
        "gold": [
            {"name": "Derivative", "awarded": 1.0, "max": 1.0,
             "reasoning": "claim 1 gives 3x^2", "claim_refs": [1]},
            {"name": "Value", "awarded": 1.0, "max": 1.0,
             "reasoning": "claim 2 gives 12", "claim_refs": [2]},
        ],
    },
    {
        "question": "Solve 2x+3=11 for x.",
        "max_marks": 2.0,
        "criteria": [
            {"name": "Isolate", "points": 1.0, "conditions": "2x=8"},
            {"name": "Solve", "points": 1.0, "conditions": "x=4"},
        ],
        "claims": [
            {"step": 1, "content": "2x = 11 - 3 = 8", "concern": ""},
            {"step": 2, "content": "x = 4", "concern": ""},
        ],
        "gold": [
            {"name": "Isolate", "awarded": 1.0, "max": 1.0,
             "reasoning": "claim 1 isolates 2x=8", "claim_refs": [1]},
            {"name": "Solve", "awarded": 1.0, "max": 1.0,
             "reasoning": "claim 2 gives x=4", "claim_refs": [2]},
        ],
    },
]


def _vary(base: dict, rng: random.Random, idx: int) -> dict:
    """Produce a valid variant with a possibly-partial (still grounded) score."""
    gold = [dict(pc) for pc in base["gold"]]
    # Randomly make one criterion partially/zero earned, but keep it grounded:
    # a zero-award criterion cites no claim (which is valid: nothing to ground).
    if rng.random() < 0.5 and gold:
        i = rng.randrange(len(gold))
        if rng.random() < 0.5:
            gold[i]["awarded"] = 0.0
            gold[i]["reasoning"] = "not shown"
            gold[i]["claim_refs"] = []
        else:
            gold[i]["awarded"] = round(gold[i]["max"] * 0.5, 3)
    return {
        "id": f"q{_BASES.index(base)+1}_a{idx}",
        "question": base["question"],
        "max_marks": base["max_marks"],
        "criteria": base["criteria"],
        "claims": base["claims"],
        "gold_per_criterion": gold,
    }


def generate_synthetic(n: int, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    out = []
    for i in range(n):
        base = _BASES[i % len(_BASES)]
        out.append(_vary(base, rng, i))
    return out


def generate_with_giskard(knowledge_texts: list[str], n: int = 20) -> list[dict]:
    """Optional: Giskard RAGET generation. Needs `giskard` + an LLM key.

    Returns [] with a printed note if giskard is unavailable, so callers can
    fall back to the synthetic set. This is a stub of the wiring, not run in
    CI; adapt the mapping from RAGET's question/reference/context to the
    record schema above once you point it at your real knowledge base.
    """
    try:
        from giskard.rag import KnowledgeBase, generate_testset  # type: ignore
    except Exception as e:
        print(f"[giskard] unavailable ({e}); use the synthetic set instead")
        return []
    import pandas as pd  # noqa

    kb = KnowledgeBase(pd.DataFrame({"text": knowledge_texts}))
    testset = generate_testset(kb, num_questions=n)
    records = []
    for i, row in enumerate(testset.to_pandas().itertuples()):
        # Map RAGET output to our record schema. Reference/context become the
        # gold answer/claims for a single free-form criterion.
        records.append({
            "id": f"raget_{i}",
            "question": getattr(row, "question", ""),
            "max_marks": 1.0,
            "criteria": [{"name": "Correctness", "points": 1.0,
                          "conditions": "matches the reference answer"}],
            "claims": [{"step": 1, "content": getattr(row, "reference_context", ""),
                        "concern": ""}],
            "gold_per_criterion": [{"name": "Correctness", "awarded": 1.0, "max": 1.0,
                                    "reasoning": "claim 1 matches the reference",
                                    "claim_refs": [1]}],
        })
    return records


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/eval/set.jsonl")
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    records = generate_synthetic(args.n, args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    total_points = sum(c["points"] for r in records for c in r["criteria"])
    print(f"wrote {len(records)} records to {out}")
    print(f"  distinct problems: {len({r['question'] for r in records})}")
    print(f"  total gold points: {total_points}")


if __name__ == "__main__":
    main()
