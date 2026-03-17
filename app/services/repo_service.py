from sqlalchemy.orm import Session
from app.models.repo import Repo
from app.services.user_service import fetch_user_repos

async def sync_user_repos(db: Session, user_id: int, access_token: str) -> list:

    github_repos = await fetch_user_repos(access_token)

    saved_repos = []
    for repo in github_repos:
        db_repo = db.query(Repo).filter(Repo.github_repo_id == repo["id"]).first()

        if db_repo:  # ← for içinde olmalı
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