import hmac

from fastapi import Header, HTTPException, status

from app.config import get_settings


def require_api_token(authorization: str | None = Header(default=None)) -> None:
    expected = get_settings().api_token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token ausente")
    supplied = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
