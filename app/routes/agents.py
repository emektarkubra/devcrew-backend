# app/routes/agents.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.models.user import User
from app.routes.users import get_current_user_id
from app.services.agents.indexer import index_repo
from app.services.agents.codebase_qa import codebase_qa

router = APIRouter(prefix="/agents")


class IndexPayload(BaseModel):
    token: str
    owner: str
    repo:  str


class QAPayload(BaseModel):
    token: str
    owner: str
    repo:  str
    query: str


# repoyu indeksler
@router.post("/index")
async def index_repository(payload: IndexPayload, db: Session = Depends(get_db)):
    user_id = get_current_user_id(payload.token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    return await index_repo(
        access_token = user.access_token,
        owner        = payload.owner,
        repo         = payload.repo,
        user_id      = user.id,
        db           = db,
    )


# code-base 
@router.post("/codebase-qa")
async def qa(payload: QAPayload, db: Session = Depends(get_db)):
    user_id = get_current_user_id(payload.token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    return await codebase_qa(
        query    = payload.query,
        owner    = payload.owner,
        repo     = payload.repo,
        user_id  = user.id,
        db       = db,
    )