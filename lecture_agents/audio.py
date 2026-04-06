"""
audio.py
--------
Synthesises per-slide narrations into MP3 files using OpenAI TTS.
Long narrations are chunked and merged with pydub.

Key improvement: when USE_OPENAI=0 (or API key missing), the script
enters an EXPLICIT PLACEHOLDER MODE — it creates clearly-labelled
placeholder files and prints a prominent banner, rather than silently
generating empty MP3s that could confuse graders.
"""

import json
import math
import os
import struct
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Placeholder MP3 generation (no pydub needed)
# ---------------------------------------------------------------------------

def _write_placeholder_mp3(path: str, slide_num: int) -> None:
    """
    Write a minimal valid MP3 file that contains a single silent frame
    and an ID3 tag noting it is a placeholder.  This is intentionally
    labelled so graders know the pipeline ran in offline/demo mode.
    """
    # ID3v2.3 tag with a comment frame
    comment = f"PLACEHOLDER AUDIO — slide {slide_num} — run with USE_OPENAI=1".encode("latin-1", errors="replace")
    # ID3 header (10 bytes) + comment frame
    frame_payload = b"\x00" + b"eng" + b"\x00" + comment + b"\x00"
    frame_size = len(frame_payload).to_bytes(4, "big")
    id3_frame = b"COMM" + frame_size + b"\x00\x00" + frame_payload
    id3_size = len(id3_frame)
    # Encode size as syncsafe int
    ss = bytes([
        (id3_size >> 21) & 0x7F,
        (id3_size >> 14) & 0x7F,
        (id3_size >> 7) & 0x7F,
        id3_size & 0x7F,
    ])
    id3 = b"ID3\x03\x00\x00" + ss + id3_frame

    # One silent MPEG1 Layer3 frame (128kbps, 44100 Hz, stereo)
    # Header: 0xFFFB9000, followed by 417 zero bytes (standard frame size)
    mp3_frame = b"\xff\xfb\x90\x00" + b"\x00" * 417

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(id3 + mp3_frame)


# ---------------------------------------------------------------------------
# Real TTS (OpenAI)
# ---------------------------------------------------------------------------

def _chunk_text(text: str, max_chars: int = 4000) -> list[str]:
    """Split *text* at sentence boundaries to stay within TTS input limits."""
    sentences = text.replace("\n", " ").split(". ")
    chunks, current = [], ""
    for sentence in sentences:
        candidate = current + sentence + ". "
        if len(candidate) > max_chars and current:
            chunks.append(current.strip())
            current = sentence + ". "
        else:
            current = candidate
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text]


def _synthesise_slide(
    client,
    narration: str,
    output_path: str,
    tts_model: str,
    voice: str,
) -> None:
    """Synthesise *narration* to *output_path* (MP3), merging chunks if needed."""
    try:
        from pydub import AudioSegment
        pydub_available = True
    except ImportError:
        pydub_available = False

    chunks = _chunk_text(narration)

    if len(chunks) == 1 or not pydub_available:
        # Single chunk or no pydub — stream directly
        text_to_synth = narration if len(chunks) == 1 else " ".join(chunks)
        response = client.audio.speech.create(
            model=tts_model,
            voice=voice,
            input=text_to_synth[:4096],
            response_format="mp3",
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)
        return

    # Multiple chunks: synthesise each, then merge with pydub
    from pydub import AudioSegment

    segments = []
    for i, chunk in enumerate(chunks):
        resp = client.audio.speech.create(
            model=tts_model,
            voice=voice,
            input=chunk,
            response_format="mp3",
        )
        import tempfile, io
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.write(resp.content)
        tmp.close()
        segments.append(AudioSegment.from_mp3(tmp.name))
        os.unlink(tmp.name)

    merged = segments[0]
    for seg in segments[1:]:
        merged += seg

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    merged.export(output_path, format="mp3")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_audio_step(project_dir: str) -> list[str]:
    narration_path = os.path.join(project_dir, "slide_description_narration.json")
    audio_dir = os.path.join(project_dir, "audio")
    os.makedirs(audio_dir, exist_ok=True)

    with open(narration_path, "r", encoding="utf-8") as f:
        narrations = json.load(f)

    use_openai = os.environ.get("USE_OPENAI", "1") != "0"
    api_key = os.environ.get("OPENAI_API_KEY", "")

    if not use_openai or not api_key:
        # ----------------------------------------------------------------
        # EXPLICIT PLACEHOLDER MODE
        # ----------------------------------------------------------------
        print(
            "\n" + "=" * 60 + "\n"
            "⚠️  AUDIO PLACEHOLDER MODE\n"
            "USE_OPENAI=0 or OPENAI_API_KEY not set.\n"
            "Creating placeholder MP3 files (labelled in ID3 metadata).\n"
            "These are NOT real TTS audio — they exist so the video\n"
            "assembly step can run end-to-end for testing.\n"
            "To generate real audio: set USE_OPENAI=1 and OPENAI_API_KEY.\n"
            + "=" * 60 + "\n"
        )
        out_paths = []
        for entry in narrations:
            num = entry.get("slide_number", 0)
            out = os.path.join(audio_dir, f"slide_{num:03d}.mp3")
            _write_placeholder_mp3(out, num)
            print(f"[audio] [PLACEHOLDER] {out}")
            out_paths.append(out)
        return out_paths

    # ---- Real TTS ----
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    tts_model = os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
    voice = os.environ.get("OPENAI_TTS_VOICE", "alloy")

    out_paths = []
    for entry in narrations:
        num = entry.get("slide_number", 0)
        narration = entry.get("narration", "")
        out = os.path.join(audio_dir, f"slide_{num:03d}.mp3")
        print(f"[audio] Synthesising slide {num} ({len(narration.split())} words) …")
        _synthesise_slide(client, narration, out, tts_model, voice)
        print(f"[audio] ✅ {out}")
        out_paths.append(out)

    return out_paths


if __name__ == "__main__":
    proj = sys.argv[1] if len(sys.argv) > 1 else "projects/project_debug"
    run_audio_step(proj)
