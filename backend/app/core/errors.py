"""Error model shared by every module.

All error responses use one envelope so the frontend handles failures uniformly:

    {"error": {"code": "invalid_credentials", "message": "...", "request_id": "..."}}

``code`` is a stable, machine-readable identifier. ``message`` is user-facing (pt-BR).
"""

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_context import current_request_id

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"
    message: str = "Não foi possível processar a solicitação."

    def __init__(
        self,
        message: str | None = None,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.headers = headers
        super().__init__(self.message)


class NotAuthenticated(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "not_authenticated"
    message = "Sua sessão expirou. Entre novamente."


class InvalidCredentials(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "invalid_credentials"
    message = "E-mail ou senha incorretos."


class IncorrectPassword(AppError):
    """Wrong password while already authenticated: 400, not 401, so clients do not
    mistake it for an expired session."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "incorrect_password"
    message = "Senha incorreta."


class PermissionDenied(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"
    message = "Você não tem permissão para realizar esta ação."


class CsrfFailed(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "csrf_failed"
    message = "Requisição bloqueada por segurança. Recarregue a página e tente novamente."


class NotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "Recurso não encontrado."


class Conflict(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "A operação conflita com o estado atual."


class RateLimited(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    message = "Muitas tentativas. Aguarde alguns minutos e tente novamente."

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(headers={"Retry-After": str(max(retry_after_seconds, 1))})


def _envelope(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "request_id": current_request_id()} | extra}


_HTTP_CODES: dict[int, tuple[str, str]] = {
    status.HTTP_404_NOT_FOUND: ("not_found", "Recurso não encontrado."),
    status.HTTP_405_METHOD_NOT_ALLOWED: ("method_not_allowed", "Método não permitido."),
}


_LENGTH_RULES = {
    "string_too_short": ("min_length", "Use pelo menos {} caracteres."),
    "too_short": ("min_length", "Use pelo menos {} caracteres."),
    "string_too_long": ("max_length", "Use no máximo {} caracteres."),
    "too_long": ("max_length", "Use no máximo {} caracteres."),
}
_FIXED_MESSAGES = {
    "missing": "Campo obrigatório.",
    "extra_forbidden": "Campo não permitido.",
    "enum": "Opção inválida.",
    "uuid_parsing": "Identificador inválido.",
    "uuid_type": "Identificador inválido.",
}


def _translate(error: Mapping[str, Any]) -> str:
    """User-facing pt-BR message for a Pydantic error. Never includes the input value."""
    kind = error["type"]
    if kind in _LENGTH_RULES:
        key, template = _LENGTH_RULES[kind]
        return template.format((error.get("ctx") or {}).get(key))
    if kind in _FIXED_MESSAGES:
        return _FIXED_MESSAGES[kind]
    if error["loc"] and error["loc"][-1] == "email":
        return "Informe um e-mail válido."
    return "Valor inválido."


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            _envelope(exc.code, exc.message), status_code=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Echoing ``input`` back could reflect passwords into logs or the UI, so only the
        # location and message of each problem are returned.
        fields = [
            {"loc": [str(part) for part in err["loc"]], "message": _translate(err)}
            for err in exc.errors()
        ]
        return JSONResponse(
            _envelope("validation_error", "Verifique os campos informados.", fields=fields),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = _HTTP_CODES.get(exc.status_code, ("http_error", "Erro na requisição."))
        return JSONResponse(
            _envelope(code, message), status_code=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error", exc_info=exc)
        return JSONResponse(
            _envelope("internal_error", "Erro inesperado. Tente novamente em instantes."),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
