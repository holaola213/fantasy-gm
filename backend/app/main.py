from fastapi import FastAPI

from app.drafts.router import router as drafts_router
from app.health.router import router as health_router
from app.leagues.router import router as leagues_router
from app.players.router import router as players_router
from app.projections.router import router as projections_router
from app.valuations.router import router as valuations_router

app = FastAPI(title="Fantasy GM API")
app.include_router(health_router)
app.include_router(leagues_router)
app.include_router(players_router)
app.include_router(projections_router)
app.include_router(drafts_router)
app.include_router(valuations_router)
