# Agentic Video Lecture Pipeline

Homework 7: **`Lecture_17_AI_screenplays.pdf`** → per-slide PNGs → multi-agent JSON → TTS → one **`.mp4`**. Style is distilled from **`lecture_transcript.txt`** into **`style.json`** (repo root). Each project folder under **`projects/`** holds slide-level JSON and generated media.

## What each agent does

| Agent | Role | Main outputs |
|-------|------|----------------|
| **Style** | Reads the transcript; builds a **speaker profile** usable for narration (tone, pacing, evidence-backed phrases, **teaching_moves**, **delivery_patterns**). | **`style.json`** |
| **Slide description** | Vision + PDF text per slide; **chains** to prior slides. Infers real **titles** (not `Slide N`), **key_concepts**, **pedagogical_role**, **what_this_slide_adds**, and a **conceptual** `relation_to_previous`. | **`slide_description.json`** |
| **Premise** | Lecture-specific thesis, scope, objectives, **supporting_slides**, **why_this_matters**, **pedagogical_focus**. | **`premise.json`** |
| **Arc** | Act structure with **why_this_section_exists** per act; **transitions** as structured objects (from/to act, reason, pedagogical logic). | **`arc.json`** |
| **Narration** | Per-slide **spoken script** plus **teaching_goal**, **likely_confusion_point**, **intuitive_hook**, **takeaway**, **target_word_count**; avoids quoting `relation_to_previous` or reading bullets verbatim; optional **one API revision** if output looks templated. | **`slide_description_narration.json`** |

### Why chaining matters

Downstream narration depends on **carryover concepts**, **what_this_slide_adds**, and **key_concepts** — not on generic “slide 2 follows slide 1” text. The slide agent is prompted and **post-processed** to reject templated bridges; the narration agent is instructed to **paraphrase** links and **teach** rather than restate JSON.

### What makes narration more lecture-like

- Central **teaching goal** and **takeaway** per slide.
- Explicit **confusion point** and **intuitive hook** where useful.
- **Anti-repetition**: recent opening signatures are passed in the prompt.
- **Validation + revision**: if narration echoes `relation_to_previous` or copies too many bullet fragments, a second JSON generation pass runs (API only).

## Pipeline steps (outputs)

| Step | Output |
|------|--------|
| Style | **`style.json`** — `speaker_profile` with **evidence_phrases**, **teaching_moves**, **delivery_patterns**, etc. |
| Slide descriptions | **`slide_description.json`** — **title_guess**, **key_concepts**, **relation_to_previous**, **pedagogical_role**, **what_this_slide_adds** |
| Premise | **`premise.json`** — thesis, scope, objectives, **supporting_slides**, **why_this_matters**, **pedagogical_focus** |
| Arc | **`arc.json`** — **acts** (with **why_this_section_exists**), **transitions** (objects), **ending_function** |
| Narration | **`slide_description_narration.json`** — merged slide fields + **narration** + teaching metadata |
| Audio / video | **`audio/slide_NNN.mp3`**, final **`Lecture_17_AI_screenplays.mp4`** (gitignored media) |

## Strengths

- **Transcript-grounded style** when the API succeeds (verbatim **evidence_phrases**).
- **Structured slide understanding** (concepts, role, what’s new vs prior).
- **Premise and arc** tied to deck content and slide indices.
- **Narration** optimized for spoken explanation, not bullet echo.

## Known limitations

- **Vision/OCR** quality depends on PDF rasterization and extracted text; incomplete text makes titles and concepts noisier.
- **429 / quota**: with default **`OPENAI_FALLBACK_ON_ERROR=1`**, agents fall back to **heuristic JSON** so ffmpeg can still run; those outputs are **not** representative of full agentic quality.
- **Second narration pass** only runs when the first pass fails lightweight checks (extra API cost per slide when triggered).

## Ground truth vs offline mode

- **`USE_OPENAI=1`** (default) + valid **`OPENAI_API_KEY`**: models fill JSON from images + transcript. **Re-run after code changes** and commit updated JSON when you want graders to see the new behavior.
- **`USE_OPENAI=0`**: heuristic **fallbacks** (no API). Use only to test wiring.

### Quota / 429 errors

If the API returns **429**, the pipeline **continues by default** with per-step fallbacks and **WARNING** logs unless **`OPENAI_FALLBACK_ON_ERROR=0`** (fail fast).

## Repo layout

```text
├── run_lecture_pipeline.py
├── lecture_agents/
├── .env                 # local only, gitignored
├── style.json           # overwritten on each run
├── lecture_transcript.txt
├── Lecture_17_AI_screenplays.pdf
├── requirements.txt
└── projects/project_YYYYMMDD_HHMMSS/
        ├── premise.json
        ├── arc.json
        ├── slide_description.json
        └── slide_description_narration.json
```

Do **not** commit PNG, MP3, MP4, or `.env`.

## Setup & run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# brew install ffmpeg   # required for audio/video steps
```

```bash
python run_lecture_pipeline.py \
  --pdf Lecture_17_AI_screenplays.pdf \
  --transcript lecture_transcript.txt
```

### Helper script

```bash
chmod +x run_full_pipeline.sh   # once
./run_full_pipeline.sh --pdf Lecture_17_AI_screenplays.pdf --transcript lecture_transcript.txt --project-name project_api_run
```

## Submission checklist

- [ ] Code + README + requirements + PDF in repo  
- [ ] At least one **`projects/project_.../`** with JSON from an **API** run when possible  
- [ ] **`style.json`** reflects **`lecture_transcript.txt`**  
- [ ] No large media or `.env` in git  

## Included run: `projects/project_hw7_final/`

This repo may include a sample project folder. If OpenAI returned **quota errors** during a run, committed JSONs may mix **API** and **fallback** content; **re-run with billing enabled** for best rubric alignment.

Due to API quota limitations during the final run, some outputs may reflect fallback behavior. However, the updated prompts, validation, and agent logic for improved narration and conceptual transitions are implemented in the codebase.
