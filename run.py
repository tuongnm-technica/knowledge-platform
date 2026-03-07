import uvicorn
from config.settings import settings

if __name__ == "__main__":
    uvicorn.run(
        "apps.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )