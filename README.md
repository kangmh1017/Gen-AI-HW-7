# Agentic Video Lecture Pipeline

Homework 7: **`Lecture_17_AI_screenplays.pdf`** → per-slide PNGs → agent JSON → TTS → one **`.mp4`**. Style comes from **`lecture_transcript.txt`** (grounded **`style.json`** at repo root).

## Pipeline steps

| Step | Output |
|------|--------|
| Style | **`style.json`** — `speaker_profile` includes **`evidence_phrases`** (verbatim quotes from the transcript; no generic filler unless it appears in the transcript) |
| Slide descriptions | **`slide_description.json`** — **`carryover_concepts`**, **`relation_to_previous`** (concrete chaining; not “builds on slide N” alone) |
| Premise | **`premise.json`** — thesis / scope / learning objectives **grounded in this deck** (long-form generation, screenplay structure, agent pipeline) |
| Arc | **`arc.json`** — **`acts[]`** each with **`start_slide`**, **`end_slide`**, **`function`**, **`summary`**, **`slide_numbers`** (non-empty) |
| Narration | **`slide_description_narration.json`** — per slide: **`narration`**, **`speaking_notes`**, **`transition_out`** (bridge to next slide); merged with slide fields |
| Audio / video | **`audio/slide_NNN.mp3`**, final **`Lecture_17_AI_screenplays.mp4`** (gitignored media) |

## Ground truth vs offline mode

- **`USE_OPENAI=1`** (default) + valid **`OPENAI_API_KEY`**: models fill the JSON fields above from images + transcript + chaining. **Re-run after code changes** and commit updated JSON so the repo matches the prompts.
- **`USE_OPENAI=0`**: heuristic **fallbacks** run (no API). Outputs are **structurally valid** but **not** graded as full “agentic” quality — use only to test ffmpeg/path wiring.

### Quota / 429 errors

If the API returns **429 (insufficient quota)**, the pipeline **does not stop by default**: each agent step uses its **schema fallback**, and TTS writes **placeholder MP3s** so video assembly can still finish. You will see **`WARNING:`** lines on stderr. Set **`OPENAI_FALLBACK_ON_ERROR=0`** if you prefer the run to **exit immediately** on API errors instead.

## Repo layout

```text
├── run_lecture_pipeline.py
├── lecture_agents/
├── .env                 # local only, gitignored
├── style.json           # overwritten on each run (commit after a real API run)
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

### Avoid `cd` / copy-paste mistakes

Do **not** use placeholder paths like `cd ".../agentic_video_lecture_pipeline"` — use the real folder path, or run the helper (from the repo root):

```bash
chmod +x run_full_pipeline.sh   # once
./run_full_pipeline.sh --pdf Lecture_17_AI_screenplays.pdf --transcript lecture_transcript.txt --project-name project_api_run
```

The script `cd`s to its own directory, uses `.venv/bin/python` if present, and prepends common **ffmpeg** locations to `PATH` when needed.

## Submission checklist

- [ ] Code + README + requirements + PDF in repo  
- [ ] At least one **`projects/project_.../`** with the four JSON files from an **API** run  
- [ ] **`style.json`** reflects **`lecture_transcript.txt`** (includes **`evidence_phrases`** when using the current `style_agent`)  
- [ ] No large media or `.env` in git  

## Included run: `projects/project_hw7_final/`

This repo includes a **full end-to-end run** (rasterize → agents → silent MP3 placeholders → concatenated MP4).  
If OpenAI returned **quota errors** on your machine, the committed JSONs match **`USE_OPENAI=0`** fallbacks: structure and transcript-based **`evidence_phrases`** in **`style.json`** are still present; chat/vision/TTS steps use **heuristic fallbacks**. **Re-run with billing enabled** and commit again for maximum rubric credit on narration and slide descriptions.
