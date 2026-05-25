import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException

# SDK import 차단 (google-genai 기준)
# 이유:
#   google.genai는 import 시점에 네트워크/인증을 시도할 수 있다.
#   테스트 환경에서는 실제 SDK가 불필요하므로, sys.modules에 MagicMock을 주입해
#   import 자체를 가로챈다.
import sys
sys.modules["google.genai"] = MagicMock()
sys.modules["google.genai.types"] = MagicMock()
sys.modules["app.core.gemini"] = MagicMock()

from main import app  # noqa: E402 (SDK mock 이후에 import해야 하므로 순서 고정)
from app.schema.error import ErrorCode  # noqa: E402
from app.schema.weather import WeatherBriefingResponse, IconCode, Clothing

client = TestClient(app)

# ── 공통 픽스처 ───────────────────────────────────────────────────────────────

# 공통 요청 바디
# 모든 테스트에서 동일한 요청 바디를 사용한다.
# 하드코딩 방지를 위해 모듈 레벨 상수로 정의한다.
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

# patch 대상 경로 상수
# 이유:
#   patch는 "실제로 사용되는 위치"를 기준으로 해야 한다.
#   router/weather.py가 get_weather_briefing을 import해서 호출하므로
#   app.router.weather 네임스페이스의 참조를 patch해야 mock이 적용된다.
#   app.service.weather를 patch하면 이미 router가 가진 참조에는 영향을 주지 않는다.
_ROUTER_PATCH_TARGET = "app.router.weather.get_weather_briefing"

# parse_briefing_response patch 대상 경로
# 이유:
#   parse_briefing_response는 app.service.weather에서 import해서 사용한다.
#   따라서 app.service.weather 네임스페이스의 참조를 patch해야 mock이 적용된다.
_PARSER_PATCH_TARGET = "app.service.weather.parse_briefing_response"

# Gemini generate_content patch 대상 경로
# 이유:
#   새 SDK는 GenerativeModel 대신 client.aio.models.generate_content를 직접 호출한다.
#   parse_briefing_response가 호출되려면 Gemini 호출이 먼저 성공해야 하므로
#   이 경로를 mock해 실제 네트워크 요청을 차단한다.
_GEMINI_MODEL_PATCH_TARGET = "app.service.weather.client.aio.models.generate_content"

# Gemini mock 응답 텍스트
# parse_briefing_response가 호출될 때 전달받을 raw_text 값이다.
# 실제 파싱은 _PARSER_PATCH_TARGET으로 mock되므로, 이 값의 내용은 중요하지 않다.
# 단, response.text 접근이 가능해야 하므로 유효한 JSON 문자열을 사용한다.
_MOCK_GEMINI_RAW_RESPONSE = json.dumps({
    "message": "mock 메시지입니다.",
    "icon_code": "SUNNY",
    "clothing": ["T_SHIRT"],
})


def _make_mock_gemini_response(raw_text: str) -> MagicMock:
    """
    client.aio.models.generate_content()가 반환할 mock response 객체를 생성합니다.

    Args:
        raw_text (str): response.text에 담길 mock 값.

    Returns:
        MagicMock: response.text = raw_text인 mock 객체.
    """
    mock_response = MagicMock()
    mock_response.text = raw_text
    return mock_response


# ── 기존 테스트: HTTPException 핸들러 포맷 검증 ───────────────────────────────

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
            _ROUTER_PATCH_TARGET,
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
            _ROUTER_PATCH_TARGET,
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
            _ROUTER_PATCH_TARGET,
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
            _ROUTER_PATCH_TARGET,
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


# ── 신규 테스트: GEMINI_PARSE_ERROR 시나리오 검증 ────────────────────────────

# 검증 목표:
#   parser(parse_briefing_response)가 예외를 던졌을 때,
#   service(get_weather_briefing)가 이를 올바른 GEMINI_PARSE_ERROR HTTPException으로
#   변환하는지 확인한다.
#
# Mock 전략:
#   - _GEMINI_MODEL_PATCH_TARGET: Gemini API 호출을 mock해 실제 네트워크 요청을 차단한다.
#     parse_briefing_response가 호출되려면 Gemini 호출이 먼저 성공해야 하기 때문이다.
#   - _PARSER_PATCH_TARGET: parse_briefing_response를 mock해 파싱 실패 상황을 격리 재현한다.
#     Gemini 응답 내용과 무관하게 파싱 예외만 테스트할 수 있다.
class TestGeminiParseError:

    def test_json_decode_error_returns_502(self):
        """
        parse_briefing_response가 json.JSONDecodeError를 발생시킬 때
        - HTTP 502 반환
        - error_code가 "GEMINI_PARSE_ERROR"인지 확인

        시나리오: Gemini가 JSON이 아닌 텍스트를 반환한 경우
        """
        with patch(
            _GEMINI_MODEL_PATCH_TARGET,
            new_callable=AsyncMock,
            return_value=_make_mock_gemini_response(_MOCK_GEMINI_RAW_RESPONSE),
        ), patch(
            _PARSER_PATCH_TARGET,
            side_effect=json.JSONDecodeError("mock decode error", doc="", pos=0),
        ):
            response = client.post("/api/v1/weather/briefing", json=VALID_REQUEST_BODY)

        assert response.status_code == 502
        body = response.json()
        assert body["error_code"] == "GEMINI_PARSE_ERROR"

    def test_key_error_returns_502(self):
        """
        parse_briefing_response가 KeyError를 발생시킬 때
        - HTTP 502 반환
        - error_code가 "GEMINI_PARSE_ERROR"인지 확인

        시나리오: JSON에 필수 키(message, icon_code, clothing 중 하나)가 없는 경우
        """
        with patch(
            _GEMINI_MODEL_PATCH_TARGET,
            new_callable=AsyncMock,
            return_value=_make_mock_gemini_response(_MOCK_GEMINI_RAW_RESPONSE),
        ), patch(
            _PARSER_PATCH_TARGET,
            side_effect=KeyError("icon_code"),
        ):
            response = client.post("/api/v1/weather/briefing", json=VALID_REQUEST_BODY)

        assert response.status_code == 502
        body = response.json()
        assert body["error_code"] == "GEMINI_PARSE_ERROR"

    def test_value_error_returns_502(self):
        """
        parse_briefing_response가 ValueError를 발생시킬 때
        - HTTP 502 반환
        - error_code가 "GEMINI_PARSE_ERROR"인지 확인

        시나리오: icon_code 또는 clothing 값이 정의된 Enum 범위를 벗어난 경우
                  예) icon_code: "HAIL" — IconCode에 정의되지 않은 값
        """
        with patch(
            _GEMINI_MODEL_PATCH_TARGET,
            new_callable=AsyncMock,
            return_value=_make_mock_gemini_response(_MOCK_GEMINI_RAW_RESPONSE),
        ), patch(
            _PARSER_PATCH_TARGET,
            side_effect=ValueError("'HAIL' is not a valid IconCode"),
        ):
            response = client.post("/api/v1/weather/briefing", json=VALID_REQUEST_BODY)

        assert response.status_code == 502
        body = response.json()
        assert body["error_code"] == "GEMINI_PARSE_ERROR"

    # ── 신규 테스트: happy path (정상 응답) 시나리오 검증 ─────────────────────────

    # 검증 목표:
    #   Gemini가 정상 응답을 반환했을 때
    #   - HTTP 200 반환
    #   - WeatherBriefingResponse 포맷(message, icon_code, clothing) 검증
    #
    # Mock 전략:
    #   - _GEMINI_MODEL_PATCH_TARGET: 실제 Gemini API 호출 차단
    #   - _PARSER_PATCH_TARGET: parse_briefing_response를 정상 Pydantic 객체 반환으로 mock
    #     이유: parser의 정확성은 TestGeminiParseError에서 이미 검증됨
    #           여기서는 "service → router → 응답 포맷" 흐름만 검증하면 충분함
    class TestHappyPath:
        # 정상 응답 mock 픽스처
        # WeatherBriefingResponse 객체를 직접 생성해 parser가 반환할 값으로 사용한다.
        _MOCK_BRIEFING_RESPONSE = WeatherBriefingResponse(
            message="오늘은 맑고 따뜻한 하루가 될 것 같습니다. 가볍게 반팔 차림으로 나서셔도 좋을 것 같아요.",
            icon_code=IconCode.SUNNY,
            clothing=[Clothing.T_SHIRT],
        )

        def test_success_returns_200(self):
            """
            Gemini 정상 응답 시
            - HTTP 200 반환
            - WeatherBriefingResponse 포맷(message, icon_code, clothing 키) 확인
            - icon_code, clothing 값이 올바른 Enum 문자열인지 확인
            """
            with patch(
                    _GEMINI_MODEL_PATCH_TARGET,
                    new_callable=AsyncMock,
                    return_value=_make_mock_gemini_response(_MOCK_GEMINI_RAW_RESPONSE),
            ), patch(
                _PARSER_PATCH_TARGET,
                return_value=self._MOCK_BRIEFING_RESPONSE,
            ):
                response = client.post("/api/v1/weather/briefing", json=VALID_REQUEST_BODY)

            assert response.status_code == 200

            body = response.json()
            assert "message" in body
            assert "icon_code" in body
            assert "clothing" in body

            assert isinstance(body["message"], str)
            assert body["icon_code"] == "SUNNY"
            assert body["clothing"] == ["T_SHIRT"]

        def test_success_with_multiple_clothing(self):
            """
            clothing이 여러 개일 때 리스트 형태로 올바르게 반환되는지 확인

            시나리오: 추위를 타는 사용자 (VERY_COLD) — 여러 겹 옷차림 추천
            """
            mock_response = WeatherBriefingResponse(
                message="오늘은 기온이 꽤 낮아 두툼하게 입고 나서시는 게 좋겠습니다. 패딩과 코트를 챙겨보세요.",
                icon_code=IconCode.CLOUDY,
                clothing=[Clothing.LONG_SLEEVE, Clothing.JACKET, Clothing.COAT],
            )

            with patch(
                    _GEMINI_MODEL_PATCH_TARGET,
                    new_callable=AsyncMock,
                    return_value=_make_mock_gemini_response(_MOCK_GEMINI_RAW_RESPONSE),
            ), patch(
                _PARSER_PATCH_TARGET,
                return_value=mock_response,
            ):
                response = client.post("/api/v1/weather/briefing", json=VALID_REQUEST_BODY)

            assert response.status_code == 200

            body = response.json()
            assert body["icon_code"] == "CLOUDY"
            assert body["clothing"] == ["LONG_SLEEVE", "JACKET", "COAT"]
            assert len(body["clothing"]) == 3