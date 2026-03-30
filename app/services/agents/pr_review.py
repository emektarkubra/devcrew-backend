import httpx
import json
from sqlalchemy.orm import Session
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from app.core.config import settings
from app.core.exceptions import AppError, PRNotFoundError
from app.models.pr_review_history import PrReviewQueryHistory
from app.core.prompts import PR_REVIEW_PROMPT

# LLM
llm = ChatGroq(
    model_name="llama-3.1-8b-instant",
    temperature=0,
    api_key=settings.GROQ_API_KEY,
)

# chain
chain = PR_REVIEW_PROMPT | llm | StrOutputParser()


# fetch pr details
async def fetch_pr_details(access_token: str, owner: str, repo: str, pr_number: int) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pr_number}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept":        "application/vnd.github.v3+json",
                },
            )
        if resp.status_code == 404:
            raise PRNotFoundError(pr_number=pr_number)
        if resp.status_code != 200:
            raise AppError(
                code        = "GITHUB_API_ERROR",
                message     = f"GitHub returned {resp.status_code}",
                status_code = resp.status_code,
                details     = {"pr_number": pr_number},
            )
        return resp.json()
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "PR_DETAILS_FETCH_ERROR",
            message     = "An error occurred while fetching PR details.",
            status_code = 500,
            details     = {"pr_number": pr_number, "error": str(e)},
        ) from e


# fetch pr diff
async def fetch_pr_diff(access_token: str, owner: str, repo: str, pr_number: int) -> str:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pr_number}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept":        "application/vnd.github.v3.diff",
                },
            )
        if resp.status_code == 404:
            raise PRNotFoundError(pr_number=pr_number)
        if resp.status_code != 200:
            raise AppError(
                code        = "GITHUB_API_ERROR",
                message     = f"GitHub returned {resp.status_code}",
                status_code = resp.status_code,
                details     = {"pr_number": pr_number},
            )
        return resp.text
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "PR_DIFF_FETCH_ERROR",
            message     = "An error occurred while fetching PR diff.",
            status_code = 500,
            details     = {"pr_number": pr_number, "error": str(e)},
        ) from e


# fetch pr files
async def fetch_pr_files(access_token: str, owner: str, repo: str, pr_number: int) -> list:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pr_number}/files",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept":        "application/vnd.github.v3+json",
                },
            )
        if resp.status_code == 404:
            raise PRNotFoundError(pr_number=pr_number)
        if resp.status_code != 200:
            raise AppError(
                code        = "GITHUB_API_ERROR",
                message     = f"GitHub returned {resp.status_code}",
                status_code = resp.status_code,
                details     = {"pr_number": pr_number},
            )
        return resp.json()
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "PR_FILES_FETCH_ERROR",
            message     = "An error occurred while fetching PR files.",
            status_code = 500,
            details     = {"pr_number": pr_number, "error": str(e)},
        ) from e


# parse diff
def parse_diff(diff_text: str) -> list[dict]:
    lines = []
    for line in diff_text.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            lines.append({"type": "add",     "content": line})
        elif line.startswith("-") and not line.startswith("---"):
            lines.append({"type": "remove",  "content": line})
        else:
            lines.append({"type": "context", "content": line})
    return lines[:100]


# risk score
def calculate_risk(issues: list) -> int:
    score = 0
    for issue in issues:
        if issue.get("severity") == "high":
            score += 30
        elif issue.get("severity") == "medium":
            score += 15
        elif issue.get("severity") == "low":
            score += 5
    return min(score, 100)


# pr review
async def pr_review(
    owner:        str,
    repo:         str,
    pr_number:    int,
    user_id:      int,
    access_token: str,
    db:           Session,
) -> dict:

    try:
        pr_details = await fetch_pr_details(access_token, owner, repo, pr_number)
        diff_text  = await fetch_pr_diff(access_token, owner, repo, pr_number)
        pr_files   = await fetch_pr_files(access_token, owner, repo, pr_number)
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "PR_FETCH_ERROR",
            message     = "An error occurred while fetching PR details.",
            status_code = 500,
            details     = {"error": str(e)},
        ) from e

    title         = pr_details.get("title", "")
    author        = pr_details.get("user", {}).get("login", "")
    changed_files = pr_details.get("changed_files", 0)

    try:
        answer = chain.invoke({
            "title":         title,
            "author":        author,
            "changed_files": changed_files,
            "diff":          diff_text[:4000],
        })
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "LLM_ERROR",
            message     = "An error occurred while analyzing the PR with LLM.",
            status_code = 500,
            details     = {"error": str(e)},
        ) from e

    try:
        cleaned_answer = answer.strip().replace("```json", "").replace("```", "")
        analysis       = json.loads(cleaned_answer)
    except Exception:
        analysis = {"issues": [], "risk_score": 0, "summary": answer}

    issues     = analysis.get("issues", [])
    risk_score = calculate_risk(issues)

    files = [
        {
            "name":    file["filename"].split("/")[-1],
            "path":    file["filename"],
            "changes": f"+{file['additions']} -{file['deletions']}",
            "risk":    "high" if file["changes"] > 50 else "medium" if file["changes"] > 20 else "low",
        }
        for file in pr_files
    ]

    try:
        db.add(PrReviewQueryHistory(
            user_id     = user_id,
            repo        = f"{owner}/{repo}",
            pr_number   = pr_number,
            pr_title    = title,
            risk_score  = risk_score,
            issue_count = len(issues),
            issues      = issues,
            diff        = parse_diff(diff_text),
            files       = files,
            summary     = analysis.get("summary", ""),
        ))
        db.commit()
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code        = "PR_HISTORY_SAVE_ERROR",
            message     = "An error occurred while saving PR review history.",
            status_code = 500,
            details     = {"pr_number": pr_number, "error": str(e)},
        ) from e

    return {
        "title":          title,
        "number":         f"#{pr_number}",
        "author":         author,
        "riskScore":      risk_score,
        "changedFiles":   changed_files,
        "criticalIssues": len([i for i in issues if i.get("severity") == "high"]),
        "issues":         issues,
        "diff":           parse_diff(diff_text),
        "files":          files,
        "summary":        analysis.get("summary", ""),
    }