"""Domain-safe exceptions exposed by the API."""


class ApplicationError(Exception):
    """Base class for expected application errors."""

    status_code = 400
    code = "application_error"

    def __init__(
        self, message: str, *, code: str | None = None, status_code: int | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(ApplicationError):
    status_code = 404
    code = "not_found"


class UnauthorizedError(ApplicationError):
    status_code = 401
    code = "unauthorized"


class ConflictError(ApplicationError):
    status_code = 409
    code = "conflict"
