# Agentic Video Lecture Pipeline

Homework 7: a **multi-stage pipeline** that turns **`Lecture_17_AI_screenplays.pdf`** (repo root) into one **narrated `.mp4`**: one still per slide, TTS audio per slide, concatenated. **Narration style** comes from a **lecture transcript/captions** file (`tone`, `pacing`, `fillers`, how the instructor **frames ideas**, etc., in `style.json`).

## What gets produced (matches assignment)

| Step | Input | Output |
|------|--------|--------|
| **Style** | Instructor transcript/captions file | **`style.json` at repository root** |
| **Project folder** | — | **`projects/project_YYYYMMDD_HHMMSS/`** (default name = current date/time) |
| **Rasterize** | PDF | **`slide_images/slide_NNN.png`** inside that project |
| **Slide descriptions** | Current slide **image** + **all prior slide descriptions** (full JSON each call) | **`slide_description.json`** |
| **Premise** | Entire **`slide_description.json`** | **`premise.json`** |
| **Arc** | **`premise.json`** + entire **`slide_description.json`** | **`arc.json`** |
| **Narration** | Current slide image + **`style.json`** + premise + arc + full slide descriptions + **all prior narrations** | **`slide_description_narration.json`** (slide fields + `narration`; **slide 1** = self-intro + lecture overview) |
| **Audio** | `narration` strings | **`audio/slide_NNN.mp3`** (chunked TTS merged per slide when text is long) |
| **Video** | Matching PNGs + MP3s | **One `.mp4`** under the project folder; **basename = PDF basename** (e.g. `Lecture_17_AI_screenplays.mp4`); segment length follows audio (`-shortest`). |

## Repository layout (grader / submission)

```text
your-repo/
├── README.md
├── style.json                    # written at repo root when you run the pipeline
├── Lecture_17_AI_screenplays.pdf # required at repo root per assignment
├── lecture_transcript.txt        # your captions/transcript (for style.json)
├── requirements.txt
├── run_lecture_pipeline.py       # entrypoint
├── lecture_agents/
├── .env                          # optional, local only — do NOT commit (see below)
└── projects/
    └── project_YYYYMMDD_HHMMSS/
        ├── premise.json
        ├── arc.json
        ├── slide_description.json
        ├── slide_description_narration.json
        ├── slide_images/         # generated; keep empty or omit from git
        ├── audio/                # generated; keep empty or omit from git
        └── Lecture_17_AI_screenplays.mp4   # generated; do not commit
```

**Do not commit** PNG, MP3, MP4, or **`.env`**. They are listed in `.gitignore`. Committing **empty** `slide_images/` and `audio/` folders (e.g. with a `.gitkeep`) is fine if your course asks for it.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### API key (`.env` recommended)

Create **`/.env`** next to `run_lecture_pipeline.py` (same folder as this README):

```bash
OPENAI_API_KEY=sk-...
```

The entrypoint loads that file automatically (`python-dotenv`). You can still use `export OPENAI_API_KEY=...` instead.

Optional:

```bash
OPENAI_MODEL=gpt-4.1              # or another vision-capable chat model
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_VOICE=alloy
USE_OPENAI=1                      # 0 = offline fallback JSON + silent MP3 (ffmpeg still required)
FFMPEG_BIN=ffmpeg               # or full path if ffmpeg is not on PATH
```

### ffmpeg

Required for **video assembly** and for **pydub** when merging MP3 chunks from TTS.

```bash
brew install ffmpeg    # macOS
```

The script checks that `ffmpeg` is available **before** starting the pipeline.

## Run

From the **repository root**:

```bash
python run_lecture_pipeline.py \
  --pdf Lecture_17_AI_screenplays.pdf \
  --transcript lecture_transcript.txt
```

Optional fixed project folder:

```bash
python run_lecture_pipeline.py \
  --pdf Lecture_17_AI_screenplays.pdf \
  --transcript lecture_transcript.txt \
  --project-name project_20260405_120000
```

The entrypoint verifies: PDF and transcript exist, `ffmpeg` is on `PATH` (or `FFMPEG_BIN`), and `OPENAI_API_KEY` is set when `USE_OPENAI=1`.

## Canvas / GitHub submission checklist

- Repo has **all code**, **`README.md`**, **`requirements.txt`**, **`Lecture_17_AI_screenplays.pdf`** at root.
- Include a **`projects/project_.../`** folder with the **four JSON deliverables** from a real run (`premise`, `arc`, `slide_description`, `slide_description_narration`).
- **`style.json`** at repo root should reflect your real transcript after you run the pipeline.
- **No** images, audio, video, or **`.env`** in the repo.
