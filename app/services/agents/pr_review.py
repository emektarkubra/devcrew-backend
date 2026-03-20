import httpx
import json
from sqlalchemy.orm import Session
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.core.config import settings
from app.core.exceptions import AppError, PRNotFoundError

# LLM
llm = ChatGroq(
    model_name="llama-3.1-8b-instant",
    temperature=0,
    api_key=settings.GROQ_API_KEY,
)

# prompt
prompt = PromptTemplate(
    template="""
You are a senior software engineer. Analyze the following PR diff carefully.

PR Title: {title}
Author: {author}
Changed files: {changed_files}

Diff:
{diff}

Return the analysis ONLY in the following JSON format, nothing else:
{{
    "issues": [
        {{
            "title": "issue title",
            "description": "detailed description",
            "file": "file name and line",
            "severity": "high/medium/low"
        }}
    ],
    "risk_score": number between 0-100,
    "summary": "general summary"
}}
""",
    input_variables=["title", "author", "changed_files", "diff"]
)

# chain
chain = prompt | llm | StrOutputParser()


# fetch pr detail
async def fetch_pr_details(access_token: str, owner: str, repo: str, pr_number: int) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pr_number}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept":        "application/vnd.github.v3+json",
            },
        )
    if resp.status_code == 404:
        raise PRNotFoundError(pr_number=pr_number)
    return resp.json()


# fetch pr diff
async def fetch_pr_diff(access_token: str, owner: str, repo: str, pr_number: int) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pr_number}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept":        "application/vnd.github.v3.diff",
            },
        )
    if resp.status_code == 404:
        raise PRNotFoundError(pr_number=pr_number)
    return resp.text


# fetch pr files
async def fetch_pr_files(access_token: str, owner: str, repo: str, pr_number: int) -> list:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pr_number}/files",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept":        "application/vnd.github.v3+json",
            },
        )
    if resp.status_code == 404:
        raise PRNotFoundError(pr_number=pr_number)
    return resp.json()


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
    except PRNotFoundError:
        raise
    except Exception as e:
        raise AppError(
            code="PR_FETCH_ERROR",
            message="PR bilgileri alınırken hata oluştu.",
            status_code=500,
            details={"error": str(e)},
        )

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
    except Exception as e:
        raise AppError(
            code="LLM_ERROR",
            message="LLM analizi sırasında hata oluştu.",
            status_code=500,
            details={"error": str(e)},
        )

    try:
        cleaned_answer = answer.strip().replace("```json", "").replace("```", "")
        analysis       = json.loads(cleaned_answer)
    except Exception:
        analysis = {"issues": [], "risk_score": 0, "summary": answer}

    issues     = analysis.get("issues", [])
    risk_score = calculate_risk(issues)

    files = [
        {
            "name":    f["filename"].split("/")[-1],
            "path":    f["filename"],
            "changes": f"+{f['additions']} -{f['deletions']}",
            "risk":    "high" if f["changes"] > 50 else "medium" if f["changes"] > 20 else "low",
        }
        for f in pr_files
    ]

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