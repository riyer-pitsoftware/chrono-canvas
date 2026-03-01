# ruff: noqa: E501 — LLM prompt template contains long natural-language lines
import logging
import time

from chronocanvas.agents.state import AgentState, PromptState
from chronocanvas.config import settings
from chronocanvas.llm.base import TaskType
from chronocanvas.llm.router import get_llm_router

logger = logging.getLogger(__name__)

# ── Imagen prompt template (natural language, photorealistic focus) ───────────

IMAGEN_PROMPT_TEMPLATE = """\
You are an expert at writing image generation prompts for Google Imagen, which produces photorealistic images from natural-language descriptions.

Based on the following research, write a vivid, detailed prompt for generating a photorealistic portrait photograph of this historical figure.

Figure: {figure_name}
Historical Context: {historical_context}
Clothing: {clothing_details}
Physical Description: {physical_description}
Known Physical Traits: {notable_features}
Art Style: {art_style_reference}

Requirements:
1. Write in natural language, NOT comma-separated tags. Imagen works best with descriptive prose.
2. DO NOT use weight syntax like (feature:1.2) — Imagen ignores this.
3. Describe the person as if directing a professional portrait photographer:
   - Specify exact skin tone, texture, and micro-level skin details: visible pores, fine lines, moles, subtle facial asymmetry, and natural imperfections
   - Describe subsurface scattering: warm translucent skin with faintly visible blood vessels beneath the surface, especially around the temples, nose bridge, and under the eyes
   - Describe eye color, shape, and expression in detail — include iris detail such as radial fiber patterns, a visible limbal ring, and sharp specular highlights on the cornea
   - Describe facial bone structure, nose shape, lip shape precisely
   - Specify exact hairstyle, hair texture, hair color
   - Describe features authentic to the figure's ethnic heritage — avoid generic or Westernized features when depicting non-Western figures
   - Avoid describing perfect bilateral symmetry — natural faces have subtle asymmetry between left and right sides
4. Describe period-accurate clothing with specific fabrics, patterns, colors, and draping
5. Specify lighting setup: e.g. "Rembrandt lighting with a soft key light from the upper left, subtle fill light, and natural catchlights in the eyes"
6. Specify camera: "Shot on a 105mm portrait lens at f/2 on a medium format sensor, shallow depth of field with tack-sharp focus on the eyes, softly blurred background"
7. End with: "Professional medium format photograph, RAW quality, 8K resolution, natural skin texture, film grain"
8. Keep it under 250 words

Return ONLY the prompt text, no explanations."""

# ── SDXL prompt template (weighted tag syntax for ComfyUI/SD) ────────────────

SDXL_PROMPT_TEMPLATE = """\
You are an expert at crafting Stable Diffusion XL prompts for photorealistic historical portraits.

Based on the following research, create a detailed SDXL prompt for generating a highly realistic portrait photograph.

Figure: {figure_name}
Historical Context: {historical_context}
Clothing: {clothing_details}
Physical Description: {physical_description}
Known Physical Traits: {notable_features}
Art Style: {art_style_reference}

Requirements:
1. Use comma-separated tag style (SDXL responds best to this format)
2. Start with: "photorealistic portrait, (masterpiece:1.2), (best quality:1.2), (ultra detailed face:1.3)"
3. Describe facial features precisely: skin texture with pores, facial bone structure, eye color and shape, natural skin imperfections, subtle wrinkles
4. Include period-accurate clothing, hairstyle, and accessories with specific detail
5. Add lighting tags: Rembrandt lighting, soft key light, subtle fill light, (catchlights in eyes:1.1)
6. Add camera tags: 85mm lens, shallow depth of field, sharp focus on eyes, bokeh background
7. Add quality tags: RAW photo, 8K, DSLR, (detailed skin texture:1.2), film grain
8. Use emphasis syntax for important elements: (sharp facial features:1.2), (realistic skin:1.3)
9. Keep it under 200 words — SDXL works better with concise, weighted prompts

IMPORTANT: This is for SDXL with Juggernaut XL checkpoint which excels at photorealism. Focus on natural, imperfect human features.

Return ONLY the prompt text, no explanations."""

def _get_prompt_template() -> str:
    """Select prompt template based on configured image provider."""
    if settings.image_provider == "imagen":
        return IMAGEN_PROMPT_TEMPLATE
    return SDXL_PROMPT_TEMPLATE

NEGATIVE_PROMPT = (
    "painting, illustration, drawing, art, sketch, cartoon, anime, 3d render, "
    "cgi, digital art, plastic skin, smooth skin, airbrushed, mannequin, doll, "
    "wax figure, uncanny valley, asymmetric eyes, crossed eyes, "
    "deformed face, distorted face, bad anatomy, deformed, extra limbs, "
    "mutated hands, fused fingers, too many fingers, "
    "modern clothing, anachronistic elements, blurry, out of focus, "
    "watermark, text, logo, signature, low quality, jpeg artifacts, "
    "overexposed, underexposed, oversaturated, "
    "perfect symmetry, overly smooth skin, porcelain skin, flat lighting, "
    "beauty filter, glamour shot, stock photo, generic face"
)


async def prompt_generation_node(state: AgentState) -> AgentState:
    ext = state.get("extraction", {})
    res = state.get("research", {})
    figure_name = ext.get("figure_name", "")
    logger.info(f"Prompt generation agent: creating prompt for {figure_name}")

    response = await get_llm_router().generate_stream(
        prompt=_get_prompt_template().format(
            figure_name=figure_name,
            historical_context=res.get("historical_context", ""),
            clothing_details=res.get("clothing_details", ""),
            physical_description=res.get("physical_description", ""),
            notable_features=ext.get("notable_features", "") or "none recorded",
            art_style_reference=res.get("art_style_reference", ""),
        ),
        task_type=TaskType.PROMPT_GENERATION,
        request_id=state.get("request_id", ""),
        agent_name="prompt_generation",
        temperature=0.8,
        max_tokens=1000,
    )

    trace = state.get("agent_trace", [])
    trace.append({
        "agent": "prompt_generation",
        "timestamp": time.time(),
        "llm_cost": response.cost,
    })

    llm_calls = list(state.get("llm_calls", []))
    llm_calls.append({
        "agent": "prompt_generation",
        "timestamp": time.time(),
        "system_prompt": response.system_prompt,
        "user_prompt": response.user_prompt,
        "raw_response": response.content,
        "parsed_output": response.content.strip(),
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
        "current_agent": "prompt_generation",
        "prompt": PromptState(
            image_prompt=response.content.strip(),
            negative_prompt=NEGATIVE_PROMPT,
            style_modifiers=[res.get("art_style_reference", "oil painting")],
        ),
        "agent_trace": trace,
        "llm_calls": llm_calls,
    }
