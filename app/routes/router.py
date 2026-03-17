from fastapi import APIRouter
from app.routes.health import router as health_router
from app.routes.user_routes import router as user_router

router = APIRouter()

router.include_router(health_router, tags=["health"])
router.include_router(user_router, tags=["github"])
