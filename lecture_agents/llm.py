from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .utils import image_to_data_url

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None


class LLMClient:
    def __init__(self, model: str, enabled: bool = True):
        self.model = model
        self.enabled = enabled and bool(os.getenv("OPENAI_API_KEY")) and OpenAI is not None
        self.client = OpenAI() if self.enabled else None

    def json_response(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_hint: Dict[str, Any],
        image_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        if not self.enabled:
            return schema_hint

        content: list[dict[str, Any]] = [{"type": "input_text", "text": user_prompt}]
        if image_path is not None:
            content.append({"type": "input_image", "image_url": image_to_data_url(image_path)})

        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": content},
            ],
            text={"format": {"type": "json_object"}},
        )
        return json.loads(response.output_text)

    def text_response(self, system_prompt: str, user_prompt: str, image_path: Optional[Path] = None) -> str:
        if not self.enabled:
            return user_prompt[:1200]

        content: list[dict[str, Any]] = [{"type": "input_text", "text": user_prompt}]
        if image_path is not None:
            content.append({"type": "input_image", "image_url": image_to_data_url(image_path)})

        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                {"role": "user", "content": content},
            ],
        )
        return response.output_text.strip()
