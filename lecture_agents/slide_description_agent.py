from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .llm import LLMClient
from .utils import write_json


class SlideDescriptionAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, image_paths: List[Path], page_texts: List[str], output_path: Path) -> dict:
        slides: list[dict] = []
        for idx, image_path in enumerate(image_paths, start=1):
            prior_full = [dict(s) for s in slides]
            prior_json = json.dumps(prior_full, indent=2, ensure_ascii=False)
            system = (
                "You describe one lecture slide at a time. You always receive the current slide image plus the "
                "complete JSON for every earlier slide. Prior descriptions are mandatory context: reuse their "
                "terminology and show how the argument progresses. "
                "Return JSON only."
            )
            user = f"""
Describe slide {idx} for downstream narration and planning.

CURRENT SLIDE NUMBER: {idx}
CURRENT SLIDE EXTRACTED TEXT (from PDF; may be incomplete):
{page_texts[idx - 1]}

COMPLETE PRIOR SLIDE DESCRIPTIONS (slides 1..{idx - 1}; [] if first slide):
{prior_json}

Return JSON with these keys:
- slide_number (int)
- title_guess (string)
- summary (string)
- bullet_points (list of strings)
- visual_elements (list of strings)
- carryover_concepts (list of 1–3 strings): concepts or terms carried forward FROM prior slides into this slide's role (empty list on slide 1)
- relation_to_previous (string): For slide 1 use exactly "N/A (first slide)". For slide 2+: write 1–2 sentences that NAME specific ideas from the previous slide's title_guess, summary, or bullet_points — never use only "builds on slide K" or similar.
- likely_pedagogical_purpose (string)

Hard ban: relation_to_previous must NOT be a single generic phrase like "builds on slide X" or "continues the lecture".
"""
            prev = slides[-1] if slides else None
            prev_title = (prev or {}).get("title_guess", "")
            prev_sum = ((prev or {}).get("summary") or "")[:200]
            fallback_relation = "N/A (first slide)"
            fallback_carry: List[str] = []
            if idx > 1 and prev:
                fallback_carry = [prev_title] if prev_title else []
                fallback_relation = (
                    f"This slide extends the prior discussion anchored in “{prev_title}”, "
                    f"carrying forward the ideas around: {prev_sum}."
                )

            fallback = {
                "slide_number": idx,
                "title_guess": f"Slide {idx}",
                "summary": page_texts[idx - 1][:500] if page_texts[idx - 1] else f"Visual content for slide {idx}.",
                "bullet_points": [line.strip() for line in page_texts[idx - 1].splitlines()[:6] if line.strip()],
                "visual_elements": ["slide image provided to model"],
                "carryover_concepts": fallback_carry,
                "relation_to_previous": fallback_relation,
                "likely_pedagogical_purpose": "introduce or elaborate a concept",
            }
            result = self.llm.json_response(system, user, fallback, image_path=image_path)
            slides.append(result)

        payload = {"slides": slides}
        write_json(output_path, payload)
        return payload
