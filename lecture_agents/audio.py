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
                self._silent_mp3(out_path, duration_ms=2500)
                continue
            try:
                self._synthesize_chunks_merged(text, out_path)
            except Exception as e:
                if os.getenv("OPENAI_FALLBACK_ON_ERROR", "1") == "1" and _tts_quota_error(e):
                    print(
                        f"WARNING: TTS failed for slide {slide['slide_number']} ({e!s}); writing silent MP3 for mux.",
                        file=sys.stderr,
                    )
                    self._silent_mp3(out_path, duration_ms=2500)
                else:
                    raise
