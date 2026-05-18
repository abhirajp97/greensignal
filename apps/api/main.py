"""GreenSignal API — FastAPI application entry point."""
from fastapi import FastAPI

from apps.api.routes import coffee, health

app = FastAPI(title="GreenSignal", version="0.1.0")

app.include_router(health.router)
app.include_router(coffee.router, prefix="/coffee")
