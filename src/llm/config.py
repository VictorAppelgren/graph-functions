from enum import IntEnum
from typing import TypedDict, Final, Mapping

class ModelTier(IntEnum):
    """Enumeration of model tiers based on task complexity."""
    SIMPLE = 1   # Simple tasks like classification, tagging
    MEDIUM = 2   # Medium tasks like summarization, relevance assessment
    COMPLEX = 3  # Complex tasks like research generation, counterfactual reasoning
    SIMPLE_LONG_CONTEXT = 4  # Simple tasks with long context window (e.g. GPT-5 Nano)

class ModelConfig(TypedDict):
    provider: str
    model: str
    temperature: float
    base_url: str

DEFAULT_CONFIG : Final[Mapping[ModelTier, ModelConfig]] = {
    #ModelTier.SIMPLE: {
    #    "provider": "ollama",
    #    "model": "gpt-oss",
    #    "temperature": 0.1,
    #    "api_base": "http://localhost:11434",
    #},
    ModelTier.SIMPLE: {
        "provider": "openai",
        "model": "openai/gpt-oss-20b",
        "temperature": 0.1,
        "base_url": "http://gate04.cfa.handels.gu.se:8686/v1"
    },
    ModelTier.MEDIUM: {
        "provider": "openai",
        "model": "openai/gpt-oss-20b",
        "temperature": 0.3,
        "base_url": "http://gate04.cfa.handels.gu.se:8787/v1"
    },
    ModelTier.COMPLEX: {
        "provider": "openai",
        "model": "openai/gpt-oss-20b",
        "temperature": 0.3,
        "base_url": "http://gate04.cfa.handels.gu.se:8787/v1"
    },
    #ModelTier.COMPLEX: {
    #    "provider": "openai",
    #    "model": "gpt-5-nano",
        #"temperature": 0,
    #},
    #ModelTier.COMPLEX: {
    #    "provider": "anthropic",
    #    "model": "claude-3-5-sonnet-20240620",
    #    "temperature": 0.3,
    #}
    #ModelTier.SIMPLE_LONG_CONTEXT: {
    #    "provider": "openai",
    #    "model": "gpt-5-nano",
    #    #"temperature": 0,
    #    # Add any other relevant config here
    #},
    ModelTier.SIMPLE_LONG_CONTEXT: {
        "provider": "openai",
        "model": "openai/gpt-oss-20b",
        "temperature": 0.3,
        "base_url": "http://gate04.cfa.handels.gu.se:8787/v1"
    },
}