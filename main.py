from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.router.weather import router as weather_router
from app.schema.error import ErrorCode, ErrorResponse

app = FastAPI(
    title="Dayleaf AI",
    description="Dayleaf AI 서버 - 날씨 브리핑 및 개인화 서비스",
    version="0.1.0",
)

# 라우터 등록
app.include_router(weather_router)

# 422 에러 핸들러
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error_code=ErrorCode.INVALID_REQUEST,
            message="요청 형식이 올바르지 않습니다.",
        ).model_dump(),
    )

# 500 에러 핸들러
@app.exception_handler(Exception)
async def internal_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error_code=ErrorCode.INTERNAL_SERVER_ERROR,
            message="예상치 못한 서버 오류가 발생했습니다.",
        ).model_dump(),
    )

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "dayleaf-ai"}