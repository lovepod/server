"""Application-specific errors mapped to HTTP responses in `main`."""


class AppError(Exception):
    """Base error with HTTP status and API-safe detail message."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class NotFoundError(AppError):
    def __init__(self, detail: str = "Resource not found") -> None:
        super().__init__(404, detail)


class BadRequestError(AppError):
    def __init__(self, detail: str = "Bad request") -> None:
        super().__init__(400, detail)


class UnauthorizedError(AppError):
    def __init__(self, detail: str = "Unauthorized") -> None:
        super().__init__(401, detail)


class PayloadTooLargeError(AppError):
    def __init__(self, detail: str = "Payload too large") -> None:
        super().__init__(413, detail)


class ServiceUnavailableError(AppError):
    def __init__(self, detail: str = "Service unavailable") -> None:
        super().__init__(503, detail)


class InternalError(AppError):
    def __init__(self, detail: str = "Internal error") -> None:
        super().__init__(500, detail)
