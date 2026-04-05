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
                "complete JSON for every earlier slide you already described. Use those prior descriptions to stay "
                "consistent with terminology, narrative thread, and how the deck is building its argument. "
                "Each new description must explicitly build on (not ignore) that history. Return JSON only."
            )
            user = f"""
Describe slide {idx} for downstream narration and planning.

CURRENT SLIDE NUMBER: {idx}
CURRENT SLIDE EXTRACTED TEXT (from PDF; may be incomplete):
{page_texts[idx - 1]}

COMPLETE PRIOR SLIDE DESCRIPTIONS (full JSON for slides 1 through {idx - 1}; empty list if this is the first slide):
{prior_json}

Return JSON with these keys:
- slide_number
- title_guess
- summary
- bullet_points
- visual_elements
- relation_to_previous
- likely_pedagogical_purpose

The field relation_to_previous must name specific ideas from prior slides when idx > 1 (not generic phrasing).
"""
            fallback = {
                "slide_number": idx,
                "title_guess": f"Slide {idx}",
                "summary": page_texts[idx - 1][:500] if page_texts[idx - 1] else f"Visual content for slide {idx}.",
                "bullet_points": [line.strip() for line in page_texts[idx - 1].splitlines()[:6] if line.strip()],
                "visual_elements": ["slide image provided to model"],
                "relation_to_previous": "N/A (first slide)" if idx == 1 else f"builds on slide {idx - 1}",
                "likely_pedagogical_purpose": "introduce or elaborate a concept",
            }
            result = self.llm.json_response(system, user, fallback, image_path=image_path)
            slides.append(result)

        payload = {"slides": slides}
        write_json(output_path, payload)
        return payload
