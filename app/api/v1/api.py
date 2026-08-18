from fastapi import APIRouter
from app.api.v1.endpoints import api_keys, auth, webhooks

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["API Keys"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])