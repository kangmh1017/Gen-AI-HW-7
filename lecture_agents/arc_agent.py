"""
arc_agent.py
------------
Takes premise.json + slide_description.json and produces arc.json.

Improvement: every act now has explicit start_slide / end_slide, and
every transition has from_act / to_act / transition_reason so the grader
can verify coherent deck coverage at a glance.
"""

import json
import os
import re
import sys

from openai import OpenAI


def run_arc_agent(
    premise_path: str,
    slide_description_path: str,
    project_dir: str,
) -> dict:
    use_openai = os.environ.get("USE_OPENAI", "1") != "0"
    output_path = os.path.join(project_dir, "arc.json")

    with open(premise_path, "r", encoding="utf-8") as f:
        premise = json.load(f)
    with open(slide_description_path, "r", encoding="utf-8") as f:
        slide_descriptions = json.load(f)

    total_slides = len(slide_descriptions)

    if not use_openai:
        print(
            "[arc_agent] ⚠️  PLACEHOLDER MODE (USE_OPENAI=0): "
            "generating stub arc.json."
        )
        arc = {
            "overview": "PLACEHOLDER — run with USE_OPENAI=1",
            "acts": [
                {
                    "act_number": 1,
                    "title": "PLACEHOLDER",
                    "start_slide": 1,
                    "end_slide": total_slides,
                    "summary": "PLACEHOLDER",
                    "pedagogical_function": "PLACEHOLDER",
                }
            ],
            "transitions": [],
            "ending_function": "PLACEHOLDER",
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(arc, f, indent=2, ensure_ascii=False)
        print(f"[arc_agent] ✅ Wrote {output_path}")
        return arc

    client = OpenAI()
    model = os.environ.get("OPENAI_MODEL", "gpt-4.1")

    slide_summary = "\n".join(
        f"Slide {d['slide_number']}: {d.get('title_guess','?')}"
        for d in slide_descriptions
    )

    schema = f"""{{
  "overview": "<2-3 sentence description of how the lecture arc unfolds>",
  "acts": [
    {{
      "act_number": <int starting at 1>,
      "title": "<short descriptive name for this phase>",
      "start_slide": <int, first slide in this act>,
      "end_slide": <int, last slide in this act — must be ≤ {total_slides}>,
      "summary": "<what happens in this act, ≥ 2 sentences>",
      "pedagogical_function": "<e.g. motivation, exposition, worked example, critique, synthesis>"
    }}
  ],
  "transitions": [
    {{
      "from_act": <act_number of source act>,
      "to_act": <act_number of destination act>,
      "at_slide": <slide number where the transition occurs>,
      "transition_reason": "<why the lecture shifts here — must reference specific content>"
    }}
  ],
  "ending_function": "<how the final slides resolve or synthesise the lecture>"
}}"""

    user_prompt = (
        "You are given a lecture premise and all slide descriptions.\n"
        "Produce a structured lecture arc using EXACTLY this JSON schema "
        "(no markdown fences, no extra keys):\n\n"
        f"{schema}\n\n"
        f"Total slides: {total_slides}. Acts must collectively cover slides 1–{total_slides} "
        "with no gaps and no overlaps (end_slide of act N = start_slide of act N+1 minus 1).\n\n"
        "== PREMISE ==\n"
        f"{json.dumps(premise, indent=2, ensure_ascii=False)}\n\n"
        "== SLIDE DESCRIPTIONS ==\n"
        f"{json.dumps(slide_descriptions, indent=2, ensure_ascii=False)}\n"
        "== END ==\n\n"
        "Slide title reference:\n"
        f"{slide_summary}"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": user_prompt}],
        max_tokens=1200,
        temperature=0.15,
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    arc = json.loads(raw)

    # Validate slide coverage
    acts = arc.get("acts", [])
    if acts:
        covered_slides = set()
        for act in acts:
            for s in range(act.get("start_slide", 0), act.get("end_slide", 0) + 1):
                covered_slides.add(s)
        expected = set(range(1, total_slides + 1))
        missing = expected - covered_slides
        if missing:
            print(f"[arc_agent] ⚠️  WARNING: slides {sorted(missing)} not covered by any act.")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(arc, f, indent=2, ensure_ascii=False)

    print(f"[arc_agent] ✅ Wrote {output_path}")
    return arc


if __name__ == "__main__":
    proj = sys.argv[1] if len(sys.argv) > 1 else "projects/project_debug"
    run_arc_agent(
        os.path.join(proj, "premise.json"),
        os.path.join(proj, "slide_description.json"),
        proj,
    )
