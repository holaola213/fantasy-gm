from fastapi import FastAPI

from app.health.router import router as health_router
from app.players.router import router as players_router

app = FastAPI(title="Fantasy GM API")
app.include_router(health_router)
app.include_router(players_router)
