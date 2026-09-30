class DatasetNameConflictError(Exception):
    status_code = 409
    code = "conflict"
    retryable = False
    message = "An active dataset with this name already exists."

    def __init__(self) -> None:
        super().__init__(self.message)


class UserEmailConflictError(Exception):
    status_code = 409
    code = "conflict"
    retryable = False
    message = "An account with this email already exists."

    def __init__(self) -> None:
        super().__init__(self.message)
