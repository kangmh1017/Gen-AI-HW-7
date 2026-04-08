from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

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

    @staticmethod
    def _api_quota_exhausted(exc: BaseException) -> bool:
        code = getattr(exc, "status_code", None)
        if code == 429:
            return True
        resp = getattr(exc, "response", None)
        if resp is not None and getattr(resp, "status_code", None) == 429:
            return True
        if "RateLimit" in type(exc).__name__:
            return True
        msg = str(exc).lower()
        if "429" in msg or "insufficient_quota" in msg or "rate limit" in msg:
            return True
        return False

    def _fallback_on_api_error(self) -> bool:
        return os.getenv("OPENAI_FALLBACK_ON_ERROR", "1") == "1"

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

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": self._user_content(user_prompt, image_path)},
                ],
                response_format={"type": "json_object"},
            )
            return self._parse_json_object(self._message_content(response))
        except Exception as e:
            if self._fallback_on_api_error() and self._api_quota_exhausted(e):
                print(
                    "WARNING: OpenAI returned 429 / quota. Using local fallback for this step. "
                    "Add billing or set USE_OPENAI=0. Set OPENAI_FALLBACK_ON_ERROR=0 to fail fast instead.",
                    file=sys.stderr,
                )
                return schema_hint
            raise

    def json_response_with_revision(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_hint: Dict[str, Any],
        image_path: Optional[Path] = None,
        revision_prompt: Optional[str] = None,
        needs_revision: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> Dict[str, Any]:
        """One follow-up JSON call if needs_revision(first_parse) is True (API only)."""
        first = self.json_response(system_prompt, user_prompt, schema_hint, image_path=image_path)
        if not self.enabled or needs_revision is None or revision_prompt is None:
            return first
        if not needs_revision(first):
            return first
        follow = (
            user_prompt
            + "\n\n---\nREVISION (required):\n"
            + revision_prompt
            + "\nReturn a single JSON object with the SAME keys as before; fix only what was wrong."
        )
        return self.json_response(system_prompt, follow, first, image_path=image_path)

    def text_response(self, system_prompt: str, user_prompt: str, image_path: Optional[Path] = None) -> str:
        if not self.enabled:
            return user_prompt[:1200]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": self._user_content(user_prompt, image_path)},
                ],
            )
            return self._message_content(response).strip()
        except Exception as e:
            if self._fallback_on_api_error() and self._api_quota_exhausted(e):
                print(
                    "WARNING: OpenAI returned 429 / quota. Using truncated prompt as fallback.",
                    file=sys.stderr,
                )
                return user_prompt[:1200]
            raise
