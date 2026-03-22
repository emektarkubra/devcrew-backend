import httpx
from sqlalchemy.orm import Session
from app.models.user import User
from app.core.config import settings
from app.core.exceptions import AppError, AuthAppError
from app.models.repo import Repo


# code -> token
async def exchange_code_for_token(code: str) -> str:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.GITHUB_URL}/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id":     settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code":          code,
                },
            )
        data = resp.json()

        if "access_token" not in data:
            raise AuthAppError(
                code="GITHUB_TOKEN_ERROR",
                message="Failed to obtain GitHub access token.",
                details={"response": data},
            )
        return data["access_token"]
    except AuthAppError:
        raise
    except Exception as e:
        raise AppError(
            code="GITHUB_TOKEN_ERROR",
            message="An error occurred while obtaining GitHub access token.",
            status_code=500,
            details={"error": str(e)},
        )


# get user info from github
async def get_github_user(access_token: str) -> dict:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.GITHUB_API_URL}/user",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if resp.status_code == 401:
            raise AuthAppError(
                code="GITHUB_UNAUTHORIZED",
                message="Invalid or expired GitHub token.",
            )
        return resp.json()
    except AuthAppError:
        raise
    except Exception as e:
        raise AppError(
            code="GITHUB_USER_ERROR",
            message="An error occurred while fetching GitHub user information.",
            status_code=500,
            details={"error": str(e)},
        )


# get or create user
async def get_or_create_user(db: Session, github_user: dict, access_token: str) -> User:
    try:
        user = db.query(User).filter(User.github_id == github_user["id"]).first()

        if user:
            user.access_token = access_token
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
    except Exception as e:
        db.rollback()
        raise AppError(
            code="USER_CREATE_ERROR",
            message="An error occurred while creating or updating the user.",
            status_code=500,
            details={"error": str(e)},
        )


# get repos
async def fetch_user_repos(access_token: str) -> list:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.GITHUB_API_URL}/user/repos",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"sort": "updated", "per_page": 50},
            )
        if resp.status_code == 401:
            raise AuthAppError(
                code="GITHUB_UNAUTHORIZED",
                message="Invalid or expired GitHub token.",
            )
        return resp.json()
    except AuthAppError:
        raise
    except Exception as e:
        raise AppError(
            code="GITHUB_REPOS_ERROR",
            message="An error occurred while fetching user repositories.",
            status_code=500,
            details={"error": str(e)},
        )
    
# get repos pr's
async def fetch_repo_prs(access_token: str, owner: str, repo: str) -> list:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/pulls",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept":        "application/vnd.github.v3+json",
                },
                params={
                    "state":    "open",
                    "per_page": 20,
                    "sort":     "updated",
                },
            )
        if resp.status_code == 401:
            raise AuthAppError(
                code="GITHUB_UNAUTHORIZED",
                message="Invalid or expired GitHub token.",
            )
        if resp.status_code == 404:
            raise AppError(
                code="REPO_NOT_FOUND",
                message="Repo bulunamadı.",
                status_code=404,
                details={"owner": owner, "repo": repo},
            )
        return resp.json()
    except (AuthAppError, AppError):
        raise
    except Exception as e:
        raise AppError(
            code="GITHUB_PRS_ERROR",
            message="PR listesi alınırken hata oluştu.",
            status_code=500,
            details={"error": str(e)},
        )