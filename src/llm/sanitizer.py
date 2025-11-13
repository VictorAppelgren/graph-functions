import json
import re
import logging
import inspect
from enum import Enum
from typing import Any, Iterable, Optional, Literal, cast, List
from pydantic import BaseModel, Field, ValidationError
from langchain_core.runnables import Runnable
from json import JSONDecodeError
from utils.app_logging import get_logger

# Module-level logger so callers don't need to pass one
MODULE_LOGGER = get_logger("llm_sanitizer")


class Tool(str, Enum):
    remove = "remove"
    hide = "hide"
    lower_priority = "lower_priority"
    none = "none"

class TopicCategory(str, Enum):
    MACRO = "macro"
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
    ids_to_remove: List[str] = []

class Summary(BaseModel):
    summary: str = ""

class Decision(BaseModel):
    motivation: Optional[str] = Field(default=None, max_length=400)
    tool: Tool
    id: Optional[str] = None  # must be in Allowed IDs (checked post-parse)


class RemoveDecision(BaseModel):
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
    candidates: List[str] = []

class ArticleCapacityAction(str, Enum):
    remove = "remove"
    downgrade = "downgrade"
    reject = "reject"

class ArticleCapacityDecision(BaseModel):
    motivation: str = Field(max_length=400)
    action: ArticleCapacityAction
    target_article_id: Optional[str] = None
    new_importance: Optional[int] = Field(default=None, ge=1, le=2)  # Only 1 or 2 for downgrades

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
    existing: List[str] = []
    new: List[str] = []

class TimeFrame(BaseModel):
    motivation: str = ""
    horizon: Literal["fundamental", "medium", "current", "invalid"] = "invalid"

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

def _extract_json_from_llm_output(raw_output: str) -> dict[str, Any] | None:
    """
    Robust JSON extraction from LLM output. Handles multiple formats.
    Returns None if no valid JSON found.
    """
    if not raw_output or not isinstance(raw_output, str):
        return None
    
    text = raw_output.strip()
    
    # Try direct JSON parse first (fastest path)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Extract from fenced code blocks
    fenced_patterns = [
        r'```json\s*\n(.*?)\n```',  # ```json ... ```
        r'```\s*\n(.*?)\n```',     # ``` ... ```
    ]
    
    for pattern in fenced_patterns:
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
    
    # Find JSON objects in text (greedy match)
    json_start = text.find('{')
    json_end = text.rfind('}')
    
    if json_start != -1 and json_end != -1 and json_end > json_start:
        try:
            return json.loads(text[json_start:json_end + 1])
        except json.JSONDecodeError:
            pass
    
    return None


def _coerce_to_dict(raw: Any) -> dict[str, Any]:
    """Convert LLM output to dict, handling various input types."""
    if isinstance(raw, dict):
        return raw
    
    # Handle LangChain AIMessage objects
    if hasattr(raw, 'content'):
        content = raw.content
        if isinstance(content, str):
            result = _extract_json_from_llm_output(content)
            if result is not None:
                return result
            # Enhanced error with preview of failed output
            preview = content[:300] + "..." if len(content) > 300 else content
            raise ValueError(f"LLM output not parseable as JSON object | raw_output_preview: '{preview}'")
    
    if isinstance(raw, str):
        # Check for empty response - provide model-specific defaults
        if raw.strip() == "":
            caller_context = _get_caller_context()
            if 'time_frame' in caller_context.lower():
                # TimeFrame: empty response = invalid article
                return {"motivation": "LLM returned empty response - treating as invalid content", "horizon": "invalid"}
            else:
                # Other models: still an error
                raise ValueError("LLM returned empty response - likely timeout/network issue")
        
        result = _extract_json_from_llm_output(raw)
        if result is not None:
            return result
        # Enhanced error with preview of failed output  
        preview = raw[:300] + "..." if len(raw) > 300 else raw
        raise ValueError(f"LLM output not parseable as JSON object | raw_output_preview: '{preview}'")
    
    # Handle None as empty result for certain models
    if raw is None:
        return {}  # Empty dict will create model with default values
    
    # Handle non-string, non-dict inputs
    raise ValueError(f"LLM output not parseable as JSON object | unexpected_type: {type(raw).__name__} | value: {str(raw)[:100]}")


def _get_caller_context() -> str:
    """Get the calling function name for better error context."""
    try:
        frame = inspect.currentframe()
        if frame and frame.f_back and frame.f_back.f_back:
            caller_frame = frame.f_back.f_back
            function_name = caller_frame.f_code.co_name
            filename = caller_frame.f_code.co_filename.split('/')[-1]
            return f"{filename}:{function_name}"
    except:
        pass
    return "unknown_caller"


def run_llm_text_response(
    chain: Runnable[str, str],
    prompt: str,
    *,
    retry_once: bool = True,
    logger: logging.Logger | None = None,
) -> Response:
    """
    Run LLM for simple text responses, wrapping result in Response model.
    Use this for analysis generation where we just need the text content.
    """
    caller_context = _get_caller_context()
    local_logger = logger or MODULE_LOGGER

    def _try_invoke() -> Response:
        try:
            raw_text = chain.invoke(prompt)
            local_logger.debug(f"LLM text output | caller={caller_context} | length={len(str(raw_text))}")
            
            # Wrap string response in Response model for type safety
            return Response(response=str(raw_text))
            
        except Exception as e:
            enhanced_msg = f"LLM text generation failed | caller={caller_context} | error={str(e)}"
            raise ValueError(enhanced_msg) from e

    try:
        return _try_invoke()
    except ValueError as e:
        if retry_once:
            local_logger.info(f"Retrying LLM text generation | caller={caller_context} | error={str(e)}")
            return _try_invoke()
        else:
            raise


def run_llm_decision[T: BaseModel](
    chain: Runnable[str, dict[str, Any]],
    prompt: str,
    model: type[T],
    *,
    retry_once: bool = True,
    allowed_ids: Iterable[str] | None = None,
    logger: logging.Logger | None = None,
) -> T:

    allowed = set(allowed_ids) if allowed_ids else None
    
    caller_context = _get_caller_context()
    model_name = model.__name__
    local_logger = logger or MODULE_LOGGER

    def _try_invoke() -> T:
        try:
            raw = chain.invoke(prompt)
            local_logger.debug(f"LLM raw output | caller={caller_context} | model={model_name} | length={len(str(raw))}")
            data = _coerce_to_dict(raw)
        except ValueError as e:
            # Add caller context to parsing errors
            enhanced_msg = f"{str(e)} | caller={caller_context} | model={model_name}"
            raise ValueError(enhanced_msg) from e

        # Minimal, centralized normalization for known schemas
        try:
            # Ensure TopicMapping.new/existing are lists, never None/""
            if model is TopicMapping:
                if data.get("existing") in (None, ""):
                    data["existing"] = []
                if data.get("new") in (None, ""):
                    data["new"] = []
            
            # Handle legacy "hidden" -> 0 for FindImpact
            if model is FindImpact and data.get("score") == "hidden":
                data["score"] = 0
        except Exception:
            # Non-fatal; validation will catch issues
            pass

        try:
            parsed = model.model_validate(data)

            if hasattr(parsed, "remove_link"):
                remove_link = getattr(parsed, "remove_link")
                if remove_link is not None and allowed is not None and remove_link not in allowed:
                    local_logger.warning(
                        "remove_link %s not in allowed ids, coercing to None | caller=%s", 
                        remove_link, caller_context
                    )
                    parsed.remove_link = None

            return parsed
        except ValidationError as e:
            local_logger.warning(
                "Invalid LLM schema | caller=%s | model=%s | error=%s", 
                caller_context, model_name, str(e)[:200]
            )
            # Always raise so callers/retry logic can handle it; avoid UnboundLocalError
            raise

    try:
        return _try_invoke()
    except (ValidationError, JSONDecodeError, ValueError) as e:
        if retry_once:
            local_logger.info(
                "Retrying LLM decision | caller=%s | model=%s | error=%s", 
                caller_context, model_name, str(e)[:200]
            )
            return _try_invoke()
        raise
