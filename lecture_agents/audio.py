from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

from pydub import AudioSegment

from .utils import ensure_dir


class AudioSynthesizer:
    def __init__(self, model: str, voice: str):
        self.model = model
        self.voice = voice
        self.enabled = bool(os.getenv("OPENAI_API_KEY")) and OpenAI is not None and os.getenv("USE_OPENAI", "1") == "1"
        self.client = OpenAI() if self.enabled else None

    def _silent_mp3(self, out_path: Path, duration_ms: int = 2500) -> None:
        AudioSegment.silent(duration=duration_ms).export(out_path, format="mp3")

    def synthesize_many(self, slides: Iterable[dict], output_dir: Path) -> None:
        ensure_dir(output_dir)
        for slide in slides:
            out_path = output_dir / f"slide_{slide['slide_number']:03d}.mp3"
            text = slide["narration"]
            if not self.enabled:
                self._silent_mp3(out_path)
                continue

            with self.client.audio.speech.with_streaming_response.create(
                model=self.model,
                voice=self.voice,
                input=text,
            ) as response:
                response.stream_to_file(out_path)
