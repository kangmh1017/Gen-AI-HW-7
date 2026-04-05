from __future__ import annotations

from pathlib import Path

from .arc_agent import ArcAgent
from .audio import AudioSynthesizer
from .config import Settings
from .llm import LLMClient
from .narration_agent import NarrationAgent
from .pdf_tools import extract_page_text, rasterize_pdf
from .premise_agent import PremiseAgent
from .slide_description_agent import SlideDescriptionAgent
from .style_agent import StyleAgent
from .utils import ensure_dir, slug_from_pdf, write_json
from .video import build_video_segments, concatenate_segments


class LecturePipeline:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm = LLMClient(model=settings.model, enabled=settings.use_openai)
        self.style_agent = StyleAgent(self.llm)
        self.slide_description_agent = SlideDescriptionAgent(self.llm)
        self.premise_agent = PremiseAgent(self.llm)
        self.arc_agent = ArcAgent(self.llm)
        self.narration_agent = NarrationAgent(self.llm)
        self.audio = AudioSynthesizer(model=settings.tts_model, voice=settings.tts_voice)

    def run(self) -> Path:
        ensure_dir(self.settings.project_root)
        ensure_dir(self.settings.slide_images_dir)
        ensure_dir(self.settings.audio_dir)
        ensure_dir(self.settings.segments_dir)

        style = self.style_agent.run(self.settings.transcript_path, self.settings.repo_root / "style.json")
        image_paths = rasterize_pdf(self.settings.pdf_path, self.settings.slide_images_dir)
        page_texts = extract_page_text(self.settings.pdf_path)

        slide_descriptions = self.slide_description_agent.run(
            image_paths=image_paths,
            page_texts=page_texts,
            output_path=self.settings.project_root / "slide_description.json",
        )
        premise = self.premise_agent.run(slide_descriptions, self.settings.project_root / "premise.json")
        arc = self.arc_agent.run(premise, slide_descriptions, self.settings.project_root / "arc.json")
        narration = self.narration_agent.run(
            image_paths=image_paths,
            style=style,
            premise=premise,
            arc=arc,
            slide_descriptions=slide_descriptions,
            output_path=self.settings.project_root / "slide_description_narration.json",
        )
        self.audio.synthesize_many(narration["slides"], self.settings.audio_dir)
        segment_paths = build_video_segments(
            self.settings.ffmpeg_bin,
            image_paths,
            self.settings.audio_dir,
            self.settings.segments_dir,
        )
        output_mp4 = self.settings.project_root / f"{slug_from_pdf(self.settings.pdf_path)}.mp4"
        concatenate_segments(self.settings.ffmpeg_bin, segment_paths, output_mp4)
        return output_mp4
