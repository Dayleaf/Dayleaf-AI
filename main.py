from fastapi import FastAPI, Request, HTTPException
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

# HTTPException 핸들러
# 처리 흐름
#   1. detail이 dict인지 확인한다.
#      → dict가 아니면 FastAPI 내부 에러일 수 있으므로 INTERNAL_SERVER_ERROR로 폴백한다.
#   2. error_code 값을 꺼낸다.
#      → service 레이어가 ErrorCode Enum 객체를 그대로 넘기는 경우를 대비해
#         Enum이면 .value(문자열)로, 이미 문자열이면 그대로 사용한다.
#         (직렬화 관심사는 응답을 조립하는 이 레이어가 책임진다.)
#   3. ErrorResponse로 변환해 JSONResponse를 반환한다.
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):

    detail = exc.detail

    # 1. detail이 dict가 아닌 경우: FastAPI 내부 HTTPException 등
    #    예) raise HTTPException(status_code=404, detail="Not Found")
    #    이 경우 error_code/message 구조가 없으므로 INTERNAL_SERVER_ERROR로 폴백한다.
    if not isinstance(detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error_code=ErrorCode.INTERNAL_SERVER_ERROR,
                message=str(detail),  # 원본 메시지를 문자열로 변환해 보존한다.
            ).model_dump(),
        )
    # 2. error_code 추출 및 방어적 직렬화
    #    service 레이어에서 ErrorCode Enum 객체를 그대로 넘기는 경우,
    #    JSONResponse는 Enum을 자동 직렬화하지 않아 오류가 발생할 수 있다.
    #    따라서 Enum이면 .value로, 문자열이면 그대로 사용한다.
    raw_error_code = detail.get("error_code", ErrorCode.INTERNAL_SERVER_ERROR)
    error_code_value = (
        raw_error_code.value                  # Enum 객체인 경우: ErrorCode.GEMINI_AUTH_ERROR → "GEMINI_AUTH_ERROR"
        if isinstance(raw_error_code, ErrorCode)
        else str(raw_error_code)              # 이미 문자열인 경우: 그대로 사용
    )

    # 3. message 추출
    #    detail에 message 키가 없는 경우를 대비해 기본값을 설정한다.
    message = detail.get("message", "알 수 없는 오류가 발생했습니다.")

    # 4. ErrorResponse로 변환해 반환
    #    error_code_value는 이미 문자열이므로 ErrorCode(error_code_value)로 Enum 변환한다.
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_code=ErrorCode(error_code_value),
            message=message,
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