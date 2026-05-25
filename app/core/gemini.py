# Gemini API 키를 로드하고 google-genai 클라이언트를 초기화한다.
# 이 모듈의 책임은 인증 설정까지이다.

import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")

# 새 SDK는 genai.configure() 대신 Client 객체로 인증한다.
# 이 client 인스턴스를 service 레이어에서 import해서 사용한다.
client = genai.Client(api_key=GEMINI_API_KEY)