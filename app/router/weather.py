from fastapi import APIRouter
from app.schema.weather import WeatherBriefingRequest, WeatherBriefingResponse
from app.service.weather import get_weather_briefing

router = APIRouter(prefix="/api/v1/weather", tags=["weather"])


@router.post("/briefing", response_model=WeatherBriefingResponse)
async def weather_briefing(request: WeatherBriefingRequest) -> WeatherBriefingResponse:
    return await get_weather_briefing(request)