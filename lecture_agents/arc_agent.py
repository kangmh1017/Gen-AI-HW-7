from __future__ import annotations

from typing import Any, Dict, List

from .llm import LLMClient
from .utils import write_json


def _fallback_acts(num_slides: int) -> List[Dict[str, Any]]:
    """Partition slides into acts with non-empty slide_numbers (offline heuristic)."""
    if num_slides < 1:
        return []
    triple = [
        ("Problem: long-form generation limits", "Why one-shot writing drifts and loses coherence."),
        ("Design: hierarchical screenplay / agent pipeline", "Premise, arc, and scene-level agents for structured output."),
        ("Synthesis: end-to-end flow and takeaways", "How the pieces connect and generalize beyond screenplays."),
    ]
    if num_slides == 1:
        segs = [(1, 1)]
        labels = [("Full lecture arc", "Covers the deck from start to finish.")]
    elif num_slides == 2:
        segs = [(1, 1), (2, 2)]
        labels = [triple[0], triple[2]]
    elif num_slides <= 5:
        mid = num_slides // 2
        segs = [(1, mid), (mid + 1, num_slides)]
        labels = [triple[0], triple[2]]
    else:
        p1 = max(1, num_slides // 3)
        p2 = max(p1 + 1, (2 * num_slides) // 3)
        segs = [(1, p1), (p1 + 1, p2), (p2 + 1, num_slides)]
        labels = triple
    acts: List[Dict[str, Any]] = []
    for i, (start, end) in enumerate(segs):
        if start > end:
            continue
        name, summ = labels[i] if i < len(labels) else (f"Act {i + 1}", "Section of the lecture.")
        slide_numbers = list(range(start, end + 1))
        acts.append(
            {
                "name": name,
                "start_slide": start,
                "end_slide": end,
                "function": "Frame and develop ideas in this section of the deck.",
                "summary": summ,
                "slide_numbers": slide_numbers,
            }
        )
    return acts


class ArcAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, premise: dict, slide_descriptions: dict, output_path) -> dict:
        slides = slide_descriptions.get("slides") or []
        n = len(slides)

        system = (
            "You build arc.json for THIS lecture from premise.json plus the full slide_description.json. "
            "Acts must be lecture-specific (not generic Opening/Development/Conclusion). "
            "Every act MUST include start_slide, end_slide, function, summary, and slide_numbers (non-empty list). "
            "Overview and transitions must reference actual slide themes. Return JSON only."
        )
        user = f"""
Create a coherent lecture arc. Slide count: {n}.

Return JSON with keys:
- overview (string): 2–4 sentences grounded in this deck's topics
- acts (array): each object MUST have:
    - name (string)
    - start_slide (int)
    - end_slide (int)
    - function (string): what this section accomplishes pedagogically
    - summary (string): what happens across these slides
    - slide_numbers (array of int): every slide index from start_slide to end_slide inclusive
- transitions (array of strings): each explains WHY the narrative moves from one act to the next (content-based)
- ending_function (string): what the last section leaves the student with

PREMISE:
{premise}

FULL slide_description.json:
{slide_descriptions}
"""
        acts_fb = _fallback_acts(n)
        trans_fb: List[str] = []
        if len(acts_fb) >= 2:
            trans_fb = [
                f"From “{acts_fb[i]['name']}” to “{acts_fb[i + 1]['name']}”: "
                f"the deck moves from {acts_fb[i]['summary'][:80]}… to {acts_fb[i + 1]['summary'][:80]}…"
                for i in range(len(acts_fb) - 1)
            ]
        elif len(acts_fb) == 1:
            trans_fb = ["Single contiguous section; no act-to-act transition in this stub partition."]
        fallback = {
            "overview": (
                "The deck moves from the failure mode of naive long-form generation to a structured, multi-stage "
                "agent design for screenplays, closing with how that pipeline generalizes."
            ),
            "acts": acts_fb,
            "transitions": trans_fb,
            "ending_function": "Students should see long-form generation as a planning problem solvable with staged agents.",
        }
        if n == 0:
            fallback["acts"] = []
            fallback["transitions"] = []
        result = self.llm.json_response(system, user, fallback)
        write_json(output_path, result)
        return result
