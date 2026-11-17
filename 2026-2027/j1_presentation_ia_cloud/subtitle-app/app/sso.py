"""Single sign-on with an OpenID Connect provider: authorization code flow with PKCE.

1. `start` sends the browser to the provider's login page. The attempt (state, nonce,
   PKCE verifier) is remembered in a short-lived cookie of that browser only.
2. The provider sends the browser back with a code; `finish` checks the state, trades
   the code for tokens over a direct server-to-provider request (authenticated with the
   client secret and the PKCE verifier) and reads the identity from the ID token.

The ID token comes straight from the provider's token endpoint, not through the browser:
as OpenID Connect Core 3.1.3.7 allows in that case, its claims (issuer, audience, expiry,
nonce) are checked but not its signature. Use HTTPS to the provider outside a private
network.
"""

import base64
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from app.config import Settings

COOKIE = "sso_attempt"
COOKIE_PATH = "/api/auth/sso"
ATTEMPT_S = 600  # time allowed to log in on the provider's page
_TIMEOUT_S = 10
_DISCOVERY_TTL_S = 3600
_CLOCK_SKEW_S = 120

_discovery_cache: dict[str, tuple[float, dict]] = {}


class SsoError(Exception):
    """The login cannot be completed; the message is shown to the user."""


@dataclass
class Identity:
    subject: str
    email: str | None
    name: str | None
    username: str | None


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _http_json(url: str, form: dict | None = None) -> dict:
    data = urllib.parse.urlencode(form).encode() if form is not None else None
    request = urllib.request.Request(url, data=data, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:300].decode(errors="replace")
        raise SsoError(f"Le fournisseur d'identité a refusé la demande ({exc.code}) : {detail}") from exc
    except (OSError, ValueError) as exc:
        raise SsoError(f"Fournisseur d'identité injoignable : {exc}") from exc


def discovery(settings: Settings) -> dict:
    """The provider's OpenID configuration, cached for an hour."""
    url = settings.oidc_discovery_url
    cached = _discovery_cache.get(url)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    document = _http_json(url)
    missing = {"issuer", "authorization_endpoint", "token_endpoint"} - document.keys()
    if missing:
        raise SsoError(f"Configuration OpenID incomplète : {', '.join(sorted(missing))}")
    _discovery_cache[url] = (time.monotonic() + _DISCOVERY_TTL_S, document)
    return document


def clear_cache() -> None:
    _discovery_cache.clear()


def start(settings: Settings, redirect_uri: str, mode: str) -> tuple[str, str]:
    """The provider URL to send the browser to, and the cookie value remembering the attempt.

    `mode` is "login" (log in or create an account) or "link" (attach the provider
    account to the account already logged in).
    """
    document = discovery(settings)
    attempt = {
        "state": secrets.token_urlsafe(24),
        "nonce": secrets.token_urlsafe(24),
        "verifier": secrets.token_urlsafe(48),
        "mode": mode,
    }
    params = {
        "response_type": "code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": redirect_uri,
        "scope": "openid profile email",
        "state": attempt["state"],
        "nonce": attempt["nonce"],
        "code_challenge": _b64url(hashlib.sha256(attempt["verifier"].encode()).digest()),
        "code_challenge_method": "S256",
    }
    endpoint = document["authorization_endpoint"]
    separator = "&" if "?" in endpoint else "?"
    return f"{endpoint}{separator}{urllib.parse.urlencode(params)}", _b64url(json.dumps(attempt).encode())


def read_attempt(cookie: str) -> dict | None:
    try:
        attempt = json.loads(_b64url_decode(cookie))
    except (ValueError, TypeError):
        return None
    if not isinstance(attempt, dict) or not {"state", "nonce", "verifier", "mode"} <= attempt.keys():
        return None
    return attempt


def _id_token_claims(token: str) -> dict:
    try:
        payload = token.split(".")[1]
        claims = json.loads(_b64url_decode(payload))
    except (IndexError, ValueError) as exc:
        raise SsoError("Jeton d'identité illisible") from exc
    if not isinstance(claims, dict):
        raise SsoError("Jeton d'identité illisible")
    return claims


def finish(settings: Settings, redirect_uri: str, code: str, state: str, attempt: dict) -> Identity:
    """Check the provider's answer and return who logged in."""
    if not secrets.compare_digest(state or "", attempt["state"]):
        raise SsoError("La tentative de connexion ne correspond pas : recommencez")
    document = discovery(settings)
    tokens = _http_json(document["token_endpoint"], {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": settings.oidc_client_id,
        "client_secret": settings.oidc_client_secret,
        "code_verifier": attempt["verifier"],
    })
    if "id_token" not in tokens:
        raise SsoError("Le fournisseur d'identité n'a pas renvoyé de jeton d'identité")
    claims = _id_token_claims(tokens["id_token"])

    audience = claims.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    now = time.time()
    if claims.get("iss") != document["issuer"]:
        raise SsoError("Jeton d'identité d'un autre émetteur")
    if settings.oidc_client_id not in audiences:
        raise SsoError("Jeton d'identité destiné à une autre application")
    if not isinstance(claims.get("exp"), (int, float)) or claims["exp"] < now - _CLOCK_SKEW_S:
        raise SsoError("Jeton d'identité expiré")
    if not secrets.compare_digest(str(claims.get("nonce", "")), attempt["nonce"]):
        raise SsoError("Jeton d'identité rejoué ou falsifié")
    if not claims.get("sub"):
        raise SsoError("Jeton d'identité sans identifiant")

    # An address the provider has not verified is kept out of the profile.
    email = claims.get("email") if claims.get("email_verified", True) else None
    return Identity(
        subject=str(claims["sub"]),
        email=email,
        name=claims.get("name"),
        username=claims.get("preferred_username"),
    )
