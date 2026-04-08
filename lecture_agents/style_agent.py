from __future__ import annotations

import re
from pathlib import Path
from typing import List

from .llm import LLMClient
from .utils import write_json


def _fallback_evidence_phrases(transcript: str, max_n: int = 8) -> List[str]:
    """Offline fallback: short verbatim-ish snippets from the transcript (not generic boilerplate)."""
    text = transcript.strip()[:12000]
    if not text:
        return []
    # Prefer clause- or sentence-sized chunks the instructor might repeat
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
            "Every claim must be grounded in the transcript. "
            "Do NOT fill transitions/framing/fillers with generic lecture boilerplate (e.g. 'first', 'next', "
            "'the main idea is') unless those exact or clearly equivalent phrases appear in the transcript. "
            "Return JSON only."
        )
        user = f"""
Read the transcript and build a reusable style profile for TTS lecture narration that sounds like THIS instructor.

Required JSON shape:
{{
  "speaker_profile": {{
    "tone": "<from transcript evidence>",
    "pacing": "<from transcript evidence>",
    "fillers": ["<only if present in transcript>"],
    "framing_devices": ["<recurring ways they set up ideas — must appear in transcript>"],
    "transitions": ["<recurring connective phrases actually used — no generic filler if absent>"],
    "rhetorical_habits": ["<patterns visible in transcript>"],
    "teaching_moves": [
      "<2–5 short labels for HOW they explain: e.g. gives a concrete story before the rule; flags a caveat before a recommendation; restates the contrast after a dense section — each must be inferable from the transcript, not generic pedagogy>"
    ],
    "evidence_phrases": [
      "<5–10 SHORT verbatim quotes copied exactly from the transcript below — distinctive phrases, signposts, hedges>"
    ],
    "audience_assumption": "<who they address>",
    "narration_preferences": {{
      "avoid_bullet_reading": true,
      "prefer_explanation_over_verbatim_text": true,
      "other": "<visible preference from transcript>"
    }}
  }}
}}

Rules for evidence_phrases:
- Verbatim substrings from TRANSCRIPT (short lines or clauses, not whole paragraphs).
- Must be copy-paste accurate (same spelling/casing as in transcript).
- If you cannot find 5, include as many as exist (minimum 3 if the transcript is long enough).

TRANSCRIPT:
{transcript[:12000]}
"""
        fb_ev = _fallback_evidence_phrases(transcript)
        fallback = {
            "speaker_profile": {
                "tone": "Use transcript evidence when API is available; offline mode uses excerpt-based fallbacks.",
                "pacing": "See transcript for rhythm; offline fallback cannot infer pacing reliably.",
                "fillers": [],
                "framing_devices": [],
                "transitions": [],
                "rhetorical_habits": ["signposting and informal asides (verify against transcript when online)"],
                "teaching_moves": [
                    "Uses informal asides and news-style examples to motivate ideas before formal framing (verify when online).",
                ],
                "evidence_phrases": fb_ev,
                "audience_assumption": "students in a live class session",
                "narration_preferences": {
                    "avoid_bullet_reading": True,
                    "prefer_explanation_over_verbatim_text": True,
                    "other": "Re-run with OPENAI and billing enabled for transcript-grounded style.",
                },
            }
        }
        result = self.llm.json_response(system, user, fallback)
        write_json(output_path, result)
        return result
