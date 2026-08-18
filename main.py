"""
Application entry point.
Run with: uvicorn main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import engine
from app.models import Base
from app.api.routes import router

# Create all tables on startup (dev convenience; use Alembic for production)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Odysseus Cruise Booking API",
    description=(
        "Book cruise holidays with Odysseus. Find a cruise, specify passengers, "
        "choose optional extras, apply promo codes, and confirm your booking."
    ),
    version="1.0.0",
    contact={"name": "Odysseus Support"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(router, prefix="/api/v1")

# Serve UI static files
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

