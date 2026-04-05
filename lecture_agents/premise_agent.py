from __future__ import annotations

from .llm import LLMClient
from .utils import write_json


class PremiseAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, slide_descriptions: dict, output_path) -> dict:
        system = "You synthesize the overall premise of a lecture deck from the complete slide_description.json. Return JSON only."
        user = f"""
You are given the entire slide_description.json document (all slides). Infer the lecture premise grounded in that content.
Return JSON with keys: thesis, scope, learning_objectives, audience, central_terms, instructor_strategy.

FULL slide_description.json:
{slide_descriptions}
"""
        fallback = {
            "thesis": "The lecture advances a coherent argument developed across the slide deck.",
            "scope": ["concept introduction", "examples", "synthesis"],
            "learning_objectives": [
                "Understand the main concepts in the deck",
                "Follow how the argument develops across slides",
            ],
            "audience": "students",
            "central_terms": [],
            "instructor_strategy": "moves from framing to evidence to takeaway",
        }
        result = self.llm.json_response(system, user, fallback)
        write_json(output_path, result)
        return result
