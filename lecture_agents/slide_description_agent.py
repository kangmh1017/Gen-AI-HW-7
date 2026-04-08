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
                "You describe one lecture slide at a time with the slide image and the full JSON of all prior slides. "
                "Chain ideas conceptually: why would an instructor put THIS slide immediately after what came before? "
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
- carryover_concepts (list of 1–3 strings): the specific concepts or tensions from earlier slides that THIS slide is answering, tightening, or pivoting from (empty on slide 1). Name ideas, not slide numbers alone.
- relation_to_previous (string): Slide 1: exactly "N/A (first slide)". Slide 2+: 1–2 tight sentences on *why this slide appears now* in the argument — e.g. after establishing limitation X, this introduces structure Y; or now that we named concept A, we need mechanism B. Use carryover_concepts explicitly by name. No filler bridges.
- likely_pedagogical_purpose (string)

Banned in relation_to_previous: "continues the previous discussion", "builds on slide N", "this slide follows from the last one" without naming a concrete conceptual move.
"""
            prev = slides[-1] if slides else None
            prev_title = (prev or {}).get("title_guess", "")
            prev_sum = ((prev or {}).get("summary") or "")[:200]
            fallback_relation = "N/A (first slide)"
            fallback_carry: List[str] = []
            if idx > 1 and prev:
                fallback_carry = [prev_title] if prev_title else []
                fallback_relation = (
                    f"After laying out «{prev_title}», this slide is the next conceptual beat: "
                    f"it presses on {prev_sum[:120]}… rather than repeating the same point."
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
