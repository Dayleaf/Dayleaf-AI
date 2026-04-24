from enum import Enum
from pydantic import BaseModel


# Enum 정의
class ColdSensitivity(str, Enum):
    VERY_COLD = "VERY_COLD"
    COLD = "COLD"
    NORMAL = "NORMAL"
    WARM = "WARM"
    VERY_WARM = "VERY_WARM"


class IconCode(str, Enum):
    SUNNY = "SUNNY"
    PARTLY_CLOUDY = "PARTLY_CLOUDY"
    CLOUDY = "CLOUDY"
    RAINY = "RAINY"
    HEAVY_RAIN = "HEAVY_RAIN"
    SNOWY = "SNOWY"
    HEAVY_SNOW = "HEAVY_SNOW"
    THUNDERSTORM = "THUNDERSTORM"
    FOGGY = "FOGGY"
    YELLOW_DUST = "YELLOW_DUST"
    TYPHOON = "TYPHOON"


class AirQuality(str, Enum):
    GOOD = "GOOD"
    MODERATE = "MODERATE"
    BAD = "BAD"
    VERY_BAD = "VERY_BAD"


class Clothing(str, Enum):
    T_SHIRT = "T_SHIRT"
    LONG_SLEEVE = "LONG_SLEEVE"
    LIGHT_JACKET = "LIGHT_JACKET"
    JACKET = "JACKET"
    COAT = "COAT"
    PADDED_JACKET = "PADDED_JACKET"
    JEANS = "JEANS"
    SHORTS = "SHORTS"
    UMBRELLA = "UMBRELLA"
    SUNSCREEN = "SUNSCREEN"
    MASK = "MASK"


# 중첩 모델
class WeatherData(BaseModel):
    temperature: float
    feels_like: float
    condition: str
    humidity: int
    wind_speed: float
    air_quality: AirQuality
    precipitation: float = 0.0


# 요청 스키마
class WeatherBriefingRequest(BaseModel):
    member_id: int
    cold_sensitivity: ColdSensitivity
    weather: WeatherData


# 응답 스키마
class WeatherBriefingResponse(BaseModel):
    message: str
    icon_code: IconCode
    clothing: list[Clothing]