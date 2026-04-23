from fastapi import FastAPI

app = FastAPI(
    title="Dayleaf AI",
    description="Dayleaf AI 서버 - 날씨 브리핑 및 개인화 서비스",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "dayleaf-ai"}