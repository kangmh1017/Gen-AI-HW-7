from __future__ import annotations

from typing import Any, Dict, List

from .llm import LLMClient
from .utils import write_json


def _fallback_acts(num_slides: int) -> List[Dict[str, Any]]:
    """Partition slides into acts with non-empty slide_numbers (offline heuristic)."""
    if num_slides < 1:
        return []
    triple = [
        (
            "Problem: long-form generation limits",
            "Why one-shot writing drifts and loses coherence.",
            "Students need a crisp failure mode before any architectural fix.",
        ),
        (
            "Design: hierarchical screenplay / agent pipeline",
            "Premise, arc, and scene-level agents for structured output.",
            "Once the problem is credible, the lecture introduces the decomposition that addresses it.",
        ),
        (
            "Synthesis: end-to-end flow and takeaways",
            "How the pieces connect and generalize beyond screenplays.",
            "The closing ties mechanism back to transferable document design.",
        ),
    ]
    if num_slides == 1:
        segs = [(1, 1)]
        labels = [("Full lecture arc", "Covers the deck from start to finish.", "Single-slide overview of the arc.")]
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
        name, summ, why = labels[i] if i < len(labels) else (f"Act {i + 1}", "Section of the lecture.", "Pedagogical beat.")
        slide_numbers = list(range(start, end + 1))
        acts.append(
            {
                "name": name,
                "start_slide": start,
                "end_slide": end,
                "function": "Frame and develop ideas in this section of the deck.",
                "summary": summ,
                "why_this_section_exists": why,
                "slide_numbers": slide_numbers,
            }
        )
    return acts


def _normalize_transitions(result: Dict[str, Any]) -> Dict[str, Any]:
    acts = result.get("acts") or []
    trans = result.get("transitions")
    if not trans or not acts:
        return result
    names = [a.get("name") or f"Act {i + 1}" for i, a in enumerate(acts)]
    if isinstance(trans, list) and trans and isinstance(trans[0], str):
        out: List[Dict[str, Any]] = []
        for i, reason in enumerate(trans):
            if i + 1 >= len(names):
                break
            out.append(
                {
                    "from_act": names[i],
                    "to_act": names[i + 1],
                    "transition_reason": reason,
                    "pedagogical_logic": reason,
                }
            )
        result["transitions"] = out
    return result


class ArcAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, premise: dict, slide_descriptions: dict, output_path) -> dict:
        slides = slide_descriptions.get("slides") or []
        n = len(slides)

        system = (
            "You build arc.json for THIS lecture from premise.json plus slide_description.json. "
            "Acts must be lecture-specific (not generic Opening/Development/Conclusion). "
            "Every act MUST include name, start_slide, end_slide, function, summary, why_this_section_exists, slide_numbers (non-empty). "
            "transitions MUST be an array of OBJECTS (not plain strings): each object links two adjacent acts and explains why the lecture must move between them. "
            "Return JSON only."
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
    - why_this_section_exists (string): why this block belongs in the lecture at this point (problem framing / structural response / synthesis / practice)
    - slide_numbers (array of int): every slide index from start_slide to end_slide inclusive
- transitions (array of objects): one object per boundary between consecutive acts, each with:
    - from_act (string): name of earlier act
    - to_act (string): name of next act
    - transition_reason (string): what changes in the argument or student understanding
    - pedagogical_logic (string): why this order beats alternatives (e.g. must feel pain of one-shot before seeing pipeline)
- ending_function (string): what the last section leaves the student with

PREMISE:
{premise}

FULL slide_description.json:
{slide_descriptions}
"""
        acts_fb = _fallback_acts(n)
        trans_fb: List[Dict[str, Any]] = []
        names = [a["name"] for a in acts_fb]
        for i in range(len(names) - 1):
            trans_fb.append(
                {
                    "from_act": names[i],
                    "to_act": names[i + 1],
                    "transition_reason": (
                        f"The deck shifts from {names[i]} to {names[i + 1]} so students do not accept tooling before "
                        f"they accept the coherence problem it solves."
                    ),
                    "pedagogical_logic": "Problem motivation must precede architectural prescription.",
                }
            )
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
        result = _normalize_transitions(result)
        write_json(output_path, result)
        return result
