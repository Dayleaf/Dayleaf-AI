# Gemini가 반환한 raw JSON 문자열을 WeatherBriefingResponse Pydantic 모델로 변환한다.

# 발생 가능한 예외 (모두 호출자로 전파):
# - json.JSONDecodeError : Gemini가 JSON이 아닌 형식으로 응답한 경우
# - KeyError             : JSON에 필수 키(message, icon_code, clothing)가 없는 경우
# - ValueError           : Enum 변환 실패 — 정의되지 않은 icon_code/clothing 값인 경우

import json

from app.schema.weather import Clothing, IconCode, WeatherBriefingResponse

# JSON 필수 키 상수 정의
# 하드코딩된 문자열 리터럴 대신 상수로 관리한다.
# 이유:
#   - 오타로 인한 런타임 KeyError를 방지한다.
#   - 키 이름이 변경될 때 이 상수만 수정하면 된다.
_KEY_MESSAGE = "message"
_KEY_ICON_CODE = "icon_code"
_KEY_CLOTHING = "clothing"


def parse_briefing_response(raw_text: str) -> WeatherBriefingResponse:
    """
    Gemini가 반환한 raw JSON 문자열을 WeatherBriefingResponse로 변환한다.

    변환 흐름:
      1) raw_text(JSON 문자열) → Python dict (json.loads)
      2) dict의 각 값 → Pydantic Enum 타입으로 변환
      3) WeatherBriefingResponse 모델 생성 후 반환
    """

    # 1. JSON 문자열 → Python dict
    # json.loads()는 파싱 실패 시 json.JSONDecodeError를 발생시킨다.
    # 이 예외는 잡지 않고 호출자(service)로 전파한다.
    data: dict = json.loads(raw_text)

    # 2, 3. dict → Pydantic 모델 변환
    return WeatherBriefingResponse(
        # dict에서 값을 꺼낸다.
        # 해당 키가 없으면 KeyError가 발생하며, 호출자(service)로 전파된다.
        message=data[_KEY_MESSAGE],

        # 문자열 "CLOUDY" → IconCode.CLOUDY Enum으로 변환한다.
        # 정의되지 않은 값이면 ValueError가 발생하며, 호출자(service)로 전파된다.
        icon_code=IconCode(data[_KEY_ICON_CODE]),

        # 문자열 리스트 ["LONG_SLEEVE", "JACKET"] → Clothing Enum 리스트로 변환한다.
        # 리스트 내 하나라도 정의되지 않은 값이면 ValueError가 발생하며, 호출자(service)로 전파된다.
        clothing=[Clothing(item) for item in data[_KEY_CLOTHING]],
    )