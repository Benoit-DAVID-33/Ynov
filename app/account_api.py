"""The user's own account (profile, password, linked accounts, history) and single sign-on.

Mounted by app/api.py next to the media routes.
"""

import logging
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import accounts, auth, sso
from app.auth import current_user
from app.config import Settings, get_settings
from app.db import get_session
from app.models import User, UserIdentity, utcnow

log = logging.getLogger("api")

router = APIRouter(prefix="/api")


class ProfileIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=256)
    email: str | None = Field(default=None, max_length=512)


class PasswordIn(BaseModel):
    current_password: str | None = Field(default=None, max_length=256)
    new_password: str = Field(max_length=256)


class DeleteAccountIn(BaseModel):
    confirm: str = Field(max_length=64)
    password: str | None = Field(default=None, max_length=256)


def set_session_cookie(response: Response, request: Request, token: str, settings: Settings) -> None:
    response.set_cookie(
        auth.USER_COOKIE, token, max_age=int(settings.session_days * 24 * 3600), httponly=True,
        samesite="lax", secure=settings.cookie_secure or request.url.scheme == "https",
    )


def _account(user: User, session: Session, settings: Settings) -> dict:
    return {
        **accounts.profile(user),
        "sso": {"enabled": settings.sso_enabled, "provider": settings.oidc_provider,
                "label": settings.oidc_label},
        "stats": accounts.user_stats(session, user.id, settings),
    }


# --- profile ------------------------------------------------------------------

@router.get("/account")
def get_account(
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    return _account(user, session, settings)


@router.patch("/account")
def update_account(
    body: ProfileIn,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Only the fields sent are changed. The username and the role are not editable here."""
    try:
        if "display_name" in body.model_fields_set:
            user.display_name = auth.validate_display_name(body.display_name)
        if "email" in body.model_fields_set:
            user.email = auth.validate_email(body.email)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    session.commit()
    return _account(user, session, settings)


@router.post("/account/password")
def change_password(
    body: PasswordIn,
    request: Request,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Set or change the password; the account's other sessions are logged out."""
    address = auth.client_address(request)
    if user.password_hash is not None:
        if auth.login_limiter.blocked(address):
            raise HTTPException(429, "Trop de tentatives : réessayez dans une minute")
        if not auth.verify_password(user.password_hash, body.current_password or ""):
            auth.login_limiter.record(address)
            raise HTTPException(403, "Mot de passe actuel incorrect")
    try:
        auth.set_password(user, body.new_password)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    auth.end_sessions(session, user, keep_token=auth.session_token(request))
    session.commit()
    log.info("account '%s' changed its password", user.username)
    return {"status": "ok"}


@router.delete("/account/identities/{provider}", status_code=204)
def unlink_identity(
    provider: str,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> None:
    identity = session.scalar(
        select(UserIdentity).where(UserIdentity.user_id == user.id, UserIdentity.provider == provider)
    )
    if identity is None:
        raise HTTPException(404, "Aucun compte associé pour ce fournisseur")
    if user.password_hash is None and len(user.identities) == 1:
        raise HTTPException(
            409, "Définissez d'abord un mot de passe : sans lui, vous ne pourriez plus vous connecter"
        )
    session.delete(identity)
    session.commit()


@router.get("/account/jobs")
def account_jobs(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    return accounts.history(session, user.id, limit, offset)


@router.delete("/account", status_code=204)
def delete_own_account(
    body: DeleteAccountIn,
    request: Request,
    response: Response,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> None:
    """Right to erasure: the account, its files and its history go for good."""
    if body.confirm.strip().lower() != user.username:
        raise HTTPException(422, "Saisissez votre nom d'utilisateur pour confirmer")
    if user.password_hash is not None and not auth.verify_password(user.password_hash, body.password or ""):
        raise HTTPException(403, "Mot de passe incorrect")
    username = user.username
    try:
        accounts.delete_account(session, user, settings)
    except accounts.AccountConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    session.commit()
    response.delete_cookie(auth.USER_COOKIE)
    log.info("account '%s' deleted by its owner", username)


# --- single sign-on -----------------------------------------------------------

def _back(path: str, error: str | None = None) -> RedirectResponse:
    url = f"{path}?{urllib.parse.urlencode({'error': error})}" if error else path
    response = RedirectResponse(url, status_code=303)
    response.delete_cookie(sso.COOKIE, path=sso.COOKIE_PATH)
    return response


def _valid_email_or_none(raw: str | None) -> str | None:
    try:
        return auth.validate_email(raw)
    except ValueError:
        return None


def _redirect_uri(request: Request) -> str:
    return str(request.url_for("sso_callback"))


@router.get("/auth/sso/login")
def sso_login(
    request: Request,
    mode: str = "login",
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Send the browser to the provider's login page."""
    if not settings.sso_enabled:
        raise HTTPException(404, "Connexion unique non configurée")
    if mode not in ("login", "link"):
        raise HTTPException(422, "Mode inconnu")
    back = "/account.html" if mode == "link" else "/login.html"
    if mode == "link" and auth.user_for_token(session, auth.session_token(request)) is None:
        return _back("/login.html", "Connectez-vous d'abord pour associer un compte")
    try:
        url, attempt = sso.start(settings, _redirect_uri(request), mode)
    except sso.SsoError as exc:
        log.warning("sso: %s", exc)
        return _back(back, str(exc))
    response = RedirectResponse(url, status_code=303)
    response.set_cookie(
        sso.COOKIE, attempt, max_age=sso.ATTEMPT_S, path=sso.COOKIE_PATH, httponly=True,
        # lax: the cookie must come back with the provider's top-level redirect.
        samesite="lax", secure=settings.cookie_secure or request.url.scheme == "https",
    )
    return response


@router.get("/auth/sso/callback", name="sso_callback")
def sso_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    error_description: str = "",
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    attempt = sso.read_attempt(request.cookies.get(sso.COOKIE, ""))
    if not settings.sso_enabled or attempt is None:
        return _back("/login.html", "Tentative de connexion expirée : recommencez")
    link = attempt["mode"] == "link"
    back = "/account.html" if link else "/login.html"
    if error:
        return _back(back, "Connexion annulée" if error == "access_denied" else error_description or error)
    try:
        identity = sso.finish(settings, _redirect_uri(request), code, state, attempt)
    except sso.SsoError as exc:
        log.warning("sso: %s", exc)
        return _back(back, str(exc))

    provider = settings.oidc_provider
    linked = session.scalar(
        select(UserIdentity).where(UserIdentity.provider == provider, UserIdentity.subject == identity.subject)
    )

    if link:
        user = auth.user_for_token(session, auth.session_token(request))
        if user is None:
            return _back("/login.html", "Session expirée : reconnectez-vous")
        if linked is not None and linked.user_id != user.id:
            return _back(back, f"Ce compte {settings.oidc_label} est déjà associé à un autre compte")
        if linked is None:
            if any(i.provider == provider for i in user.identities):
                return _back(back, f"Un autre compte {settings.oidc_label} est déjà associé")
            session.add(UserIdentity(user_id=user.id, provider=provider, subject=identity.subject,
                                     email=identity.email))
        session.commit()
        log.info("account '%s' linked to %s", user.username, provider)
        return _back("/account.html?linked=1")

    if linked is not None:
        user = linked.user
        if user.disabled_at is not None:
            return _back(back, "Ce compte est désactivé")
    else:
        # First visit: an account is created, without password (it can be set later).
        local_part = (identity.email or "").split("@")[0]
        user = User(
            username=auth.available_username(session, identity.username or local_part or "user"),
            password_hash=None,
            display_name=auth.validate_display_name((identity.name or "")[:64]),
            email=_valid_email_or_none(identity.email),
        )
        session.add(user)
        session.flush()
        linked = UserIdentity(user_id=user.id, provider=provider, subject=identity.subject,
                              email=identity.email)
        session.add(linked)
        log.info("account '%s' created through %s", user.username, provider)

    now = utcnow()
    linked.last_login_at = user.last_login_at = now
    linked.email = identity.email
    token, _ = auth.open_session(session, user, settings.session_days * 24 * 3600)
    session.commit()
    response = _back("/")
    set_session_cookie(response, request, token, settings)
    return response
