import json
import re
import logging
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, ValidationError
from langchain_core.runnables import Runnable
from typing import Any, Iterable, cast
from json import JSONDecodeError


class Tool(str, Enum):
    remove = "remove"
    hide = "hide"
    lower_priority = "lower_priority"
    none = "none"

class TopicCategory(str, Enum):
    MACRO_DRIVER = "macro_driver"
    ASSET = "asset"
    POLICY = "policy"
    GEOGRAPHY = "geography"
    COMPANY = "company"
    INDUSTRY_VERTICAL = "industry_vertical"
    AMBIGUOUS = "ambiguous"
    NONE = "none"

class CategoryName(str, Enum):
    MACRO_EVENT = "macro_event"
    EARNINGS = "earnings"
    REGULATION = "regulation"
    POLICY_STATEMENT = "policy_statement"
    CENTRAL_BANK_ACTION = "central_bank_action"
    ECONOMIC_DATA = "economic_data"
    GEOPOLITICAL = "geopolitical"
    COMPANY_UPDATE = "company_update"
    MARKET_COMMENTARY = "market_commentary"
    OTHER = "other"

class Answer(str, Enum):
    YES = "yes"
    NO = "no"

class IsRelevantModel(BaseModel):
    relevant: Answer = Answer.NO

class TopicAction(str, Enum):
    ADD = "add"
    REPLACE = "replace"
    REJECT = "reject"

class Response(BaseModel):
    response: str = ""

class UncrucialTopics(BaseModel):
    ids_to_remove: list[str] = []

class Summary(BaseModel):
    summary: str = ""

class Decision(BaseModel):
    motivation: Optional[str] = Field(default=None, max_length=400)
    tool: Tool
    id: Optional[str] = None  # must be in Allowed IDs (checked post-parse)


class RemoveDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    motivation: str | None = Field(default=None, max_length=400)
    remove_link: str | None = None

class CheckTopicRelevance(BaseModel):
    should_add: bool = False
    motivation: str = ""

class TestResult(BaseModel):
    response: str = ""

class ClassifyTopicImportance(BaseModel):
    importance: int | str = 1
    rationale: str = ""

class FilterInterestingTopics(BaseModel):
    motivation: str = ""
    candidates: list[str] = []

class WideQueryModel(BaseModel):
    motivation: str = ""
    query: str = ""

class ClassifyTopicCategory(BaseModel):
    motivation: str = ""
    category: TopicCategory = TopicCategory.NONE

class SelectOneNewLinkModel(BaseModel):
    motivation: str = ""
    type: str = ""
    source: str = ""
    target: str = ""

class TopicCapacityModel(BaseModel):
    action: TopicAction = TopicAction.REJECT
    motivation: str = ""
    id_to_remove: str | None = None

class ProposeTopic(BaseModel):
    id: str = ""
    name: str = ""
    type: TopicCategory = TopicCategory.NONE
    motivation: str = ""

class TopicMapping(BaseModel):
    motivation: str = ""
    existing: list[str] = []
    new: list[str] = []

class TimeFrame(BaseModel):
    motivation: str = ""
    horizon: str = ""

class ShouldRewrite(BaseModel):
    motivation: str = ""
    rewrite: bool = False

class RelevanceGate(BaseModel):
    motivation: str = ""
    relevant: bool = False

class Keywords(BaseModel):
    list: List[str] = []

class FindImpact(BaseModel):
    motivation: str = ""
    score: int = 0

class FindCategory(BaseModel):
    motivation: str = ""
    name: CategoryName = CategoryName.OTHER

class ValidateRelevance(BaseModel):
    should_link: bool = False
    motivation: str = ""

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
                return cast(dict[str, Any], json.loads(raw[start : end + 1]))
    raise ValueError("LLM output not parseable as JSON object")


def run_llm_decision[T: BaseModel](
    chain: Runnable[str, dict[str, Any]],
    prompt: str,
    model: type[T],
    *,
    retry_once: bool = True,
    allowed_ids: Iterable[str] | None = None,
    logger: logging.Logger | None = None,
) -> T:

    if allowed_ids:
        allowed = set(allowed_ids)

    def _try_invoke() -> T:
        raw = chain.invoke(prompt)
        data = _coerce_to_dict(raw)

        try:
            parsed = model.model_validate(data)
        except ValidationError as e:
            if logger:
                logger.warning("Invalid LLM schema: %s", str(e)[:200])
                raise

        if hasattr(parsed, "remove_link"):
            remove_link = getattr(parsed, "remove_link")
            if remove_link is not None and remove_link not in allowed:
                if logger:
                    logger.warning(
                        "remove_link %s not in allowed ids, coercing to None", remove_link
                    )
                parsed.remove_link = None

        return parsed

    try:
        return _try_invoke()
    except (ValidationError, JSONDecodeError) as e:
        if retry_once:
            if logger:
                logger.info("Retrying LLM decision once due to error: %s", str(e)[:200])
            return _try_invoke()
        raise
