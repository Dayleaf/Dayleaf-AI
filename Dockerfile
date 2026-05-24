# Python 3.11 slim 이미지를 베이스로 사용
# slim: 불필요한 OS 패키지를 제거한 경량 이미지 (보안 + 용량 최적화)
FROM python:3.11-slim

# 컨테이너 내 작업 디렉토리 설정
WORKDIR /app

# 의존성 파일만 먼저 복사 후 설치
# 이유: requirements.txt가 변경되지 않으면 이 레이어는 캐시를 재사용한다.
#       소스 코드가 바뀌어도 의존성 재설치를 생략해 빌드 속도를 높인다.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사 (.dockerignore에서 제외된 파일은 복사되지 않음)
COPY . .

# FastAPI 서버가 사용하는 포트 명시 (문서화 목적, 실제 포트 바인딩은 docker-compose에서 담당)
EXPOSE 8000

# 컨테이너 실행 시 uvicorn 서버 시작
# --host 0.0.0.0: 컨테이너 외부에서 접근 가능하도록 모든 인터페이스에 바인딩
# --port 8000: 명시적 포트 지정
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]