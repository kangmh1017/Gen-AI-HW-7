from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .llm import LLMClient
from .output_quality import (
    dedupe_opening_list,
    narration_echoes_relation_field,
    narration_too_much_bullet_overlap,
    opening_signature,
)
from .utils import write_json


def _clip(text: object, max_len: int) -> str:
    s = str(text or "").replace("\n", " ").strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _needs_narration_revision(slide_description: Dict[str, Any]):
    """Build a closure for LLMClient.json_response_with_revision."""

    def check(result: Dict[str, Any]) -> bool:
        narr = result.get("narration") or ""
        rel = slide_description.get("relation_to_previous") or ""
        bullets = slide_description.get("bullet_points") or []
        summ = slide_description.get("summary") or ""
        if narration_echoes_relation_field(narr, rel):
            return True
        if narration_too_much_bullet_overlap(narr, bullets, summ):
            return True
        low = narr.lower()
        if "this slide extends" in low or "anchored in" in low:
            return True
        return False

    return check


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
        recent_openings: List[str] = []

        for idx, image_path in enumerate(image_paths, start=1):
            prior_narrations = [
                {
                    "slide_number": s["slide_number"],
                    "narration": s["narration"],
                    "transition_out": s.get("transition_out"),
                }
                for s in output_slides
            ]
            slide_description = slide_lookup[idx]
            is_title_slide = idx == 1
            avoid = ", ".join(dedupe_opening_list(recent_openings, "")) or "(none yet)"

            system = (
                "You write spoken lecture narration for ONE slide — a human instructor teaching aloud, not essay prose. "
                "Use STYLE.speaker_profile: tone, pacing, evidence_phrases, teaching_moves, delivery_patterns, framing, transitions. "
                "Use slide fields key_concepts, what_this_slide_adds, pedagogical_role — do NOT paste relation_to_previous verbatim into narration. "
                "Paraphrase conceptual links in your own words. Do not read bullet_points as a list; explain and reorder ideas for listening. "
                "Vary sentence openings; avoid stock phrases like 'This slide shows', 'Now we will discuss', 'The main point is'. "
                "Return JSON only."
            )
            user = f"""
Slide {idx} of {total}. IS_TITLE_SLIDE: {is_title_slide}

RECENT NARRATION OPENINGS TO AVOID REPEATING (first ~7 words of prior slides): {avoid}

STYLE (style.json):
{style}

PREMISE:
{premise}

ARC:
{arc}

CURRENT SLIDE (use key_concepts, what_this_slide_adds, pedagogical_role; treat relation_to_previous as planning context only — do not quote it):
{slide_description}

PRIOR SLIDE NARRATIONS (for continuity only):
{prior_narrations}

Return JSON with keys:
- slide_number (int)
- teaching_goal (string): the ONE thing students should understand from this slide
- likely_confusion_point (string): a plausible misconception or stumble (short)
- intuitive_hook (string): a plain-language intuition or analogy (short)
- takeaway (string): what to remember before moving on (one sentence)
- target_word_count (int): approximate word count you aimed for (50–200 non-title; 45–120 title)
- narration (string): spoken script ONLY for TTS. Non-title: ~85–200 words (tighter if slide is thin). Title: ~55–115 words. Conversational.
- speaking_notes (array of strings): 2–4 brief cues for the speaker
- transition_out (string): one or two sentences toward the next slide (or closing on last slide)

Narration content (weave naturally, not as a labeled list):
1) Brief conceptual bridge from what came before (paraphrase, do not copy relation_to_previous text)
2) Why this slide matters in the lecture arc
3) Explain core ideas using key_concepts — teach, don't enumerate
4) Address likely_confusion_point or reinforce intuitive_hook in passing
5) Short forward pointer consistent with takeaway

Rules:
- Title slide: short self-intro + roadmap for the session (screenplays, long-form, agent pipeline).
- Forbidden: markdown, stage directions in brackets, quoting JSON fields verbatim, repeating the same opening pattern as recent slides.
- TTS-safe plain text.
"""
            fallback = self._fallback_block(idx, total, is_title_slide, slide_description)
            revision_prompt = (
                "The narration echoed relation_to_previous or read bullets too closely. "
                "Rewrite ONLY the spoken narration and align teaching_goal, likely_confusion_point, intuitive_hook, takeaway. "
                "Teach one central idea in conversational sentences; do not start with 'This slide' or 'On this slide'."
            )
            needs_rev = _needs_narration_revision(slide_description)
            result = self.llm.json_response_with_revision(
                system,
                user,
                fallback,
                image_path=image_path,
                revision_prompt=revision_prompt,
                needs_revision=needs_rev,
            )
            merged = {**slide_description, **result}
            narr = merged.get("narration") or ""
            recent_openings.append(opening_signature(narr))
            output_slides.append(merged)

        payload = {"slides": output_slides}
        write_json(output_path, payload)
        return payload

    def _fallback_block(self, idx: int, total: int, is_title_slide: bool, slide_description: Dict[str, Any]) -> Dict[str, Any]:
        tit = _clip(slide_description.get("title_guess"), 72)
        kc = slide_description.get("key_concepts") or []
        kc_s = _clip(", ".join(kc[:3]), 120) if kc else _clip(slide_description.get("summary"), 200)
        adds = _clip(slide_description.get("what_this_slide_adds"), 160)
        cc = slide_description.get("carryover_concepts") or []
        cref = _clip(cc[0], 50) if cc else "what we set up already"

        if is_title_slide:
            fb_narr = (
                "Hi — in this session we’re going to treat AI screenplays as a serious long-form writing problem. "
                "I’ll walk you through why one-shot generation falls apart on coherence, and how a staged, multi-agent pipeline "
                "can keep premise, arc, and scenes aligned. The goal is not just a demo: it’s a reusable pattern for any long document."
            )
            fb_bridge = (
                "Next we’ll ground the promise of long outputs in the actual failure modes you hit when you ask for a full script in one go."
            )
            goal = "Frame long-form AI writing as a planning and decomposition problem."
            confuse = "Thinking a single prompt can hold an entire movie in working memory."
            hook = "Long text is less like typing a paragraph and more like running a project with dependencies."
            take = "We’re building intuition for staged generation before we name each agent."
        else:
            shapes = idx % 5
            if shapes == 0:
                fb_narr = (
                    f"Let me connect this to {cref}. The move on this part of the deck is to pressure-test the idea that "
                    f"«{tit}» stands alone — it doesn’t; it sits in a bigger story about structure. "
                    f"In practical terms: {adds or kc_s}. "
                    f"I want you to hear the mechanism, not memorize a bullet list."
                )
            elif shapes == 1:
                fb_narr = (
                    f"If you’re tracking the arc of the lecture, this is where we tighten the screw: {tit}. "
                    f"The intuition I’d give you first is that models are locally strong but globally sloppy unless we scaffold them. "
                    f"So here’s the content in spoken form: {kc_s}. "
                    f"Hold onto that because we’ll reuse it when we wire agents together."
                )
            elif shapes == 2:
                fb_narr = (
                    f"Another way to say the same tension: we’re trying to make «{tit}» actionable. "
                    f"That means turning {kc_s} into something you could actually implement. "
                    f"I’m not going to read the slide line by line — I’m going to tell you what matters for coherence and why instructors put this block here."
                )
            elif shapes == 3:
                fb_narr = (
                    f"From here, think about what you’d *test* if you were peer-reviewing a generated screenplay. "
                    f"{tit} is basically the checklist for that review: {kc_s}. "
                    f"The through-line from earlier slides is that decomposition buys you inspectable pieces; this slide names what those pieces should contain."
                )
            else:
                fb_narr = (
                    f"So zoom in with me on {tit}. The add here is: {adds or kc_s}. "
                    f"What students often miss is that the hard part isn’t prompting once — it’s keeping later sections from drifting. "
                    f"We’ll keep returning to that as we add agents."
                )
            fb_bridge = (
                f"Next we’ll pick up the thread on slide {idx + 1}."
                if idx < total
                else "That’s the core pipeline story; we’ll close with how you’d adapt it beyond screenplays."
            )
            goal = f"Solidify «{tit}» as a meaningful step in the staged pipeline."
            confuse = "Treating each agent as isolated instead of as shared context and constraints."
            hook = "Each stage shrinks what the model must hold in mind at once."
            take = f"Remember {kc_s.split(',')[0] if kc_s else tit} as the hinge for this section."

        wcount = 95 if is_title_slide else min(190, max(80, len(fb_narr.split()) + 5))

        return {
            "slide_number": idx,
            "teaching_goal": goal,
            "likely_confusion_point": confuse,
            "intuitive_hook": hook,
            "takeaway": take,
            "target_word_count": wcount,
            "narration": fb_narr,
            "speaking_notes": [
                "Teach one idea; avoid list voice",
                "Gesture to arc / pipeline, not slide numbers",
            ],
            "transition_out": fb_bridge,
        }
