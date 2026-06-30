"""Application-level error carrying an HTTP status and a machine-readable code."""

class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code   # e.g. 400, 404, 409
        self.code = code                 # e.g. "ORDER_NOT_FOUND"
        self.message = message
