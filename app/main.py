from fastapi import FastAPI
from app.routes.router import api_router
from app.core.database import Base, engine

Base.metadata.create_all(bind=engine)  # Tabloları oluştur

app = FastAPI(title="MyAPI")
app.include_router(api_router)