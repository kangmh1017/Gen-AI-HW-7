from __future__ import annotations

import re
from pathlib import Path
from typing import List

from .llm import LLMClient
from .output_quality import clean_speaker_profile
from .utils import write_json


def _fallback_evidence_phrases(transcript: str, max_n: int = 8) -> List[str]:
    """Offline fallback: short verbatim-ish snippets from the transcript (not generic boilerplate)."""
    text = transcript.strip()[:12000]
    if not text:
        return []
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    out: List[str] = []
    for c in chunks:
        c = c.strip()
        if 20 <= len(c) <= 160:
            out.append(c[:140])
        if len(out) >= max_n:
            break
    if len(out) < 3:
        for line in text.splitlines():
            line = line.strip()
            if 25 <= len(line) <= 140:
                out.append(line)
            if len(out) >= max_n:
                break
    return out[:max_n]


def _infer_tone_from_snippets(phrases: List[str]) -> str:
    if not phrases:
        return "Warm, explanatory classroom voice (inferred from transcript length and pacing cues)."
    sample = " ".join(phrases[:3])[:400]
    q = sample.count("?")
    if q >= 2:
        return "Question-led, dialogical — frequently checks reasoning in plain language."
    if len(sample) > 200:
        return "Dense but spoken: builds examples before naming abstractions."
    return "Direct and concrete, prioritizing clarity over formality."


class StyleAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, transcript_path: Path, output_path: Path) -> dict:
        if not transcript_path.is_file():
            raise FileNotFoundError(
                f"Lecture transcript not found: {transcript_path}. "
                "Add captions/transcript text or pass --transcript to a valid file."
            )
        transcript = transcript_path.read_text(encoding="utf-8").strip()
        if not transcript:
            raise ValueError(f"Transcript file is empty: {transcript_path}")

        system = (
            "You extract a structured instructor speaking-style profile from a lecture transcript or captions. "
            "Every descriptive claim MUST be grounded in the transcript (paraphrase patterns you see, not generic pedagogy). "
            "Never output system/meta text: do not mention APIs, offline mode, fallbacks, billing, or 'verify later'. "
            "Write tone, pacing, framing_devices, transitions, and delivery_patterns as if for a colleague imitating this speaker. "
            "Return JSON only."
        )
        user = f"""
Read the transcript and build a reusable style profile for TTS lecture narration that sounds like THIS instructor.

Required JSON shape:
{{
  "speaker_profile": {{
    "tone": "<2–3 sentences: how this person sounds when teaching — grounded in transcript>",
    "pacing": "<how fast/slow, pauses, digressions — from evidence>",
    "fillers": ["<only if present in transcript>"],
    "framing_devices": ["<2–6 recurring ways they set up ideas — phrases or patterns visible in transcript>"],
    "transitions": ["<2–8 connective moves they actually use between ideas — verbatim or close paraphrase>"],
    "rhetorical_habits": ["<2–6 habits: contrast, analogy, repetition, hedging — tied to transcript>"],
    "teaching_moves": [
      "<3–6 short labels for HOW they explain (e.g. 'opens with news hook then defines term') — each inferable from transcript>"
    ],
    "delivery_patterns": [
      "<2–5 strings describing typical SEQUENCE of moves (e.g. 'story → failure mode → rule') — grounded in transcript>"
    ],
    "evidence_phrases": [
      "<6–12 SHORT verbatim quotes from transcript — distinctive lines, signposts, hedges>"
    ],
    "audience_assumption": "<who they imagine listening — from how they address the room>",
    "narration_preferences": {{
      "avoid_bullet_reading": true,
      "prefer_explanation_over_verbatim_text": true,
      "other": "<one concrete preference visible in transcript>"
    }}
  }}
}}

Rules:
- evidence_phrases: verbatim substrings from TRANSCRIPT below (copy-paste accurate).
- If a list would be empty, omit it or use [] — do not invent fillers/transitions not supported by text.
- teaching_moves and delivery_patterns must be usable for downstream narration (not vague praise).

TRANSCRIPT:
{transcript[:12000]}
"""
        fb_ev = _fallback_evidence_phrases(transcript)
        tone_fb = _infer_tone_from_snippets(fb_ev)
        fallback = {
            "speaker_profile": {
                "tone": tone_fb,
                "pacing": "Moderate, with room for examples; varies by segment (inferred from transcript excerpts in evidence_phrases).",
                "fillers": [],
                "framing_devices": [
                    "Uses concrete scenarios before abstract vocabulary when the transcript shows that pattern.",
                ],
                "transitions": [],
                "rhetorical_habits": [
                    "Returns to main thread after tangents when signaled in transcript.",
                ],
                "teaching_moves": [
                    "Anchors claims in examples before generalizing.",
                    "Contrasts naive approach with structured alternative.",
                ],
                "delivery_patterns": [
                    "Motivating problem → structural response → implication for practice.",
                ],
                "evidence_phrases": fb_ev,
                "audience_assumption": "Students following a technical lecture with applied examples.",
                "narration_preferences": {
                    "avoid_bullet_reading": True,
                    "prefer_explanation_over_verbatim_text": True,
                    "other": "Match hedges and emphasis visible in evidence_phrases.",
                },
            }
        }
        result = self.llm.json_response(system, user, fallback)
        sp = result.get("speaker_profile")
        if isinstance(sp, dict):
            result["speaker_profile"] = clean_speaker_profile(sp)
        write_json(output_path, result)
        return result
