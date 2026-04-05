from __future__ import annotations

from pathlib import Path
from typing import List

from .llm import LLMClient
from .utils import write_json


class SlideDescriptionAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, image_paths: List[Path], page_texts: List[str], output_path: Path) -> dict:
        slides = []
        for idx, image_path in enumerate(image_paths, start=1):
            prior_descriptions = [
                {"slide_number": s["slide_number"], "summary": s["summary"]}
                for s in slides
            ]
            system = (
                "You are describing one lecture slide at a time. Use the current slide image and the prior slide descriptions "
                "to keep the description coherent with the presentation flow. Return JSON only."
            )
            user = f"""
Describe the current slide for downstream lecture narration.

CURRENT SLIDE NUMBER: {idx}
CURRENT SLIDE OCR/TEXT:
{page_texts[idx-1]}

ALL PRIOR SLIDE DESCRIPTIONS:
{prior_descriptions}

Return JSON with these keys:
- slide_number
- title_guess
- summary
- bullet_points
- visual_elements
- relation_to_previous
- likely_pedagogical_purpose
"""
            fallback = {
                "slide_number": idx,
                "title_guess": f"Slide {idx}",
                "summary": page_texts[idx - 1][:500] if page_texts[idx - 1] else f"Visual content for slide {idx}.",
                "bullet_points": [line.strip() for line in page_texts[idx - 1].splitlines()[:6] if line.strip()],
                "visual_elements": ["slide image provided to model"],
                "relation_to_previous": "continues the lecture flow",
                "likely_pedagogical_purpose": "introduce or elaborate a concept",
            }
            result = self.llm.json_response(system, user, fallback, image_path=image_path)
            slides.append(result)

        payload = {"slides": slides}
        write_json(output_path, payload)
        return payload
