from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from app.core.database import get_db
from app.core.config import settings
from app.core.exceptions import UserNotFoundError, AuthAppError
from app.models.user import User
from app.models.repo import Repo
from app.services.repo_service import sync_user_repos
from app.services.user_service import (
    exchange_code_for_token,
    get_github_user,
    get_or_create_user,
)
from app.schemas.users import UserDetailResponse
from app.schemas.repos import RepoResponse
from app.schemas.agents import PRListRequest
from app.services.user_service import fetch_repo_prs

router = APIRouter()

GITHUB_AUTH_URL = (
    "https://github.com/login/oauth/authorize"
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
            code    = "INVALID_TOKEN",
            message = "Geçersiz token",
        )


@router.get("/auth/github/login")
def github_login():
    return RedirectResponse(GITHUB_AUTH_URL)


@router.get("/auth/github/callback")
async def github_callback(code: str, db: Session = Depends(get_db)):
    access_token = await exchange_code_for_token(code)
    github_user  = await get_github_user(access_token)
    user         = await get_or_create_user(db, github_user, access_token)

    await sync_user_repos(db, user.id, access_token)

    jwt_token = create_jwt(user.id)
    return RedirectResponse(f"http://localhost:5173?token={jwt_token}")


@router.get("/profile", response_model=UserDetailResponse)
async def get_current_user_profile(token: str, db: Session = Depends(get_db)):
    user_id = get_current_user_id(token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    github_user = await get_github_user(user.access_token)

    return UserDetailResponse(
        id           = user.id,
        github_id    = user.github_id,
        username     = user.username,
        email        = user.email or github_user.get("email"),
        avatar_url   = user.avatar_url,
        name         = github_user.get("name"),
        bio          = github_user.get("bio"),
        location     = github_user.get("location"),
        company      = github_user.get("company"),
        blog         = github_user.get("blog"),
        followers    = github_user.get("followers"),
        following    = github_user.get("following"),
        public_repos = github_user.get("public_repos"),
        html_url     = github_user.get("html_url"),
    )


@router.get("/repos", response_model=list[RepoResponse])
async def get_repos(token: str, db: Session = Depends(get_db)):
    user_id = get_current_user_id(token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    return db.query(Repo).filter(Repo.owner_id == user_id).all()




@router.post("/pr-list")
async def get_pr_list(payload: PRListRequest, db: Session = Depends(get_db)):
    user_id = get_current_user_id(payload.token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(user_id=user_id)

    prs = await fetch_repo_prs(user.access_token, payload.owner, payload.repo)

    return [
        {
            "number": pr["number"],
            "title":  pr["title"],
            "author": pr["user"]["login"],
            "state":  pr["state"],
            "url":    pr["html_url"],
        }
        for pr in prs
    ]