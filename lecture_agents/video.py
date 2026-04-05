from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, List

from .utils import ensure_dir


def build_video_segments(
    ffmpeg_bin: str,
    image_paths: List[Path],
    audio_dir: Path,
    segments_dir: Path,
) -> List[Path]:
    ensure_dir(segments_dir)
    segment_paths: List[Path] = []

    for idx, image_path in enumerate(image_paths, start=1):
        audio_path = audio_dir / f"slide_{idx:03d}.mp3"
        segment_path = segments_dir / f"segment_{idx:03d}.mp4"
        # -shortest ends when the shorter stream finishes; looping video is unbounded, so segment length tracks audio.
        cmd = [
            ffmpeg_bin,
            "-y",
            "-loop", "1",
            "-i", str(image_path),
            "-i", str(audio_path),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            str(segment_path),
        ]
        subprocess.run(cmd, check=True)
        segment_paths.append(segment_path)

    return segment_paths


def concatenate_segments(ffmpeg_bin: str, segment_paths: Iterable[Path], output_path: Path) -> None:
    concat_file = output_path.parent / "concat.txt"
    lines = [f"file '{path.resolve()}'" for path in segment_paths]
    concat_file.write_text("\n".join(lines), encoding="utf-8")

    cmd = [
        ffmpeg_bin,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(output_path),
    ]
    subprocess.run(cmd, check=True)
