# 라우터 (router/weather.py)와 Gemini 클라이언트 (core/gemini.py) 사이의 비즈니스 로직 레이어이다.

# 흐름 : [라우터] → get_weather_briefing() → [프롬프트 빌드] → [Gemini 호출] → [응답 파싱] → [라우터]

# 레이어별 책임 분리:
# - prompt/weather.py : 프롬프트 문자열 조립
# - service/weather.py: Gemini 호출 + 예외의 HTTP 변환 책임
# - parser/weather.py : raw JSON 문자열 → Pydantic 모델 변환 (순수 변환, HTTP 무관)

import google.generativeai as genai
from fastapi import HTTPException
from google.api_core.exceptions import DeadlineExceeded, GoogleAPICallError

# core/gemini.py의 import만으로 genai.configure()가 실행된다.
# 즉, 이 줄 하나로 Gemini API 키 인증이 완료된다.
import app.core.gemini

from app.parser.weather import parse_briefing_response
from app.prompt.weather import SYSTEM_PROMPT, build_user_prompt
from app.schema.error import ErrorCode
from app.schema.weather import WeatherBriefingRequest, WeatherBriefingResponse

# Gemini 모델 이름 상수
# 하드코딩된 문자열 대신 상수로 관리한다.
# 이유:
#   - 모델 이름 변경 시 이 상수만 수정하면 된다.
#   - 오타로 인한 런타임 오류를 방지한다.
_GEMINI_MODEL_NAME = "models/gemini-2.5-flash"

# Gemini GenerationConfig 상수
# 각 값의 의미와 선택 이유를 상수명과 주석으로 명시한다.

# temperature: 모델의 창의성 수준 (0.0 ~ 1.0)
# 0.7 = 분류 정확성(icon_code, clothing)과 문체 다양성(message)의 균형점
_TEMPERATURE = 0.7

# max_output_tokens: 브리핑 메시지(2문장) + JSON 구조 오버헤드를 고려한 적정 토큰 수
_MAX_OUTPUT_TOKENS = 2048

# 인증 에러 판별 키워드 목록
# GoogleAPICallError 메시지 문자열로 인증 오류와 일반 API 오류를 구분한다.
# 하드코딩 방지를 위해 상수로 분리하며, 새로운 키워드 추가 시 이 목록만 수정한다.
_AUTH_ERROR_KEYWORDS = ("API_KEY", "PERMISSION_DENIED", "UNAUTHENTICATED")


async def get_weather_briefing(request: WeatherBriefingRequest) -> WeatherBriefingResponse:
    """
    날씨 브리핑 생성의 진입점(entry point).

    이 함수는 라우터에서 직접 호출되며, 크게 세 단계로 동작한다:
      1단계) 유저 프롬프트 빌드: cold_sensitivity와 날씨 데이터를 자연어로 조합
      2단계) Gemini API 호출: 시스템 프롬프트 + 유저 프롬프트로 JSON 브리핑 생성
      3단계) 응답 파싱: raw JSON 문자열을 parser 레이어에 위임 후 HTTPException으로 변환
    """

    # 1. 유저 프롬프트 빌드
    # build_user_prompt()는 app/prompt/weather.py에서 정의된 함수.
    # cold_sensitivity Enum을 자연어로 변환하고,
    # 날씨 데이터를 마크다운 형식으로 조립해 Gemini가 읽기 쉬운 텍스트를 만든다.
    user_prompt = build_user_prompt(request)

    # 2. Gemini API 호출
    try:
        # system_instruction은 generate_content_async()가 아닌
        # GenerativeModel() 생성자에 전달해야 한다.
        model = genai.GenerativeModel(
            model_name=_GEMINI_MODEL_NAME,
            system_instruction=SYSTEM_PROMPT,  # 사서 '리프'의 페르소나 및 응답 규칙
        )

        response = await model.generate_content_async(
            # 유저 메시지: 이번 요청의 날씨 데이터 + 체질 정보
            contents=[user_prompt],

            generation_config=genai.GenerationConfig(
                # JSON만 반환하도록 모델 레벨에서 강제한다.
                response_mime_type="application/json",
                temperature=_TEMPERATURE,
                max_output_tokens=_MAX_OUTPUT_TOKENS,
            ),
        )

    except DeadlineExceeded:
        # Gemini API 응답이 SDK 기본 타임아웃을 초과한 경우
        raise HTTPException(
            status_code=504,
            detail={
                "error_code": ErrorCode.GEMINI_TIMEOUT,
                "message": "Gemini 응답 시간이 초과되었습니다.",
            },
        )

    except GoogleAPICallError as e:
        # GoogleAPICallError는 Gemini SDK의 모든 API 오류의 상위 예외.
        # 에러 메시지 문자열로 인증 오류와 일반 API 오류를 구분한다.
        is_auth_error = any(keyword in str(e) for keyword in _AUTH_ERROR_KEYWORDS)

        if is_auth_error:
            raise HTTPException(
                status_code=401,
                detail={
                    "error_code": ErrorCode.GEMINI_AUTH_ERROR,
                    "message": "Gemini API 키 인증에 실패했습니다.",
                },
            )

        raise HTTPException(
            status_code=502,
            detail={
                "error_code": ErrorCode.GEMINI_API_ERROR,
                "message": f"Gemini API 호출에 실패했습니다: {str(e)}",
            },
        )

    # 3. 응답 파싱
    # 파싱의 구체적인 구현은 parser/weather.py에 위임한다.
    # service는 "파싱이 어떻게 되는지"는 모르고,
    # "파싱이 실패했을 때 어떤 HTTP 응답을 줄지"만 책임진다.
    try:
        return parse_briefing_response(response.text)

    except (ValueError, KeyError) as e:
        # ValueError  : icon_code 또는 clothing이 정의된 Enum 범위를 벗어난 경우
        # KeyError    : JSON에 필수 키(message, icon_code, clothing)가 없는 경우
        raise HTTPException(
            status_code=502,
            detail={
                "error_code": ErrorCode.GEMINI_PARSE_ERROR,
                "message": f"Gemini 응답 파싱에 실패했습니다: {str(e)}",
            },
        )

    except Exception as e:
        # json.JSONDecodeError 포함, 예상치 못한 파싱 오류 전체를 처리한다.
        # json.JSONDecodeError는 ValueError의 하위 클래스이지만,
        # 명시적으로 분리해 "JSON 자체가 깨진 경우"임을 로그/메시지에서 구분할 수 있도록 한다.
        raise HTTPException(
            status_code=502,
            detail={
                "error_code": ErrorCode.GEMINI_PARSE_ERROR,
                "message": f"Gemini 응답이 유효한 JSON 형식이 아닙니다: {str(e)}",
            },
        )

