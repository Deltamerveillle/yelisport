"""Domain-safe exceptions exposed by the API."""


class ApplicationError(Exception):
    """Base class for expected application errors."""

    status_code = 400
    code = "application_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(ApplicationError):
    status_code = 404
    code = "not_found"


class UnauthorizedError(ApplicationError):
    status_code = 401
    code = "unauthorized"
