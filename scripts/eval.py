"""Evaluation harness (T3.3 + T3.4).

Two things the brief explicitly asks for: false positive / negative rates for
the checker, and per-node metrics. This produces both.

Modes:

  inject  (default, offline, no keys, no model needed for the core):
      Take each gold (correct, grounded) grade as the CLEAN/negative class,
      then synthesise faulty variants by injecting the three failure types
      the checker must catch:
        - ungrounded_award  : award > 0 with no citation
        - fabricated_cite   : cites a claim that does not exist
        - inflated_award    : awarded above the criterion max
      Run the DETERMINISTIC checker (grader.rules.verify_citations) over all
      samples and compute a confusion matrix + precision/recall/F1/FP/FN.
      This is the checker's FP/FN number. Also reports HHEM grounding
      separation on faithful vs contradicted justifications, if the model is
      available (skipped gracefully otherwise).

  full  (needs GOOGLE_API_KEY/GROQ_API_KEY and image paths in the records):
      Additionally run the live pipeline (grade_one_pass) and report scorer
      agreement vs gold (MAE, exact-match) and how often the gate skipped the
      LLM Critic. Skipped with a note if keys/images are absent.

Writes eval_report.json and eval_report.md next to --out.

Usage:
    python scripts/eval.py --set data/eval/set.jsonl --out data/eval
    python scripts/eval.py --set data/eval/set.jsonl --out data/eval --full
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

# Make `backend` importable regardless of CWD.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.grader import rules  # noqa: E402

try:
    from backend.grader import grounding as _grounding  # noqa: E402
    _HAVE_GROUNDING = True
except Exception:
    _HAVE_GROUNDING = False


# --------------------------------------------------------------------------
# Error injection
# --------------------------------------------------------------------------
def _first_scored(gold: list[dict]) -> int | None:
    for i, pc in enumerate(gold):
        if float(pc.get("awarded", 0) or 0) > 0:
            return i
    return None


def inject_ungrounded(gold: list[dict]) -> list[dict] | None:
    g = copy.deepcopy(gold)
    i = _first_scored(g)
    if i is None:
        return None
    g[i]["reasoning"] = "looks correct overall"
    g[i].pop("claim_refs", None)
    return g


def inject_fabricated(gold: list[dict]) -> list[dict] | None:
    g = copy.deepcopy(gold)
    i = _first_scored(g)
    if i is None:
        return None
    g[i]["claim_refs"] = [99]
    g[i]["reasoning"] = "claim 99 supports this"
    return g


def inject_inflated(gold: list[dict]) -> list[dict] | None:
    g = copy.deepcopy(gold)
    i = _first_scored(g)
    if i is None:
        return None
    g[i]["awarded"] = float(g[i].get("max", 0)) + 1.0
    return g


_INJECTORS = {
    "ungrounded_award": inject_ungrounded,
    "fabricated_cite": inject_fabricated,
    "inflated_award": inject_inflated,
}


# --------------------------------------------------------------------------
# Checker evaluation (deterministic; the brief's FP/FN)
# --------------------------------------------------------------------------
def evaluate_checker(records: list[dict]) -> dict:
    tp = fp = tn = fn = 0
    per_type = {k: {"caught": 0, "total": 0} for k in _INJECTORS}
    fp_examples, fn_examples = [], []

    for rec in records:
        claims = rec.get("claims", [])
        gold = rec.get("gold_per_criterion", [])

        # CLEAN sample (negative): the checker should PASS it.
        clean = rules.verify_citations(claims, gold)
        if clean["passed"]:
            tn += 1
        else:
            fp += 1
            fp_examples.append({"id": rec.get("id"), "summary": clean["summary"]})

        # FAULTY samples (positive): the checker should FAIL each.
        for kind, injector in _INJECTORS.items():
            faulty = injector(gold)
            if faulty is None:
                continue
            per_type[kind]["total"] += 1
            res = rules.verify_citations(claims, faulty)
            if not res["passed"]:
                tp += 1
                per_type[kind]["caught"] += 1
            else:
                fn += 1
                fn_examples.append({"id": rec.get("id"), "kind": kind})

    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    total = tp + fp + tn + fn
    return {
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round((tp + tn) / total, 4) if total else 0.0,
        "fp_rate": round(fp / (fp + tn), 4) if (fp + tn) else 0.0,
        "fn_rate": round(fn / (fn + tp), 4) if (fn + tp) else 0.0,
        "per_injection_type": per_type,
        "fp_examples": fp_examples[:5],
        "fn_examples": fn_examples[:5],
    }


# --------------------------------------------------------------------------
# Grounding separation (optional; needs HHEM)
# --------------------------------------------------------------------------
def evaluate_grounding(records: list[dict]) -> dict:
    if not _HAVE_GROUNDING:
        return {"available": False, "reason": "grounding module import failed"}
    faithful, contradicted = [], []
    for rec in records:
        premise = _grounding.build_premise(rec)
        gold = rec.get("gold_per_criterion", [])
        good = " ".join(pc.get("reasoning", "") for pc in gold).strip()
        bad = "This is unrelated; the answer discusses the wrong topic entirely."
        sg = _grounding.grounding_score(premise, good)
        sb = _grounding.grounding_score(premise, bad)
        if sg is not None:
            faithful.append(sg)
        if sb is not None:
            contradicted.append(sb)
    if not faithful or not contradicted:
        return {"available": False,
                "reason": "HHEM model unavailable (no score produced)"}
    mf = sum(faithful) / len(faithful)
    mc = sum(contradicted) / len(contradicted)
    return {
        "available": True,
        "mean_faithful": round(mf, 4),
        "mean_contradicted": round(mc, 4),
        "separation": round(mf - mc, 4),
        "n": len(faithful),
    }


# --------------------------------------------------------------------------
# Scorer agreement (optional; needs keys + image paths)
# --------------------------------------------------------------------------
def evaluate_scorer(records: list[dict]) -> dict:
    import os
    if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GROQ_API_KEY")):
        return {"available": False, "reason": "no API key set"}
    gradable = [r for r in records if r.get("image_path")]
    if not gradable:
        return {"available": False,
                "reason": "records have no image_path; synthetic set is text-only"}
    from backend.grader import grade_one_pass  # noqa
    abs_err, exact, skipped_critic, n = 0.0, 0, 0, 0
    for r in gradable:
        gold_total = sum(pc.get("awarded", 0) for pc in r["gold_per_criterion"])
        g = grade_one_pass(r["image_path"], r["question"], r["max_marks"], r["criteria"])
        abs_err += abs(float(g.get("score", 0)) - gold_total)
        exact += int(abs(float(g.get("score", 0)) - gold_total) < 1e-6)
        # Gate skipped the LLM critic when critic_feedback is empty and it passed.
        skipped_critic += int(g.get("grounding_band") == "high")
        n += 1
    return {
        "available": True, "n": n,
        "mae": round(abs_err / n, 4) if n else 0.0,
        "exact_match_rate": round(exact / n, 4) if n else 0.0,
        "critic_skipped_rate": round(skipped_critic / n, 4) if n else 0.0,
    }


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------
def _md(report: dict) -> str:
    c = report["checker"]["confusion"]
    lines = [
        "# GradeOps eval report", "",
        f"Records: {report['n_records']}", "",
        "## Checker FP/FN (deterministic citation verifier)", "",
        f"- precision **{report['checker']['precision']}**, "
        f"recall **{report['checker']['recall']}**, "
        f"F1 **{report['checker']['f1']}**, accuracy **{report['checker']['accuracy']}**",
        f"- FP rate {report['checker']['fp_rate']}, FN rate {report['checker']['fn_rate']}",
        f"- confusion: TP {c['tp']}, FP {c['fp']}, TN {c['tn']}, FN {c['fn']}", "",
        "### Catch rate by injected error type", "",
    ]
    for k, v in report["checker"]["per_injection_type"].items():
        rate = (v["caught"] / v["total"]) if v["total"] else 0.0
        lines.append(f"- {k}: {v['caught']}/{v['total']} ({rate:.0%})")
    g = report["grounding"]
    lines += ["", "## Grounding separation (HHEM)", ""]
    if g.get("available"):
        lines.append(f"- faithful {g['mean_faithful']} vs contradicted "
                     f"{g['mean_contradicted']} (separation {g['separation']}, n={g['n']})")
    else:
        lines.append(f"- not run: {g.get('reason')}")
    s = report["scorer"]
    lines += ["", "## Scorer agreement vs gold (live pipeline)", ""]
    if s.get("available"):
        lines.append(f"- MAE {s['mae']}, exact-match {s['exact_match_rate']}, "
                     f"critic-skipped {s['critic_skipped_rate']} (n={s['n']})")
    else:
        lines.append(f"- not run: {s.get('reason')}")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", dest="path", default="data/eval/set.jsonl")
    ap.add_argument("--out", default="data/eval")
    ap.add_argument("--full", action="store_true",
                    help="also run the live pipeline (needs keys + image_path)")
    args = ap.parse_args()

    records = [json.loads(line) for line in Path(args.path).read_text().splitlines() if line.strip()]

    report = {
        "n_records": len(records),
        "checker": evaluate_checker(records),
        "grounding": evaluate_grounding(records),
        "scorer": evaluate_scorer(records) if args.full else {"available": False, "reason": "run with --full"},
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "eval_report.json").write_text(json.dumps(report, indent=2))
    (out / "eval_report.md").write_text(_md(report))

    ch = report["checker"]
    print(f"checker: P={ch['precision']} R={ch['recall']} F1={ch['f1']} "
          f"acc={ch['accuracy']}  FP={ch['confusion']['fp']} FN={ch['confusion']['fn']}")
    for k, v in ch["per_injection_type"].items():
        rate = (v["caught"] / v["total"]) if v["total"] else 0.0
        print(f"  {k}: {v['caught']}/{v['total']} ({rate:.0%})")
    if report["grounding"].get("available"):
        gg = report["grounding"]
        print(f"grounding separation: faithful {gg['mean_faithful']} vs "
              f"contradicted {gg['mean_contradicted']} ({gg['separation']})")
    else:
        print(f"grounding: {report['grounding'].get('reason')}")
    print(f"scorer: {report['scorer'].get('reason', 'ran')}")
    print(f"wrote {out/'eval_report.json'} and {out/'eval_report.md'}")


if __name__ == "__main__":
    main()
