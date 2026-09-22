from fastapi import HTTPException, status


class EventAIError(Exception):
    """Base application error."""


class NotImplementedStageError(EventAIError):
    """Raised when a later-stage module is called too early."""


class JobFailedError(EventAIError):
    def __init__(self, message: str, code: str = "job_failed") -> None:
        super().__init__(message)
        self.code = code


def http_error(status_code: int, detail: str, code: str | None = None) -> HTTPException:
    payload: dict[str, str] = {"detail": detail}
    if code:
        payload["code"] = code
    return HTTPException(status_code=status_code, detail=payload)


unauthorized = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail={"detail": "Could not validate credentials", "code": "unauthorized"},
    headers={"WWW-Authenticate": "Bearer"},
)
