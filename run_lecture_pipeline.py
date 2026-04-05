from __future__ import annotations

import argparse
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
    project_name = args.project_name or now_project_name()
    project_root = repo_root / "projects" / project_name

    settings = Settings(
        repo_root=repo_root,
        pdf_path=(repo_root / args.pdf).resolve() if not Path(args.pdf).is_absolute() else Path(args.pdf),
        transcript_path=(repo_root / args.transcript).resolve() if not Path(args.transcript).is_absolute() else Path(args.transcript),
        project_root=project_root,
    )

    output_path = LecturePipeline(settings).run()
    print(f"Done. Final video: {output_path}")


if __name__ == "__main__":
    main()
