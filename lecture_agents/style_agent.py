from __future__ import annotations

from pathlib import Path

from .llm import LLMClient
from .utils import write_json


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
            "Ground every field in evidence from the transcript (paraphrase; do not invent unrelated traits). "
            "Return JSON only."
        )
        user = f"""
Read the transcript and build a reusable style profile for generating narrated lecture audio that matches this instructor.

Use this exact JSON shape (fill every field; use empty arrays only when the transcript truly offers no examples):
{{
  "speaker_profile": {{
    "tone": "<overall voice: e.g. warm, formal, playful>",
    "pacing": "<how fast they move, pauses, density>",
    "fillers": ["<discourse fillers or hedges they use, if any>"],
    "framing_devices": ["<how they set up ideas: e.g. 'today we will', 'the key question is'>"],
    "transitions": ["<connective phrases they repeat>"],
    "rhetorical_habits": ["<patterns: rhetorical questions, analogies, signposting, etc.>"],
    "audience_assumption": "<who they seem to be talking to>",
    "narration_preferences": {{
      "avoid_bullet_reading": true,
      "prefer_explanation_over_verbatim_text": true,
      "other": "<any other preference visible in the transcript>"
    }}
  }}
}}

TRANSCRIPT (may be truncated):
{transcript[:12000]}
"""
        fallback = {
            "speaker_profile": {
                "tone": "clear, explanatory, conversational, lightly academic",
                "pacing": "moderate, with short pauses between ideas",
                "fillers": [],
                "framing_devices": ["Let's start with", "The main idea is"],
                "transitions": ["first", "next", "so", "the key point is"],
                "rhetorical_habits": ["signposting upcoming sections"],
                "audience_assumption": "students following a lecture",
                "narration_preferences": {
                    "avoid_bullet_reading": True,
                    "prefer_explanation_over_verbatim_text": True,
                    "other": "Explain concepts in plain language before jargon.",
                },
            }
        }
        result = self.llm.json_response(system, user, fallback)
        write_json(output_path, result)
        return result
