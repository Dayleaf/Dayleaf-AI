from enum import Enum
from pydantic import BaseModel


# 에러 코드 Enum
class ErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    GEMINI_AUTH_ERROR = "GEMINI_AUTH_ERROR"
    GEMINI_API_ERROR = "GEMINI_API_ERROR"
    GEMINI_PARSE_ERROR = "GEMINI_PARSE_ERROR"
    GEMINI_TIMEOUT = "GEMINI_TIMEOUT"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"


# 에러 응답 스키마
class ErrorResponse(BaseModel):
    error_code: ErrorCode
    message: str