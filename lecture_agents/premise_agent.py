"""
premise_agent.py
----------------
Takes slide_description.json as input and writes premise.json.

Improvement: every high-level claim in the premise now includes
`supporting_slides` — a list of slide numbers from the deck that
justify that claim.  This makes the grounding auditable.
"""

import json
import os
import re
import sys

from openai import OpenAI


def run_premise_agent(
    slide_description_path: str,
    project_dir: str,
) -> dict:
    use_openai = os.environ.get("USE_OPENAI", "1") != "0"
    output_path = os.path.join(project_dir, "premise.json")

    with open(slide_description_path, "r", encoding="utf-8") as f:
        slide_descriptions = json.load(f)

    if not use_openai:
        print(
            "[premise_agent] ⚠️  PLACEHOLDER MODE (USE_OPENAI=0): "
            "generating stub premise.json."
        )
        premise = {
            "thesis": "PLACEHOLDER — run with USE_OPENAI=1",
            "scope": "PLACEHOLDER",
            "learning_objectives": ["PLACEHOLDER"],
            "audience": "PLACEHOLDER",
            "central_terms": ["PLACEHOLDER"],
            "instructor_strategy": "PLACEHOLDER",
            "supporting_slides": {},
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(premise, f, indent=2, ensure_ascii=False)
        print(f"[premise_agent] ✅ Wrote {output_path}")
        return premise

    client = OpenAI()
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1")

    # Build a compact slide summary to keep tokens reasonable
    slide_summary = "\n".join(
        f"Slide {d['slide_number']}: {d.get('title_guess','?')} — "
        + "; ".join(d.get("key_points", [])[:3])
        for d in slide_descriptions
    )

    schema = """{
  "thesis": "<one sentence: the central argument or topic of this lecture>",
  "scope": "<what is and is NOT covered, ≥ 2 sentences>",
  "learning_objectives": [
    "<objective 1 — cite supporting slide numbers in parentheses, e.g. '...  (slides 3, 4)'>",
    "<objective 2  (slides ...)>",
    "..."
  ],
  "audience": "<assumed background knowledge and who this is for>",
  "central_terms": ["<key term 1>", "<key term 2>", "..."],
  "instructor_strategy": "<how the instructor structures the argument across the deck>",
  "supporting_slides": {
    "thesis": [<slide numbers that most directly support the thesis>],
    "learning_objective_1": [<slide numbers>],
    "learning_objective_2": [<slide numbers>],
    "central_terms": [<slide numbers where key terms are introduced/defined>]
  }
}"""

    user_prompt = (
        "You are given descriptions of every slide in a lecture deck.\n"
        "Produce a structured lecture premise using EXACTLY this JSON schema "
        "(no markdown fences, no extra keys):\n\n"
        f"{schema}\n\n"
        "The supporting_slides values must be real slide numbers from the list.\n\n"
        "== SLIDE DESCRIPTIONS ==\n"
        f"{json.dumps(slide_descriptions, indent=2, ensure_ascii=False)}\n"
        "== END ==\n\n"
        "Quick reference — slide titles:\n"
        f"{slide_summary}"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": user_prompt}],
        max_tokens=1000,
        temperature=0.15,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    premise = json.loads(raw)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(premise, f, indent=2, ensure_ascii=False)

    print(f"[premise_agent] ✅ Wrote {output_path}")
    return premise


if __name__ == "__main__":
    proj = sys.argv[1] if len(sys.argv) > 1 else "projects/project_debug"
    desc_path = os.path.join(proj, "slide_description.json")
    run_premise_agent(desc_path, proj)
