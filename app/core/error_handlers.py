from __future__ import annotations

import uuid
import traceback
import logging
from typing import Any, Dict, Optional, List
from datetime import datetime

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import (SQLAlchemyError,IntegrityError,OperationalError,ProgrammingError,DataError,DatabaseError)
from app.core.exceptions import AppError



# Service → Exception fırlatır
#           ↓
# FastAPI yakalar
#           ↓
# Bu handler dosyası devreye girer
#           ↓
# • Log basar (error_id ile)
# • HTTP status belirler
# • Standart JSON response üretir




logger = logging.getLogger(__name__)


class ErrorLogger:
    # Log işini yapan class. Her hataya benzersiz bir ID veriyor.
    # Client bunu görür {"error_id": "abc-123"} ve id ye gore detaylari bulabilir.

    @staticmethod
    def log_error(              
        error: Exception,          
        *,
        request: Optional[Request] = None,
        error_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not error_id:
            error_id = str(uuid.uuid4()) 

        error_context: Dict[str, Any] = {
            "error_id": error_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        if request:
            error_context.update(
                {
                    "request_method": request.method,
                    "request_path": request.url.path,
                    "request_query": dict(request.query_params),
                    "client_ip": ErrorLogger._extract_client_ip(request),
                    "user_agent": request.headers.get("user-agent", "unknown"),
                    "request_id": getattr(request.state, "request_id", "unknown"),
                }
            )

        if context:
            error_context.update(context)


        # O anki exception’ın tüm stack trace’ini string olarak üretir.
        # Hata nerede oluştu? Hangi dosyada? Hangi satırda? Hangi fonksiyon çağrılırken?
        error_context["stack_trace"] = traceback.format_exc() 



        # log seviyesi belirlenir
        if isinstance(error, (HTTPException, StarletteHTTPException)):    # isinstance Python’da tip kontrolü yapmak için kullanılır. 
            if getattr(error, "status_code", 500) >= 500:                 # yani error (HTTPException, StarletteHTTPException) miras mi almis 
                logger.error("HTTP server error", extra=error_context)    # obj.attribute_name ile aynı şeyi yapar. yani error.status_code. 3. parametre default verilir. hata firlatmaz
            else:
                logger.warning("HTTP client error", extra=error_context)
        elif isinstance(error, AppError):
            if error.status_code >= 500:
                logger.error("Domain error (server)", extra=error_context)
            else:
                logger.warning("Domain error (client)", extra=error_context)
        elif isinstance(error, SQLAlchemyError):
            logger.error("Database error", extra=error_context)
        elif isinstance(error, RequestValidationError):
            logger.warning("Request validation error", extra=error_context)
        else:
            logger.error("Unexpected error", extra=error_context)

        return error_id




    @staticmethod
    def _extract_client_ip(request: Request) -> str:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

        if request.client:
            return request.client.host

        return "unknown"


def create_error_response(    # client’a dönecek JSON’u üretir:
    *,
    status_code: int,
    code: str,
    message: str,
    error_id: str,
    details: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    payload: Dict[str, Any] = {
        "error": True,
        "code": code,
        "message": message,
        "error_id": error_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    if details:
        payload["details"] = details

    return JSONResponse(status_code=status_code, content=payload)


def _format_validation_errors(exc: RequestValidationError) -> List[Dict[str, Any]]:
    formatted: List[Dict[str, Any]] = []
    for err in exc.errors():
        loc = err.get("loc", [])
        # loc example: ('body','email') or ('query','page')
        field = " -> ".join(str(x) for x in loc)
        formatted.append(
            {
                "field": field,
                "message": err.get("msg"),
                "type": err.get("type"),
            }
        )
    return formatted


# ---------------- Handlers ----------------

async def app_error_handler(request: Request, exc: AppError) -> JSONResponse: # yazdigimiz custom AppError’ları yakalar.
    error_id = ErrorLogger.log_error(
        exc,
        request=request,
        context={"status_code": exc.status_code, "code": exc.code, "details": exc.details},
    )

    return create_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.client_message,
        error_id=error_id,
        details=exc.details,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse: # http errorlar buraya duser
    error_id = ErrorLogger.log_error(
        exc,
        request=request,
        context={"status_code": exc.status_code},
    )

    message = exc.detail if isinstance(exc.detail, str) else "Request failed"

    return create_error_response(
        status_code=exc.status_code,
        code="HTTP_ERROR",
        message=message,
        error_id=error_id,
        details=exc.detail if isinstance(exc.detail, dict) else None,
    )


async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    error_id = ErrorLogger.log_error(
        exc,
        request=request,
        context={"status_code": exc.status_code},
    )

    return create_error_response(
        status_code=exc.status_code,
        code="HTTP_ERROR",
        message=str(exc.detail),
        error_id=error_id,
    )


async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse: # Field bazlı hataları formatlar
    validation_details = _format_validation_errors(exc)
    error_id = ErrorLogger.log_error(
        exc,
        request=request,
        context={"validation_errors": validation_details},
    )

    return create_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="VALIDATION_ERROR",
        message="Request validation failed",
        error_id=error_id,
        details={"validation_errors": validation_details},
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse: # DB’den hata gelirse buraya düşer.
    # classify DB errors
    if isinstance(exc, IntegrityError):
        status_code = status.HTTP_409_CONFLICT
        code = "DB_INTEGRITY_ERROR"
        message = "Data integrity constraint violation"
    elif isinstance(exc, OperationalError):
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        code = "DB_OPERATIONAL_ERROR"
        message = "Database temporarily unavailable"
    elif isinstance(exc, DataError):
        status_code = status.HTTP_400_BAD_REQUEST
        code = "DB_DATA_ERROR"
        message = "Invalid data provided"
    elif isinstance(exc, ProgrammingError):
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        code = "DB_PROGRAMMING_ERROR"
        message = "Database programming error"
    elif isinstance(exc, DatabaseError):
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        code = "DB_ERROR"
        message = "Database error occurred"
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        code = "DB_ERROR"
        message = "Database error occurred"

    error_id = ErrorLogger.log_error(
        exc,
        request=request,
        context={
            "status_code": status_code,
            "code": code,
            "original_error": str(getattr(exc, "orig", None)),
        },
    )

    # NOTE: Keep response sanitized (no raw SQL / driver messages)
    return create_error_response(
        status_code=status_code,
        code=code,
        message=message,
        error_id=error_id,
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse: # Bilinmeyen her şey buraya düşer.
    error_id = ErrorLogger.log_error(exc, request=request, context={"unexpected_error": True})

    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_ERROR",
        message="An unexpected error occurred",
        error_id=error_id,
    )


def register_exception_handlers(app) -> None: # AppError türü bir exception fırlatılırsa otomatik app_error_handler çalışacak.
    """
    Register exception handlers on FastAPI app.
    Call once in main.py after app = FastAPI().
    """
    app.add_exception_handler(AppError, app_error_handler)

    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)

    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)

    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)

    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("KAI-Flow exception handlers registered")