# 배포 가이드 — OCI Docker 수동 배포

> Dayleaf-AI 서버를 OCI(Oracle Cloud Infrastructure) 인스턴스에 Docker로 수동 배포하는 절차입니다.

---

## 배포 환경

| 항목 | 값 |
|------|-----|
| 플랫폼 | OCI (Oracle Cloud Infrastructure) |
| 인스턴스 | Ampere A1 (ARM / aarch64) |
| 배포 방식 | Docker + docker compose (수동) |
| 배포 브랜치 | `develop` |
| 서비스 포트 | `8000` |

> **ARM 아키텍처 주의**: Ampere A1은 ARM64 환경입니다.
> x86에서 빌드한 이미지는 호환되지 않으므로, 이미지는 **인스턴스 내부에서 직접 빌드**합니다.

---

## 사전 준비 (최초 1회)

### 1. 인스턴스 환경 확인

```bash
# Docker / Compose 설치 확인
docker --version
docker compose version

# 8000 포트 충돌 여부 확인 (출력이 없으면 사용 가능)
sudo ss -tlnp | grep :8000
```

### 2. 레포지토리 클론

```bash
cd ~
git clone https://github.com/Dayleaf/Dayleaf-AI.git
cd Dayleaf-AI
```

### 3. 환경변수 설정

```bash
cp .env.example .env
nano .env   # GEMINI_API_KEY 값을 실제 키로 교체
```

`.env`는 `.gitignore` / `.dockerignore`로 제외되어 git·이미지에 포함되지 않습니다.
주입 후 형식만 확인(키 값은 마스킹):

```bash
cat .env | sed 's/=.*/=****/'
# 출력: GEMINI_API_KEY=****
```

---

## 배포 실행

```bash
# 백그라운드(-d)로 빌드 및 실행
# restart: unless-stopped 설정으로 인스턴스 재부팅 후에도 자동 기동된다.
docker compose up -d --build

# 컨테이너 상태 확인 (STATUS가 Up이어야 정상)
docker compose ps
```

---

## 외부 접근 설정

서버를 외부(백엔드 팀)에서 호출하려면 **OCI 보안 목록**에 8000 포트 유입 규칙을 추가합니다.

**OCI 콘솔 경로**: Networking → Virtual Cloud Networks → (VCN 선택) → Security Lists → Add Ingress Rules

| 항목 | 값 |
|------|-----|
| Source Type | CIDR |
| Source CIDR | `0.0.0.0/0` (검증용 / 운영 시 백엔드 서버 IP로 축소 권장) |
| IP Protocol | TCP |
| Destination Port Range | `8000` |

> 인스턴스 내부 방화벽(iptables)은 기존 규칙에 전체 허용(`ACCEPT all`)이 포함되어 있어
> 별도 수정 없이 보안 목록 개방만으로 외부 접근이 가능합니다.
> 운영 환경이 다를 경우 iptables 규칙을 별도 점검해야 합니다.

---

## 동작 검증

### 헬스체크 (내부)

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"dayleaf-ai"}
```

### 헬스체크 (외부 — 로컬 PC에서)

```bash
curl http://<인스턴스_공인_IP>:8000/health
# {"status":"ok","service":"dayleaf-ai"}
```

### 브리핑 엔드포인트 (Gemini 실호출)

```bash
curl -X POST http://<인스턴스_공인_IP>:8000/api/v1/weather/briefing \
  -H "Content-Type: application/json" \
  -d '{
    "member_id": 1,
    "cold_sensitivity": "VERY_COLD",
    "weather": {
      "temperature": 12.5, "feels_like": 9.0, "condition": "흐림",
      "humidity": 70, "wind_speed": 3.2, "precipitation": 2.5,
      "air_quality": "MODERATE"
    }
  }'
```

> Gemini 서버 혼잡 시 `503 UNAVAILABLE`(`GEMINI_API_ERROR`)이 반환될 수 있습니다.
> 이는 일시적 현상으로, 잠시 후 재호출하면 정상 응답이 옵니다.

---

## 운영 명령어

```bash
docker compose ps              # 상태 확인
docker compose logs -f         # 실시간 로그
docker compose down            # 중지
docker compose up -d --build   # 재배포 (코드 업데이트 후)
```

코드 업데이트 시:

```bash
cd ~/Dayleaf-AI
git pull origin develop
docker compose up -d --build
```
