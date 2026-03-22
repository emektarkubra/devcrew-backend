import httpx
import base64
from app.models.embedding import CodeEmbedding
from sqlalchemy.orm import Session
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from app.core.exceptions import RepoIndexError, EmbeddingError, AppError
from app.core.constants import SUPPORTED_EXTENSIONS
from app.core.config import settings


# split text
def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=100)
    return text_splitter.split_text(text)


# embedding (lazy load)
_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = HuggingFaceBgeEmbeddings(
            model_name="intfloat/multilingual-e5-small",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embedding_model

def get_embedding(text: str) -> list[float]:
    return get_embedding_model().embed_query(text)


# default branch
async def get_default_branch(access_token: str, owner: str, repo: str) -> str:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if resp.status_code == 404:
            raise AppError(
                code="REPO_NOT_FOUND",
                message="Repo bulunamadı.",
                status_code=404,
                details={"repo": f"{owner}/{repo}"},
            )
        return resp.json().get("default_branch", "main")
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code="GITHUB_API_ERROR",
            message="GitHub API'ye erişilirken hata oluştu.",
            status_code=500,
            details={"error": str(e)},
        )


# fetch repo file list
async def fetch_repo_files(access_token: str, owner: str, repo: str, branch: str) -> list[dict]:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if resp.status_code == 404:
            raise AppError(
                code="REPO_TREE_NOT_FOUND",
                message="Repo dosya listesi alınamadı.",
                status_code=404,
                details={"repo": f"{owner}/{repo}", "branch": branch},
            )
        

        excludedFiles = {'.venv', 'venv', 'node_modules', '__pycache__', '.git', 'dist', 'build'}

        tree = resp.json().get("tree", [])
    
        return [
            f for f in tree
            if f["type"] == "blob"
            and f["path"].endswith(SUPPORTED_EXTENSIONS)
            and not any(f["path"].startswith(file + '/') for file in excludedFiles)
        ]
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code="GITHUB_API_ERROR",
            message="Repo dosyaları alınırken hata oluştu.",
            status_code=500,
            details={"error": str(e)},
        )


# fetch file content
async def fetch_file_content(access_token: str, owner: str, repo: str, path: str, branch: str) -> str:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.GITHUB_API_URL}/repos/{owner}/{repo}/contents/{path}?ref={branch}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if resp.status_code == 404:
            raise AppError(
                code="FILE_NOT_FOUND",
                message=f"{path} dosyası bulunamadı.",
                status_code=404,
                details={"path": path},
            )
        data = resp.json()
        return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
    except AppError:
        raise
    except Exception as e:
        raise AppError(
            code="FILE_FETCH_ERROR",
            message="Dosya içeriği alınırken hata oluştu.",
            status_code=500,
            details={"path": path, "error": str(e)},
        )


# repo index
async def index_repo(owner: str, repo: str, db: Session, user_id: int, access_token: str):
    repo_full = f"{owner}/{repo}"

    try:
        db.query(CodeEmbedding).filter(
            CodeEmbedding.user_id == user_id,
            CodeEmbedding.repo    == repo_full,
        ).delete()
        db.commit()
    except Exception:
        raise RepoIndexError(repo=repo_full)

    branch       = await get_default_branch(access_token, owner, repo)
    files        = await fetch_repo_files(access_token, owner, repo, branch)
    total_chunks = 0

    for file in files:
        try:
            content = await fetch_file_content(access_token, owner, repo, file["path"], branch)
            chunks  = chunk_text(content)

            for chunk in chunks:
                try:
                    vector = get_embedding(f"passage: {chunk}")
                    db.add(CodeEmbedding(
                        user_id    = user_id,
                        repo       = repo_full,
                        file_path  = file["path"],
                        chunk_text = chunk,
                        embedding  = vector,
                    ))
                    total_chunks += 1
                except Exception as e:
                    print(f"EMBED ERROR: {file['path']} — {e}")
                    continue  # tek chunk hata verse bile devam et

            print(f"✓ {file['path']} — {len(chunks)} chunks")

        except Exception as e:
            print(f"FILE ERROR: {file['path']} — {e}")
            continue  # tek dosya hata verse bile devam et

    db.commit()
    print(f"INDEX DONE: {total_chunks} chunks")

    return {
        "status":        "success",
        "repo":          repo_full,
        "files_indexed": len(files),
        "total_chunks":  total_chunks,
    }