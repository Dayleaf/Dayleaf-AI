from app.schema.weather import WeatherBriefingRequest, WeatherBriefingResponse, IconCode, Clothing


async def get_weather_briefing(request: WeatherBriefingRequest) -> WeatherBriefingResponse:
    """
    날씨 브리핑을 생성
    현재는 Mock 고정값을 반환
    TODO: Gemini 연동 시 이 함수 내부를 교체하기
    """
    return WeatherBriefingResponse(
        message="오늘은 구름이 제법 많이 끼어 있네요. 나서실 때는 얇은 외투 하나 챙기시는 게 좋을 것 같아요. 체감 온도가 실제보다 조금 낮아요.",
        icon_code=IconCode.CLOUDY,
        clothing=[Clothing.LONG_SLEEVE, Clothing.LIGHT_JACKET],
    )