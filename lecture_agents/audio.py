from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Iterable, List

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

from pydub import AudioSegment

from .utils import ensure_dir

_MAX_TTS_CHARS = 3800


def _split_text_for_tts(text: str, max_chars: int) -> List[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    parts = re.split(r"(?<=[.!?])\s+", text)
    chunks: List[str] = []
    buf: List[str] = []
    n = 0
    for p in parts:
        if not p:
            continue
        add = len(p) if not buf else len(p) + 1
        if n + add <= max_chars:
            buf.append(p)
            n += add
            continue
        if buf:
            chunks.append(" ".join(buf))
            buf = []
            n = 0
        if len(p) <= max_chars:
            buf = [p]
            n = len(p)
        else:
            for i in range(0, len(p), max_chars):
                chunks.append(p[i : i + max_chars])
    if buf:
        chunks.append(" ".join(buf))
    return chunks


def _trim_trailing_silence(segment: AudioSegment, chunk_ms: int = 200, silence_thresh_db: float = -45.0) -> AudioSegment:
    if len(segment) <= chunk_ms:
        return segment
    out = segment
    while len(out) > chunk_ms:
        tail = out[-chunk_ms:]
        if tail.dBFS > silence_thresh_db:
            break
        out = out[:-chunk_ms]
    return out


def _tts_quota_error(exc: Exception) -> bool:
    code = getattr(exc, "status_code", None)
    if code == 429:
        return True
    msg = str(exc).lower()
    return "429" in msg or "insufficient_quota" in msg or "rate limit" in msg


def _write_placeholder_mp3(path: Path, slide_num: int) -> None:
    """Minimal valid MP3 when TTS is off (labelled so graders know it is not real speech)."""
    comment = f"PLACEHOLDER AUDIO — slide {slide_num} — set USE_OPENAI=1 for TTS".encode("latin-1", errors="replace")
    frame_payload = b"\x00" + b"eng" + b"\x00" + comment + b"\x00"
    frame_size = len(frame_payload).to_bytes(4, "big")
    id3_frame = b"COMM" + frame_size + b"\x00\x00" + frame_payload
    id3_size = len(id3_frame)
    ss = bytes(
        [
            (id3_size >> 21) & 0x7F,
            (id3_size >> 14) & 0x7F,
            (id3_size >> 7) & 0x7F,
            id3_size & 0x7F,
        ]
    )
    id3 = b"ID3\x03\x00\x00" + ss + id3_frame
    mp3_frame = b"\xff\xfb\x90\x00" + b"\x00" * 417
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(id3 + mp3_frame)


class AudioSynthesizer:
    def __init__(self, model: str, voice: str):
        self.model = model
        self.voice = voice
        self.enabled = bool(os.getenv("OPENAI_API_KEY")) and OpenAI is not None and os.getenv("USE_OPENAI", "1") == "1"
        self.client = OpenAI() if self.enabled else None

    def _silent_mp3(self, out_path: Path, duration_ms: int = 2500) -> None:
        AudioSegment.silent(duration=duration_ms).export(out_path, format="mp3")

    def _synthesize_chunks_merged(self, text: str, out_path: Path) -> None:
        pieces = _split_text_for_tts(text, _MAX_TTS_CHARS)
        if not pieces:
            self._silent_mp3(out_path, duration_ms=500)
            return

        combined = AudioSegment.empty()
        for chunk in pieces:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                with self.client.audio.speech.with_streaming_response.create(
                    model=self.model,
                    voice=self.voice,
                    input=chunk,
                ) as response:
                    response.stream_to_file(tmp_path)
                combined += AudioSegment.from_mp3(str(tmp_path))
            finally:
                tmp_path.unlink(missing_ok=True)

        combined = _trim_trailing_silence(combined)
        combined.export(out_path, format="mp3")

    def synthesize_many(self, slides: Iterable[dict], output_dir: Path) -> None:
        ensure_dir(output_dir)
        for slide in slides:
            out_path = output_dir / f"slide_{slide['slide_number']:03d}.mp3"
            text = (slide.get("narration") or "").strip()
            if not self.enabled:
                if not text:
                    self._silent_mp3(out_path)
                else:
                    _write_placeholder_mp3(out_path, int(slide["slide_number"]))
                continue
            try:
                self._synthesize_chunks_merged(text, out_path)
            except Exception as e:
                if os.getenv("OPENAI_FALLBACK_ON_ERROR", "1") == "1" and _tts_quota_error(e):
                    print(
                        f"WARNING: TTS failed for slide {slide['slide_number']} ({e!s}); writing placeholder MP3.",
                        file=sys.stderr,
                    )
                    _write_placeholder_mp3(out_path, int(slide["slide_number"]))
                else:
                    raise
