# Agentic Video Lecture Pipeline

This repository implements a multi-stage pipeline that turns a PDF slide deck into a narrated lecture video.

## What the pipeline does

1. Reads a lecture transcript or caption file and writes `style.json` at the repo root.
2. Creates a new project folder under `projects/project_YYYYMMDD_HHMMSS/`.
3. Rasterizes the PDF into one PNG per slide under `slide_images/`.
4. Generates `slide_description.json` by sending the current slide image and all prior slide descriptions to the model for every slide.
5. Generates `premise.json` from the full slide descriptions.
6. Generates `arc.json` from `premise.json` and `slide_description.json`.
7. Generates `slide_description_narration.json` by sending the current slide image, `style.json`, `premise.json`, `arc.json`, all slide descriptions, and all prior slide narrations to the model.
8. Synthesizes slide narration to `audio/slide_001.mp3`, `audio/slide_002.mp3`, and so on.
9. Builds one video segment per slide and concatenates them into a single MP4 named after the PDF.

## Expected repository contents

Place these files in the repository root before running:

- `Lecture_17_AI_screenplays.pdf`
- `lecture_transcript.txt`

The assignment only explicitly requires the PDF to be committed. The transcript can be committed as well, or you can keep it local and pass its path with `--transcript`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### API configuration

This scaffold supports OpenAI for slide understanding and text to speech.

```bash
export OPENAI_API_KEY=YOUR_KEY_HERE
export OPENAI_MODEL=gpt-4.1
export OPENAI_TTS_MODEL=gpt-4o-mini-tts
export OPENAI_TTS_VOICE=alloy
```

If `OPENAI_API_KEY` is not set, the pipeline still runs in fallback mode. In that mode it creates heuristic JSON outputs and silent MP3 placeholders so you can test the filesystem flow.

### ffmpeg

Install `ffmpeg` and make sure it is available in your shell.

On macOS with Homebrew:

```bash
brew install ffmpeg
```

## Run

```bash
python run_lecture_pipeline.py \
  --pdf Lecture_17_AI_screenplays.pdf \
  --transcript lecture_transcript.txt
```

Optional custom project name:

```bash
python run_lecture_pipeline.py \
  --pdf Lecture_17_AI_screenplays.pdf \
  --transcript lecture_transcript.txt \
  --project-name project_20260404_153000
```

## Output structure

```text
projects/
└── project_YYYYMMDD_HHMMSS/
    ├── premise.json
    ├── arc.json
    ├── slide_description.json
    ├── slide_description_narration.json
    ├── slide_images/
    │   ├── slide_001.png
    │   └── ...
    ├── audio/
    │   ├── slide_001.mp3
    │   └── ...
    ├── segments/
    │   ├── segment_001.mp4
    │   └── ...
    └── Lecture_17_AI_screenplays.mp4
```

## Notes for grading

- Prior slide descriptions are passed into every slide-description generation step.
- Prior slide narrations are passed into every narration-generation step.
- Slide 1 is treated as a title slide and uses a specialized introduction prompt.
- Large generated media files are excluded through `.gitignore`.

## Suggested final cleanup before GitHub submission

- Put the real `Lecture_17_AI_screenplays.pdf` in the repo root.
- Add the real lecture transcript or caption file.
- Run the pipeline once so the JSON files inside a real `projects/project_.../` folder are grounded in the actual deck.
- Confirm that image, audio, and video files are not committed.
