from fastapi import APIRouter

from app.api.routes import documents, health, intelligence, knowledge_bases, media, rag

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(knowledge_bases.router)
api_router.include_router(documents.router)
api_router.include_router(rag.router)
api_router.include_router(intelligence.router)
api_router.include_router(media.router)
