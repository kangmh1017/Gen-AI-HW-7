from __future__ import annotations

from .llm import LLMClient
from .utils import write_json


class ArcAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, premise: dict, slide_descriptions: dict, output_path) -> dict:
        system = (
            "You convert premise.json plus the full slide_description.json into a structured lecture arc. "
            "The arc must be consistent with the premise and with how ideas build across the slide list. Return JSON only."
        )
        user = f"""
Create a coherent lecture arc from the materials below.
Return JSON with keys: overview, acts, transitions, ending_function.
Use slide numbers in acts where helpful.

PREMISE (premise.json):
{premise}

FULL slide_description.json:
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
