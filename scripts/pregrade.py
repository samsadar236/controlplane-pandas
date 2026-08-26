"""Pre-grade the demo set into the database (T4.1), via the real API.

Why HTTP and not direct DB writes: this drives the same endpoints the app
already uses (POST /api/exams, /api/rubrics, /api/papers/upload), so the
resulting gradeops.db is exactly what the app produces, with no assumptions
about internal ORM constructors. Run it once against a locally-running
instance the night before the demo, then bake the produced gradeops.db into
the image (see the Dockerfile note at the bottom).

This needs the app running and the grading keys set (GOOGLE_API_KEY / GROQ_API_KEY),
so it is not run in CI.

Manifest (JSON):
    {
      "session_id": "public",
      "exam_title": "Demo Midterm",
      "rubrics": [
        {"title": "Q1", "question_text": "...", "max_marks": 3.0,
         "course_instructions": "...",
         "criteria": [{"name": "...", "points": 1.0, "conditions": "..."}]}
      ],
      "papers": [
        {"file": "data/demo/paper1.pdf", "rubric_index": 0, "student_anon_id": "STU-001"}
      ]
    }

Usage:
    # 1. start the app locally with keys set, then:
    python scripts/pregrade.py --manifest data/demo/manifest.json --base http://localhost:8000
    # 2. bake the produced gradeops.db into the image (see note below)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    raise


def _post_json(base: str, path: str, body: dict, headers: dict | None = None) -> dict:
    r = requests.post(f"{base}{path}", json=body, headers=headers or {}, timeout=120)
    r.raise_for_status()
    return r.json()


def create_exam(base: str, title: str, session_id: str) -> int:
    out = _post_json(base, "/api/exams", {"title": title}, {"X-Session-Id": session_id})
    print(f"  exam #{out['id']} '{out['title']}'")
    return out["id"]


def create_rubric(base: str, exam_id: int, rubric: dict) -> int:
    body = {
        "exam_id": exam_id,
        "title": rubric["title"],
        "question_text": rubric["question_text"],
        "max_marks": float(rubric["max_marks"]),
        "course_instructions": rubric.get("course_instructions", ""),
        "criteria": rubric["criteria"],
    }
    out = _post_json(base, "/api/rubrics", body)
    print(f"  rubric #{out['id']} '{out['title']}' ({out['version']})")
    return out["id"]


def upload_paper(base: str, exam_id: int, rubric_id: int, file_path: str,
                 student_anon_id: str | None) -> dict:
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"paper file not found: {file_path}")
    data = {"exam_id": str(exam_id), "rubric_id": str(rubric_id)}
    if student_anon_id:
        data["student_anon_id"] = student_anon_id
    with p.open("rb") as fh:
        files = {"file": (p.name, fh)}
        r = requests.post(f"{base}/api/papers/upload", data=data, files=files, timeout=1800)
    r.raise_for_status()
    out = r.json()
    print(f"  paper #{out['paper_id']} ({out['student_anon_id']}): "
          f"{len(out['crop_ids'])} crop(s) graded")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--base", default="http://localhost:8000")
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    session_id = manifest.get("session_id", "public")

    print(f"pre-grading against {args.base} (session '{session_id}')")
    exam_id = create_exam(args.base, manifest["exam_title"], session_id)

    rubric_ids = [create_rubric(args.base, exam_id, r) for r in manifest["rubrics"]]

    total_crops = 0
    for paper in manifest["papers"]:
        rid = rubric_ids[int(paper.get("rubric_index", 0))]
        out = upload_paper(args.base, exam_id, rid, paper["file"],
                           paper.get("student_anon_id"))
        total_crops += len(out["crop_ids"])

    print(f"\ndone: exam #{exam_id}, {len(rubric_ids)} rubric(s), {total_crops} crop(s) graded.")
    print("The app's gradeops.db is now populated. Bake it into the image:")
    print("  Dockerfile:  COPY gradeops.db /app/gradeops.db")
    print("  and make sure DATABASE_URL points at that path (sqlite:////app/gradeops.db).")
    print("The live demo then reads from the DB with no LLM call, and survives restarts.")


if __name__ == "__main__":
    main()
