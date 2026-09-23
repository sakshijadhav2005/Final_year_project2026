from fastapi import APIRouter

from app.api.v1 import admin, auth, chat, content, events, health, jobs, uploads

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(uploads.router)
api_router.include_router(jobs.router)
api_router.include_router(content.router)
api_router.include_router(events.router)
api_router.include_router(chat.router)
api_router.include_router(admin.router)
