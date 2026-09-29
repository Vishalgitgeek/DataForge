from fastapi import Request, Response
from sqlalchemy.exc import IntegrityError
from starlette.middleware.base import RequestResponseEndpoint

from app.infrastructure import database
from app.core.errors import DatasetNameConflictError
from app.infrastructure.errors import is_dataset_name_conflict


async def transaction_middleware(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    session = database.session_factory()
    request.state.db_session = session

    try:
        try:
            response = await call_next(request)
        except BaseException:
            await session.rollback()
            raise

        if response.status_code >= 400:
            await session.rollback()
            return response

        try:
            await session.commit()
        except IntegrityError as error:
            await session.rollback()
            if is_dataset_name_conflict(error):
                raise DatasetNameConflictError() from error
            raise
        except BaseException:
            await session.rollback()
            raise

        return response
    finally:
        await session.close()
