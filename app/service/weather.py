# 라우터 (router/weather.py)와 Gemini 클라이언트 (core/gemini.py) 사이의 비즈니스 로직 레이어이다.

# 흐름 : [라우터] → get_weather_briefing() → [프롬프트 빌드] → [Gemini 호출] → [응답 파싱] → [라우터]

# 레이어별 책임 분리:
# - prompt/weather.py : 프롬프트 문자열 조립
# - service/weather.py: Gemini 호출 + 예외의 HTTP 변환 책임
# - parser/weather.py : raw JSON 문자열 → Pydantic 모델 변환 (순수 변환, HTTP 무관)

from google.genai import types
from google.genai import errors as genai_errors
from fastapi import HTTPException

# core/gemini.py import로 Client 인스턴스를 가져온다.
from app.core.gemini import client

from app.parser.weather import parse_briefing_response
from app.prompt.weather import SYSTEM_PROMPT, build_user_prompt
from app.schema.error import ErrorCode
from app.schema.weather import WeatherBriefingRequest, WeatherBriefingResponse

# Gemini 모델 이름 상수
_GEMINI_MODEL_NAME = "models/gemini-2.5-flash"

# temperature: 분류 정확성과 문체 다양성의 균형점
_TEMPERATURE = 0.7

# max_output_tokens: 브리핑 메시지(2문장) + JSON 구조 오버헤드를 고려한 적정 토큰 수
_MAX_OUTPUT_TOKENS = 2048

# 인증 에러 판별 키워드 목록
_AUTH_ERROR_KEYWORDS = ("API_KEY", "PERMISSION_DENIED", "UNAUTHENTICATED")


async def get_weather_briefing(request: WeatherBriefingRequest) -> WeatherBriefingResponse:
    """
    날씨 브리핑 생성의 진입점(entry point).

    1단계) 유저 프롬프트 빌드
    2단계) Gemini API 호출
    3단계) 응답 파싱
    """

    # 1. 유저 프롬프트 빌드
    user_prompt = build_user_prompt(request)

    # 2. Gemini API 호출
    try:
        response = await client.aio.models.generate_content(
            model=_GEMINI_MODEL_NAME,
            contents=[user_prompt],
            config=types.GenerateContentConfig(
                # 사서 '리프'의 페르소나 및 응답 규칙
                system_instruction=SYSTEM_PROMPT,
                # JSON만 반환하도록 모델 레벨에서 강제한다.
                response_mime_type="application/json",
                temperature=_TEMPERATURE,
                max_output_tokens=_MAX_OUTPUT_TOKENS,
            ),
        )


    except genai_errors.ServerError as e:

        # 새 SDK는 DeadlineExceeded 대신 ServerError의 status로 타임아웃을 판별한다.

        if "timeout" in str(e).lower() or "deadline" in str(e).lower():
            raise HTTPException(

                status_code=504,

                detail={

                    "error_code": ErrorCode.GEMINI_TIMEOUT,

                    "message": "Gemini 응답 시간이 초과되었습니다.",

                },

            )

        raise HTTPException(

            status_code=502,

            detail={

                "error_code": ErrorCode.GEMINI_API_ERROR,

                "message": f"Gemini API 호출에 실패했습니다: {str(e)}",

            },

        )


    except genai_errors.ClientError as e:

        # 401/403 계열 — 인증 실패

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
    try:
        return parse_briefing_response(response.text)

    except (ValueError, KeyError) as e:
        raise HTTPException(
            status_code=502,
            detail={
                "error_code": ErrorCode.GEMINI_PARSE_ERROR,
                "message": f"Gemini 응답 파싱에 실패했습니다: {str(e)}",
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail={
                "error_code": ErrorCode.GEMINI_PARSE_ERROR,
                "message": f"Gemini 응답이 유효한 JSON 형식이 아닙니다: {str(e)}",
            },
        )