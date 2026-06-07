# API Contract — Spring Boot ↔ AI 서버

> **설계 원칙**: Spring Boot가 날씨 API를 호출하여 날씨 데이터를 정제한 후 AI 서버로 전달합니다.
> AI 서버는 오직 Gemini 프롬프팅과 응답 파싱에만 집중합니다.

---

## 1. 날씨 브리핑 생성

**`POST /api/v1/weather/briefing`**

### 요청 (Spring Boot → AI 서버)

```json
{
  "member_id": 1,
  "cold_sensitivity": "VERY_COLD",
  "weather": {
    "temperature": 12.5,
    "feels_like": 9.0,
    "condition": "흐림",
    "humidity": 70,
    "wind_speed": 3.2,
    "precipitation": 2.5,
    "air_quality": "MODERATE"
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `member_id` | integer | 회원 ID |
| `cold_sensitivity` | enum | 사용자 체질 |
| `weather.temperature` | float | 현재 기온 (°C) |
| `weather.feels_like` | float | 체감 온도 (°C) |
| `weather.condition` | string | 날씨 상태 (예: 맑음, 흐림, 비) |
| `weather.humidity` | integer | 습도 (0~100%) |
| `weather.wind_speed` | float | 풍속 (m/s) |
| `weather.precipitation` | float | 강수량 (mm/h), 없으면 0.0 |
| `weather.air_quality` | enum | 미세먼지 등급 |

### 응답 (AI 서버 → Spring Boot)

**`200 OK`**

```json
{
  "message": "오늘은 구름이 제법 많이 끼어 있네요. 나서실 때는 얇은 외투 하나 챙기시는 게 좋을 것 같아요. 체감 온도가 실제보다 조금 낮으니, 오늘은 따뜻한 음료 한 잔 곁에 두시길 권해드립니다.",
  "icon_code": "CLOUDY",
  "clothing": ["LONG_SLEEVE", "LIGHT_JACKET"]
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `message` | string | 사서 톤의 날씨 브리핑 메시지 |
| `icon_code` | enum | 날씨 아이콘 코드 |
| `clothing` | enum[] | 추천 의류 목록 |

---

## 2. 에러 응답 공통 포맷

모든 에러는 아래 형식으로 반환됩니다.

```json
{
  "error_code": "INVALID_REQUEST",
  "message": "요청 형식이 올바르지 않습니다."
}
```

| `error_code` | HTTP Status | 설명 |
|---|---|---|
| `INVALID_REQUEST` | 422 | 요청 스키마 오류 |
| `GEMINI_AUTH_ERROR` | 401 | Gemini API 키 인증 실패 |
| `GEMINI_API_ERROR` | 502 | Gemini API 호출 실패 |
| `GEMINI_PARSE_ERROR` | 502 | Gemini 응답 파싱 실패 |
| `GEMINI_TIMEOUT` | 504 | Gemini 응답 타임아웃 |
| `INTERNAL_SERVER_ERROR` | 500 | 예상치 못한 서버 오류 |

---

## 3. 구현 상태 안내

`POST /api/v1/weather/briefing`은 **Gemini 실호출로 구현 완료**되었습니다.
더 이상 고정값(Mock)을 반환하지 않으며, 요청 데이터를 바탕으로 실제 브리핑을 생성합니다.

- **모델**: `gemini-2.5-flash`
- **응답**: 위 2번 응답 예시와 동일한 형식의 실시간 생성 결과
- **배포**: OCI 인스턴스에 배포되어 동작 중입니다.
  실제 호출 주소 및 배포 절차는 [배포 가이드](./deployment.md)를 참고하세요.

> Gemini 서버 혼잡 시 일시적으로 `503`(`GEMINI_API_ERROR`)이 반환될 수 있으며,
> 잠시 후 재호출하면 정상 응답이 옵니다.
> 
---

## 4. Enum 정의

### ColdSensitivity — 사용자 체질

| 값 | 설명 |
|---|---|
| `VERY_COLD` | 추위를 많이 탐 |
| `COLD` | 추위를 타는 편 |
| `NORMAL` | 보통 |
| `WARM` | 더위를 타는 편 |
| `VERY_WARM` | 더위를 많이 탐 |

### IconCode — 날씨 아이콘 코드

| 값 | 설명 |
|---|---|
| `SUNNY` | 맑음 |
| `PARTLY_CLOUDY` | 구름 조금 |
| `CLOUDY` | 흐림 |
| `RAINY` | 비 |
| `HEAVY_RAIN` | 폭우 |
| `SNOWY` | 눈 |
| `HEAVY_SNOW` | 폭설 |
| `THUNDERSTORM` | 천둥번개 |
| `FOGGY` | 안개 |
| `YELLOW_DUST` | 황사 |
| `TYPHOON` | 태풍 |

### AirQuality — 미세먼지 등급

| 값 | 설명 |
|---|---|
| `GOOD` | 좋음 |
| `MODERATE` | 보통 |
| `BAD` | 나쁨 |
| `VERY_BAD` | 매우 나쁨 |

### Clothing — 추천 의류

| 값 | 설명 |
|---|---|
| `T_SHIRT` | 반팔 티셔츠 |
| `LONG_SLEEVE` | 긴소매 |
| `LIGHT_JACKET` | 얇은 외투 |
| `JACKET` | 재킷 |
| `COAT` | 코트 |
| `PADDED_JACKET` | 패딩 |
| `JEANS` | 청바지 |
| `SHORTS` | 반바지 |
| `UMBRELLA` | 우산 |
| `SUNSCREEN` | 자외선 차단제 |
| `MASK` | 마스크 (황사/미세먼지) |