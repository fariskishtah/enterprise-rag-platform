from fastapi import APIRouter

from app.api.routes import (
    auth,
    demo,
    documents,
    evaluation,
    feedback,
    health,
    intelligence,
    knowledge_bases,
    media,
    rag,
    templates,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(knowledge_bases.router)
api_router.include_router(documents.router)
api_router.include_router(rag.router)
api_router.include_router(intelligence.router)
api_router.include_router(media.router)
api_router.include_router(evaluation.router)
api_router.include_router(feedback.router)
api_router.include_router(templates.router)
api_router.include_router(demo.router)
