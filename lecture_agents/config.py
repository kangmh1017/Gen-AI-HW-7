from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    repo_root: Path
    pdf_path: Path
    transcript_path: Path
    project_root: Path
    model: str = os.getenv("OPENAI_MODEL", "gpt-4.1")
    tts_model: str = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
    tts_voice: str = os.getenv("OPENAI_TTS_VOICE", "alloy")
    use_openai: bool = os.getenv("USE_OPENAI", "1") == "1"
    ffmpeg_bin: str = os.getenv("FFMPEG_BIN", "ffmpeg")

    @property
    def slide_images_dir(self) -> Path:
        return self.project_root / "slide_images"

    @property
    def audio_dir(self) -> Path:
        return self.project_root / "audio"

    @property
    def segments_dir(self) -> Path:
        return self.project_root / "segments"
