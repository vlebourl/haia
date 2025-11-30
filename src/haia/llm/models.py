"""Pydantic models for LLM abstraction layer."""

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single message in a conversation."""

    role: str = Field(
        ...,
        description="Message role: 'system', 'user', or 'assistant'",
        pattern="^(system|user|assistant)$",
    )
    content: str = Field(..., description="Message content (text)", min_length=1)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"role": "user", "content": "Hello, how are you?"},
                {"role": "assistant", "content": "I'm doing well, thank you!"},
                {"role": "system", "content": "You are a helpful assistant."},
            ]
        }
    }


class TokenUsage(BaseModel):
    """Token usage statistics from LLM API call."""

    prompt_tokens: int = Field(..., description="Tokens in the input prompt", ge=0)
    completion_tokens: int = Field(
        ..., description="Tokens in the generated completion", ge=0
    )
    total_tokens: int = Field(
        ..., description="Total tokens used (prompt + completion)", ge=0
    )

    @property
    def cost_estimate(self) -> float:
        """Rough cost estimate (varies by provider/model).

        Based on Anthropic Claude Haiku pricing:
        - Input: $0.25/M tokens
        - Output: $1.25/M tokens
        """
        input_cost = (self.prompt_tokens / 1_000_000) * 0.25
        output_cost = (self.completion_tokens / 1_000_000) * 1.25
        return input_cost + output_cost

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"prompt_tokens": 47, "completion_tokens": 65, "total_tokens": 112}
            ]
        }
    }


class LLMResponse(BaseModel):
    """Unified response from LLM provider."""

    content: str = Field(..., description="Generated text content", min_length=1)
    model: str = Field(..., description="Model identifier used for generation")
    usage: TokenUsage = Field(..., description="Token usage statistics")
    finish_reason: str | None = Field(
        None,
        description="Reason generation stopped: 'stop', 'length', 'tool_calls', etc.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "content": "Hello! I'm doing well, thank you for asking.",
                    "model": "claude-haiku-4-5-20251001",
                    "usage": {
                        "prompt_tokens": 47,
                        "completion_tokens": 65,
                        "total_tokens": 112,
                    },
                    "finish_reason": "stop",
                }
            ]
        }
    }


class LLMResponseChunk(BaseModel):
    """A single chunk in a streaming LLM response."""

    content: str = Field(..., description="Incremental content chunk")
    finish_reason: str | None = Field(
        None, description="Only set on final chunk: 'stop', 'length', etc."
    )
    usage: TokenUsage | None = Field(
        None, description="Only set on final chunk: final token usage"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"content": "Hello", "finish_reason": None, "usage": None},
                {"content": " there!", "finish_reason": None, "usage": None},
                {
                    "content": "",
                    "finish_reason": "stop",
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "total_tokens": 15,
                    },
                },
            ]
        }
    }
