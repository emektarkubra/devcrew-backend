import httpx
from sqlalchemy.orm import Session
from app.models.user import User
from app.core.config import settings

GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL  = "https://api.github.com/user"
GITHUB_REPOS_URL = "https://api.github.com/user/repos"

async def exchange_code_for_token(code: str) -> str:
    """GitHub'dan gelen code ile access_token al"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id":     settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code":          code,
            },
        )
    return resp.json()["access_token"]


async def get_github_user(access_token: str) -> dict:
    """GitHub'dan kullanıcı bilgilerini çek"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            GITHUB_USER_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    return resp.json()


async def get_or_create_user(db: Session, github_user: dict, access_token: str) -> User:
    """Kullanıcı DB'de varsa getir, yoksa oluştur"""
    user = db.query(User).filter(User.github_id == github_user["id"]).first()

    if user:
        user.access_token = access_token  # token'ı güncelle
    else:
        user = User(
            github_id    = github_user["id"],
            username     = github_user["login"],
            email        = github_user.get("email"),
            avatar_url   = github_user.get("avatar_url"),
            access_token = access_token,
        )
        db.add(user)

    db.commit()
    db.refresh(user)
    return user


async def fetch_user_repos(access_token: str) -> list:
    """Kullanıcının GitHub repolarını çek"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            GITHUB_REPOS_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            params={"sort": "updated", "per_page": 50},
        )
    return resp.json()