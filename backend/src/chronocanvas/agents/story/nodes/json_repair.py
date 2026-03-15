"""Shared JSON extraction and repair for LLM responses.

Handles markdown fences, trailing commas, unescaped control chars,
single-quoted strings, unquoted keys, truncated output, and other
common LLM quirks.  Gemini 2.5 Flash thinking tokens consume the
max_output_tokens budget, frequently truncating JSON before the
closing brace — strategy 8 (truncation repair) recovers these.
"""

import json
import logging
import re

try:
    import json5 as _json5
except ImportError:
    _json5 = None

logger = logging.getLogger(__name__)


def extract_and_parse_json(text: str) -> dict:
    """Extract and parse JSON from LLM output with aggressive repair.

    Raises ValueError if no valid JSON can be recovered.
    """
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?```\s*$", "", text, flags=re.MULTILINE)

    # Extract JSON object
    json_start = text.find("{")
    json_end = text.rfind("}") + 1
    if json_start == -1 or json_end <= json_start:
        # No closing brace at all — try truncation repair directly
        if json_start >= 0:
            json_text = text[json_start:]
            logger.warning("No closing brace found — attempting truncation repair")
            return _truncation_repair(json_text)
        raise ValueError("No JSON object found in response")

    json_text = text[json_start:json_end]

    # Try parsing as-is first (fast path)
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        pass

    # --- Progressive repair ---

    # 1. Fix trailing commas before } or ]
    repaired = re.sub(r",\s*([}\]])", r"\1", json_text)

    # 2. Escape unescaped control chars inside string values
    chars = []
    in_str = False
    esc = False
    for ch in repaired:
        if esc:
            chars.append(ch)
            esc = False
            continue
        if ch == "\\":
            chars.append(ch)
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            chars.append(ch)
            continue
        if in_str and ch in "\n\r\t":
            chars.append({"\n": "\\n", "\r": "\\r", "\t": "\\t"}[ch])
            continue
        chars.append(ch)
    repaired = "".join(chars)

    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # 3. Replace single quotes with double quotes (outside existing double-quoted strings)
    sq_fixed = re.sub(r"(?<![\\])'", '"', json_text)
    sq_fixed = re.sub(r",\s*([}\]])", r"\1", sq_fixed)
    try:
        return json.loads(sq_fixed)
    except json.JSONDecodeError:
        pass

    # 4. Quote bare keys: {key: "value"} → {"key": "value"}
    bare_key_fixed = re.sub(
        r'(?<=[{,])\s*([a-zA-Z_]\w*)\s*:', r' "\1":', repaired
    )
    try:
        return json.loads(bare_key_fixed)
    except json.JSONDecodeError:
        pass

    # 5. json5 fallback (if available)
    if _json5 is not None:
        try:
            return _json5.loads(json_text)
        except Exception:
            pass
        try:
            return _json5.loads(repaired)
        except Exception:
            pass

    # 6. Fix unescaped double quotes inside string values
    quote_fixed = repaired
    for _ in range(80):
        try:
            return json.loads(quote_fixed)
        except json.JSONDecodeError as qe:
            pos = qe.pos
            if pos is None or pos >= len(quote_fixed):
                break
            found = False
            search_start = min(pos, len(quote_fixed) - 1)
            for i in range(search_start, 0, -1):
                if quote_fixed[i] != '"':
                    continue
                num_backslashes = 0
                j = i - 1
                while j >= 0 and quote_fixed[j] == '\\':
                    num_backslashes += 1
                    j -= 1
                if num_backslashes % 2 == 1:
                    continue
                after_quote = quote_fixed[i + 1:].lstrip()
                if after_quote and after_quote[0] in ':,]}':
                    continue
                quote_fixed = quote_fixed[:i] + '\\"' + quote_fixed[i + 1:]
                found = True
                break
            if not found:
                break

    # 7. Last resort: strip all control chars inside strings and retry
    last_resort = re.sub(r'[\x00-\x1f]', ' ', json_text)
    last_resort = re.sub(r",\s*([}\]])", r"\1", last_resort)
    try:
        return json.loads(last_resort)
    except json.JSONDecodeError:
        pass

    # 8. Truncation repair
    return _truncation_repair(last_resort)


def _truncation_repair(text: str) -> dict:
    """Close any open brackets/braces from truncated JSON output."""
    open_stack = []
    in_s = False
    esc = False
    for ch in text:
        if esc:
            esc = False
            continue
        if ch == '\\':
            esc = True
            continue
        if ch == '"':
            in_s = not in_s
            continue
        if in_s:
            continue
        if ch in '{[':
            open_stack.append('}' if ch == '{' else ']')
        elif ch in '}]' and open_stack:
            open_stack.pop()
    if open_stack:
        repaired = text
        if in_s:
            repaired += '"'
        repaired += ''.join(reversed(open_stack))
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"JSON repair failed after all strategies. "
        f"First 300 chars: {text[:300]}"
    )
