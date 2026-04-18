from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional
from fastapi import status


@dataclass
class ErrorMeta:
    code: str
    message: str
    status_code: int
    details: Optional[Dict[str, Any]] = None
    safe_message: Optional[str] = None


class AppError(Exception):
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

    @property
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


# ---- Error Category Bases ----


class ValidationAppError(AppError):
    def __init__(
        self, code: str, message: str, *, details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code, message, status_code=status.HTTP_400_BAD_REQUEST, details=details
        )


class NotFoundAppError(AppError):
    def __init__(
        self, code: str, message: str, *, details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code, message, status_code=status.HTTP_404_NOT_FOUND, details=details
        )


class ConflictAppError(AppError):
    def __init__(
        self, code: str, message: str, *, details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code, message, status_code=status.HTTP_409_CONFLICT, details=details
        )


class AuthAppError(AppError):
    def __init__(
        self, code: str, message: str, *, details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code, message, status_code=status.HTTP_401_UNAUTHORIZED, details=details
        )


class ForbiddenAppError(AppError):
    def __init__(
        self, code: str, message: str, *, details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code, message, status_code=status.HTTP_403_FORBIDDEN, details=details
        )


class RateLimitAppError(AppError):
    def __init__(
        self, code: str, message: str, *, details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code,
            message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
        )


class ServiceUnavailableAppError(AppError):
    def __init__(
        self, code: str, message: str, *, details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code,
            message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
        )


# ---- Concrete Errors ----


class EmailAlreadyExistsError(ConflictAppError):
    def __init__(self, *, email: Optional[str] = None):
        super().__init__(
            code="EMAIL_ALREADY_EXISTS",
            message="Email already exists.",
            details={"email": email} if email else None,
        )


class UserNotFoundError(NotFoundAppError):
    def __init__(self, *, user_id: Optional[int] = None):
        super().__init__(
            code="USER_NOT_FOUND",
            message="User not found.",
            details={"user_id": user_id} if user_id is not None else None,
        )


class RepoNotIndexedError(NotFoundAppError):
    def __init__(self, *, repo: Optional[str] = None):
        super().__init__(
            code="REPO_NOT_INDEXED",
            message="Repository has not been indexed yet.",
            details={"repo": repo} if repo else None,
        )


class RepoIndexError(AppError):
    def __init__(self, *, repo: Optional[str] = None, reason: Optional[str] = None):
        super().__init__(
            code="REPO_INDEX_ERROR",
            message="Repository indexing failed.",
            status_code=500,
            details={
                **({"repo": repo} if repo else {}),
                **({"reason": reason} if reason else {}),
            }
            or None,
        )


class EmbeddingError(AppError):
    def __init__(
        self, *, file_path: Optional[str] = None, reason: Optional[str] = None
    ):
        super().__init__(
            code="EMBEDDING_ERROR",
            message="Embedding generation failed.",
            status_code=500,
            details={
                **({"file_path": file_path} if file_path else {}),
                **({"reason": reason} if reason else {}),
            }
            or None,
        )


class PRNotFoundError(NotFoundAppError):
    def __init__(self, *, pr_number: Optional[int] = None):
        super().__init__(
            code="PR_NOT_FOUND",
            message="Pull request not found.",
            details={"pr_number": pr_number} if pr_number else None,
        )


class FileNotFoundInRepoError(NotFoundAppError):
    def __init__(self, *, file_path: Optional[str] = None, repo: Optional[str] = None):
        super().__init__(
            code="FILE_NOT_FOUND_IN_REPO",
            message="File not found in repository.",
            details={
                **({"file_path": file_path} if file_path else {}),
                **({"repo": repo} if repo else {}),
            }
            or None,
        )


class GitHubAPIError(AppError):
    def __init__(
        self,
        *,
        status_code: int = 500,
        repo: Optional[str] = None,
        reason: Optional[str] = None,
    ):
        super().__init__(
            code="GITHUB_API_ERROR",
            message="GitHub API error.",
            status_code=status_code,
            details={
                **({"repo": repo} if repo else {}),
                **({"reason": reason} if reason else {}),
            }
            or None,
        )


class DocumentationGenerationError(AppError):
    def __init__(
        self,
        *,
        target: Optional[str] = None,
        http_code: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        computed_details = details or ({"target": target} if target else None)
        super().__init__(
            code="DOCUMENTATION_GENERATION_ERROR",
            message="Documentation generation failed.",
            status_code=500,
            details=computed_details,
        )
        self.http_code = http_code


class AIRateLimitError(AppError):
    def __init__(self, owner: str, repo: str, error_str: str = ""):
        if "daily" in error_str.lower() or "quota" in error_str.lower():
            message = "AI model daily token quota reached. Please try again tomorrow."
        else:
            message = "AI model rate limit reached. Please wait a moment and try again."

        super().__init__(
            code="RATE_LIMIT_ERROR",
            message=message,
            status_code=429,
            details={"owner": owner, "repo": repo},
        )


class FileContextError(AppError):
    def __init__(
        self, *, file_path: Optional[str] = None, reason: Optional[str] = None
    ):
        super().__init__(
            code="FILE_CONTEXT_ERROR",
            message="Could not fetch file for documentation context.",
            status_code=500,
            details={
                **({"file_path": file_path} if file_path else {}),
                **({"reason": reason} if reason else {}),
            }
            or None,
        )
