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


class InvalidCredentialsError(Exception):
    status_code = 401
    code = "invalid_credentials"
    retryable = False
    message = "Invalid email or password."

    def __init__(self) -> None:
        super().__init__(self.message)


class AuthenticationError(Exception):
    status_code = 401
    code = "authentication_required"
    retryable = False
    message = "Authentication is required."

    def __init__(self) -> None:
        super().__init__(self.message)


class AccessTokenExpiredError(AuthenticationError):
    code = "token_expired"
    message = "The access token has expired."


class RefreshTokenExpiredError(AuthenticationError):
    code = "token_expired"
    message = "The refresh token has expired."


class RefreshTokenReuseError(AuthenticationError):
    pass
