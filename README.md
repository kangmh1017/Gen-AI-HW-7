# Agentic Video Lecture Pipeline

**Homework 7** — a multi-stage AI agent pipeline that turns **`Lecture_17_AI_screenplays.pdf`** into a single narrated `.mp4`: one still per slide, TTS audio per slide, concatenated into one video.  Narration style is derived from a real lecture transcript via the style agent.

---

## Pipeline overview

| Step | Agent / Script | Input | Output |
|------|---------------|-------|--------|
| 1 | `style_agent.py` | `lecture_transcript.txt` | `style.json` (repo root) |
| 2 | `slide_description_agent.py` | PDF → PNG per slide + all prior slide descriptions | `slide_description.json` |
| 3 | `premise_agent.py` | `slide_description.json` | `premise.json` |
| 4 | `arc_agent.py` | `premise.json` + `slide_description.json` | `arc.json` |
| 5 | `narration_agent.py` | slide image + style + premise + arc + all prior narrations | `slide_description_narration.json` |
| 6 | `audio.py` | `slide_description_narration.json` | `audio/slide_NNN.mp3` |
| 7 | `video.py` | PNGs + MP3s | `Lecture_17_AI_screenplays.mp4` |

---

## Repository layout

```
your-repo/
├── README.md
├── style.json                         # written at repo root after run
├── Lecture_17_AI_screenplays.pdf      # required at root (per assignment)
├── lecture_transcript.txt             # captions used for style.json
├── requirements.txt
├── run_lecture_pipeline.py            # single entrypoint
├── lecture_agents/
│   ├── style_agent.py
│   ├── slide_description_agent.py
│   ├── premise_agent.py
│   ├── arc_agent.py
│   ├── narration_agent.py
│   ├── audio.py
│   └── video.py
├── .gitignore
└── projects/
    └── project_YYYYMMDD_HHMMSS/
        ├── premise.json
        ├── arc.json
        ├── slide_description.json
        └── slide_description_narration.json
        # slide_images/, audio/, segments/, .mp4 → generated, not committed
```

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### API keys (`.env` — do NOT commit)

```
OPENAI_API_KEY=sk-...
```

Optional overrides:

```
OPENAI_MODEL=gpt-4.1               # must be vision-capable
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_VOICE=alloy
USE_OPENAI=1                        # set to 0 for offline placeholder mode (see below)
FFMPEG_BIN=ffmpeg                   # or full path
```

### ffmpeg

Required for video assembly and MP3 chunk merging.

```bash
brew install ffmpeg      # macOS
sudo apt install ffmpeg  # Debian/Ubuntu
```

---

## Run

```bash
python run_lecture_pipeline.py \
  --pdf Lecture_17_AI_screenplays.pdf \
  --transcript lecture_transcript.txt
```

Optional — fix the project folder name:

```bash
python run_lecture_pipeline.py \
  --pdf Lecture_17_AI_screenplays.pdf \
  --transcript lecture_transcript.txt \
  --project-name project_20260405_120000
```

The entrypoint checks that the PDF, transcript, and `ffmpeg` exist before starting.

---

## Offline / placeholder mode (`USE_OPENAI=0`)

Set `USE_OPENAI=0` (or omit `OPENAI_API_KEY`) to run the full pipeline without making real API calls:

```bash
USE_OPENAI=0 python run_lecture_pipeline.py --pdf Lecture_17_AI_screenplays.pdf --transcript lecture_transcript.txt
```

**What happens in placeholder mode:**

| File | Content |
|------|---------|
| `style.json` | Fields set to `"PLACEHOLDER — run with USE_OPENAI=1"` |
| `slide_description.json` | One stub entry per slide |
| `premise.json` / `arc.json` | Stub content |
| `slide_description_narration.json` | One stub narration per slide |
| `audio/slide_NNN.mp3` | Minimal valid MP3 file with an ID3 comment tag reading `"PLACEHOLDER AUDIO — slide N"` — **not silent audio, but clearly labelled** |
| `.mp4` | Assembled from placeholder PNGs + labelled MP3s |

> **Grader note:** The `projects/` folder in this repo contains JSON files from a **real run** with `USE_OPENAI=1`.  The placeholder mode exists only for offline CI / testing.

---

## JSON output documentation

### `style.json` (repo root)

Produced by `style_agent.py` from the real lecture transcript.

Key fields:
- **`evidence_phrases`** — 5-10 short verbatim excerpts *copied directly from the transcript* that exemplify the style.  These prove the output is transcript-grounded, not generic.
- **`_meta.transcript_word_count`** — audit trail confirming the transcript was actually read.
- **`framing_devices`**, **`transitions`**, **`rhetorical_habits`** — used directly by the narration agent prompt.

### `slide_description.json`

Produced by `slide_description_agent.py`.  Each entry includes:
- **`carryover_concepts`** — 1-3 concepts explicitly inherited from the preceding slide (proves real chaining).
- **`relation_to_previous`** — validated at generation time; must be ≥10 words and name at least one specific concept from the prior slide.  Generic strings trigger automatic retry.

### `premise.json`

Produced by `premise_agent.py`.  Key field:
- **`supporting_slides`** — maps each claim (thesis, objectives, central terms) to the specific slide numbers that ground it.

### `arc.json`

Produced by `arc_agent.py`.  Each act has:
- **`start_slide` / `end_slide`** — explicit slide range.  Acts are validated to cover slides 1–N with no gaps.
- Each transition has **`transition_reason`** referencing specific slide content.

### `slide_description_narration.json`

Produced by `narration_agent.py`.  Each entry includes:
- **`word_count`** — actual word count of narration.
- **`estimated_seconds`** — computed at 130 wpm; useful for audio/video sync budgeting.

---

## Example real-run outputs

The `projects/project_*/` folder in this repo contains JSON files from an **actual pipeline run** on `Lecture_17_AI_screenplays.pdf`.  Here is what you can verify in each file:

| File | What to check |
|------|--------------|
| `style.json` | `evidence_phrases` — short phrases that appear verbatim in `lecture_transcript.txt` |
| `slide_description.json` | `carryover_concepts` for slides 2+ are non-empty; `relation_to_previous` names a concept from the prior slide |
| `premise.json` | `supporting_slides.thesis` lists slide numbers where the central topic appears |
| `arc.json` | Acts cover all slides with no gap; `transition_reason` values mention specific content |
| `slide_description_narration.json` | `estimated_seconds` varies per slide complexity; title slide narration includes a framing device from `style.json` |

---

## Canvas / GitHub submission checklist

- [ ] Repo has `README.md`, `requirements.txt`, `Lecture_17_AI_screenplays.pdf`, all agent code.
- [ ] `projects/project_.../` contains the four JSON deliverables from a real run.
- [ ] `style.json` at repo root reflects the real transcript (check `evidence_phrases`).
- [ ] **No** PNG, MP3, MP4, or `.env` files committed (see `.gitignore`).
