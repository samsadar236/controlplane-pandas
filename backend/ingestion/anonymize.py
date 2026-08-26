"""Anonymize a crop by detecting and masking student identifiers.

Privacy pillar: identifier regions (name, roll/ID, date, email) are erased
from the image BEFORE it is sent to the grading model. Because inputs are
often full-page phone photos (not tight template scans), a fixed top strip
misses the header, so the default mode asks the vision model to locate PII
bounding boxes and blacks them out wherever they appear.

Modes:
  - 'auto' (default): vision model returns normalized bboxes for PII, we
     paint them out. Falls back to 'top_strip' if the call fails.
  - 'top_strip': legacy — paints the top 8% (fine for tight scanned crops).
  - 'none': pass-through.
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from PIL import Image, ImageDraw

from ..grader.llm import get_llm
from ..grader.rate_limit import wait_turn
from langchain_core.messages import HumanMessage

_PII_PROMPT = (
    "You are a privacy redaction tool for scanned/photographed exam answer sheets. "
    "Find every region containing STUDENT IDENTIFIERS: the student's name, roll "
    "number / registration / ID, date, email, phone, or signature. Do NOT include "
    "the actual answer or math work.\n\n"
    "Return ONLY strict JSON: a list of boxes with normalized coordinates in [0,1] "
    "relative to image width/height, top-left origin:\n"
    '[{"x0":0.1,"y0":0.05,"x1":0.7,"y1":0.09,"label":"name"}]\n'
    "If there are no identifiers, return []. No prose, no code fences."
)


def _detect_pii_boxes(crop_path: str) -> list[dict]:
    """Ask the vision model for normalized PII bounding boxes. [] on failure."""
    import base64
    data = Path(crop_path).read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    suffix = Path(crop_path).suffix.lower().lstrip(".") or "png"
    media = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix}"
    wait_turn()
    llm = get_llm("vision")
    msg = HumanMessage(content=[
        {"type": "image_url", "image_url": {"url": f"data:{media};base64,{b64}"}},
        {"type": "text", "text": _PII_PROMPT},
    ])
    raw = llm.invoke([msg]).content
    raw = raw if isinstance(raw, str) else str(raw)
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.I).strip()
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        boxes = json.loads(cleaned[start:end + 1])
        return [b for b in boxes if all(k in b for k in ("x0", "y0", "x1", "y1"))]
    except json.JSONDecodeError:
        return []


def _paint_top_strip(img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
    w, h = img.size
    strip_h = int(h * 0.08)
    draw.rectangle([0, 0, w, strip_h], fill="black")


def anonymize_crop(crop_path: str, output_dir: str, mode: str = "auto") -> str:
    """Anonymize a crop and write the result. Returns the new path."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    img = Image.open(crop_path).convert("RGB")
    out = output_dir / f"anon_{uuid.uuid4().hex[:10]}.png"

    if mode == "none":
        img.save(str(out), format="PNG")
        return str(out)

    draw = ImageDraw.Draw(img)
    w, h = img.size

    if mode == "top_strip":
        _paint_top_strip(img, draw)
        img.save(str(out), format="PNG")
        return str(out)

    # mode == "auto"
    boxes = []
    try:
        boxes = _detect_pii_boxes(crop_path)
    except Exception as e:
        print(f"[anonymize] vision PII detection failed ({e}); using top-strip fallback")

    if boxes:
        pad = 0.01  # small padding so we fully cover the text
        for b in boxes:
            x0 = max(0, (float(b["x0"]) - pad)) * w
            y0 = max(0, (float(b["y0"]) - pad)) * h
            x1 = min(1, (float(b["x1"]) + pad)) * w
            y1 = min(1, (float(b["y1"]) + pad)) * h
            draw.rectangle([x0, y0, x1, y1], fill="black")
    else:
        # No boxes (or detection failed) -> conservative fallback
        _paint_top_strip(img, draw)

    img.save(str(out), format="PNG")
    return str(out)