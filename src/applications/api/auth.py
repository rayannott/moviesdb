"""Authentication and authorization for the API."""

import hashlib
import json
import secrets
from enum import StrEnum
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from starlette.requests import Request

_HASH_ITERATIONS = 600_000
_HASH_ALGORITHM = "sha256"
_SALT_BYTES = 32

security = HTTPBasic()


class UserRole(StrEnum):
    """API user roles."""

    ADMIN = "admin"
    VIEWER = "viewer"


class AuthUser(BaseModel):
    """Stored API user with hashed credentials."""

    username: str
    password_hash: str
    salt: str
    role: UserRole

    def __str__(self) -> str:
        return f"AuthUser(username={self.username}, role={self.role.value})"


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Hash a password with PBKDF2-HMAC-SHA256.

    Returns:
        Tuple of (hash_hex, salt_hex).
    """
    salt_bytes = bytes.fromhex(salt) if salt else secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        _HASH_ALGORITHM, password.encode(), salt_bytes, _HASH_ITERATIONS
    )
    return dk.hex(), salt_bytes.hex()


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Verify a password against its stored hash."""
    computed_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(computed_hash, password_hash)


def load_users(filepath: Path) -> dict[str, AuthUser]:
    """Load users from a JSON config file."""
    if not filepath.exists():
        return {}
    with open(filepath) as f:
        data = json.load(f)
    return {u["username"]: AuthUser(**u) for u in data.get("users", [])}


def save_users(filepath: Path, users: dict[str, AuthUser]) -> None:
    """Persist users to a JSON config file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    data = {"users": [u.model_dump() for u in users.values()]}
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def get_current_user(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(security),
) -> AuthUser:
    """Authenticate via HTTP Basic and return the matching user."""
    users: dict[str, AuthUser] = request.app.state.auth_users
    user = users.get(credentials.username)
    if user is None or not verify_password(
        credentials.password, user.password_hash, user.salt
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user


def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    """Dependency that rejects non-admin users with 403."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
