import json
import httpx
import base64
from datetime import datetime
from sqlalchemy.orm import Session
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from app.core.config import settings
from app.core.exceptions import AppError, RepoNotIndexedError
from app.core.prompts import DEBUG_PROMPT, DEBUG_FIX_PROMPT
from app.models.embedding import CodeEmbedding
from app.services.agents.indexer import get_embedding
from app.models.debug_history import DebugHistory
from app.services.agents.pr_review import find_and_replace

llm = ChatGroq(
    model_name="llama-3.3-70b-versatile",
    temperature=0,
    api_key=settings.GROQ_API_KEY,
)

chain = DEBUG_PROMPT | llm | StrOutputParser()
fix_chain = DEBUG_FIX_PROMPT | llm | StrOutputParser()


def normalize_path(path: str) -> str:
    """Remove container path prefixes to get the repo-relative path."""
    path = path.lstrip("/")
    if path.startswith("app/app/"):
        path = path[len("app/app/") :]
    elif path.startswith("app/"):
        pass
    return path


async def debug_error(
    error: str,
    owner: str,
    repo: str,
    user_id: int,
    access_token: str,
    db: Session,
) -> dict:

    repo_full = f"{owner}/{repo}"
    query_vector = get_embedding(f"query: {error}")

    results = (
        db.query(CodeEmbedding)
        .filter(
            CodeEmbedding.user_id == user_id,
            CodeEmbedding.repo == repo_full,
        )
        .order_by(CodeEmbedding.embedding.cosine_distance(query_vector))
        .limit(8)
        .all()
    )

    if not results:
        from app.services.agents.indexer import index_repo

        await index_repo(
            owner=owner,
            repo=repo,
            db=db,
            user_id=user_id,
            access_token=access_token,
        )
        results = (
            db.query(CodeEmbedding)
            .filter(
                CodeEmbedding.user_id == user_id,
                CodeEmbedding.repo == repo_full,
            )
            .order_by(CodeEmbedding.embedding.cosine_distance(query_vector))
            .limit(8)
            .all()
        )

    if not results:
        raise RepoNotIndexedError(repo=repo_full)

    context = "\n\n".join([f"# {r.file_path}\n{r.chunk_text}" for r in results])

    try:
        answer = chain.invoke(
            {
                "error": error,
                "context": context,
            }
        )
    except Exception as e:
        raise AppError(
            code="LLM_ERROR",
            message="LLM analysis failed.",
            status_code=500,
            details={"error": str(e)},
        )

    try:
        cleaned = answer.strip().replace("```json", "").replace("```", "")
        analysis = json.loads(cleaned)
    except Exception:
        analysis = {
            "root_cause": answer,
            "severity": "unknown",
            "explanation": "",
            "issues": [],
        }

    raw_issues = analysis.get("issues", [])

    issues_with_code = []
    for issue in raw_issues:
        file_name = normalize_path(issue.get("affected_file", ""))

        chunk = (
            db.query(CodeEmbedding)
            .filter(
                CodeEmbedding.user_id == user_id,
                CodeEmbedding.repo == repo_full,
                CodeEmbedding.file_path.ilike(f"%{file_name}%"),
            )
            .first()
        )

        full_path = chunk.file_path if chunk else file_name
        full_path = normalize_path(full_path)

        chunks = (
            db.query(CodeEmbedding)
            .filter(
                CodeEmbedding.user_id == user_id,
                CodeEmbedding.repo == repo_full,
                CodeEmbedding.file_path == full_path,
            )
            .all()
        )
        code = "\n".join([c.chunk_text for c in chunks]) if chunks else ""

        issues_with_code.append(
            {
                "title": issue.get("title", ""),
                "description": issue.get("description", ""),
                "affectedFile": {
                    "path": full_path,
                    "name": full_path.split("/")[-1],
                    "code": code[:500],
                },
                "fixSuggestion": issue.get("fix_suggestion", ""),
            }
        )

    seen = set()
    affected_files = []
    for issue in issues_with_code:
        path = issue["affectedFile"]["path"]
        if path not in seen:
            seen.add(path)
            affected_files.append(issue["affectedFile"])

    db.add(
        DebugHistory(
            user_id=user_id,
            repo=repo_full,
            error=error[:2000],
            root_cause=analysis.get("root_cause", ""),
            severity=analysis.get("severity", "unknown"),
            affected_files=affected_files,
            issues=issues_with_code,
            explanation=analysis.get("explanation", ""),
        )
    )
    db.commit()

    return {
        "rootCause": analysis.get("root_cause", ""),
        "severity": analysis.get("severity", "unknown"),
        "explanation": analysis.get("explanation", ""),
        "affectedFiles": affected_files,
        "issues": issues_with_code,
        "contextFiles": list({r.file_path for r in results}),
    }


async def apply_debug_fix_and_open_pr(
    access_token: str,
    owner: str,
    repo: str,
    issues: list,
    error: str,
) -> dict:

    async with httpx.AsyncClient(timeout=30.0) as client:
        repo_resp = await client.get(
            f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
    if repo_resp.status_code != 200:
        raise AppError(
            code="GITHUB_API_ERROR",
            message="Could not fetch repo info.",
            status_code=repo_resp.status_code,
        )

    default_branch = repo_resp.json().get("default_branch", "main")

    async with httpx.AsyncClient(timeout=30.0) as client:
        ref_resp = await client.get(
            f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/git/ref/heads/{default_branch}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
    if ref_resp.status_code != 200:
        raise AppError(
            code="GITHUB_API_ERROR",
            message="Could not fetch branch ref.",
            status_code=ref_resp.status_code,
        )

    base_sha = ref_resp.json()["object"]["sha"]
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    new_branch = f"devCrew/fix-{timestamp}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        branch_resp = await client.post(
            f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/git/refs",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={
                "ref": f"refs/heads/{new_branch}",
                "sha": base_sha,
            },
        )
    if branch_resp.status_code not in (200, 201):
        raise AppError(
            code="GITHUB_API_ERROR",
            message="Could not create new branch.",
            status_code=branch_resp.status_code,
        )

    applied = []
    failed = []

    for issue in issues:
        file_info = issue.get("affectedFile", {})
        file_path = normalize_path(file_info.get("path", ""))
        fix_suggestion = issue.get("fixSuggestion", "")

        if not file_path:
            failed.append({"file": file_path, "reason": "No file path"})
            continue

        async with httpx.AsyncClient(timeout=30.0) as client:
            file_resp = await client.get(
                f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/contents/{file_path}",
                params={"ref": new_branch},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
        if file_resp.status_code != 200:
            failed.append({"file": file_path, "reason": "File not found"})
            continue

        file_data = file_resp.json()
        file_sha = file_data["sha"]
        current_content = base64.b64decode(file_data["content"]).decode("utf-8")

        try:
            raw = fix_chain.invoke(
                {
                    "file_path": file_path,
                    "file_content": current_content[:5000],
                    "error": error[:500],
                    "fix_suggestion": fix_suggestion,
                }
            )
            cleaned = raw.strip().replace("```json", "").replace("```", "")
            fix = json.loads(cleaned)
            original = fix.get("original", "")
            fixed = fix.get("fixed", "")
        except Exception as e:
            failed.append({"file": file_path, "reason": f"LLM error: {str(e)}"})
            continue

        if not original:
            failed.append({"file": file_path, "reason": "No original code generated"})
            continue

        new_content = find_and_replace(current_content, original, fixed)

        if new_content is None:
            failed.append(
                {"file": file_path, "reason": "Could not locate original code"}
            )
            continue

        encoded = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")

        async with httpx.AsyncClient(timeout=30.0) as client:
            update_resp = await client.put(
                f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/contents/{file_path}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                json={
                    "message": f"fix: {issue.get('title', file_path)} (DevCrew Debug Agent)",
                    "content": encoded,
                    "sha": file_sha,
                    "branch": new_branch,
                },
            )
        if update_resp.status_code in (200, 201):
            applied.append(file_path)
        else:
            failed.append(
                {
                    "file": file_path,
                    "reason": update_resp.json().get("message", "GitHub API error"),
                }
            )

    if not applied:
        raise AppError(
            code="NO_FILES_APPLIED",
            message="Could not apply fix to any files.",
            status_code=400,
            details={"failed": failed},
        )

    issue_summary = "\n".join(
        [f"- {i.get('title', '')}: {i.get('fixSuggestion', '')}" for i in issues]
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        pr_resp = await client.post(
            f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/pulls",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={
                "title": f"fix: {error[:80]}",
                "body": f"## DevCrew Debug Agent\n\n**Error:**\n```\n{error[:500]}\n```\n\n**Fixes applied:**\n{issue_summary}\n\n**Files changed:** {', '.join(applied)}",
                "head": new_branch,
                "base": default_branch,
            },
        )

    if pr_resp.status_code not in (200, 201):
        raise AppError(
            code="PR_OPEN_ERROR",
            message="Fix applied but could not open PR.",
            status_code=pr_resp.status_code,
            details={"branch": new_branch},
        )

    pr_data = pr_resp.json()

    return {
        "pr_url": pr_data.get("html_url", ""),
        "pr_number": pr_data.get("number"),
        "branch": new_branch,
        "applied": applied,
        "failed": failed,
    }
