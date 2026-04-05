from __future__ import annotations

from pathlib import Path
from typing import List

from .llm import LLMClient
from .utils import write_json


class NarrationAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(
        self,
        image_paths: List[Path],
        style: dict,
        premise: dict,
        arc: dict,
        slide_descriptions: dict,
        output_path: Path,
    ) -> dict:
        output_slides = []
        slide_lookup = {s["slide_number"]: s for s in slide_descriptions["slides"]}

        for idx, image_path in enumerate(image_paths, start=1):
            prior_narrations = [
                {"slide_number": s["slide_number"], "narration": s["narration"]}
                for s in output_slides
            ]
            slide_description = slide_lookup[idx]
            is_title_slide = idx == 1

            system = (
                "You are writing spoken lecture narration for one slide. Use the provided style, premise, arc, current slide image, "
                "slide description, and prior narrations. Make the narration sound natural and connected."
            )
            user = f"""
Write spoken narration for slide {idx}.

IS_TITLE_SLIDE: {is_title_slide}
STYLE:
{style}

PREMISE:
{premise}

ARC:
{arc}

CURRENT SLIDE DESCRIPTION:
{slide_description}

ALL SLIDE DESCRIPTIONS:
{slide_descriptions}

ALL PRIOR NARRATIONS:
{prior_narrations}

Requirements:
- Return JSON with keys slide_number, narration, speaking_notes.
- If this is the title slide, the speaker must introduce themselves and give a short overview of the lecture topic.
- Do not merely read bullet points. Explain them.
- Keep continuity with prior narration.
"""
            if is_title_slide:
                fallback_narration = (
                    "Hi everyone, I’m your instructor for today’s lecture. In this session, I want to introduce the main theme of the presentation, "
                    "show you how the ideas are organized, and preview the key questions we’ll work through together."
                )
            else:
                fallback_narration = (
                    f"On this slide, we build on the previous discussion by focusing on {slide_description.get('title_guess', 'the next idea')}. "
                    f"The main point here is {slide_description.get('summary', 'the slide content')}."
                )
            fallback = {
                "slide_number": idx,
                "narration": fallback_narration,
                "speaking_notes": ["Explain the slide clearly", "Connect it to the previous slide"],
            }
            result = self.llm.json_response(system, user, fallback, image_path=image_path)
            output_slides.append({**slide_description, **result})

        payload = {"slides": output_slides}
        write_json(output_path, payload)
        return payload
