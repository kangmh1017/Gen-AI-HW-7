from __future__ import annotations

from .llm import LLMClient
from .utils import write_json


class PremiseAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, slide_descriptions: dict, output_path) -> dict:
        system = (
            "You synthesize the premise of THIS specific lecture from the full slide_description.json. "
            "The deck is Lecture 17 on AI-generated screenplays / long-form structured text and agentic decomposition. "
            "The thesis, scope, learning_objectives, and central_terms must name concrete topics visible in the slides "
            "(e.g. one-shot long-form limits, hierarchical planning, premise/arc/scene agents, screenplay structure). "
            "Ban vague placeholders like 'understand main concepts' unless tied to named topics from the deck. "
            "Return JSON only."
        )
        user = f"""
Infer premise.json grounded in the slide content below.

Return JSON with keys:
- thesis (string): one specific sentence about THIS lecture's argument
- scope (list of strings): major subtopics in order
- learning_objectives (list of strings): measurable outcomes tied to slide content
- audience (string)
- central_terms (list of strings): jargon or recurring terms from the deck
- instructor_strategy (string): how the instructor builds the story across slides

FULL slide_description.json:
{slide_descriptions}
"""
        fallback = {
            "thesis": (
                "Long-form AI writing (especially screenplays) fails in one-shot generation because models lose global "
                "coherence; this lecture presents a hierarchical, multi-agent pipeline (premise, arc, sequence/scene) "
                "to structure generation and keep narrative consistency."
            ),
            "scope": [
                "Limits of one-shot long-form generation and context drift",
                "Screenplay as a structured target for hierarchical decomposition",
                "Agent roles for premise, arc, and scene-level planning",
                "End-to-end flow from high-level story structure to executable script segments",
            ],
            "learning_objectives": [
                "Explain why one-shot generation struggles with long coherent documents.",
                "Describe how premise/arc/scene decomposition reduces drift in long outputs.",
                "Map the agentic pipeline stages to screenplay structure and generalize to other long documents.",
            ],
            "audience": "students learning agentic workflows for generative text",
            "central_terms": [
                "one-shot generation",
                "hierarchical planning",
                "premise agent",
                "arc agent",
                "screenplay",
                "coherence",
                "long-form",
            ],
            "instructor_strategy": (
                "Motivate the failure mode of naive long outputs, then introduce structured decomposition and "
                "walk through an agentic pipeline using screenplay generation as the running example."
            ),
        }
        result = self.llm.json_response(system, user, fallback)
        write_json(output_path, result)
        return result
