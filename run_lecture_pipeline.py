from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

from lecture_agents import LecturePipeline
from lecture_agents.config import Settings
from lecture_agents.utils import now_project_name


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a narrated video lecture from a PDF slide deck.")
    parser.add_argument("--pdf", default="Lecture_17_AI_screenplays.pdf", help="Path to the lecture PDF.")
    parser.add_argument(
        "--transcript",
        default="lecture_transcript.txt",
        help="Path to the lecture transcript/captions text file used to derive style.json.",
    )
    parser.add_argument(
        "--project-name",
        default=None,
        help="Optional project folder name under projects/. Defaults to project_YYYYMMDD_HHMMSS.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent

    try:
        from dotenv import load_dotenv

        load_dotenv(repo_root / ".env")
    except ImportError:
        pass

    project_name = args.project_name or now_project_name()
    project_root = repo_root / "projects" / project_name

    pdf_path = (repo_root / args.pdf).resolve() if not Path(args.pdf).is_absolute() else Path(args.pdf)
    transcript_path = (
        (repo_root / args.transcript).resolve() if not Path(args.transcript).is_absolute() else Path(args.transcript)
    )
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if not transcript_path.is_file():
        raise FileNotFoundError(
            f"Transcript not found: {transcript_path}. Add lecture captions or pass --transcript PATH."
        )

    settings = Settings(
        repo_root=repo_root,
        pdf_path=pdf_path,
        transcript_path=transcript_path,
        project_root=project_root,
    )

    if not shutil.which(settings.ffmpeg_bin):
        raise RuntimeError(
            f"ffmpeg not found on PATH (tried executable name: {settings.ffmpeg_bin!r}). "
            "Install ffmpeg (e.g. `brew install ffmpeg` on macOS) or set FFMPEG_BIN to the full path."
        )

    if settings.use_openai and not (os.getenv("OPENAI_API_KEY") or "").strip():
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Put it in a `.env` file next to run_lecture_pipeline.py "
            "(see README) or export it. For offline placeholder output only, set USE_OPENAI=0 "
            "(ffmpeg is still required)."
        )

    output_path = LecturePipeline(settings).run()
    print(f"Done. Final video: {output_path}")


if __name__ == "__main__":
    main()
