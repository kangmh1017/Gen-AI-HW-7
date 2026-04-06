from __future__ import annotations

from pathlib import Path
from typing import List

from .llm import LLMClient
from .utils import write_json


def _clip(text: object, max_len: int) -> str:
    s = str(text or "").replace("\n", " ").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


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
        total = len(image_paths)

        for idx, image_path in enumerate(image_paths, start=1):
            prior_narrations = [
                {"slide_number": s["slide_number"], "narration": s["narration"], "transition_out": s.get("transition_out")}
                for s in output_slides
            ]
            slide_description = slide_lookup[idx]
            is_title_slide = idx == 1

            system = (
                "You write spoken lecture narration for ONE slide. Output must sound like a human instructor, not a template. "
                "You MUST use STYLE.speaker_profile: mirror tone, pacing, evidence_phrases vibe, framing_devices, "
                "transitions, and fillers where natural. "
                "Use PREMISE and ARC for what this lecture is trying to accomplish. "
                "Use carryover_concepts and relation_to_previous from the current slide description to connect to prior slides. "
                "Vary sentence openings across slides — do NOT start multiple slides the same way. "
                "Do not read bullet points verbatim; paraphrase and explain. "
                "Return JSON only."
            )
            user = f"""
Slide {idx} of {total}. IS_TITLE_SLIDE: {is_title_slide}

STYLE (style.json):
{style}

PREMISE:
{premise}

ARC:
{arc}

CURRENT SLIDE (includes carryover_concepts and relation_to_previous when present):
{slide_description}

FULL slide_description.json:
{slide_descriptions}

PRIOR SLIDE NARRATIONS (with transition_out where present):
{prior_narrations}

Return JSON with keys:
- slide_number (int)
- narration (string): 80–220 words for non-title slides unless the slide is very sparse. For title: 60–120 words.
- speaking_notes (array of strings): 2–4 brief reminders for the speaker
- transition_out (string): one or two sentences that bridge toward the NEXT slide's topic (or closing thought on last slide)

Rules:
- Title slide: introduce yourself in the instructor voice and summarize what this lecture covers (AI screenplays / long-form agentic generation as in the deck).
- Non-title: explicitly connect to the immediately previous slide using prior narrations + relation_to_previous; add one new idea from THIS slide's summary/bullets explained in plain language.
- Forbidden patterns: do not use "On this slide, we build on the previous discussion by focusing on Slide K" or "The main point here is" as a stock opener.
- TTS-safe: no markdown, no bracketed stage directions.
"""
            # Varied offline fallbacks (avoid identical template every slide)
            if is_title_slide:
                fb_narr = (
                    "Hi, I’m your instructor for today’s session on AI-generated screenplays and long-form writing. "
                    "We’re going to look at why one-shot generation breaks down for long documents, and how a structured, "
                    "multi-agent pipeline can keep a screenplay coherent from premise through scenes. "
                    "By the end, you should see how to generalize this flow to other long text tasks."
                )
                fb_bridge = (
                    "Next, we’ll start from the core problem: what goes wrong when we ask a model to write a full script in one go."
                )
            else:
                shapes = idx % 4
                rel = _clip(slide_description.get("relation_to_previous"), 180)
                summ = _clip(slide_description.get("summary"), 320)
                tit = _clip(slide_description.get("title_guess"), 80)
                if shapes == 0:
                    fb_narr = (
                        f"Picking up from where we left off: {rel} "
                        f"Here I want to unpack {tit} — not by reading bullets, but by explaining why it matters for long-form coherence. "
                        f"{summ}"
                    )
                elif shapes == 1:
                    fb_narr = (
                        f"The thread from the last slide leads us to {tit}. In plain terms, {summ}"
                    )
                elif shapes == 2:
                    cc = slide_description.get("carryover_concepts") or []
                    cref = _clip(cc[0], 60) if cc else "what we just saw"
                    fb_narr = (
                        f"Another angle on the same story: {summ} "
                        f"Notice how this connects back to {cref}."
                    )
                else:
                    fb_narr = (
                        f"So if we take seriously {rel or 'that setup'}, the natural next step is to look at {tit} — {summ}"
                    )
                fb_bridge = (
                    f"That sets us up for what comes next as we move through slide {idx + 1 if idx < total else idx}."
                    if idx < total
                    else "That wraps the technical through-line; we’ll consolidate takeaways on the final slides."
                )

            fallback = {
                "slide_number": idx,
                "narration": fb_narr,
                "speaking_notes": [
                    "Explain, don’t enumerate bullets",
                    "Gesture back to prior slide in one clause",
                ],
                "transition_out": fb_bridge,
            }
            result = self.llm.json_response(system, user, fallback, image_path=image_path)
            output_slides.append({**slide_description, **result})

        payload = {"slides": output_slides}
        write_json(output_path, payload)
        return payload
