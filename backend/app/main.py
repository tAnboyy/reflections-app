"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, Base
from app.routes import modules, config, chat, analytics


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (good enough for prototype)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Reflection Chatbot API",
    description="Minimal academic prototype — AI-powered reflection chatbot",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(modules.router)
app.include_router(config.router)
app.include_router(chat.router)
app.include_router(analytics.router)


@app.get("/health")
def health():
    return {"status": "ok"}
