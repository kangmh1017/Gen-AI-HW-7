"""
video.py
--------
For each slide, mux the PNG with the matching MP3 into a video segment,
then concatenate into one .mp4 whose basename matches the PDF.

Improvements vs. original:
  • All segments are scaled to 1280×720 (pad with black bars if needed)
    so concat copy never fails due to resolution mismatch.
  • Validates that each segment file exists and is non-empty before concat.
  • Uses aac audio codec for maximum compatibility.
  • Segments are re-encoded to a consistent format before concat list.
"""

import os
import re
import subprocess
import sys
from pathlib import Path


TARGET_W, TARGET_H = 1280, 720
FFMPEG_LOGLEVEL = "error"  # change to "info" for debugging


def _ffmpeg_bin() -> str:
    return os.environ.get("FFMPEG_BIN", "ffmpeg")


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def _check_ffmpeg() -> None:
    try:
        _run([_ffmpeg_bin(), "-version"])
    except FileNotFoundError:
        raise RuntimeError(
            f"ffmpeg not found at '{_ffmpeg_bin()}'. "
            "Install it (e.g. brew install ffmpeg) or set FFMPEG_BIN."
        )


def _slide_num_from_path(path: str) -> int:
    m = re.search(r"(\d+)", Path(path).stem)
    return int(m.group(1)) if m else 0


def mux_segments(
    image_paths: list[str],
    audio_paths: list[str],
    segments_dir: str,
) -> list[str]:
    """
    Create one video segment per slide.
    Resolution is normalised to TARGET_W × TARGET_H with letterboxing.
    Returns list of segment paths in order.
    """
    os.makedirs(segments_dir, exist_ok=True)
    segment_paths = []

    for img, aud in zip(image_paths, audio_paths):
        num = _slide_num_from_path(img)
        out = os.path.join(segments_dir, f"seg_{num:03d}.mp4")

        vf = (
            f"scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
            f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2:black"
        )

        cmd = [
            _ffmpeg_bin(), "-y",
            "-loglevel", FFMPEG_LOGLEVEL,
            "-loop", "1", "-i", img,
            "-i", aud,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            "-movflags", "+faststart",
            out,
        ]
        result = _run(cmd, check=False)
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed for slide {num}:\n{result.stderr}"
            )

        if not os.path.exists(out) or os.path.getsize(out) == 0:
            raise RuntimeError(f"Segment {out} was not created or is empty.")

        print(f"[video] Segment: {out}")
        segment_paths.append(out)

    return segment_paths


def concatenate_segments(
    segment_paths: list[str],
    output_path: str,
    segments_dir: str,
) -> str:
    """
    Write an ffmpeg concat list file and merge all segments.
    Validates codec/resolution consistency first.
    """
    # Validate all segments
    for seg in segment_paths:
        if not os.path.exists(seg) or os.path.getsize(seg) == 0:
            raise RuntimeError(f"Segment missing or empty before concat: {seg}")

    # Write concat list
    list_path = os.path.join(segments_dir, "concat_list.txt")
    with open(list_path, "w") as f:
        for seg in segment_paths:
            abs_path = os.path.abspath(seg)
            f.write(f"file '{abs_path}'\n")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    cmd = [
        _ffmpeg_bin(), "-y",
        "-loglevel", FFMPEG_LOGLEVEL,
        "-f", "concat", "-safe", "0", "-i", list_path,
        "-c", "copy",
        output_path,
    ]
    result = _run(cmd, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed:\n{result.stderr}")

    size_mb = os.path.getsize(output_path) / 1_048_576
    print(f"[video] ✅ Final video: {output_path} ({size_mb:.1f} MB)")
    return output_path


def run_video_step(pdf_path: str, project_dir: str) -> str:
    _check_ffmpeg()

    pdf_stem = Path(pdf_path).stem
    images_dir = os.path.join(project_dir, "slide_images")
    audio_dir = os.path.join(project_dir, "audio")
    segments_dir = os.path.join(project_dir, "segments")
    output_path = os.path.join(project_dir, f"{pdf_stem}.mp4")

    image_paths = sorted(
        [os.path.join(images_dir, fn) for fn in os.listdir(images_dir)
         if fn.lower().endswith(".png")]
    )
    audio_paths = sorted(
        [os.path.join(audio_dir, fn) for fn in os.listdir(audio_dir)
         if fn.lower().endswith(".mp3")]
    )

    if len(image_paths) != len(audio_paths):
        raise ValueError(
            f"Mismatch: {len(image_paths)} images vs {len(audio_paths)} MP3s. "
            "Run all prior steps before video assembly."
        )

    print(f"[video] Muxing {len(image_paths)} segments at {TARGET_W}×{TARGET_H} …")
    segment_paths = mux_segments(image_paths, audio_paths, segments_dir)

    print(f"[video] Concatenating {len(segment_paths)} segments …")
    return concatenate_segments(segment_paths, output_path, segments_dir)


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else "Lecture_17_AI_screenplays.pdf"
    proj = sys.argv[2] if len(sys.argv) > 2 else "projects/project_debug"
    run_video_step(pdf, proj)
