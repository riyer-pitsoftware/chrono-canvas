"""Conversational storytelling — Gemini chat with storyboard context for refinement."""

import json
import logging
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from chronocanvas.config import settings
from chronocanvas.llm.providers.gemini import GEMINI_PRICING, gemini_generate_with_timeout

logger = logging.getLogger(__name__)

CONVERSATION_SYSTEM_PROMPT = """\
You are a creative story director helping refine a visual storyboard. You can see the \
current storyboard images and understand the story structure.

When the user suggests changes, respond with one of these actions:
1. SUGGEST_EDIT: Propose a specific scene edit (user must approve)
2. SUGGEST_NEW_SCENE: Propose adding a new scene
3. DISCUSS: Just discuss the story without making changes
4. SUGGEST_REORDER: Propose reordering scenes

Always respond with valid JSON:
{
  "action": "suggest_edit" | "suggest_new_scene" | "discuss" | "suggest_reorder",
  "message": "Your conversational response to the user...",
  "scene_suggestions": [
    {
      "scene_index": 0,
      "edit_instruction": "specific edit to apply if approved",
      "reason": "why this change improves the story"
    }
  ]
}

For "discuss" action, scene_suggestions can be empty.
Be collaborative, creative, and concise."""


class ConversationSession:
    """Manages a conversation about a storyboard with Gemini."""

    def __init__(self, request_id: str, storyboard_data: dict[str, Any]):
        self.request_id = request_id
        self.storyboard_data = storyboard_data
        self.history: list[dict[str, Any]] = []
        self.client = genai.Client(api_key=settings.google_api_key)
        self.model = settings.gemini_model

    def _build_context_parts(self) -> list[types.Part]:
        """Build initial context with storyboard images and data."""
        parts: list[types.Part] = []

        panels = self.storyboard_data.get("panels", [])
        characters = self.storyboard_data.get("characters", [])

        # Add story overview
        char_names = [c.get("name", f"Character {i}") for i, c in enumerate(characters)]
        parts.append(types.Part.from_text(
            text=f"Current storyboard has {len(panels)} scenes.\n"
            f"Characters: {', '.join(char_names)}\n\n"
        ))

        # Add each scene with image
        for panel in panels:
            scene_idx = panel.get("scene_index", "?")
            desc = panel.get("description", "")
            mood = panel.get("mood", "")
            narration = panel.get("narration_text", "")

            parts.append(types.Part.from_text(
                text=f"Scene {scene_idx}: {desc}\n"
                f"Mood: {mood}\n"
                f"Narration: {narration}\n"
            ))

            # Include image if available
            image_path = panel.get("image_path", "")
            if image_path and Path(image_path).exists():
                image_bytes = Path(image_path).read_bytes()
                parts.append(types.Part.from_bytes(
                    data=image_bytes, mime_type="image/png",
                ))

        return parts

    async def send_message(self, user_message: str) -> dict[str, Any]:
        """Send a user message and get Gemini's response."""
        # Build contents with history
        contents: list[types.Content] = []

        # First message includes storyboard context
        if not self.history:
            context_parts = self._build_context_parts()
            context_parts.append(types.Part.from_text(text=f"\nUser: {user_message}"))
            contents.append(types.Content(role="user", parts=context_parts))
        else:
            # Replay history
            for entry in self.history:
                role = entry["role"]
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=entry["text"])],
                ))
            contents.append(types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_message)],
            ))

        start = time.perf_counter()
        response = await gemini_generate_with_timeout(
            self.client,
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=CONVERSATION_SYSTEM_PROMPT,
                temperature=0.7,
                max_output_tokens=1500,
                response_mime_type="application/json",
            ),
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        input_tokens = response.usage_metadata.prompt_token_count or 0
        output_tokens = response.usage_metadata.candidates_token_count or 0
        pricing = GEMINI_PRICING.get(self.model, {"input": 0, "output": 0})
        cost = input_tokens * pricing["input"] + output_tokens * pricing["output"]

        raw_text = response.text or "{}"
        json_start = raw_text.find("{")
        json_end = raw_text.rfind("}") + 1
        parsed = json.loads(raw_text[json_start:json_end]) if json_start >= 0 else {
            "action": "discuss",
            "message": raw_text,
            "scene_suggestions": [],
        }

        # Update history
        self.history.append({"role": "user", "text": user_message})
        self.history.append({"role": "model", "text": raw_text})

        return {
            "action": parsed.get("action", "discuss"),
            "message": parsed.get("message", ""),
            "scene_suggestions": parsed.get("scene_suggestions", []),
            "cost": cost,
            "duration_ms": elapsed_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }


# In-memory session store (per-request)
_sessions: dict[str, ConversationSession] = {}


def get_or_create_session(
    request_id: str,
    storyboard_data: dict[str, Any],
) -> ConversationSession:
    if request_id not in _sessions:
        _sessions[request_id] = ConversationSession(request_id, storyboard_data)
    return _sessions[request_id]


def clear_session(request_id: str) -> None:
    _sessions.pop(request_id, None)
