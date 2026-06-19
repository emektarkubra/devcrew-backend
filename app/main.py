from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine
from app.routes.router import router
from app.core.config import settings
from app.models.user import User
from app.models.repo import Repo
from app.models.embedding import CodeEmbedding
from app.models.code_query_history import CodeQueryHistory
from app.models.pr_review_history import PrReviewQueryHistory
from app.models import team_mode_history
from app.core.error_handlers import register_exception_handlers
from sqlalchemy import text


# # create_all'dan önce ekle
with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    conn.commit()

Base.metadata.create_all(bind=engine)

app = FastAPI()


# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[
#         settings.FRONTEND_URL,
#         "https://devcrew-web.vercel.app",
#     ],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://devcrew-web.vercel.app",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(router)
