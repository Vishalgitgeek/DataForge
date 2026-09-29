from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.errors import DatasetNameConflictError
from app.core.logging import request_id_context


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
