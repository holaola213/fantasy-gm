from fastapi import FastAPI

from app.health.router import router as health_router

app = FastAPI(title="Fantasy GM API")
app.include_router(health_router)
