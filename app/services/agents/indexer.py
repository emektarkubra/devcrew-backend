import httpx
import base64
from app.models.embedding import CodeEmbedding
from sqlalchemy.orm import Session
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from app.core.exceptions import RepoIndexError, EmbeddingError
from app.core.exceptions import RepoIndexError, EmbeddingError


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




# fetch repo file list
async def fetch_repo_files(access_token: str, owner: str, repo: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    tree = resp.json().get("tree", [])

    return [
        f for f in tree
        if f["type"] == "blob" and f["path"].endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".java"))
    ]



# fetch file content
async def fetch_file_content(access_token: str, owner: str, repo: str, path: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    data = resp.json()
    return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")



# repo index
async def index_repo(owner: str, repo: str, db: Session, user_id: int, access_token: str):
    repo_full = f"{owner}/{repo}"

    try:
        db.query(CodeEmbedding).filter(
            CodeEmbedding.user_id == user_id,
            CodeEmbedding.repo    == repo_full,
        ).delete()
        db.commit()
    except Exception as e:
        raise RepoIndexError(repo=repo_full)

    files = await fetch_repo_files(access_token, owner, repo)
    total_chunks = 0

    for file in files:
        try:
            content = await fetch_file_content(access_token, owner, repo, file["path"])
            chunks  = chunk_text(content)

            for chunk in chunks:
                try:
                    vector = get_embedding(f"passage: {chunk}")
                except Exception:
                    raise EmbeddingError(file_path=file["path"])

                db.add(CodeEmbedding(
                    user_id    = user_id,
                    repo       = repo_full,
                    file_path  = file["path"],
                    chunk_text = chunk,
                    embedding  = vector,
                ))
                total_chunks += 1

        except EmbeddingError:
            raise
        except Exception as e:
            print(f"Hata: {file['path']} — {e}")
            continue

    db.commit()

    return {
        "status":        "success",
        "repo":          repo_full,
        "files_indexed": len(files),
        "total_chunks":  total_chunks,
    }


