from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .utils import image_to_data_url

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None

UserContent = Union[str, List[Dict[str, Any]]]


class LLMClient:
    def __init__(self, model: str, enabled: bool = True):
        self.model = model
        self.enabled = enabled and bool(os.getenv("OPENAI_API_KEY")) and OpenAI is not None
        self.client = OpenAI() if self.enabled else None

    def _user_content(self, user_prompt: str, image_path: Optional[Path] = None) -> UserContent:
        if image_path is None:
            return user_prompt
        return [
            {"type": "text", "text": user_prompt},
            {
                "type": "image_url",
                "image_url": {"url": image_to_data_url(image_path)},
            },
        ]

    def _message_content(self, response: Any) -> str:
        text = response.choices[0].message.content
        if text is None:
            raise ValueError("LLM returned no message content")
        return text

    @staticmethod
    def _parse_json_object(raw: str) -> Dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return json.loads(text)

    def json_response(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_hint: Dict[str, Any],
        image_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        if not self.enabled:
            return schema_hint

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": self._user_content(user_prompt, image_path)},
            ],
            response_format={"type": "json_object"},
        )
        return self._parse_json_object(self._message_content(response))

    def text_response(self, system_prompt: str, user_prompt: str, image_path: Optional[Path] = None) -> str:
        if not self.enabled:
            return user_prompt[:1200]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": self._user_content(user_prompt, image_path)},
            ],
        )
        return self._message_content(response).strip()
