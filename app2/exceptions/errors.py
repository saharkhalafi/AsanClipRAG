# app2/exceptions/errors.py
class AppBaseError(Exception):
    """Base error for all application errors"""
    def __init__(self, message: str = "Internal server error", status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ValidationError(AppBaseError):
    """Invalid input or business rule violation"""

    def __init__(self, message: str = "Invalid input", *, context: dict | None = None):
        super().__init__(message, 400)
        self.context = context or {}


class NotFoundError(AppBaseError):
    """Resource not found"""
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, 404)


class RateLimitError(AppBaseError):
    """Rate limit exceeded"""
    def __init__(self, message: str = "Too many requests"):
        super().__init__(message, 429)


class DatabaseError(AppBaseError):
    """Database related errors"""
    def __init__(self, message: str = "Database error"):
        super().__init__(message, 500)
