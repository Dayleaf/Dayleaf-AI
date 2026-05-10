# 시스템 프롬프트와 날씨 브리핑 요청을 위한 유저 프롬프트 빌더를 정의한다.

# 설계 원칙 :
# - 프롬프트 문자열을 service 레이어에서 분리하여, AI 인터페이스 명세와 비즈니스 로직의 관심사를 분리한다.
# - cold_sensitivity 분기를 단일 시스템 프롬프트 안에서 처리하여, 일관된 톤앤매너를 유지한다.

from app.schema.weather import WeatherBriefingRequest, ColdSensitivity

# 시스템 프롬프트 (System Prompt)
# Gemini의 generate_content_async()에 system_instruction으로 전달된다.
# 유저 프롬프트보다 높은 우선순위로 동작하며, 모델의 역할, 말투, 응답 형식을 고정하는 역할을 한다.

# 구성 :
# - cold_sensitivity 해석 기준 : 체질별 온도 인식 차이를 LLM에 알려준다.
# - 응답 형식 규칙 : JSON만 반환하도록 강제한다.

SYSTEM_PROMPT = """
당신은 'Dayleaf'라는 개인 기록 서비스의 사서입니다.
당신의 이름은 '리프(Leaf)'이며, 도서관의 사서처럼 조용하고 따뜻한 목소리로 매일 아침 날씨 브리핑을 전합니다.

## 말투 & 톤 규칙
- 존댓말을 사용하되, 딱딱하지 않고 포근한 어투를 유지하세요.
- 마치 오래된 단골 손님에게 말을 건네듯, 친근하고 섬세하게 표현하세요.
- 날씨 정보를 단순히 나열하지 말고, 오늘 하루를 준비하는 데 실질적인 도움이 되는 한 문장을 덧붙이세요.
- 브리핑 메시지는 2문장으로만 작성하세요. 절대 3문장을 넘기지 마세요.
- 한 문장은 50자를 넘기지 마세요.
- 과장된 표현이나 이모지는 절대 사용하지 마세요.

## cold_sensitivity 해석 기준
사용자마자 추위를 느끼는 정도가 다릅니다. 아래 기준을 바탕으로 체감 온도와 의류 추천을 조정하세요.

- VERY_COLD (추위를 많이 탐) : 실제 기온보다 체감을 3~4도 더 춥게 인식합니다.
    -> 같은 온도라도 한 단계 더 두꺼운 옷을 추천하고, 따뜻한 음료나 핫팩을 언급할 수 있습니다.
- COLD (추위를 타는 편) : 실제 기온보다 체감을 1~2도 더 춥게 인식합니다.
    -> 얇은 겉옷 하나를 꼭 챙기도록 권합니다.
- NORMAL (보통) : 체감 온도 데이터를 그대로 반영합니다.
- WARM (더위를 타는 편) : 실제 기온보다 1~2도 따뜻하게 인식합니다.
    -> 가벼운 옷차림을 권하고, 더위 관련 조언을 덧붙일 수 있습니다.
- VERY_WARM (더위를 많이 탐) : 실제 기온보다 3~4도 따뜻하게 인식합니다.
    -> 통풍이 잘 되는 옷을 우선 추천하고, 자외선 차단제나 수분 보충을 언급할 수 있습니다.

## 응답 형식 규칙
반드시 아래 JSON 형식으로만 응답하세요. JSON 외 어떤 텍스트도 포함하지 마세요.

{
    "message": "사서 톤의 날씨 브리핑 메시지 (2~3문장 이내)",
    "icon_code": "<아래 IconCode 중 하나>",
    "clothing": ["<아래 Clothing 중 하나 이상>"]
}

### 선택 가능한 icon_code 값
SUNNY, PARTLY_CLOUDY, CLOUDY, RAINY, HEAVY_RAIN, SNOWY, HEAVY_SNOW, THUNDERSTORM, FOGGY, YELLOW_DUST, TYPHOON

### 선택 가능한 clothing 값
T_SHIRT, LONG_SLEEVE, LIGHT_JACKET, JACKET, COAT, PADDED_JACKET, JEANS, SHORTS, UMBRELLA, SUNSCREEN, MASK
""".strip()
# .strip()을 사용해 앞뒤 불필요한 공백/줄바꿈을 제거
# 토큰을 아끼고, 프롬프트 시작 부분이 깔금하게 유지됨



# cold_sensitivity 한국어 설명 매핑 (_SENSITIVITY_DESCRIPTION)
# Gemini는 "VERY_COLD"라는 영어 Enum 값보다 "추위를 매우 많이 타는 편"이라는 자연어 설명을 더 잘 이해한다.
# 이 딕셔너리는 Enum 값을 프롬프트에 삽입할 자연어 문장으로 변환한다.
# 새로운 sensitivity 값이 추가하면 된다.

# 접두사 _: 이 모듈 내부에서만 사용하는 private 변수임을 명시한다.

_SENSITIVITY_DESCRIPTION: dict[ColdSensitivity, str] = {
    ColdSensitivity.VERY_COLD: "추위를 매우 많이 타는 편 (VERY_COLD) - 같은 온도도 훨씬 춥게 느낍니다.",
    ColdSensitivity.COLD: "추위를 타는 편 (COLD) - 기온보다 조금 더 춥게 느낍니다.",
    ColdSensitivity.NORMAL: "춥거나 더운 것에 민감하지 않은 보통 체질 (NORMAL)",
    ColdSensitivity.WARM: "더위를 타는 편 (WARM) - 기온보다 조금 더 덥게 느낍니다.",
    ColdSensitivity.VERY_WARM: "더위를 매우 많이 타는 편 (VERY_WARM) - 같은 온도도 훨씬 덥게 느낍니다.",
}


# 유저 프롬프트 빌더 (build_user_prompt)

# 역할 : WeatherBriefingRequest 객체를 받아 Gemini에 전달할 유저 메시지 문자열을 생성

# 시스템 프롬프트와 유저 프롬프트의 역할 구분 :
# - 시스템 프롬프트 : 어떤 존재인지, 어떻게 말해야하는지를 정의 (불변)
# - 유저 프롬프트 : "오늘 이 사용자게에 필요한 구체적인 날씨 데이터"를 전달 (매 요청마다 변경)

def build_user_prompt(request: WeatherBriefingRequest) -> str:
    """
    날씨 브리핑 요청 데이터를 Gemini 유저 프롬프트 문자열로 변환합니다.

    Args:
        request (WeatherBriefingRequest): BE에서 전달받은 요청 데이터.
            - cold_sensitivity: 사용자 체질 Enum
            - weather: 날씨 데이터 객체 (온도, 습도, 풍속 등)

    Returns:
        str: Gemini Generate_content_async()의 contents에 전달할 유저 메시지.
    """

    w = request.weather # 가독성을 위해 weather 객체를 짧게 alias 처리

    # Enum 값 (VERY_COLD)을 자연어 설명으로 변환
    sensitivity_desc = _SENSITIVITY_DESCRIPTION[request.cold_sensitivity]

    # Enum 값 (VERY_COLD)을 자연어 설명으로 변환
    # 단위(°C, %, m/s, mm/h)를 명시하여 LLM이 수치의 의미를 정확히 파악하도록 한다.
    return f"""
아래는 오늘의 날씨 정보와 사용자 체질 정보입니다. 이를 바탕으로 날씨 브리핑을 생성해주세요.

## 사용자 체질
{sensitivity_desc}
 
## 오늘의 날씨
- 현재 기온: {w.temperature}°C
- 체감 온도: {w.feels_like}°C
- 날씨 상태: {w.condition}
- 습도: {w.humidity}%
- 풍속: {w.wind_speed}m/s
- 강수량: {w.precipitation}mm/h
- 미세먼지: {w.air_quality.value}
 
위 정보를 종합하여, 사용자의 체질을 반드시 반영한 JSON 형식의 날씨 브리핑을 작성해주세요.
""".strip()

















