import base64
import httpx
import json
from sqlalchemy.orm import Session
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from app.core.config import settings
from app.core.exceptions import AppError, PRNotFoundError
from app.models.pr_review_history import PrReviewQueryHistory
from app.core.prompts import PR_REVIEW_PROMPT, APPLY_FIX_PROMPT

# LLM
llm = ChatGroq(
    model_name="llama-3.3-70b-versatile",
    temperature=0,
    api_key=settings.GROQ_API_KEY,
)

review_chain = PR_REVIEW_PROMPT | llm | StrOutputParser()
fix_chain = APPLY_FIX_PROMPT | llm | StrOutputParser()


# fetch pr details
async def fetch_pr_details(
    access_token: str, owner: str, repo: str, pr_number: int
) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pr_number}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
        if resp.status_code == 404:
            raise PRNotFoundError(pr_number=pr_number)
        if resp.status_code != 200:
            raise AppError(
                code="GITHUB_API_ERROR",
                message=f"GitHub returned {resp.status_code}",
                status_code=resp.status_code,
                details={"pr_number": pr_number},
            )
        return resp.json()
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code="PR_DETAILS_FETCH_ERROR",
            message="An error occurred while fetching PR details.",
            status_code=500,
            details={"pr_number": pr_number, "error": str(e)},
        ) from e


# fetch pr diff
async def fetch_pr_diff(
    access_token: str, owner: str, repo: str, pr_number: int
) -> str:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pr_number}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3.diff",
                },
            )
        if resp.status_code == 404:
            raise PRNotFoundError(pr_number=pr_number)
        if resp.status_code != 200:
            raise AppError(
                code="GITHUB_API_ERROR",
                message=f"GitHub returned {resp.status_code}",
                status_code=resp.status_code,
                details={"pr_number": pr_number},
            )
        return resp.text
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code="PR_DIFF_FETCH_ERROR",
            message="An error occurred while fetching PR diff.",
            status_code=500,
            details={"pr_number": pr_number, "error": str(e)},
        ) from e


# fetch pr files
async def fetch_pr_files(
    access_token: str, owner: str, repo: str, pr_number: int
) -> list:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/pulls/{pr_number}/files",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
        if resp.status_code == 404:
            raise PRNotFoundError(pr_number=pr_number)
        if resp.status_code != 200:
            raise AppError(
                code="GITHUB_API_ERROR",
                message=f"GitHub returned {resp.status_code}",
                status_code=resp.status_code,
                details={"pr_number": pr_number},
            )
        return resp.json()
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code="PR_FILES_FETCH_ERROR",
            message="An error occurred while fetching PR files.",
            status_code=500,
            details={"pr_number": pr_number, "error": str(e)},
        ) from e


# fetch file content from branch
async def fetch_file_content_from_branch(
    access_token: str,
    owner: str,
    repo: str,
    file_path: str,
    branch: str,
) -> tuple[str, str]:
    """Returns (content, sha)"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/contents/{file_path}",
                params={"ref": branch},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
        if resp.status_code != 200:
            return "", ""
        data = resp.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        sha = data["sha"]
        return content, sha
    except Exception:
        return "", ""


# parse diff
def parse_diff(diff_text: str) -> list[dict]:
    lines = []
    for line in diff_text.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            lines.append({"type": "add", "content": line})
        elif line.startswith("-") and not line.startswith("---"):
            lines.append({"type": "remove", "content": line})
        else:
            lines.append({"type": "context", "content": line})
    return lines[:100]


# calculate risk score
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


# extract relevant context around the issue
def extract_relevant_context(
    content: str, issue_title: str, issue_description: str, max_chars: int = 3000
) -> str:
    lines = content.splitlines()

    skip_words = {
        "this",
        "code",
        "that",
        "with",
        "from",
        "have",
        "could",
        "should",
        "using",
        "does",
        "not",
        "more",
        "robust",
        "prevent",
        "allow",
        "query",
        "user",
        "input",
        "attack",
        "method",
        "used",
        "also",
        "would",
        "make",
    }

    keywords = [
        word
        for word in (issue_title + " " + issue_description).lower().split()
        if len(word) > 4 and word not in skip_words
    ]

    scored_lines = []
    for i, line in enumerate(lines):
        score = sum(1 for kw in keywords if kw in line.lower())
        scored_lines.append((score, i))

    scored_lines.sort(reverse=True)

    if not scored_lines or scored_lines[0][0] == 0:
        return content[:max_chars]

    center = scored_lines[0][1]
    start = max(0, center - 20)
    end = min(len(lines), center + 30)

    return "\n".join(lines[start:end])


# pr review
async def pr_review(
    owner: str,
    repo: str,
    pr_number: int,
    user_id: int,
    access_token: str,
    db: Session,
) -> dict:

    try:
        pr_details = await fetch_pr_details(access_token, owner, repo, pr_number)
        diff_text = await fetch_pr_diff(access_token, owner, repo, pr_number)
        pr_files = await fetch_pr_files(access_token, owner, repo, pr_number)
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code="PR_FETCH_ERROR",
            message="An error occurred while fetching PR details.",
            status_code=500,
            details={"error": str(e)},
        ) from e

    title = pr_details.get("title", "")
    author = pr_details.get("user", {}).get("login", "")
    changed_files = pr_details.get("changed_files", 0)

    try:
        answer = review_chain.invoke(
            {
                "title": title,
                "author": author,
                "changed_files": changed_files,
                "diff": diff_text[:4000],
            }
        )
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code="LLM_ERROR",
            message="An error occurred while analyzing the PR with LLM.",
            status_code=500,
            details={"error": str(e)},
        ) from e

    try:
        cleaned_answer = answer.strip().replace("```json", "").replace("```", "")
        analysis = json.loads(cleaned_answer)
    except Exception:
        analysis = {"issues": [], "risk_score": 0, "summary": answer}

    issues = analysis.get("issues", [])
    risk_score = calculate_risk(issues)

    files = [
        {
            "name": file["filename"].split("/")[-1],
            "path": file["filename"],
            "changes": f"+{file['additions']} -{file['deletions']}",
            "risk": "high"
            if file["changes"] > 50
            else "medium"
            if file["changes"] > 20
            else "low",
        }
        for file in pr_files
    ]

    try:
        db.add(
            PrReviewQueryHistory(
                user_id=user_id,
                repo=f"{owner}/{repo}",
                pr_number=pr_number,
                pr_title=title,
                risk_score=risk_score,
                issue_count=len(issues),
                issues=issues,
                diff=parse_diff(diff_text),
                files=files,
                summary=analysis.get("summary", ""),
            )
        )
        db.commit()
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code="PR_HISTORY_SAVE_ERROR",
            message="An error occurred while saving PR review history.",
            status_code=500,
            details={"pr_number": pr_number, "error": str(e)},
        ) from e

    return {
        "title": title,
        "number": f"#{pr_number}",
        "author": author,
        "riskScore": risk_score,
        "changedFiles": changed_files,
        "criticalIssues": len([i for i in issues if i.get("severity") == "high"]),
        "issues": issues,
        "diff": parse_diff(diff_text),
        "files": files,
        "summary": analysis.get("summary", ""),
    }


# generate fixes
async def generate_fixes(
    access_token: str,
    owner: str,
    repo: str,
    pr_number: int,
    issues: list,
) -> dict:

    try:
        pr_details = await fetch_pr_details(access_token, owner, repo, pr_number)
        branch = pr_details.get("head", {}).get("ref", "main")
    except AppError:
        raise

    file_contents: dict[str, str] = {}

    for issue in issues:
        raw_file = issue.get("file", "")
        file_path = raw_file.split(",")[0].split(" ")[0].strip()
        if file_path and file_path not in file_contents:
            content, _ = await fetch_file_content_from_branch(
                access_token=access_token,
                owner=owner,
                repo=repo,
                file_path=file_path,
                branch=branch,
            )
            file_contents[file_path] = content

    fixes = []

    for issue in issues:
        raw_file = issue.get("file", "")
        file_path = raw_file.split(",")[0].split(" ")[0].strip()

        if not file_path:
            fixes.append(
                {
                    "issue_title": issue.get("title", ""),
                    "file": file_path,
                    "original": "",
                    "fixed": "",
                    "explanation": "Could not determine file path",
                    "error": True,
                }
            )
            continue

        content = file_contents.get(file_path, "")

        if not content:
            fixes.append(
                {
                    "issue_title": issue.get("title", ""),
                    "file": file_path,
                    "original": "",
                    "fixed": "",
                    "explanation": "Could not fetch file content",
                    "error": True,
                }
            )
            continue

        try:
            relevant_content = extract_relevant_context(
                content,
                issue.get("title", ""),
                issue.get("description", ""),
            )

            raw = fix_chain.invoke(
                {
                    "file_path": file_path,
                    "file_content": relevant_content,
                    "issue_title": issue.get("title", ""),
                    "issue_description": issue.get("description", ""),
                    "suggestion": issue.get("suggestion", ""),
                }
            )
            cleaned = raw.strip().replace("```json", "").replace("```", "")
            result = json.loads(cleaned)

            fixes.append(
                {
                    "issue_title": issue.get("title", ""),
                    "file": file_path,
                    "original": result.get("original", ""),
                    "fixed": result.get("fixed", ""),
                    "explanation": result.get("explanation", ""),
                    "error": False,
                }
            )
        except Exception as e:
            fixes.append(
                {
                    "issue_title": issue.get("title", ""),
                    "file": file_path,
                    "original": "",
                    "fixed": "",
                    "explanation": f"Failed to generate fix: {str(e)}",
                    "error": True,
                }
            )

    return {"fixes": fixes}


# find and replace original code with fixed code
def find_and_replace(content: str, original: str, fixed: str) -> str | None:
    """Stripped original'i dosyada satır satır arar, indent'i koruyarak replace eder."""
    if not original or not original.strip():
        return None

    content_lines = content.splitlines()
    original_lines = [l for l in original.splitlines() if l.strip()]

    if not original_lines:
        return None

    stripped_original = [l.strip() for l in original_lines]

    for i in range(len(content_lines)):
        if content_lines[i].strip() != stripped_original[0]:
            continue

        match_indices = [i]
        j = 1
        k = i + 1

        while j < len(stripped_original) and k < len(content_lines):
            if not content_lines[k].strip():
                k += 1
                continue
            if content_lines[k].strip() == stripped_original[j]:
                match_indices.append(k)
                j += 1
                k += 1
            else:
                break

        if j < len(stripped_original):
            continue

        base_indent = len(content_lines[i]) - len(content_lines[i].lstrip())

        fixed_lines = []
        fixed_split = fixed.splitlines()
        first_fixed_indent = 0

        if fixed_split and fixed_split[0].strip():
            first_fixed_indent = len(fixed_split[0]) - len(fixed_split[0].lstrip())

        for fl in fixed_split:
            if not fl.strip():
                fixed_lines.append("")
                continue
            fl_indent = len(fl) - len(fl.lstrip())
            new_indent = base_indent + (fl_indent - first_fixed_indent)
            new_indent = max(0, new_indent)
            fixed_lines.append(" " * new_indent + fl.lstrip())

        start = match_indices[0]
        end = match_indices[-1]
        new_lines = content_lines[:start] + fixed_lines + content_lines[end + 1 :]
        return "\n".join(new_lines)

    return None


# apply fixes to branch
async def apply_fixes_to_branch(
    access_token: str,
    owner: str,
    repo: str,
    pr_number: int,
    fixes: list,
) -> dict:

    try:
        pr_details = await fetch_pr_details(access_token, owner, repo, pr_number)
        branch = pr_details.get("head", {}).get("ref", "main")
    except AppError:
        raise

    applied = []
    failed = []

    for fix in fixes:
        if fix.get("error") or not fix.get("original"):
            failed.append(
                {
                    "file": fix.get("file", ""),
                    "reason": "Invalid fix — no original code",
                }
            )
            continue

        file_path = fix["file"]

        content, sha = await fetch_file_content_from_branch(
            access_token=access_token,
            owner=owner,
            repo=repo,
            file_path=file_path,
            branch=branch,
        )

        if not content or not sha:
            failed.append({"file": file_path, "reason": "File not found on branch"})
            continue

        new_content = find_and_replace(content, fix["original"], fix["fixed"])

        if new_content is None:
            failed.append(
                {"file": file_path, "reason": "Original code not found in file"}
            )
            continue

        if new_content == content:
            failed.append({"file": file_path, "reason": "No changes made"})
            continue

        encoded = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                update_resp = await client.put(
                    f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/contents/{file_path}",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                    json={
                        "message": f"fix: {fix['issue_title']} (DevCrew)",
                        "content": encoded,
                        "sha": sha,
                        "branch": branch,
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
        except Exception as e:
            failed.append({"file": file_path, "reason": str(e)})

    return {
        "branch": branch,
        "applied": applied,
        "failed": failed,
    }
