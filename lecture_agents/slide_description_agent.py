from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from .llm import LLMClient
from .output_quality import infer_title_from_page_text, is_generic_relation, looks_like_placeholder_title, repair_relation_to_previous
from .utils import write_json


def _heuristic_key_concepts(page_text: str, max_items: int = 5) -> List[str]:
    lines = [ln.strip(" •\t–-") for ln in page_text.splitlines() if ln.strip()]
    out: List[str] = []
    for line in lines[:15]:
        if len(line) < 8:
            continue
        if line.lower().startswith("slide"):
            continue
        out.append(line[:100])
        if len(out) >= max_items:
            break
    return out[:max_items]


class SlideDescriptionAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, image_paths: List[Path], page_texts: List[str], output_path: Path) -> dict:
        slides: list[dict] = []
        for idx, image_path in enumerate(image_paths, start=1):
            page_text = page_texts[idx - 1] if idx - 1 < len(page_texts) else ""
            prior_full = [dict(s) for s in slides]
            prior_json = json.dumps(prior_full, indent=2, ensure_ascii=False)
            prev: Optional[dict] = slides[-1] if slides else None

            system = (
                "You describe one lecture slide at a time with the slide image and full JSON of prior slides. "
                "Infer a REAL title from the slide (largest heading or first substantive line in extracted text). "
                "Never use the placeholder title 'Slide N'. "
                "relation_to_previous must state a CONCEPTUAL transition: what was established, what is new, why the order makes sense. "
                "Return JSON only."
            )
            user = f"""
Describe slide {idx} for downstream narration and planning.

CURRENT SLIDE NUMBER: {idx}
CURRENT SLIDE EXTRACTED TEXT (from PDF; may be incomplete):
{page_text}

COMPLETE PRIOR SLIDE DESCRIPTIONS (slides 1..{idx - 1}; [] if first slide):
{prior_json}

Return JSON with these keys:
- slide_number (int)
- title_guess (string): the slide's actual title or heading — from image + text (largest/prominent line, else first meaningful line). NOT "Slide {idx}".
- summary (string): 2–5 sentences synthesizing what the slide communicates
- bullet_points (list of strings): key visible points (short)
- visual_elements (list of strings): layout cues, diagrams, emphasis
- key_concepts (list of strings): 2–5 concrete concepts or terms THIS slide introduces or centers
- carryover_concepts (list of 1–3 strings): ideas from earlier slides this slide presupposes or extends (empty on slide 1)
- relation_to_previous (string): slide 1 exactly "N/A (first slide)". slide 2+: 2–3 sentences: what the prior slide(s) established, what this slide adds, why we need this move now. Ban generic bridges.
- pedagogical_role (string): one of: motivate_problem | define_structure | introduce_method | walkthrough_example | contrast_limitations | synthesize | preview_practice — pick closest
- what_this_slide_adds (string): what is NEW relative to prior slides (one or two sentences)
- likely_pedagogical_purpose (string): short phrase summarizing instructional intent

Banned patterns in relation_to_previous: "extends the prior discussion", "builds on slide", "continues the previous discussion", "anchored in Slide".
"""
            fb_title = infer_title_from_page_text(page_text, idx)
            fb_keys = _heuristic_key_concepts(page_text)
            fallback_relation = "N/A (first slide)"
            fallback_carry: List[str] = []
            if idx > 1 and prev:
                pk = prev.get("key_concepts") or []
                fallback_carry = pk[:2] if pk else [str(prev.get("title_guess") or "prior topic")[:80]]
                pt = prev.get("title_guess") or "the prior topic"
                fallback_relation = (
                    f"Having developed «{pt[:80]}», we now layer in {fb_title} so students see "
                    f"how the argument advances rather than repeating the same claim."
                )

            fallback = {
                "slide_number": idx,
                "title_guess": fb_title,
                "summary": page_text[:500] if page_text else f"Content for section {idx}.",
                "bullet_points": [line.strip() for line in page_text.splitlines()[:8] if line.strip()],
                "visual_elements": ["Slide layout from PDF/image"],
                "key_concepts": fb_keys or [fb_title],
                "carryover_concepts": fallback_carry,
                "relation_to_previous": fallback_relation,
                "pedagogical_role": "introduce_method",
                "what_this_slide_adds": f"Develops the thread around {fb_title} with concrete detail from the deck.",
                "likely_pedagogical_purpose": "Advance the lecture argument with new information.",
            }
            result = self.llm.json_response(system, user, fallback, image_path=image_path)
            result = self._repair_slide(idx, result, page_text, prev)
            slides.append(result)

        payload = {"slides": slides}
        write_json(output_path, payload)
        return payload

    def _repair_slide(self, idx: int, slide: dict, page_text: str, prior: Optional[dict]) -> dict:
        tg = slide.get("title_guess")
        if looks_like_placeholder_title(str(tg), idx):
            slide["title_guess"] = infer_title_from_page_text(page_text, idx)
        rel = slide.get("relation_to_previous") or ""
        if idx > 1 and (is_generic_relation(rel) or not rel.strip()):
            slide["relation_to_previous"] = repair_relation_to_previous(rel, idx, prior, slide)
        if not slide.get("key_concepts"):
            slide["key_concepts"] = _heuristic_key_concepts(page_text)
        if not slide.get("what_this_slide_adds"):
            slide["what_this_slide_adds"] = (
                f"Adds specifics under «{slide.get('title_guess', 'this topic')}» following the prior section."
            )
        if not slide.get("pedagogical_role"):
            slide["pedagogical_role"] = "introduce_method"
        if not slide.get("likely_pedagogical_purpose"):
            slide["likely_pedagogical_purpose"] = "Advance the core argument of this section."
        return slide
