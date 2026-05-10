from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException

# SDK import 차단
import sys
sys.modules["google.generativeai"] = MagicMock()
sys.modules["google.ai.generativelanguage_v1beta"] = MagicMock()
sys.modules["app.core.gemini"] = MagicMock()

from main import app  # noqa: E402 (SDK mock 이후에 import해야 하므로 순서 고정)
from app.schema.error import ErrorCode  # noqa: E402

client = TestClient(app)

# 공통 요청 바디
VALID_REQUEST_BODY = {
    "member_id": 1,
    "cold_sensitivity": "NORMAL",
    "weather": {
        "temperature": 15.0,
        "feels_like": 13.0,
        "condition": "맑음",
        "humidity": 50,
        "wind_speed": 2.0,
        "precipitation": 0.0,
        "air_quality": "GOOD",
    },
}

# patch 대상 경로
# 이유:
#   patch는 "실제로 사용되는 위치"를 기준으로 해야 한다.
#   router/weather.py가 get_weather_briefing을 import해서 호출하므로
#   app.router.weather 네임스페이스의 참조를 patch해야 mock이 적용된다.
#   app.service.weather를 patch하면 이미 router가 가진 참조에는 영향을 주지 않는다.
PATCH_TARGET = "app.router.weather.get_weather_briefing"

# 핸들러 포맷 검증
# 검증 목표:
#   HTTPException의 detail(dict)이 ErrorResponse 포맷으로 변환되는지 확인한다.
#   실제 Gemini 호출은 mock으로 대체한다.
class TestHttpExceptionHandler:

    def test_gemini_auth_error_response_format(self):
        """
        GEMINI_AUTH_ERROR 발생 시
        - HTTP 401 반환
        - ErrorResponse 포맷 (error_code, message 키) 확인
        - error_code 값이 문자열 "GEMINI_AUTH_ERROR"인지 확인 (Enum 직렬화 검증)
        """
        with patch(
            PATCH_TARGET,
            new_callable=AsyncMock,
            side_effect=HTTPException(
                status_code=401,
                detail={
                    "error_code": ErrorCode.GEMINI_AUTH_ERROR,  # Enum 객체로 던짐
                    "message": "Gemini API 키 인증에 실패했습니다.",
                },
            ),
        ):
            response = client.post("/api/v1/weather/briefing", json=VALID_REQUEST_BODY)

        assert response.status_code == 401
        body = response.json()
        assert "error_code" in body
        assert "message" in body
        assert body["error_code"] == "GEMINI_AUTH_ERROR"  # 문자열로 직렬화됐는지 확인
        assert body["message"] == "Gemini API 키 인증에 실패했습니다."

    def test_gemini_api_error_response_format(self):
        """
        GEMINI_API_ERROR 발생 시 HTTP 502 + ErrorResponse 포맷 확인
        """
        with patch(
            PATCH_TARGET,
            new_callable=AsyncMock,
            side_effect=HTTPException(
                status_code=502,
                detail={
                    "error_code": ErrorCode.GEMINI_API_ERROR,
                    "message": "Gemini API 호출에 실패했습니다.",
                },
            ),
        ):
            response = client.post("/api/v1/weather/briefing", json=VALID_REQUEST_BODY)

        assert response.status_code == 502
        body = response.json()
        assert body["error_code"] == "GEMINI_API_ERROR"
        assert body["message"] == "Gemini API 호출에 실패했습니다."

    def test_gemini_timeout_response_format(self):
        """
        GEMINI_TIMEOUT 발생 시 HTTP 504 + ErrorResponse 포맷 확인
        """
        with patch(
            PATCH_TARGET,
            new_callable=AsyncMock,
            side_effect=HTTPException(
                status_code=504,
                detail={
                    "error_code": ErrorCode.GEMINI_TIMEOUT,
                    "message": "Gemini 응답 시간이 초과되었습니다.",
                },
            ),
        ):
            response = client.post("/api/v1/weather/briefing", json=VALID_REQUEST_BODY)

        assert response.status_code == 504
        body = response.json()
        assert body["error_code"] == "GEMINI_TIMEOUT"
        assert body["message"] == "Gemini 응답 시간이 초과되었습니다."

    def test_non_dict_detail_fallback(self):
        """
        detail이 dict가 아닌 경우 (FastAPI 내부 에러 등)
        INTERNAL_SERVER_ERROR로 폴백되는지 확인
        """
        with patch(
            PATCH_TARGET,
            new_callable=AsyncMock,
            side_effect=HTTPException(
                status_code=500,
                detail="예상치 못한 문자열 에러",  # dict가 아닌 경우
            ),
        ):
            response = client.post("/api/v1/weather/briefing", json=VALID_REQUEST_BODY)

        assert response.status_code == 500
        body = response.json()
        assert body["error_code"] == "INTERNAL_SERVER_ERROR"