"""FastAPI application with routers and CORS."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.routers.health_service import health_router
from backend.routers.chat_service import chat_router

load_dotenv()

FRONTEND_PORT = os.getenv('FRONTEND_PORT', '5173')
PORT = os.getenv('PORT', '8000')

app = FastAPI(title='Kalli — Onboarding Assistant')

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f'http://localhost:{FRONTEND_PORT}',
        f'http://localhost:{PORT}',
    ],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(health_router, prefix='/api/v1')
app.include_router(chat_router, prefix='/api/v1')


@app.on_event('startup')
def on_startup():
    from backend.db import engine
    from database.tables import Base
    Base.metadata.create_all(bind=engine)
