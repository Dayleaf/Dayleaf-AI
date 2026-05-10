# Gemini 1.5 Flash를 호출하여 사서 톤의 날씨 브리핑을 생성한다.
# 라우터 (router/weather.py)와 Gemini 클라이언트 (core/gemini.py) 사이의 비즈니스 로직 레이어이다.

# 흐름 : [라우터] → get_weather_briefing() → [프롬프트 빌드] → [Gemini 호출] → [응답 파싱] → [라우터]

import json

import google.generativeai as genai
from fastapi import HTTPException
from google.api_core.exceptions import DeadlineExceeded, GoogleAPICallError

# core/gemini.py의 import만으로 genai.configure()가 실행된다.
# 즉, 이 줄 하나로 Gemini API 키 인증이 완료된다.
import app.core.gemini

from app.prompt.weather import SYSTEM_PROMPT, build_user_prompt
from app.schema.error import ErrorCode
from app.schema.weather import (
    Clothing,
    IconCode,
    WeatherBriefingRequest,
    WeatherBriefingResponse,
)

async def get_weather_briefing(request: WeatherBriefingRequest) -> WeatherBriefingResponse:
    """
    날씨 브리핑 생성의 진입점(entry point)

    이 함수는 라우터에서 직접 호출되며, 크게 세 단계로 동작한다:
      1단계) 유저 프롬프트 빌드: cold_sensitivity와 날씨 데이터를 자연어로 조합
      2단계) Gemini API 호출: 시스템 프롬프트 + 유저 프롬프트로 JSON 브리핑 생성
      3단계) 응답 파싱: JSON 문자열을 WeatherBriefingResponse Pydantic 모델로 변환
    """

    # ── 1단계: 유저 프롬프트 빌드 ────────────────────────────────────────────────
    # build_user_prompt()는 app/prompt/weather.py에서 정의된 함수
    # cold_sensitivity Enum을 자연어로 변환하고,
    # 날씨 데이터를 마크다운 형식으로 조립해 Gemini가 읽기 쉬운 텍스트를 만든다.
    user_prompt = build_user_prompt(request)

    # ── 2단계: Gemini API 호출 ────────────────────────────────────────────────────
    try:
        # system_instruction은 generate_content_async()가 아닌
        # GenerativeModel() 생성자에 전달해야 한다.
        model = genai.GenerativeModel(
            model_name="models/gemini-2.5-flash",  # 먼저 이걸로 시도
            system_instruction=SYSTEM_PROMPT,  # 사서 '리프'의 페르소나 및 응답 규칙
        )

        response = await model.generate_content_async(
            # 유저 메시지: 이번 요청의 날씨 데이터 + 체질 정보
            contents=[user_prompt],

            generation_config=genai.GenerationConfig(
                # JSON만 반환하도록 모델 레벨에서 강제한다.
                response_mime_type="application/json",

                # temperature: 모델의 창의성 수준 (0.0 ~ 1.0)
                # 0.7 = 분류 정확성(icon_code, clothing)과 문체 다양성(message)의 균형점
                temperature=0.7,

                # 브리핑 메시지(2~3문장) + JSON 구조 오버헤드를 고려한 적정 토큰 수
                max_output_tokens=2048,
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
        # GoogleAPICallError는 Gemini SDK의 모든 API 오류의 상위 예외
        # 에러 메시지 문자열로 인증 오류와 일반 API 오류를 구분한다.
        is_auth_error = any(
            keyword in str(e)
            for keyword in ("API_KEY", "PERMISSION_DENIED", "UNAUTHENTICATED")
        )

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

    # ── 3단계: 응답 파싱 ──────────────────────────────────────────────────────────
    try:
        # response.text: Gemini가 반환한 원시 문자열
        # response_mime_type="application/json" 덕분에 순수 JSON 문자열
        raw_text = response.text

        # JSON 문자열 → Python dict로 변환
        data = json.loads(raw_text)

        # dict → Pydantic 모델로 변환
        # IconCode(data["icon_code"]): 문자열 "CLOUDY" → IconCode.CLOUDY Enum 변환
        # [Clothing(c) for c in data["clothing"]]: 문자열 리스트 → Clothing Enum 리스트 변환
        return WeatherBriefingResponse(
            message=data["message"],
            icon_code=IconCode(data["icon_code"]),
            clothing=[Clothing(c) for c in data["clothing"]],
        )

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        # json.JSONDecodeError: Gemini가 JSON이 아닌 형식으로 응답한 경우
        # KeyError: JSON에 필수 키(message, icon_code, clothing)가 없는 경우
        # ValueError: Enum 변환 실패 — 정의되지 않은 icon_code/clothing 값을 반환한 경우
        raise HTTPException(
            status_code=502,
            detail={
                "error_code": ErrorCode.GEMINI_PARSE_ERROR,
                "message": f"Gemini 응답 파싱에 실패했습니다: {str(e)}",
            },
        )
