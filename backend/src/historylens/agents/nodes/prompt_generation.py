import logging
import time

from historylens.agents.state import AgentState
from historylens.llm.base import TaskType
from historylens.llm.router import llm_router

logger = logging.getLogger(__name__)

PROMPT_GEN_TEMPLATE = """You are an expert at crafting Stable Diffusion XL prompts for photorealistic historical portraits.

Based on the following research, create a detailed SDXL prompt for generating a highly realistic portrait photograph.

Figure: {figure_name}
Historical Context: {historical_context}
Clothing: {clothing_details}
Physical Description: {physical_description}
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

NEGATIVE_PROMPT = (
    "painting, illustration, drawing, art, sketch, cartoon, anime, 3d render, "
    "cgi, digital art, plastic skin, smooth skin, airbrushed, mannequin, doll, "
    "wax figure, uncanny valley, asymmetric eyes, crossed eyes, "
    "deformed face, distorted face, bad anatomy, deformed, extra limbs, "
    "mutated hands, fused fingers, too many fingers, "
    "modern clothing, anachronistic elements, blurry, out of focus, "
    "watermark, text, logo, signature, low quality, jpeg artifacts, "
    "overexposed, underexposed, oversaturated"
)


async def prompt_generation_node(state: AgentState) -> AgentState:
    logger.info(f"Prompt generation agent: creating prompt for {state.get('figure_name', '')}")

    response = await llm_router.generate(
        prompt=PROMPT_GEN_TEMPLATE.format(
            figure_name=state.get("figure_name", ""),
            historical_context=state.get("historical_context", ""),
            clothing_details=state.get("clothing_details", ""),
            physical_description=state.get("physical_description", ""),
            art_style_reference=state.get("art_style_reference", ""),
        ),
        task_type=TaskType.PROMPT_GENERATION,
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
    })

    return {
        **state,
        "current_agent": "prompt_generation",
        "image_prompt": response.content.strip(),
        "negative_prompt": NEGATIVE_PROMPT,
        "style_modifiers": [state.get("art_style_reference", "oil painting")],
        "agent_trace": trace,
        "llm_calls": llm_calls,
    }
