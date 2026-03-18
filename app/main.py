from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine
from app.routes.router import router
from app.models.user import User
from app.models.repo import Repo
from app.models.embedding import CodeEmbedding

Base.metadata.create_all(bind=engine)  # Tabloları oluştur

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)