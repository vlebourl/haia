"""Pydantic models for error responses."""

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Detailed error information (OpenAI format)."""

    message: str = Field(..., description="Human-readable error message")
    type: str = Field(..., description="Error type identifier")
    code: str | None = Field(None, description="Error code")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Invalid API key provided",
                "type": "authentication_error",
                "code": "invalid_api_key",
            }
        }


class ErrorResponse(BaseModel):
    """Error response wrapper (OpenAI format)."""

    error: ErrorDetail = Field(..., description="Error details")

    @classmethod
    def from_exception(
        cls, exc: Exception, error_type: str, code: str | None = None
    ) -> "ErrorResponse":
        """Create error response from exception."""
        return cls(error=ErrorDetail(message=str(exc), type=error_type, code=code))

    class Config:
        json_schema_extra = {
            "example": {
                "error": {
                    "message": "Invalid API key provided",
                    "type": "authentication_error",
                    "code": "invalid_api_key",
                }
            }
        }
