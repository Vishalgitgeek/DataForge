from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import (
    AuthenticationError,
    DatasetNameConflictError,
    InvalidCredentialsError,
    ResourceNotFoundError,
    UserEmailConflictError,
)
from app.core.logging import request_id_context


async def request_validation_exception_handler(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed.",
                "details": {
                    "errors": jsonable_encoder(
                        [
                            {
                                "location": list(item["loc"]),
                                "message": item["msg"],
                                "type": item["type"],
                            }
                            for item in error.errors()
                        ]
                    )
                },
                "retryable": False,
            },
            "request_id": request_id_context.get(),
        },
    )


async def dataset_name_conflict_exception_handler(
    request: Request,
    error: DatasetNameConflictError,
) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "retryable": error.retryable,
            },
            "request_id": request_id_context.get(),
        },
    )


async def resource_not_found_exception_handler(
    request: Request,
    error: ResourceNotFoundError,
) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "retryable": error.retryable,
            },
            "request_id": request_id_context.get(),
        },
    )


async def user_email_conflict_exception_handler(
    request: Request,
    error: UserEmailConflictError,
) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "retryable": error.retryable,
            },
            "request_id": request_id_context.get(),
        },
    )


async def invalid_credentials_exception_handler(
    request: Request,
    error: InvalidCredentialsError,
) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "retryable": error.retryable,
            },
            "request_id": request_id_context.get(),
        },
    )


async def authentication_exception_handler(
    request: Request,
    error: AuthenticationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "retryable": error.retryable,
            },
            "request_id": request_id_context.get(),
        },
    )
