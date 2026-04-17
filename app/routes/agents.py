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
from app.core.exceptions import UserNotFoundError, AppError, AIRateLimitError
from app.schemas.agents import (
    ApplyFixRequest, IndexRequest, IndexResponse,
    QARequest, QAResponse,
    HistoryRequest, HistoryItemResponse,
    PRReviewRequest, PRHistoryRequest, DebugRequest,
    DebugHistoryRequest, DocumentationRequest,
    DocumentationHistoryRequest, RepoFilesRequest, SaveTestsRequest,
    TestGeneratorRequest, TestHistoryRequest, ApplyFixesToBranchRequest,
    ApplyDebugFixRequest,
    CheckIndexResponse, PRReviewResponse, PRHistoryItemResponse,
    DebugResponse, DebugHistoryItemResponse, DebugApplyFixResponse,
    TestGeneratorResponse, TestHistoryItemResponse, SaveTestsResponse,
    DocumentationResponse, DocumentationHistoryItemResponse,
    RepoFilesResponse, ApplyFixesResponse, ApplyFixesToBranchResponse, TokenRequest
)
from app.services.agents.pr_review import generate_fixes, pr_review, apply_fixes_to_branch
from app.models.pr_review_history import PrReviewQueryHistory
from app.services.agents.debugging import debug_error, apply_debug_fix_and_open_pr
from app.models.debug_history import DebugHistory
from app.services.repo_service import fetch_all_repo_files
from app.services.agents.test_generator import generate_tests
from app.models.test_history import TestHistory
from app.models.embedding import CodeEmbedding
from app.services.agents.team_mode import run_team_mode
from app.schemas.agents import TeamModeRequest, TeamModeResponse
from fastapi.responses import StreamingResponse
from app.models.team_mode_history import TeamModeHistory
from app.services.agents.architecture import analyze_architecture
from app.services.agents.repo_intelligence import get_repo_intelligence
import asyncio
import json

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
        err_str = str(e).lower()
        if "rate_limit_exceeded" in err_str or "429" in err_str or "rate limit" in err_str:
            raise AIRateLimitError(owner=payload.owner, repo=payload.repo) from e
        raise AppError(
            code        = "INDEX_ERROR",
            message     = f"An error occurred while indexing the repository: {e}",
            status_code = 500,
            details     = {"owner": payload.owner, "repo": payload.repo},
        ) from e


# check-index
@router.post("/check-index", response_model=CheckIndexResponse)
async def check_index(payload: IndexRequest, db: Session = Depends(get_db)):
    user_id   = get_current_user_id(payload.token)
    repo_full = f"{payload.owner}/{payload.repo}"

    count = db.query(CodeEmbedding).filter(
        CodeEmbedding.user_id == user_id,
        CodeEmbedding.repo    == repo_full,
    ).count()

    return {
        "indexed":    count > 0,
        "file_count": db.query(CodeEmbedding.file_path)
            .filter(
                CodeEmbedding.user_id == user_id,
                CodeEmbedding.repo    == repo_full,
            )
            .distinct()
            .count()
    }


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
        err_str = str(e).lower()
        if "rate_limit_exceeded" in err_str or "429" in err_str or "rate limit" in err_str:
            raise AIRateLimitError(owner=payload.owner, repo=payload.repo) from e
        raise AppError(
            code        = "CODEBASE_QA_ERROR",
            message     = f"An error occurred while processing the codebase Q&A: {e}",
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
            message     = f"An error occurred while fetching Q&A history: {e}",
            status_code = 500,
            details     = {"repo": repo_full},
        ) from e


# pr-review
@router.post("/pr-review", response_model=PRReviewResponse)
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
        err_str = str(e).lower()
        if "rate_limit_exceeded" in err_str or "429" in err_str or "rate limit" in err_str:
            raise AIRateLimitError(owner=payload.owner, repo=payload.repo) from e
        raise AppError(
            code        = "PR_REVIEW_ERROR",
            message     = f"An error occurred while reviewing the pull request: {e}",
            status_code = 500,
            details     = {"owner": payload.owner, "repo": payload.repo, "pr_number": payload.pr_number},
        ) from e


@router.post("/pr-review/history", response_model=List[PRHistoryItemResponse])
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
            message     = f"An error occurred while fetching PR review history: {e}",
            status_code = 500,
            details     = {"repo": repo_full},
        ) from e


# debugging
@router.post("/debug", response_model=DebugResponse)
async def debug(payload: DebugRequest, db: Session = Depends(get_db)):
    user_id = get_current_user_id(payload.token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    try:
        return await debug_error(
            error        = payload.error,
            owner        = payload.owner,
            repo         = payload.repo,
            user_id      = user.id,
            access_token = user.access_token,
            db           = db,
        )
    except AppError:
        raise
    except Exception as e:
        err_str = str(e).lower()
        if "rate_limit_exceeded" in err_str or "429" in err_str or "rate limit" in err_str:
            raise AIRateLimitError(owner=payload.owner, repo=payload.repo) from e
        raise AppError(
            code        = "DEBUG_ERROR",
            message     = f"An error occurred while debugging the error: {e}",
            status_code = 500,
            details     = {"owner": payload.owner, "repo": payload.repo},
        ) from e


@router.post("/debug/history", response_model=List[DebugHistoryItemResponse])
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
            "affectedFiles": [
                f["path"] if isinstance(f, dict) else f
                for f in (h.affected_files or [])
            ],
            "issues":        h.issues or [],
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
            message     = f"An error occurred while fetching debug history: {e}",
            status_code = 500,
            details     = {"repo": repo_full},
        ) from e


@router.post("/debug/apply-fix", response_model=DebugApplyFixResponse)
async def debug_apply_fix(payload: ApplyDebugFixRequest, db: Session = Depends(get_db)):
    user_id = get_current_user_id(payload.token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    try:
        return await apply_debug_fix_and_open_pr(
            access_token = user.access_token,
            owner        = payload.owner,
            repo         = payload.repo,
            issues       = payload.issues,
            error        = payload.error,
        )
    except AppError:
        raise
    except Exception as e:
        err_str = str(e).lower()
        if "rate_limit_exceeded" in err_str or "429" in err_str or "rate limit" in err_str:
            raise AIRateLimitError(owner=payload.owner, repo=payload.repo) from e
        raise AppError(
            code        = "DEBUG_APPLY_FIX_ERROR",
            message     = f"An error occurred while applying debug fix: {e}",
            status_code = 500,
            details     = {"error": str(e)},
        ) from e


# test generator
@router.post("/test-generator", response_model=TestGeneratorResponse)
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
        err_str = str(e).lower()
        if "rate_limit_exceeded" in err_str or "429" in err_str or "rate limit" in err_str:
            raise AIRateLimitError(owner=payload.owner, repo=payload.repo) from e
        raise AppError(
            code        = "TEST_GENERATOR_ERROR",
            message     = f"An error occurred while generating tests: {e}",
            status_code = 500,
            details     = {"owner": payload.owner, "repo": payload.repo, "target": payload.target},
        ) from e


@router.post("/test-generator/history", response_model=List[TestHistoryItemResponse])
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
                "mergedCode": h.merged_code,
                "timeAgo":   h.created_at,
            }
            for h in history
        ]
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "TEST_HISTORY_ERROR",
            message     = f"An error occurred while fetching test history: {e}",
            status_code = 500,
            details     = {"repo": repo_full},
        ) from e


@router.post("/test-generator/save", response_model=SaveTestsResponse)
async def save_tests(payload: SaveTestsRequest, db: Session = Depends(get_db)):
    user_id = get_current_user_id(payload.token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    try:
        combined = "\n\n".join([
            f"// {t['name']}\n{t['code']}"
            for t in payload.tests
        ])
        return {
            "content":  combined,
            "filename": payload.filename,
        }
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "SAVE_TESTS_ERROR",
            message     = f"Failed to generate test file: {e}",
            status_code = 500,
            details     = {"error": str(e)},
        ) from e


# documentation
@router.post("/documentation", response_model=DocumentationResponse)
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
        err_str = str(e).lower()
        if "rate_limit_exceeded" in err_str or "429" in err_str or "rate limit" in err_str:
            raise AIRateLimitError(owner=payload.owner, repo=payload.repo) from e
        raise AppError(
            code        = "DOCUMENTATION_ERROR",
            message     = f"An error occurred while generating documentation: {e}",
            status_code = 500,
            details     = {"owner": payload.owner, "repo": payload.repo, "target": payload.target},
        ) from e


@router.post("/documentation/history", response_model=List[DocumentationHistoryItemResponse])
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
            message     = f"An error occurred while fetching documentation history: {e}",
            status_code = 500,
            details     = {"repo": repo_full},
        ) from e


# repo files
@router.post("/repo-files", response_model=RepoFilesResponse)
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
            message     = f"An error occurred while fetching repository files: {e}",
            status_code = 500,
            details     = {"owner": payload.owner, "repo": payload.repo},
        ) from e


# apply fixes
@router.post("/pr-review/apply-fixes", response_model=ApplyFixesResponse)
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
        err_str = str(e).lower()
        if "rate_limit_exceeded" in err_str or "429" in err_str or "rate limit" in err_str:
            raise AIRateLimitError(owner=payload.owner, repo=payload.repo) from e
        raise AppError(
            code        = "APPLY_FIX_ERROR",
            message     = f"An error occurred while generating fixes: {e}",
            status_code = 500,
            details     = {"error": str(e)},
        ) from e


@router.post("/pr-review/apply-fixes-to-branch", response_model=ApplyFixesToBranchResponse)
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
            message     = f"An error occurred while applying fixes to branch: {e}",
            status_code = 500,
            details     = {"error": str(e)},
        ) from e
    

# team mode stream
@router.get("/team-mode/stream")
async def team_mode_stream(
    token:           str,
    owner:           str,
    repo:            str,
    selected_agents: str,
    db: Session = Depends(get_db),
):
    try:
        user_id      = get_current_user_id(token)
        user         = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise UserNotFoundError(user_id=user_id)
        access_token = user.access_token
    except Exception as e:
        raise AppError(code="AUTH_ERROR", message=str(e), status_code=401)

    agents = [a.strip() for a in selected_agents.split(",") if a.strip()]

    async def event_stream():
        from app.services.agents.team_mode.nodes import make_nodes, aggregator_node

        def send(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        try:
            codebase_node, pr_review_node, test_node, doc_node = make_nodes(db, user_id)

            node_map = {
                "codebase":      codebase_node,
                "pr_review":     pr_review_node,
                "test":          test_node,
                "documentation": doc_node,
            }

            state = {
                "repo":            f"{owner}/{repo}",
                "owner":           owner,
                "repo_name":       repo,
                "access_token":    access_token,
                "selected_agents": agents,
                "completed":       [],
                "current_agent":   "",
                "retry_count":     0,
                "results":         {},
                "health_score":    None,
                "health_summary":  None,
                "top_actions":     None,
            }

            for agent in agents:
                try:
                    yield send("agent_start", {"agent": agent})
                    await asyncio.sleep(0)

                    state["current_agent"] = agent
                    node_fn = node_map.get(agent)
                    if node_fn:
                        state = await node_fn(state)

                    result = state.get("results", {}).get(agent, {})

                    yield send("agent_done", {
                        "agent":   agent,
                        "summary": result.get("summary", ""),
                        "actions": result.get("actions", []),
                        "score":   result.get("score", 0),
                    })
                    await asyncio.sleep(0)

                    if agent not in state["completed"]:
                        state["completed"].append(agent)

                except Exception as e:
                    yield send("agent_done", {
                        "agent":   agent,
                        "summary": f"Error: {str(e)}",
                        "actions": [],
                        "score":   0,
                    })
                    if agent not in state["completed"]:
                        state["completed"].append(agent)
                    await asyncio.sleep(0)
                    continue

            try:
                state = aggregator_node(state)
            except Exception as e:
                state["health_score"]   = 0
                state["health_summary"] = f"Aggregation error: {str(e)}"
                state["top_actions"]    = []

            try:
                db.add(TeamModeHistory(
                    user_id      = user_id,
                    repo         = f"{owner}/{repo}",
                    agents       = agents,
                    results      = state.get("results", {}),
                    health_score = state.get("health_score"),
                    summary      = state.get("health_summary"),
                    top_actions  = state.get("top_actions", []),
                ))
                db.commit()
            except Exception:
                pass 

            yield send("complete", {
                "health_score": state.get("health_score", 0),
                "summary":      state.get("health_summary", ""),
                "top_actions":  state.get("top_actions", []),
                "results":      state.get("results", {}),
            })

        except Exception as e:
            yield send("error", {"message": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":               "no-cache",
            "X-Accel-Buffering":           "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.post("/team-mode/history")
async def get_team_mode_history(
    payload: TokenRequest,
    db: Session = Depends(get_db),
):
    user_id = get_current_user_id(payload.token)
    user    = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise UserNotFoundError(user_id=user_id)

    try:
        items = (
            db.query(TeamModeHistory)
            .filter(TeamModeHistory.user_id == user_id)
            .order_by(TeamModeHistory.created_at.desc())
            .limit(20)
            .all()
        )

        return [
            {
                "id":           item.id,
                "repo":         item.repo,
                "agents":       item.agents,
                "results":      item.results,
                "health_score": item.health_score,
                "summary":      item.summary,
                "top_actions":  item.top_actions,
                "timeAgo":      item.created_at.isoformat(),
            }
            for item in items
        ]
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "HISTORY_FETCH_ERROR",
            message     = f"Failed to fetch team mode history: {e}",
            status_code = 500,
            details     = {"error": str(e)},
        ) from e
    

# architecture
@router.get("/architecture")
async def get_architecture(
    token: str,
    owner: str,
    repo:  str,
    db: Session = Depends(get_db),
):
    user_id = get_current_user_id(token)
    user    = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise UserNotFoundError(user_id=user_id)

    try:
        result = await analyze_architecture(
            owner        = owner,
            repo         = repo,
            access_token = user.access_token,
        )
        return result
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "ARCHITECTURE_ERROR",
            message     = f"Failed to analyze architecture: {e}",
            status_code = 500,
            details     = {"error": str(e)},
        ) from e
    

# repo intelligence
@router.get("/repo-intelligence")
async def repo_intelligence(
    token:  str,
    owner:  str,
    repo:   str,
    period: str = "30d",
    db: Session = Depends(get_db),
):
    user_id = get_current_user_id(token)
    user    = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise UserNotFoundError(user_id=user_id)

    try:
        result = await get_repo_intelligence(
            owner        = owner,
            repo         = repo,
            access_token = user.access_token,
            period       = period,
        )
        return result
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "REPO_INTELLIGENCE_ERROR",
            message     = "Failed to fetch repo intelligence.",
            status_code = 500,
            details     = {"error": str(e)},
        ) from e