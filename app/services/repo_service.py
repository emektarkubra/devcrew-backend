from sqlalchemy.orm import Session
from app.models.repo import Repo
from app.services.user_service import fetch_user_repos

async def sync_user_repos(db: Session, user_id: int, access_token: str) -> list:

    github_repos = await fetch_user_repos(access_token)

    saved_repos = []
    for repo in github_repos: 
        db_repo = db.query(Repo).filter(Repo.github_repo_id == repo["id"]).first()

        if db_repo:
            # Güncelle
            db_repo.name        = repo["name"]
            db_repo.full_name   = repo["full_name"]
            db_repo.description = repo.get("description")
            db_repo.language    = repo.get("language")
            db_repo.is_private  = repo["private"]
            db_repo.stars       = repo.get("stargazers_count", 0)
        else:
            # Yeni kayıt
            db_repo = Repo(
                github_repo_id = repo["id"],
                name           = repo["name"],
                full_name      = repo["full_name"],
                description    = repo.get("description"),
                language       = repo.get("language"),
                is_private     = repo["private"],
                stars          = repo.get("stargazers_count", 0),
                owner_id       = user_id,
            )
            db.add(db_repo)

        saved_repos.append(db_repo)

    db.commit()
    return saved_repos