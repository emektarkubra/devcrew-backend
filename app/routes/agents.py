from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.documentation_history import DocumentationHistory
from app.models.user import User
from app.models.code_query_history import CodeQueryHistory
from app.routes.users import get_current_user_id
from app.services.agents.documentation import generate_documentation
from app.services.agents.indexer import index_repo
from app.services.agents.codebase_qa import codebase_qa
from app.core.exceptions import UserNotFoundError, AppError
from app.schemas.agents import (
    ApplyFixRequest, IndexRequest, IndexResponse,
    QARequest, QAResponse,
    HistoryRequest, HistoryItemResponse,
    PRReviewRequest, PRHistoryRequest, DebugRequest,
    DebugHistoryRequest, DocumentationRequest,
    DocumentationHistoryRequest, RepoFilesRequest,
    TestGeneratorRequest, TestHistoryRequest, ApplyFixesToBranchRequest
)
from app.services.agents.pr_review import generate_fixes, pr_review, apply_fixes_to_branch
from app.models.pr_review_history import PrReviewQueryHistory
from app.services.agents.debugging import debug_error
from app.models.debug_history import DebugHistory
from app.services.repo_service import fetch_all_repo_files
from app.services.agents.test_generator import generate_tests
from app.models.test_history import TestHistory

router = APIRouter(prefix="/agents")


# index
@router.post("/index", response_model=IndexResponse)
async def index_repository(payload: IndexRequest, db: Session = Depends(get_db)):
    user_id = get_current_user_id(payload.token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    try:
        return await index_repo(
            access_token = user.access_token,
            owner        = payload.owner,
            repo         = payload.repo,
            user_id      = user.id,
            db           = db,
        )
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "INDEX_ERROR",
            message     = "An error occurred while indexing the repository.",
            status_code = 500,
            details     = {"owner": payload.owner, "repo": payload.repo},
        ) from e


# codebase-qa
@router.post("/codebase-qa", response_model=QAResponse)
async def qa(payload: QARequest, db: Session = Depends(get_db)):
    user_id = get_current_user_id(payload.token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    try:
        return await codebase_qa(
            query   = payload.query,
            owner   = payload.owner,
            repo    = payload.repo,
            user_id = user.id,
            db      = db,
        )
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "CODEBASE_QA_ERROR",
            message     = "An error occurred while processing the codebase Q&A.",
            status_code = 500,
            details     = {"owner": payload.owner, "repo": payload.repo},
        ) from e


@router.post("/codebase-qa/history", response_model=List[HistoryItemResponse])
async def qa_history(payload: HistoryRequest, db: Session = Depends(get_db)):
    user_id   = get_current_user_id(payload.token)
    repo_full = f"{payload.owner}/{payload.repo}"

    try:
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
                response   = h.response,
                filesFound = h.file_count,
                files      = h.files or [],
                timeAgo    = h.created_at,
            )
            for h in history
]
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "CODEBASE_QA_HISTORY_ERROR",
            message     = "An error occurred while fetching Q&A history.",
            status_code = 500,
            details     = {"repo": repo_full},
        ) from e


# pr-review
@router.post("/pr-review")
async def review_pr(payload: PRReviewRequest, db: Session = Depends(get_db)):
    user_id = get_current_user_id(payload.token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    try:
        return await pr_review(
            owner        = payload.owner,
            repo         = payload.repo,
            pr_number    = payload.pr_number,
            user_id      = user.id,
            access_token = user.access_token,
            db           = db,
        )
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "PR_REVIEW_ERROR",
            message     = "An error occurred while reviewing the pull request.",
            status_code = 500,
            details     = {"owner": payload.owner, "repo": payload.repo, "pr_number": payload.pr_number},
        ) from e


@router.post("/pr-review/history")
async def pr_review_history(payload: PRHistoryRequest, db: Session = Depends(get_db)):
    user_id   = get_current_user_id(payload.token)
    repo_full = f"{payload.owner}/{payload.repo}"

    try:
        history = (
            db.query(PrReviewQueryHistory)
            .filter(
                PrReviewQueryHistory.user_id == user_id,
                PrReviewQueryHistory.repo    == repo_full,
            )
            .order_by(PrReviewQueryHistory.created_at.desc())
            .limit(20)
            .all()
        )

        return [
            {
                "pr":           f"#{h.pr_number}",
                "title":        h.pr_title,
                "riskScore":    h.risk_score,
                "issueCount":   h.issue_count,
                "issues":       h.issues,
                "diff":         h.diff,
                "files":        h.files,
                "summary":      h.summary,
                "changedFiles": len(h.files) if h.files else 0,
                "timeAgo":      h.created_at,
            }
            for h in history
        ]
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "PR_REVIEW_HISTORY_ERROR",
            message     = "An error occurred while fetching PR review history.",
            status_code = 500,
            details     = {"repo": repo_full},
        ) from e


# debugging
@router.post("/debug")
async def debug(payload: DebugRequest, db: Session = Depends(get_db)):
    user_id = get_current_user_id(payload.token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    try:
        return await debug_error(
            error   = payload.error,
            owner   = payload.owner,
            repo    = payload.repo,
            user_id = user.id,
            db      = db,
        )
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "DEBUG_ERROR",
            message     = "An error occurred while debugging the error.",
            status_code = 500,
            details     = {"owner": payload.owner, "repo": payload.repo},
        ) from e


@router.post("/debug/history")
async def debug_history(payload: DebugHistoryRequest, db: Session = Depends(get_db)):
    user_id   = get_current_user_id(payload.token)
    repo_full = f"{payload.owner}/{payload.repo}"

    try:
        history = (
            db.query(DebugHistory)
            .filter(
                DebugHistory.user_id == user_id,
                DebugHistory.repo    == repo_full,
            )
            .order_by(DebugHistory.created_at.desc())
            .limit(20)
            .all()
        )

        return [
            {
                "error":         h.error,
                "rootCause":     h.root_cause,
                "severity":      h.severity,
                "affectedFiles": h.affected_files,
                "fix":           h.fix,
                "explanation":   h.explanation,
                "resolved":      h.resolved,
                "timeAgo":       h.created_at,
            }
            for h in history
        ]
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "DEBUG_HISTORY_ERROR",
            message     = "An error occurred while fetching debug history.",
            status_code = 500,
            details     = {"repo": repo_full},
        ) from e


# test generator
@router.post("/test-generator")
async def test_generator(payload: TestGeneratorRequest, db: Session = Depends(get_db)):
    user_id = get_current_user_id(payload.token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    try:
        return await generate_tests(
            target       = payload.target,
            owner        = payload.owner,
            repo         = payload.repo,
            user_id      = user.id,
            framework    = payload.framework,
            access_token = user.access_token,
            db           = db,
        )
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "TEST_GENERATOR_ERROR",
            message     = "An error occurred while generating tests.",
            status_code = 500,
            details     = {"owner": payload.owner, "repo": payload.repo, "target": payload.target},
        ) from e


@router.post("/test-generator/history")
async def test_generator_history(payload: TestHistoryRequest, db: Session = Depends(get_db)):
    user_id   = get_current_user_id(payload.token)
    repo_full = f"{payload.owner}/{payload.repo}"

    try:
        history = (
            db.query(TestHistory)
            .filter(
                TestHistory.user_id == user_id,
                TestHistory.repo    == repo_full,
            )
            .order_by(TestHistory.created_at.desc())
            .limit(20)
            .all()
        )

        return [
            {
                "target":    h.target,
                "testCount": h.test_count,
                "coverage":  h.coverage,
                "tests":     h.tests,
                "framework": h.framework,
                "timeAgo":   h.created_at,
            }
            for h in history
        ]
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "TEST_HISTORY_ERROR",
            message     = "An error occurred while fetching test history.",
            status_code = 500,
            details     = {"repo": repo_full},
        ) from e


# documentation
@router.post("/documentation")
async def generate_docs(payload: DocumentationRequest, db: Session = Depends(get_db)):
    user_id = get_current_user_id(payload.token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    try:
        return await generate_documentation(
            target       = payload.target,
            owner        = payload.owner,
            repo         = payload.repo,
            doc_type     = payload.doc_type,
            user_id      = user.id,
            db           = db,
            access_token = user.access_token,
        )
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "DOCUMENTATION_ERROR",
            message     = "An error occurred while generating documentation.",
            status_code = 500,
            details     = {"owner": payload.owner, "repo": payload.repo, "target": payload.target},
        ) from e


@router.post("/documentation/history")
async def documentation_history(payload: DocumentationHistoryRequest, db: Session = Depends(get_db)):
    user_id   = get_current_user_id(payload.token)
    repo_full = f"{payload.owner}/{payload.repo}"

    try:
        history = (
            db.query(DocumentationHistory)
            .filter(
                DocumentationHistory.user_id == user_id,
                DocumentationHistory.repo    == repo_full,
            )
            .order_by(DocumentationHistory.created_at.desc())
            .limit(20)
            .all()
        )

        return [
            {
                "target":      h.target,
                "docType":     h.doc_type,
                "description": h.description,
                "content":     h.content,
                "timeAgo":     h.created_at,
            }
            for h in history
        ]
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "DOCUMENTATION_HISTORY_ERROR",
            message     = "An error occurred while fetching documentation history.",
            status_code = 500,
            details     = {"repo": repo_full},
        ) from e


# repo files
@router.post("/repo-files")
async def repo_files(payload: RepoFilesRequest, db: Session = Depends(get_db)):
    user_id = get_current_user_id(payload.token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    try:
        files = await fetch_all_repo_files(
            access_token = user.access_token,
            owner        = payload.owner,
            repo         = payload.repo,
        )
        return {"files": files}
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "REPO_FILES_ERROR",
            message     = "An error occurred while fetching repository files.",
            status_code = 500,
            details     = {"owner": payload.owner, "repo": payload.repo},
        ) from e


# apply fixes
@router.post("/pr-review/apply-fixes")
async def apply_fixes_endpoint(payload: ApplyFixRequest, db: Session = Depends(get_db)):
    user_id = get_current_user_id(payload.token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    try:
        return await generate_fixes(
            access_token = user.access_token,
            owner        = payload.owner,
            repo         = payload.repo,
            pr_number    = payload.pr_number,
            issues       = payload.issues,
        )
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "APPLY_FIX_ERROR",
            message     = "An error occurred while generating fixes.",
            status_code = 500,
            details     = {"error": str(e)},
        ) from e


@router.post("/pr-review/apply-fixes-to-branch")
async def apply_fixes_to_branch_endpoint(payload: ApplyFixesToBranchRequest, db: Session = Depends(get_db)):
    user_id = get_current_user_id(payload.token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    try:
        return await apply_fixes_to_branch(
            access_token = user.access_token,
            owner        = payload.owner,
            repo         = payload.repo,
            pr_number    = payload.pr_number,
            fixes        = payload.fixes,
        )
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "APPLY_FIX_TO_BRANCH_ERROR",
            message     = "An error occurred while applying fixes to branch.",
            status_code = 500,
            details     = {"error": str(e)},
        ) from e