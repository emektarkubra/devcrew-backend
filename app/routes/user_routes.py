from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from app.core.database import get_db
from app.core.config import settings
from app.models.user import User 
from app.services.user_service import (
    exchange_code_for_token,
    get_github_user,
    get_or_create_user,
    fetch_user_repos
)

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
        raise HTTPException(status_code=401, detail="Geçersiz token")


@router.get("/auth/github/login")
def github_login():
    """Kullanıcıyı GitHub login sayfasına yönlendir"""
    return RedirectResponse(GITHUB_AUTH_URL)


@router.get("/auth/github/callback")
async def github_callback(code: str, db: Session = Depends(get_db)):
    """GitHub callback — code → token → kullanıcı oluştur → JWT dön"""
    access_token = await exchange_code_for_token(code)
    github_user  = await get_github_user(access_token)
    user         = await get_or_create_user(db, github_user, access_token)
    jwt_token    = create_jwt(user.id)
    return RedirectResponse(f"http://localhost:5173?token={jwt_token}")


@router.get("/me")
async def get_me(token: str, db: Session = Depends(get_db)):
    user_id = get_current_user_id(token)
    user    = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    # GitHub'dan güncel profil bilgilerini çek
    github_user = await get_github_user(user.access_token)

    return {
        "id":         user.id,
        "username":   user.username,
        "email":      user.email or github_user.get("email"),
        "avatar_url": user.avatar_url,
        "github_id":  user.github_id,
        # GitHub'dan ekstra alanlar
        "name":       github_user.get("name"),
        "bio":        github_user.get("bio"),
        "location":   github_user.get("location"),
        "company":    github_user.get("company"),
        "blog":       github_user.get("blog"),
        "followers":  github_user.get("followers"),
        "following":  github_user.get("following"),
        "public_repos": github_user.get("public_repos"),
        "html_url":   github_user.get("html_url"),
    }


@router.get("/repos")
async def get_repos(token: str, db: Session = Depends(get_db)):
    """Kullanıcının repolarını getir"""
    user_id = get_current_user_id(token)
    user    = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    repos = await fetch_user_repos(user.access_token)
    return repos