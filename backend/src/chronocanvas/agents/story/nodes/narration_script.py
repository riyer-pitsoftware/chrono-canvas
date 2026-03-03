"""Narration script node — generates cinematic voiceover text per panel.

Uses the LLM router (same pattern as scene_decomposition) to produce short
narration scripts for each storyboard panel.  These scripts are later
synthesized into audio by the narration_audio node.

Non-fatal: if the LLM call fails, panels continue without narration text.
"""

import json
import logging
import time

from chronocanvas.agents.story.state import StoryState
from chronocanvas.llm.base import TaskType
from chronocanvas.llm.router import get_llm_router

logger = logging.getLogger(__name__)

NARRATION_SCRIPT_PROMPT = """\
You are a cinematic narrator writing voiceover scripts for a visual storyboard.

For each scene below, write a short, evocative narration (1-3 sentences) that a \
narrator would speak over the image.  The narration should:
- Complement — not repeat — the visual description
- Set mood and atmosphere through tone and word choice
- Flow naturally from one scene to the next when read in sequence
- Be concise enough to read aloud in under 15 seconds per scene

SCENES:
{scenes_json}

Output ONLY valid JSON:
{{
  "narrations": [
    {{"scene_index": 0, "narration_text": "The narration for scene 0..."}},
    {{"scene_index": 1, "narration_text": "The narration for scene 1..."}}
  ]
}}"""


async def narration_script_node(state: StoryState) -> StoryState:
    request_id = state.get("request_id", "unknown")
    panels = list(state.get("panels", []))
    logger.info(
        "Narration script: generating for %d panels [request_id=%s]",
        len(panels), request_id,
    )

    trace = list(state.get("agent_trace", []))
    llm_calls = list(state.get("llm_calls", []))

    completed_panels = [p for p in panels if p.get("status") == "completed"]
    if not completed_panels:
        logger.info("Skipping narration script: no completed panels")
        trace.append({
            "agent": "narration_script",
            "timestamp": time.time(),
            "skipped": True,
            "reason": "No completed panels",
        })
        return {
            "current_agent": "narration_script",
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }

    scenes_for_prompt = [
        {
            "scene_index": p.get("scene_index"),
            "description": p.get("description", ""),
            "characters": p.get("characters", []),
            "mood": p.get("mood", ""),
            "setting": p.get("setting", ""),
        }
        for p in completed_panels
    ]

    prompt = NARRATION_SCRIPT_PROMPT.format(
        scenes_json=json.dumps(scenes_for_prompt, indent=2),
    )

    try:
        router = get_llm_router()
        response = await router.generate(
            prompt=prompt,
            task_type=TaskType.EXTRACTION,
            temperature=0.7,
            max_tokens=2000,
            json_mode=True,
            agent_name="narration_script",
        )

        content = response.content
        json_start = content.find("{")
        json_end = content.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            raise ValueError("No JSON found in narration script response")

        parsed = json.loads(content[json_start:json_end])
        narrations = {
            n["scene_index"]: n["narration_text"]
            for n in parsed.get("narrations", [])
        }

        # Annotate panels
        for panel in panels:
            scene_idx = panel.get("scene_index")
            if scene_idx in narrations:
                panel["narration_text"] = narrations[scene_idx]

        logger.info(
            "Generated narration for %d/%d panels [request_id=%s]",
            len(narrations), len(panels), request_id,
        )

        trace.append({
            "agent": "narration_script",
            "timestamp": time.time(),
            "panels_narrated": len(narrations),
        })

        llm_calls.append({
            "agent": "narration_script",
            "timestamp": time.time(),
            "user_prompt": prompt,
            "raw_response": content[:500],
            "parsed_output": parsed,
            "provider": response.provider,
            "model": response.model,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "cost": response.cost,
            "duration_ms": response.duration_ms,
            "requested_provider": response.requested_provider,
            "fallback": response.fallback,
        })

        return {
            "current_agent": "narration_script",
            "panels": panels,
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }

    except Exception as e:
        logger.warning(
            "Narration script generation failed [request_id=%s]: %s",
            request_id, e,
        )
        trace.append({
            "agent": "narration_script",
            "timestamp": time.time(),
            "error": str(e),
        })
        # Non-fatal: continue without narration text
        return {
            "current_agent": "narration_script",
            "agent_trace": trace,
            "llm_calls": llm_calls,
        }
