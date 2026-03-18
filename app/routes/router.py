from fastapi import APIRouter
from app.routes.health import router as health_router
from app.routes.users import router as users
from app.routes.agents import router as agents

router = APIRouter()

router.include_router(health_router, tags=["health"])
router.include_router(users, tags=["github"])
router.include_router(agents, tags=["agents"])
