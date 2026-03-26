from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
from fastapi import status


@dataclass
class ErrorMeta:  # hata oldugunda bunlar doner
    """Serializable metadata carried by domain exceptions."""
    code: str
    message: str
    status_code: int
    details: Optional[Dict[str, Any]] = None
    safe_message: Optional[str] = None  # what client sees if you want to hide internals


class AppError(Exception): # tüm domain/app hataları
    """
    Base application/domain error.
    - code: stable error code for frontend/clients
    - message: internal message (can be same as safe_message)
    - safe_message: optional client-safe message (for 5xx, security)
    - details: structured context for debugging/observability
    - status_code: default HTTP status mapping
    """

    meta: ErrorMeta

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
        safe_message: Optional[str] = None,
    ):
        self.meta = ErrorMeta(
            code=code,
            message=message,
            status_code=status_code,
            details=details or None,
            safe_message=safe_message,
        )
        super().__init__(message)

    @property  # self.meta.xxx erişimini kolaylaştırıyor: yani handler yazarken exc.meta.code yerine exc.code diyebiliyorsun.
    def code(self) -> str:
        return self.meta.code

    @property
    def status_code(self) -> int:
        return self.meta.status_code

    @property
    def details(self) -> Optional[Dict[str, Any]]:
        return self.meta.details

    @property
    def message(self) -> str:
        return self.meta.message

    @property
    def client_message(self) -> str:
        return self.meta.safe_message or self.meta.message


# ---- Error Category Bases (optional but useful) ----

class ValidationAppError(AppError): # 400
    def __init__(
        self, 
        code: str, 
        message: str, 
        *, 
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(code, message, status_code=status.HTTP_400_BAD_REQUEST, details=details)


class NotFoundAppError(AppError): # 404
    def __init__(
        self, 
        code: str, 
        message: str, 
        *, 
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(code, message, status_code=status.HTTP_404_NOT_FOUND, details=details)


class ConflictAppError(AppError): # 409
    def __init__(
        self, 
        code: str, 
        message: str, 
        *, 
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(code, message, status_code=status.HTTP_409_CONFLICT, details=details)


class AuthAppError(AppError): # 401
    def __init__(
        self, 
        code: str, 
        message: str, 
        *, 
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(code, message, status_code=status.HTTP_401_UNAUTHORIZED, details=details)


class ForbiddenAppError(AppError): # 403
    def __init__(
        self, 
        code: str, 
        message: str, 
        *, 
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(code, message, status_code=status.HTTP_403_FORBIDDEN, details=details)


class RateLimitAppError(AppError): # 429
    def __init__(
        self, 
        code: str, 
        message: str, 
        *, 
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(code, message, status_code=status.HTTP_429_TOO_MANY_REQUESTS, details=details)


class ServiceUnavailableAppError(AppError): # 503
    def __init__(
        self, 
        code: str, 
        message: str, 
        *, 
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(code, message, status_code=status.HTTP_503_SERVICE_UNAVAILABLE, details=details)


# ---- Concrete Examples (use these in services) ----

class EmailAlreadyExistsError(ConflictAppError):
    def __init__(self, *, email: Optional[str] = None):
        super().__init__(
            code="EMAIL_ALREADY_EXISTS",
            message="Email already exists",
            details={"email": email} if email else None,
        )


class UserNotFoundError(NotFoundAppError):
    def __init__(self, *, user_id: Optional[int] = None):
        super().__init__(
            code="USER_NOT_FOUND",
            message="User not found",
            details={"user_id": user_id} if user_id is not None else None,
        )

# Agents

class RepoNotIndexedError(NotFoundAppError):
    def __init__(self, *, repo: Optional[str] = None):
        super().__init__(
            code="REPO_NOT_INDEXED",
            message="Bu repo henüz indexlenmemiş.",
            details={"repo": repo} if repo else None,
        )

class RepoIndexError(AppError):
    def __init__(self, *, repo: Optional[str] = None):
        super().__init__(
            code="REPO_INDEX_ERROR",
            message="Repo indexlenirken hata oluştu.",
            status_code=500,
            details={"repo": repo} if repo else None,
        )

class EmbeddingError(AppError):
    def __init__(self, *, file_path: Optional[str] = None):
        super().__init__(
            code="EMBEDDING_ERROR",
            message="Embedding oluşturulurken hata oluştu.",
            status_code=500,
            details={"file_path": file_path} if file_path else None,
        )

class PRNotFoundError(NotFoundAppError):
    def __init__(self, *, pr_number: Optional[int] = None):
        super().__init__(
            code="PR_NOT_FOUND",
            message="PR bulunamadı.",
            details={"pr_number": pr_number} if pr_number else None,
        )

class FileNotFoundInRepoError(NotFoundAppError):
    def __init__(self, *, file_path: Optional[str] = None, repo: Optional[str] = None):
        super().__init__(
            code="FILE_NOT_FOUND_IN_REPO",
            message="File not found in repository.",
            details={
                "file_path": file_path,
                "repo": repo,
            },
        )


class GitHubAPIError(AppError):
    def __init__(self, *, status_code: int = 500, repo: Optional[str] = None):
        super().__init__(
            code="GITHUB_API_ERROR",
            message="GitHub API returned an error.",
            status_code=status_code,
            details={"repo": repo} if repo else None,
        )


class DocumentationGenerationError(AppError):
    def __init__(self, *, target: Optional[str] = None):
        super().__init__(
            code="DOCUMENTATION_GENERATION_ERROR",
            message="Documentation generation failed.",
            status_code=500,
            details={"target": target} if target else None,
        )