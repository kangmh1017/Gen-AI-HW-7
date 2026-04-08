from __future__ import annotations

from .llm import LLMClient
from .utils import write_json


class PremiseAgent:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, slide_descriptions: dict, output_path) -> dict:
        slides = slide_descriptions.get("slides") or []
        n = len(slides)
        supporting_default = list(range(1, n + 1)) if n else []

        system = (
            "You synthesize the premise of THIS specific lecture from slide_description.json (titles, key_concepts, summaries). "
            "The deck is Lecture 17 on AI-generated screenplays, long-form structured text, and agentic decomposition. "
            "The thesis, scope, learning_objectives, central_terms, supporting_slides, why_this_matters, and pedagogical_focus "
            "must name concrete topics visible in the slides (one-shot limits, hierarchical planning, premise/arc/sequence/scene agents, coherence). "
            "Ban vague placeholders like 'understand main concepts' unless tied to named topics from the deck. "
            "Return JSON only."
        )
        user = f"""
Infer premise.json grounded in the slide content below.

Return JSON with keys:
- thesis (string): one specific sentence about THIS lecture's argument
- scope (list of strings): major subtopics in lecture order
- learning_objectives (list of strings): measurable outcomes tied to slide content
- audience (string)
- central_terms (list of strings): jargon or recurring terms from the deck
- instructor_strategy (string): how the instructor builds the story across slides
- supporting_slides (list of int): slide numbers whose titles/concepts best support the thesis and learning objectives (cite real slide indices 1..N)
- why_this_matters (string): 2–3 sentences on why this lecture matters conceptually (long-form failure modes, planning, agent design) — not generic motivation
- pedagogical_focus (string): what kind of understanding students should leave with (e.g. diagnose drift, map pipeline stages, transfer to other documents)

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
                "Agent roles for premise, arc, sequence, and scene-level planning",
                "End-to-end flow and generalization to other long documents",
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
            "supporting_slides": supporting_default,
            "why_this_matters": (
                "Without staged planning, long generative outputs drift and contradict themselves; treating screenplays "
                "as hierarchical artifacts makes automation tractable and transfers to books, reports, and other long forms."
            ),
            "pedagogical_focus": (
                "Students should be able to justify multi-stage agent design from coherence requirements, not merely list tool names."
            ),
        }
        result = self.llm.json_response(system, user, fallback)
        if not result.get("supporting_slides") and supporting_default:
            result["supporting_slides"] = supporting_default
        write_json(output_path, result)
        return result
