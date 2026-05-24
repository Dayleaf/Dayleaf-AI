# Dayleaf AI Server

[![CI](https://github.com/Dayleaf/Dayleaf-AI/actions/workflows/ci.yml/badge.svg?branch=develop)](https://github.com/Dayleaf/Dayleaf-AI/actions/workflows/ci.yml)

🌿 Dayleaf의 AI 서버입니다.
`Python` + `FastAPI` 기반으로 구성되어 있으며, Gemini 1.5 Flash를 활용한 날씨 브리핑 서비스를 제공합니다.

## 기술 스택

- Python 3.11
- FastAPI
- Gemini 2.5 Flash

## 로컬 개발환경 실행 가이드

### 1. 레포지토리 클론

```bash
git clone https://github.com/Dayleaf/Dayleaf-AI.git
cd Dayleaf-AI
```

### 2. 가상환경 생성 및 활성화

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어 아래 값을 채워주세요.

```env
GEMINI_API_KEY=발급받은_키_입력
```

### 5. 서버 실행

```bash
uvicorn main:app --reload
```

### 6. 헬스체크
GET http://localhost:8000/health

### 7. API 문서
http://localhost:8000/docs

---

## Docker 실행 가이드

### 1. 환경변수 설정

로컬 개발 가이드의 4번과 동일하게 `.env` 파일을 준비해주세요.

```bash
cp .env.example .env
# .env 파일을 열어 GEMINI_API_KEY 값을 채워주세요.
```

### 2. 컨테이너 빌드 및 실행

```bash
docker-compose up --build
```

### 3. 헬스체크
GET http://localhost:8000/health

### 4. 컨테이너 종료

```bash
docker-compose down
```
