"""Accounts: password hashing, login sessions, rate limiting and the FastAPI dependencies."""

import hashlib
import logging
import re
import secrets
import sys
import time
from collections import defaultdict, deque
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_session
from app.models import AuthSession, User, utcnow

log = logging.getLogger("auth")

USER_COOKIE = "session"
ROLE_USER = "user"
ROLE_ADMIN = "admin"

USERNAME_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]{2,31}")
USERNAME_RULE = (
    "Le nom d'utilisateur contient de 3 à 32 caractères : lettres, chiffres, point, tiret "
    "ou tiret bas, en commençant par une lettre ou un chiffre"
)
PASSWORD_MIN = 8
PASSWORD_MAX = 128  # argon2 cost grows with the input: bounded so that it cannot be abused

_hasher = PasswordHasher()
# Checked when the account does not exist, so that "unknown user" and "wrong
# password" take the same time.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


class UsernameTaken(Exception):
    pass


def normalize_username(raw: str) -> str:
    return raw.strip().lower()


def validate_username(raw: str) -> str:
    username = normalize_username(raw)
    if not USERNAME_PATTERN.fullmatch(username):
        raise ValueError(USERNAME_RULE)
    return username


def validate_password(password: str) -> None:
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        raise ValueError(
            f"Le mot de passe contient de {PASSWORD_MIN} à {PASSWORD_MAX} caractères"
        )


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_user(session: Session, username: str, password: str, role: str = ROLE_USER) -> User:
    """Add an account. Raises ValueError on an invalid name or password, UsernameTaken."""
    username = validate_username(username)
    validate_password(password)
    user = User(username=username, password_hash=hash_password(password), role=role)
    try:
        # A savepoint: losing a race on the unique name must not undo the caller's work.
        with session.begin_nested():
            session.add(user)
    except IntegrityError as exc:
        raise UsernameTaken(username) from exc
    return user


def authenticate(
    session: Session, username: str, password: str, role: str | None = None
) -> User | None:
    user = session.scalar(select(User).where(User.username == normalize_username(username)))
    valid = verify_password(user.password_hash if user else _DUMMY_HASH, password)
    if user is None or not valid or user.disabled_at is not None or (role and user.role != role):
        return None
    user.last_login_at = utcnow()
    return user


def _token_id(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def open_session(session: Session, user: User, lifetime_s: float) -> tuple[str, float]:
    """Record a login. Returns the cookie token and its lifetime in seconds."""
    token = secrets.token_urlsafe(32)
    session.add(
        AuthSession(
            id=_token_id(token), user_id=user.id, expires_at=utcnow() + timedelta(seconds=lifetime_s)
        )
    )
    return token, lifetime_s


def close_session(session: Session, token: str) -> None:
    session.execute(delete(AuthSession).where(AuthSession.id == _token_id(token)))


def user_for_token(session: Session, token: str, role: str | None = None) -> User | None:
    """The account of a valid, unexpired session; None otherwise (or if the role differs)."""
    if not token:
        return None
    user = session.scalar(
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(AuthSession.id == _token_id(token), AuthSession.expires_at > utcnow())
    )
    if user is None or user.disabled_at is not None or (role and user.role != role):
        return None
    return user


def purge_expired_sessions(session: Session) -> int:
    return session.execute(delete(AuthSession).where(AuthSession.expires_at <= utcnow())).rowcount


def ensure_admin(session: Session, settings: Settings) -> None:
    """Create the first administrator from ADMIN_USERNAME / ADMIN_PASSWORD, if none exists."""
    if session.scalar(select(User.id).where(User.role == ROLE_ADMIN).limit(1)) is not None:
        return
    password = settings.admin_password
    generated = not password
    if generated:
        password = secrets.token_urlsafe(12)
    try:
        create_user(session, settings.admin_username, password, ROLE_ADMIN)
    except (ValueError, UsernameTaken) as exc:
        log.warning("administrator account not created: %s", exc)
        return
    log.info("administrator account '%s' created", settings.admin_username)
    if generated:
        # On stderr only (docker compose logs admin): not in the log files the console serves.
        print(
            f"\n*** ADMIN_PASSWORD absent : compte administrateur '{settings.admin_username}' "
            f"créé avec le mot de passe {password}\n*** Notez-le : il n'est affiché qu'une fois "
            "(changement : python -m app.users passwd).\n",
            file=sys.stderr, flush=True,
        )


class AttemptLimiter:
    """At most `limit` attempts per `window_s` seconds for each key (an IP address).

    In memory: each process counts on its own, which is enough to slow down guessing.
    """

    def __init__(self, limit: int, window_s: float):
        self.limit = limit
        self.window_s = window_s
        self._attempts: dict[str, deque[float]] = defaultdict(deque)

    def _recent(self, key: str) -> deque[float]:
        attempts = self._attempts[key]
        while attempts and attempts[0] <= time.monotonic() - self.window_s:
            attempts.popleft()
        if not attempts:
            self._attempts.pop(key, None)
        return attempts

    def blocked(self, key: str) -> bool:
        return len(self._recent(key)) >= self.limit

    def record(self, key: str) -> None:
        self._attempts[key].append(time.monotonic())

    def clear(self, key: str | None = None) -> None:
        if key is None:
            self._attempts.clear()
        else:
            self._attempts.pop(key, None)


login_limiter = AttemptLimiter(limit=5, window_s=60)
registration_limiter = AttemptLimiter(limit=10, window_s=3600)


def reset_limiters() -> None:
    login_limiter.clear()
    registration_limiter.clear()


def client_address(request: Request) -> str:
    return request.client.host if request.client else "?"


def current_user(request: Request, session: Session = Depends(get_session)) -> User:
    user = user_for_token(session, request.cookies.get(USER_COOKIE, ""))
    if user is None:
        raise HTTPException(401, "Connexion requise")
    return user


def current_user_id(user: User = Depends(current_user)) -> str:
    return user.id
