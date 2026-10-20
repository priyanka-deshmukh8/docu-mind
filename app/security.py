from fastapi import Header


def current_user_id(x_user_id: str | None = Header(default=None)) -> str:
    # Development-only identity. Replace with JWT/OIDC validation in production.
    return (x_user_id or "demo-user").strip()
