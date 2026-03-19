from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.user import User
from app.models.code_query_history import CodeQueryHistory
from app.routes.users import get_current_user_id
from app.services.agents.indexer import index_repo
from app.services.agents.codebase_qa import codebase_qa
from app.core.exceptions import UserNotFoundError
from app.schemas.agents import (
    IndexRequest, IndexResponse,
    QARequest, QAResponse,
    HistoryRequest, HistoryItemResponse,
)

router = APIRouter(prefix="/agents")


# repo index
@router.post("/index", response_model=IndexResponse)
async def index_repository(payload: IndexRequest, db: Session = Depends(get_db)):
    user_id = get_current_user_id(payload.token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    return await index_repo(
        access_token = user.access_token,
        owner        = payload.owner,
        repo         = payload.repo,
        user_id      = user.id,
        db           = db,
    )


# codebase-qa query
@router.post("/codebase-qa", response_model=QAResponse)
async def qa(payload: QARequest, db: Session = Depends(get_db)):
    user_id = get_current_user_id(payload.token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    return await codebase_qa(
        query   = payload.query,
        owner   = payload.owner,
        repo    = payload.repo,
        user_id = user.id,
        db      = db,
    )


# codebase-qa history
@router.post("/codebase-qa/history", response_model=List[HistoryItemResponse])
async def qa_history(payload: HistoryRequest, db: Session = Depends(get_db)):
    user_id   = get_current_user_id(payload.token)
    repo_full = f"{payload.owner}/{payload.repo}"

    history = (
        db.query(CodeQueryHistory)
        .filter(
            CodeQueryHistory.user_id == user_id,
            CodeQueryHistory.repo    == repo_full,
        )
        .order_by(CodeQueryHistory.created_at.desc())
        .limit(20)
        .all()
    )

    return [
        HistoryItemResponse(
            question   = h.query,
            filesFound = h.file_count,
            timeAgo    = h.created_at,
        )
        for h in history
    ]