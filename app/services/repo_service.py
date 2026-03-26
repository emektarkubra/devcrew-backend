from urllib import response

import httpx
from sqlalchemy.orm import Session
from app.models.repo import Repo
from app.services.user_service import fetch_user_repos
from app.core.config import settings
from app.core.exceptions import FileNotFoundInRepoError, GitHubAPIError

async def sync_user_repos(db: Session, user_id: int, access_token: str) -> list:

    github_repos = await fetch_user_repos(access_token)

    saved_repos = []
    for repo in github_repos:
        db_repo = db.query(Repo).filter(Repo.github_repo_id == repo["id"]).first()

        if db_repo: 
            db_repo.name           = repo["name"]
            db_repo.full_name      = repo["full_name"]
            db_repo.description    = repo.get("description")
            db_repo.language       = repo.get("language")
            db_repo.is_private     = repo["private"]
            db_repo.stars          = repo.get("stargazers_count", 0)
            db_repo.default_branch = repo.get("default_branch")
            db_repo.watchers_count = repo.get("watchers_count", 0)
            db_repo.size           = repo.get("size", 0)
            db_repo.updated_at     = repo.get("updated_at")
            db_repo.forks_count    = repo.get("forks_count", 0)
            db_repo.html_url       = repo.get("html_url")
        else:
            db_repo = Repo(
                github_repo_id = repo["id"],
                name           = repo["name"],
                full_name      = repo["full_name"],
                description    = repo.get("description"),
                language       = repo.get("language"),
                is_private     = repo["private"],
                stars          = repo.get("stargazers_count", 0),
                default_branch = repo.get("default_branch"),
                watchers_count = repo.get("watchers_count", 0),
                size           = repo.get("size", 0),
                updated_at     = repo.get("updated_at"),
                forks_count    = repo.get("forks_count", 0),
                html_url       = repo.get("html_url"),
                owner_id       = user_id,
            )
            db.add(db_repo)

        saved_repos.append(db_repo)

    db.commit()
    return saved_repos



# file content
async def fetch_file_content(access_token: str, owner: str, repo: str, file_path: str) -> str:
    url = f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/contents/{file_path}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3.raw",
            }
        )

    if response.status_code == 404:
        raise FileNotFoundInRepoError(file_path=file_path, repo=f"{owner}/{repo}")

    if response.status_code != 200:
        raise GitHubAPIError(status_code=response.status_code, repo=f"{owner}/{repo}")

    return response.text


# repo file list
async def fetch_repo_file_list(access_token: str, owner: str, repo: str) -> list[str]:
    url = f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/contents/"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            }
        )

    if response.status_code != 200:
        return []

    files = response.json()
    return [f["path"] for f in files if f["type"] == "file"]



# all repo files
async def fetch_all_repo_files(
    access_token: str,
    owner:        str,
    repo:         str,
    path:         str = "",
    client:       httpx.AsyncClient = None,
    _root:        bool = True,
) -> list[str]:

    SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

    url = f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept":        "application/vnd.github.v3+json",
    }

    if _root:
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await fetch_all_repo_files(access_token, owner, repo, path, client, _root=False)

    response = await client.get(url, headers=headers)

    if response.status_code != 200:
        return []

    items = response.json()
    files = []

    for item in items:
        if item["type"] == "file":
            files.append(item["path"])
        elif item["type"] == "dir" and item["name"] not in SKIP_DIRS:
            sub_files = await fetch_all_repo_files(access_token, owner, repo, item["path"], client, _root=False)
            files.extend(sub_files)

    return files    