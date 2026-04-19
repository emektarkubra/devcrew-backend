from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from jose import jwt, JWTError
from app.core.database import get_db
from app.core.config import settings
from app.core.exceptions import UserNotFoundError, AuthAppError, AppError
from app.models.user import User
from app.models.repo import Repo
from app.services.repo_service import sync_user_repos
from app.services.user_service import (
    exchange_code_for_token,
    get_github_user,
    get_or_create_user,
    fetch_repo_prs,
)
from app.schemas.users import UserDetailResponse
from app.schemas.repos import RepoResponse, RepoSearchResponse
from app.schemas.agents import PRListRequest

router = APIRouter()

GITHUB_AUTH_URL = (
    f"{settings.GITHUB_URL}/login/oauth/authorize"
    f"?client_id={settings.GITHUB_CLIENT_ID}"
    f"&scope=repo,user"
)


def create_jwt(user_id: int) -> str:
    return jwt.encode({"sub": str(user_id)}, settings.SECRET_KEY, algorithm="HS256")


def get_current_user_id(token: str) -> int:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return int(payload["sub"])
    except JWTError:
        raise AuthAppError(
            code="INVALID_TOKEN",
            message="Geçersiz token",
        )


def normalize_tr(text: str) -> str:
    return (
        text.replace("ı", "i")
        .replace("İ", "i")
        .replace("ğ", "g")
        .replace("Ğ", "g")
        .replace("ü", "u")
        .replace("Ü", "u")
        .replace("ş", "s")
        .replace("Ş", "s")
        .replace("ö", "o")
        .replace("Ö", "o")
        .replace("ç", "c")
        .replace("Ç", "c")
        .lower()
    )


@router.get("/auth/github/login")
def github_login():
    return RedirectResponse(GITHUB_AUTH_URL)


@router.get("/auth/github/callback")
async def github_callback(code: str, db: Session = Depends(get_db)):
    try:
        access_token = await exchange_code_for_token(code)
        github_user = await get_github_user(access_token)
        user = await get_or_create_user(db, github_user, access_token)
        jwt_token = create_jwt(user.id)

        try:
            await sync_user_repos(db=db, user_id=user.id, access_token=access_token)
        except Exception as e:
            print(f"⚠️ sync_user_repos failed: {e}")
            # login'i engelleme, devam et

        return RedirectResponse(f"{settings.FRONTEND_URL}?token={jwt_token}")
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code="GITHUB_CALLBACK_ERROR",
            message="An error occurred during GitHub authentication.",
            status_code=500,
            details={"error": str(e)},
        ) from e


@router.get("/profile", response_model=UserDetailResponse)
async def get_current_user_profile(token: str, db: Session = Depends(get_db)):
    user_id = get_current_user_id(token)
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    try:
        github_user = await get_github_user(user.access_token)
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code="PROFILE_FETCH_ERROR",
            message="An error occurred while fetching profile.",
            status_code=500,
            details={"user_id": user_id},
        ) from e

    return UserDetailResponse(
        id=user.id,
        github_id=user.github_id,
        username=user.username,
        email=user.email or github_user.get("email"),
        avatar_url=user.avatar_url,
        name=github_user.get("name"),
        bio=github_user.get("bio"),
        location=github_user.get("location"),
        company=github_user.get("company"),
        blog=github_user.get("blog"),
        followers=github_user.get("followers"),
        following=github_user.get("following"),
        public_repos=github_user.get("public_repos"),
        html_url=github_user.get("html_url"),
    )


@router.get("/repos", response_model=list[RepoResponse])
async def get_repos(token: str, db: Session = Depends(get_db)):
    user_id = get_current_user_id(token)
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    try:
        return db.query(Repo).filter(Repo.owner_id == user_id).all()
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code="REPOS_FETCH_ERROR",
            message="An error occurred while fetching repositories.",
            status_code=500,
            details={"user_id": user_id},
        ) from e


@router.get("/repos/search", response_model=RepoSearchResponse)
async def search_repos(
    token: str,
    type: str = "all",
    language: str = "all",
    sort: str = "updated",
    search: str = "",
    page: int = 0,
    per_page: int = 10,
    db: Session = Depends(get_db),
):
    user_id = get_current_user_id(token)
    base_query = db.query(Repo).filter(Repo.owner_id == user_id)

    try:
        if type == "public":
            base_query = base_query.filter(Repo.is_private.is_(False))
        elif type == "private":
            base_query = base_query.filter(Repo.is_private.is_(True))
        elif type == "forks":
            base_query = base_query.filter(Repo.forks_count > 0)

        if language != "all":
            base_query = base_query.filter(
                func.lower(Repo.language) == language.lower()
            )

        if search:
            search_norm = normalize_tr(search)
            normalized_name = func.replace(
                func.replace(
                    func.replace(
                        func.replace(func.lower(Repo.name), "ı", "i"), "ğ", "g"
                    ),
                    "ş",
                    "s",
                ),
                "ö",
                "o",
            )
            base_query = base_query.filter(normalized_name.ilike(f"%{search_norm}%"))

        total = base_query.count()

        if sort == "updated":
            base_query = base_query.order_by(Repo.updated_at.desc())
        elif sort == "created":
            base_query = base_query.order_by(Repo.created_at.desc())
        elif sort == "name":
            base_query = base_query.order_by(Repo.name.asc())
        elif sort == "stars":
            base_query = base_query.order_by(Repo.stars.desc())

        items = base_query.offset(page * per_page).limit(per_page).all()

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code="REPO_SEARCH_ERROR",
            message="An error occurred while searching repositories.",
            status_code=500,
            details={"user_id": user_id},
        ) from e


@router.get("/repos/stats")
async def get_repo_stats(token: str, db: Session = Depends(get_db)):
    user_id = get_current_user_id(token)

    try:
        all_repos = db.query(Repo).filter(Repo.owner_id == user_id).all()
        return {
            "total": len(all_repos),
            "public": sum(1 for r in all_repos if not r.is_private),
            "private": sum(1 for r in all_repos if r.is_private),
            "stars": sum(r.stars or 0 for r in all_repos),
            "languages": len(set(r.language for r in all_repos if r.language)),
        }
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code="REPO_STATS_ERROR",
            message="An error occurred while fetching repository statistics.",
            status_code=500,
            details={"user_id": user_id},
        ) from e


@router.post("/pr-list")
async def get_pr_list(payload: PRListRequest, db: Session = Depends(get_db)):
    user_id = get_current_user_id(payload.token)
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    try:
        prs = await fetch_repo_prs(user.access_token, payload.owner, payload.repo)
        return [
            {
                "number": pr["number"],
                "title": pr["title"],
                "author": pr["user"]["login"],
                "state": pr["state"],
                "url": pr["html_url"],
            }
            for pr in prs
        ]
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code="PR_LIST_ERROR",
            message="An error occurred while fetching pull requests.",
            status_code=500,
            details={"owner": payload.owner, "repo": payload.repo},
        ) from e
