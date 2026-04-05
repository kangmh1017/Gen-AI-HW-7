from __future__ import annotations

from pathlib import Path

from .llm import LLMClient
from .utils import write_json


class StyleAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, transcript_path: Path, output_path: Path) -> dict:
        transcript = transcript_path.read_text(encoding="utf-8")
        system = (
            "You are extracting a structured speaking-style profile from a lecture transcript. "
            "Return JSON only."
        )
        user = f"""
Read the lecture transcript below and extract a reusable style profile for narration.
Focus on tone, pacing, transitions, rhetorical habits, audience assumptions, and narration preferences.
Return JSON.

TRANSCRIPT:
{transcript[:12000]}
"""
        fallback = {
            "speaker_profile": {
                "tone": "clear, explanatory, conversational, lightly academic",
                "pacing": "moderate",
                "transitions": ["first", "next", "so", "the key point is"],
                "audience_assumption": "students following a lecture",
                "narration_preferences": {
                    "avoid_bullet_reading": True,
                    "prefer_explanation_over_verbatim_text": True,
                },
            }
        }
        result = self.llm.json_response(system, user, fallback)
        write_json(output_path, result)
        return result
