"""Langgraph wiring for the agentic grader (cascade).

Graph:
    extractor -> scorer -> justifier -> verifier --gate--> critic --pass--> END
                   ^                        |                  |
                   |                        +--(clear)--> END  |
                   +----------------- retry-with-feedback (optional) ----+

The `verifier` node runs the deterministic checks (citation rules + HHEM
grounding) with no LLM call. `gate_router` then sends only borderline cases
to the LLM `critic`; clean and clearly-broken answers skip it. This is the
cost/latency lever: most answers never reach the LLM.

Multi-pass:
    Under Lane A (deterministic, temperature 0) the default is a single
    pass, so multi-pass variance is not used as a confidence signal.
    grade_multi_pass is kept for the stochastic (Lane B) option; with
    num_passes=1 it simply runs one pass.
"""
from __future__ import annotations

import base64
from pathlib import Path

from langgraph.graph import StateGraph, START, END

from ..config import settings
from .state import GradingState
from .nodes import (
    extractor_node, scorer_node, justifier_node, critic_node, critic_router,
)
from .cascade import verifier_node, gate_router


def build_grading_graph():
    g = StateGraph(GradingState)
    g.add_node("extractor", extractor_node)
    g.add_node("scorer", scorer_node)
    g.add_node("justifier", justifier_node)
    g.add_node("verifier", verifier_node)
    g.add_node("critic", critic_node)

    g.add_edge(START, "extractor")
    g.add_edge("extractor", "scorer")
    g.add_edge("scorer", "justifier")
    g.add_edge("justifier", "verifier")
    # Deterministic gate: only borderline cases reach the LLM critic.
    g.add_conditional_edges("verifier", gate_router, {"critic": "critic", END: END})
    # Critic may request a retry (optional; off unless grader_critic_retry > 0).
    g.add_conditional_edges("critic", critic_router, {"scorer": "scorer", END: END})
    return g.compile()


GRAPH = build_grading_graph()


def _read_image_b64(image_path: str) -> tuple[str, str]:
    p = Path(image_path)
    data = p.read_bytes()
    suffix = p.suffix.lower().lstrip(".")
    media_type = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix or 'jpeg'}"
    return base64.b64encode(data).decode("ascii"), media_type


def grade_one_pass(image_path: str, question: str, max_marks: float,
                   criteria: list[dict]) -> dict:
    img_b64, media_type = _read_image_b64(image_path)
    initial: GradingState = {
        "image_b64": img_b64,
        "media_type": media_type,
        "question": question,
        "max_marks": max_marks,
        "criteria": criteria,
        "retry_count": 0,
        "errors": [],
    }
    try:
        final = GRAPH.invoke(initial)
    except Exception as e:
        return {
            "score": 0.0,
            "max_score": max_marks,
            "per_criterion": [],
            "transcript": "",
            "justification": f"[grading failed: {e}]",
            "flags": ["api_error"],
            "critic_passed": False,
            "critic_feedback": str(e),
            "rule_summary": "not evaluated (grading failed)",
            "grounding_score": None,
            "grounding_band": "unknown",
            "deterministic_passed": False,
        }
    return {
        "score": float(final.get("score", 0.0)),
        "max_score": float(final.get("max_score", max_marks)),
        "per_criterion": final.get("per_criterion", []),
        "transcript": final.get("transcript", ""),
        "justification": final.get("justification", ""),
        "flags": final.get("flags", []),
        "critic_passed": bool(final.get("critic_passed", True)),
        "critic_feedback": final.get("critic_feedback", ""),
        "rule_summary": final.get("rule_summary", ""),
        "grounding_score": final.get("grounding_score"),
        "grounding_band": final.get("grounding_band", "unknown"),
        "deterministic_passed": bool(final.get("deterministic_passed", True)),
    }


def grade_multi_pass(image_path: str, question: str, max_marks: float,
                     criteria: list[dict], num_passes: int | None = None) -> list[dict]:
    """Run NUM_PASSES grading invocations sequentially.

    Sequential is intentional: the rate-limit module enforces a global
    minimum gap between calls, so parallelism does not help and only
    increases the risk of bursting past the per-minute quota. Under Lane A
    the default is a single pass.
    """
    n = num_passes or settings.grader_num_passes
    return [grade_one_pass(image_path, question, max_marks, criteria) for _ in range(n)]
