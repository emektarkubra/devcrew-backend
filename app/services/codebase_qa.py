import httpx
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL  = "https://api.github.com/user"
GITHUB_REPOS_URL = "https://api.github.com/user/repos"



async def codebase_qa_service(query: str):
    # TODO: RAG pipeline buraya gelecek
    return {
        "answer": f"{query} sorusu için analiz yapıldı.",
        "files": []
    }