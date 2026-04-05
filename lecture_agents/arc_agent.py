from __future__ import annotations

from .llm import LLMClient
from .utils import write_json


class ArcAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, premise: dict, slide_descriptions: dict, output_path) -> dict:
        system = "You are converting a lecture premise plus slide descriptions into a structured lecture arc. Return JSON only."
        user = f"""
Create a coherent lecture arc from the materials below.
Return JSON with keys: overview, acts, transitions, ending_function.

PREMISE:
{premise}

SLIDE_DESCRIPTIONS:
{slide_descriptions}
"""
        fallback = {
            "overview": "The lecture moves from setup to development to synthesis.",
            "acts": [
                {"name": "Opening", "function": "frame the topic", "slides": []},
                {"name": "Development", "function": "explain major concepts", "slides": []},
                {"name": "Conclusion", "function": "synthesize takeaways", "slides": []},
            ],
            "transitions": ["setup -> development", "development -> conclusion"],
            "ending_function": "leave students with a clear takeaway",
        }
        result = self.llm.json_response(system, user, fallback)
        write_json(output_path, result)
        return result
