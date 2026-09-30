from sqlalchemy.exc import IntegrityError

DATASET_NAME_UNIQUE_CONSTRAINT = "uq_datasets_active_owner_name"
USER_EMAIL_UNIQUE_CONSTRAINT = "users_email_key"


def is_dataset_name_conflict(error: IntegrityError) -> bool:
    """Return whether a database integrity error is the active dataset-name conflict."""
    pending: list[BaseException] = [error.orig]
    visited: set[int] = set()

    while pending:
        cause = pending.pop()
        if id(cause) in visited:
            continue
        visited.add(id(cause))

        if getattr(cause, "constraint_name", None) == DATASET_NAME_UNIQUE_CONSTRAINT:
            return True

        diagnostic = getattr(cause, "diag", None)
        if (
            getattr(diagnostic, "constraint_name", None)
            == DATASET_NAME_UNIQUE_CONSTRAINT
        ):
            return True

        if cause.__cause__ is not None:
            pending.append(cause.__cause__)
        if cause.__context__ is not None:
            pending.append(cause.__context__)

    return False


def is_user_email_conflict(error: IntegrityError) -> bool:
    """Return whether a database integrity error violates user email uniqueness."""
    pending: list[BaseException] = [error.orig]
    visited: set[int] = set()

    while pending:
        cause = pending.pop()
        if id(cause) in visited:
            continue
        visited.add(id(cause))

        if getattr(cause, "constraint_name", None) == USER_EMAIL_UNIQUE_CONSTRAINT:
            return True

        diagnostic = getattr(cause, "diag", None)
        if (
            getattr(diagnostic, "constraint_name", None)
            == USER_EMAIL_UNIQUE_CONSTRAINT
        ):
            return True

        if cause.__cause__ is not None:
            pending.append(cause.__cause__)
        if cause.__context__ is not None:
            pending.append(cause.__context__)

    return False
