"""
narration_agent.py
------------------
For each slide, calls the model with:
  - current slide image
  - style.json
  - premise.json
  - arc.json
  - slide_description.json (all)
  - all prior narrations

Key improvements vs. original:
  • target_word_count  – derived from slide complexity (50-200 words).
  • estimated_seconds  – computed from actual word count (~130 wpm).
  • Title slide intro  – must use ≥ 1 framing_device from style.json.
  • All slides         – transition phrase must echo prior narration's close.
"""

import base64
import json
import math
import os
import re
import sys
import time

from openai import OpenAI

# Average speaking pace for the style; adjust if transcript suggests otherwise
WORDS_PER_MINUTE = 130


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _target_word_count(slide_desc: dict) -> int:
    """
    Heuristic: more key points → more words.
    Title/single-image slides get shorter narrations.
    """
    layout = slide_desc.get("layout_type", "").lower()
    key_points = slide_desc.get("key_points", [])
    n = len(key_points)

    if layout in ("title", "image", "blank"):
        return 60
    if n <= 2:
        return 80
    if n <= 4:
        return 130
    return min(200, 80 + n * 20)


def _estimated_seconds(word_count: int) -> int:
    return math.ceil(word_count / WORDS_PER_MINUTE * 60)


def _narrate_slide(
    client: OpenAI,
    model: str,
    slide_idx: int,
    image_path: str,
    style: dict,
    premise: dict,
    arc: dict,
    slide_descriptions: list[dict],
    prior_narrations: list[dict],
) -> dict:
    slide_num = slide_idx + 1
    slide_desc = slide_descriptions[slide_idx]
    target_wc = _target_word_count(slide_desc)
    b64 = _encode_image(image_path)

    # ---- Build context blocks ----
    style_block = json.dumps(style, indent=2, ensure_ascii=False)
    premise_block = json.dumps(premise, indent=2, ensure_ascii=False)
    arc_block = json.dumps(arc, indent=2, ensure_ascii=False)
    desc_block = json.dumps(slide_descriptions, indent=2, ensure_ascii=False)
    prior_block = json.dumps(prior_narrations, indent=2, ensure_ascii=False) if prior_narrations else "[]"

    # ---- Slide-specific instructions ----
    if slide_idx == 0:
        special = (
            "This is the TITLE SLIDE. The narration must:\n"
            "1. Introduce the speaker (use 'I' — you are the instructor).\n"
            "2. State the lecture topic clearly.\n"
            "3. Give a 2-3 sentence overview of what will be covered.\n"
            "4. Use AT LEAST ONE of the framing_devices from style.json as your opening.\n"
            f"   framing_devices: {json.dumps(style.get('framing_devices', []))}\n"
            "Do NOT start with 'Hi everyone, I'm your instructor' — use the actual "
            "style from the transcript instead."
        )
    else:
        prev_narr = prior_narrations[-1].get("narration", "") if prior_narrations else ""
        # Last 20 words of previous narration for continuity reference
        prev_close = " ".join(prev_narr.split()[-20:]) if prev_narr else ""
        special = (
            f"This is slide {slide_num}. "
            "The narration must:\n"
            "1. Open with a transition that connects to the PREVIOUS slide's closing idea.\n"
            f"   Previous narration ended with: '…{prev_close}'\n"
            "2. Explain the slide content — do NOT just read bullet points.\n"
            "3. Use at least one rhetorical habit or transition phrase from style.json.\n"
            "4. Close in a way that naturally leads into the next slide (if not the last).\n"
        )

    user_content = [
        {
            "type": "text",
            "text": (
                f"== STYLE ==\n{style_block}\n\n"
                f"== PREMISE ==\n{premise_block}\n\n"
                f"== ARC ==\n{arc_block}\n\n"
                f"== ALL SLIDE DESCRIPTIONS ==\n{desc_block}\n\n"
                f"== PRIOR NARRATIONS ==\n{prior_block}\n\n"
                f"== TASK: NARRATE SLIDE {slide_num} ==\n"
                f"{special}\n\n"
                f"Target word count: {target_wc} words (±20%).\n"
                "Return ONLY valid JSON (no markdown fences):\n"
                "{\n"
                '  "slide_number": <int>,\n'
                '  "narration": "<narration text>",\n'
                '  "word_count": <int>,\n'
                '  "estimated_seconds": <int>\n'
                "}"
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
        },
    ]

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": user_content}],
        max_tokens=600,
        temperature=0.4,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    result = json.loads(raw)

    # Recompute estimated_seconds from actual word count for accuracy
    actual_wc = len(result.get("narration", "").split())
    result["word_count"] = actual_wc
    result["estimated_seconds"] = _estimated_seconds(actual_wc)
    result["slide_number"] = slide_num

    return result


def run_narration_agent(
    pdf_path: str,         # used only to locate slide images
    style_path: str,
    project_dir: str,
) -> list[dict]:
    use_openai = os.environ.get("USE_OPENAI", "1") != "0"
    output_path = os.path.join(project_dir, "slide_description_narration.json")

    premise_path = os.path.join(project_dir, "premise.json")
    arc_path = os.path.join(project_dir, "arc.json")
    desc_path = os.path.join(project_dir, "slide_description.json")
    images_dir = os.path.join(project_dir, "slide_images")

    with open(style_path, "r", encoding="utf-8") as f:
        style = json.load(f)
    with open(premise_path, "r", encoding="utf-8") as f:
        premise = json.load(f)
    with open(arc_path, "r", encoding="utf-8") as f:
        arc = json.load(f)
    with open(desc_path, "r", encoding="utf-8") as f:
        slide_descriptions = json.load(f)

    # Locate images
    image_paths = sorted(
        [os.path.join(images_dir, fn) for fn in os.listdir(images_dir)
         if fn.endswith(".png")],
        key=lambda p: p,
    )

    if not use_openai:
        print(
            "[narration_agent] ⚠️  PLACEHOLDER MODE (USE_OPENAI=0): "
            "generating stub narrations."
        )
        results = []
        for i, desc in enumerate(slide_descriptions):
            results.append({
                "slide_number": i + 1,
                "slide_description": desc,
                "narration": f"PLACEHOLDER narration for slide {i+1}. Run with USE_OPENAI=1.",
                "word_count": 10,
                "estimated_seconds": 5,
            })
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"[narration_agent] ✅ Wrote {output_path}")
        return results

    client = OpenAI()
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1")

    results = []
    prior_narrations = []

    for idx, (img_path, desc) in enumerate(zip(image_paths, slide_descriptions)):
        print(f"[narration_agent] Narrating slide {idx+1}/{len(image_paths)} …")
        narr = _narrate_slide(
            client=client,
            model=model,
            slide_idx=idx,
            image_path=img_path,
            style=style,
            premise=premise,
            arc=arc,
            slide_descriptions=slide_descriptions,
            prior_narrations=prior_narrations,
        )
        entry = {
            "slide_number": idx + 1,
            "slide_description": desc,
            "narration": narr.get("narration", ""),
            "word_count": narr.get("word_count", 0),
            "estimated_seconds": narr.get("estimated_seconds", 0),
        }
        results.append(entry)
        prior_narrations.append(entry)
        time.sleep(0.5)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    total_sec = sum(r.get("estimated_seconds", 0) for r in results)
    print(
        f"[narration_agent] ✅ Wrote {output_path} "
        f"({len(results)} slides, ~{total_sec//60}m{total_sec%60}s estimated)"
    )
    return results


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else "Lecture_17_AI_screenplays.pdf"
    proj = sys.argv[2] if len(sys.argv) > 2 else "projects/project_debug"
    run_narration_agent(pdf, "style.json", proj)
