from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, List

from .utils import ensure_dir

# Normalise segment size so concat -c copy works across slides
TARGET_W, TARGET_H = 1280, 720


def build_video_segments(
    ffmpeg_bin: str,
    image_paths: List[Path],
    audio_dir: Path,
    segments_dir: Path,
) -> List[Path]:
    ensure_dir(segments_dir)
    segment_paths: List[Path] = []
    vf = (
        f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:black"
    )

    for idx, image_path in enumerate(image_paths, start=1):
        audio_path = audio_dir / f"slide_{idx:03d}.mp3"
        segment_path = segments_dir / f"segment_{idx:03d}.mp4"
        # -shortest: duration follows audio (looping image is unbounded)
        cmd = [
            ffmpeg_bin,
            "-y",
            "-loglevel",
            "error",
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-pix_fmt",
            "yuv420p",
            "-shortest",
            "-movflags",
            "+faststart",
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
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        str(output_path),
    ]
    subprocess.run(cmd, check=True)
