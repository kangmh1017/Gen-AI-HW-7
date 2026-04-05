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
                "You write spoken lecture narration for one slide at a time. You must match the instructor's "
                "speaking style encoded in STYLE (tone, pacing, fillers, framing_devices, transitions, rhetorical_habits). "
                "Use PREMISE and ARC for global coherence, the full slide deck descriptions for context, and "
                "PRIOR NARRATIONS so the script sounds like one continuous lecture. Return JSON only."
            )
            user = f"""
Write spoken narration for slide {idx}.

IS_TITLE_SLIDE: {is_title_slide}

STYLE (from style.json — mirror this voice in your wording and rhythm):
{style}

PREMISE:
{premise}

ARC:
{arc}

CURRENT SLIDE DESCRIPTION (this slide only):
{slide_description}

FULL slide_description.json (entire deck document):
{slide_descriptions}

ALL PRIOR SLIDE NARRATIONS (empty list on slide 1):
{prior_narrations}

Requirements:
- Return JSON with keys: slide_number, narration, speaking_notes (speaking_notes is a list of strings).
- If IS_TITLE_SLIDE is true: the speaker must introduce themselves (e.g. role/instructor identity) and give a short summary of the lecture topic and what the session will cover, in the STYLE voice.
- Otherwise: continue naturally from PRIOR NARRATIONS; do not repeat the introduction formula.
- Do not merely read bullet points aloud; explain and connect ideas.
- Keep narration suitable for text-to-speech (no stage directions, no markdown).
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
