"""
slide_description_agent.py
--------------------------
Rasterises the PDF to per-slide PNGs, then calls the model for each slide
with the current image + ALL previous descriptions in context.

Key improvements vs. original:
  • `carryover_concepts`  – explicit list of 1-3 concepts inherited from
                            the previous slide, making chaining auditable.
  • `relation_to_previous` – validated: generic strings trigger a retry.
  • Post-generation validator rejects placeholder-like chaining text.
"""

import base64
import json
import os
import re
import sys
import time
from pathlib import Path

from openai import OpenAI

# ---------------------------------------------------------------------------
# PDF rasterisation
# ---------------------------------------------------------------------------

def rasterize_pdf(pdf_path: str, output_dir: str, dpi: int = 150) -> list[str]:
    """Convert every page of *pdf_path* to a PNG under *output_dir*."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise RuntimeError("PyMuPDF is required: pip install pymupdf")

    os.makedirs(output_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    paths = []
    for i, page in enumerate(doc):
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        out = os.path.join(output_dir, f"slide_{i+1:03d}.png")
        pix.save(out)
        paths.append(out)
        print(f"[rasterize] Saved {out}")
    doc.close()
    return paths


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


_GENERIC_RELATION_PATTERNS = re.compile(
    r"^\s*builds?\s+on\s+(slide\s+\d+|previous\s+slide|the\s+previous)\s*\.?\s*$",
    re.IGNORECASE,
)

def _is_trivial_relation(text: str) -> bool:
    """Return True if the relation_to_previous string is too generic."""
    if not text:
        return True
    if _GENERIC_RELATION_PATTERNS.match(text.strip()):
        return True
    # Must reference at least one noun (heuristic: ≥ 4 words)
    if len(text.split()) < 4:
        return True
    return False


# ---------------------------------------------------------------------------
# per-slide description call
# ---------------------------------------------------------------------------

def _describe_slide(
    client: OpenAI,
    model: str,
    slide_idx: int,          # 0-based
    image_path: str,
    prior_descriptions: list[dict],
    max_retries: int = 2,
) -> dict:
    """
    Call the model for one slide.  Retries if relation_to_previous is trivial.
    Returns a dict with keys:
      slide_number, title_guess, layout_type, key_points,
      extracted_text, visual_elements, relation_to_previous, carryover_concepts
    """
    b64 = _encode_image(image_path)
    slide_num = slide_idx + 1

    prior_block = ""
    if prior_descriptions:
        prior_block = (
            "== PREVIOUS SLIDE DESCRIPTIONS (all) ==\n"
            + json.dumps(prior_descriptions, indent=2, ensure_ascii=False)
            + "\n== END PREVIOUS DESCRIPTIONS ==\n\n"
        )

    schema = """{
  "slide_number": <int>,
  "title_guess": "<short title for this slide>",
  "layout_type": "<e.g. title, bullet-list, diagram, code, two-column, image>",
  "key_points": ["<point 1>", "<point 2>", ...],
  "extracted_text": "<verbatim text visible on the slide>",
  "visual_elements": "<description of images, diagrams, charts if any>",
  "relation_to_previous": "<REQUIRED: ≥ 10 words, must name at least one specific concept, term, or title from the previous slide description>",
  "carryover_concepts": ["<concept 1 carried forward from previous slide>", ...]
}"""

    carryover_hint = ""
    if prior_descriptions:
        prev = prior_descriptions[-1]
        prev_title = prev.get("title_guess", "")
        prev_points = prev.get("key_points", [])[:3]
        carryover_hint = (
            f"\nThe immediately preceding slide was titled '{prev_title}' "
            f"and covered: {', '.join(prev_points)}. "
            "You MUST reference at least one of these concepts in "
            "relation_to_previous and list 1–3 of them in carryover_concepts."
        )

    user_content = [
        {
            "type": "text",
            "text": (
                f"{prior_block}"
                f"Describe slide {slide_num} using EXACTLY this JSON schema "
                f"(no markdown, no extra keys):\n{schema}\n"
                f"{carryover_hint}\n"
                "For slide 1 set relation_to_previous to 'N/A — first slide' "
                "and carryover_concepts to []."
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
        },
    ]

    for attempt in range(max_retries + 1):
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": user_content}],
            max_tokens=900,
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        try:
            desc = json.loads(raw)
        except json.JSONDecodeError:
            print(f"[slide_desc] Slide {slide_num}: JSON parse error, retrying...")
            time.sleep(1)
            continue

        # Ensure required fields
        desc.setdefault("slide_number", slide_num)
        desc.setdefault("carryover_concepts", [])

        relation = desc.get("relation_to_previous", "")
        if slide_idx == 0:
            desc["relation_to_previous"] = "N/A — first slide"
            desc["carryover_concepts"] = []
            break

        if _is_trivial_relation(relation):
            if attempt < max_retries:
                print(
                    f"[slide_desc] Slide {slide_num}: relation_to_previous is too "
                    f"generic ('{relation}'), retrying ({attempt+1}/{max_retries})…"
                )
                # Add explicit retry instruction
                user_content[0]["text"] += (
                    "\n\n⚠️ RETRY REQUIRED: Your previous relation_to_previous was "
                    f"too generic: '{relation}'. "
                    "Write a specific sentence that names at least one concept, "
                    "term, diagram, or title from the preceding slide."
                )
                time.sleep(1)
                continue
            else:
                print(
                    f"[slide_desc] Slide {slide_num}: WARNING — relation still generic "
                    "after max retries."
                )
        break

    return desc


# ---------------------------------------------------------------------------
# main agent
# ---------------------------------------------------------------------------

def run_slide_description_agent(
    pdf_path: str,
    project_dir: str,
) -> list[dict]:
    use_openai = os.environ.get("USE_OPENAI", "1") != "0"
    images_dir = os.path.join(project_dir, "slide_images")
    output_path = os.path.join(project_dir, "slide_description.json")

    # Always rasterise (idempotent)
    image_paths = rasterize_pdf(pdf_path, images_dir)

    if not use_openai:
        print(
            "[slide_desc] ⚠️  PLACEHOLDER MODE (USE_OPENAI=0): "
            "generating stub slide_description.json."
        )
        descriptions = [
            {
                "slide_number": i + 1,
                "title_guess": f"Slide {i+1} [PLACEHOLDER]",
                "layout_type": "unknown",
                "key_points": ["PLACEHOLDER"],
                "extracted_text": "PLACEHOLDER",
                "visual_elements": "PLACEHOLDER",
                "relation_to_previous": "N/A — first slide" if i == 0 else "PLACEHOLDER — run with USE_OPENAI=1",
                "carryover_concepts": [],
            }
            for i in range(len(image_paths))
        ]
    else:
        client = OpenAI()
        model = os.environ.get("OPENAI_MODEL", "gpt-4.1")

        descriptions = []
        for idx, img_path in enumerate(image_paths):
            print(f"[slide_desc] Describing slide {idx+1}/{len(image_paths)} …")
            desc = _describe_slide(
                client=client,
                model=model,
                slide_idx=idx,
                image_path=img_path,
                prior_descriptions=descriptions,
            )
            descriptions.append(desc)
            time.sleep(0.5)  # rate-limit courtesy

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(descriptions, f, indent=2, ensure_ascii=False)

    print(f"[slide_desc] ✅ Wrote {output_path} ({len(descriptions)} slides)")
    return descriptions


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else "Lecture_17_AI_screenplays.pdf"
    proj = sys.argv[2] if len(sys.argv) > 2 else "projects/project_debug"
    run_slide_description_agent(pdf, proj)
