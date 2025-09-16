import json
import re
import logging
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, ValidationError
from langchain_core.runnables import Runnable
from typing import Any, Iterable, cast
from time import sleep

class Tool(str, Enum):
    remove = "remove"
    hide = "hide"
    lower_priority = "lower_priority"
    none = "none"

class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")  # reject unknown fields
    motivation: Optional[str] = Field(default=None, max_length=400)
    tool: Tool
    id: Optional[str] = None  # must be in Allowed IDs (checked post-parse)

class RemoveDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    motivation: str | None = Field(default=None, max_length=400)
    remove_link: str | None = None

JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

def _extract_json_blob(text: str) -> str:
    m = JSON_FENCE.search(text)
    return m.group(1) if m else text

def _coerce_to_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return cast(dict[str, Any], json.loads(_extract_json_blob(raw)))
        except json.JSONDecodeError:
            # last-ditch: try to locate the first {...} span
            start = raw.find("{") 
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                return cast(dict[str, Any], json.loads(raw[start:end+1]))
    raise ValueError("LLM output not parseable as JSON object")

def run_llm_decision[T: BaseModel](
    chain: Runnable[str, dict[str, Any]],
    prompt: str,
    allowed_ids: Iterable[str],
    model: type[T],
    logger: logging.Logger,
    *,
    retry_once: bool = True,
) -> T:
    from json import JSONDecodeError

    allowed = set(allowed_ids)

    def _try_invoke() -> T:
        raw = chain.invoke(prompt)
        data = _coerce_to_dict(raw)

        try:
            parsed = model.model_validate(data)
        except ValidationError as e:
            logger.warning("Invalid LLM schema: %s", str(e)[:200])
            raise

        if hasattr(parsed, "remove_link"):
            remove_link = getattr(parsed, "remove_link")
            if remove_link is not None and remove_link not in allowed:
                logger.warning("remove_link %s not in allowed ids, coercing to None", remove_link)
                parsed.remove_link = None  

        return parsed

    try:
        return _try_invoke()
    except (ValidationError, JSONDecodeError) as e:
        if retry_once:
            logger.info("Retrying LLM decision once due to error: %s", str(e)[:200])
            return _try_invoke()
        raise