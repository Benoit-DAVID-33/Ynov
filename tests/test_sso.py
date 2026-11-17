import base64
import json
import time
import urllib.parse

import pytest
from fastapi.testclient import TestClient

from app import sso
from app.config import get_settings
from app.db import session_scope
from app.models import User, UserIdentity, utcnow
from tests.conftest import USER_PASSWORD

ISSUER = "http://sso.example/realms/subtitle"


def _b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


class FakeProvider:
    """Stands in for the OpenID provider: discovery document and token endpoint."""

    def __init__(self):
        self.subject = "kc-123"
        self.claims = {}
        self.nonce = None
        self.token_requests = []

    def http_json(self, url, form=None):
        if form is None:
            return {
                "issuer": ISSUER,
                "authorization_endpoint": f"{ISSUER}/auth",
                "token_endpoint": "http://sso-internal/token",
            }
        self.token_requests.append(form)
        claims = {
            "iss": ISSUER, "aud": "subtitle-app", "exp": time.time() + 300, "nonce": self.nonce,
            "sub": self.subject, "email": "Marie.Curie@example.org", "email_verified": True,
            "name": "Marie Curie", "preferred_username": "marie", **self.claims,
        }
        return {"access_token": "x", "id_token": f"{_b64({'alg': 'RS256'})}.{_b64(claims)}.sig"}


@pytest.fixture
def provider(settings, monkeypatch):
    monkeypatch.setenv("OIDC_DISCOVERY_URL", "http://sso-internal/.well-known/openid-configuration")
    monkeypatch.setenv("OIDC_CLIENT_ID", "subtitle-app")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "secret")
    get_settings.cache_clear()
    sso.clear_cache()
    fake = FakeProvider()
    monkeypatch.setattr(sso, "_http_json", fake.http_json)
    return fake


def _login_through_provider(browser, provider, mode="login", state=None):
    """Follow the flow as a browser would; returns the response of the callback."""
    start = browser.get(f"/api/auth/sso/login?mode={mode}", follow_redirects=False)
    assert start.status_code == 303, start.text
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(start.headers["location"]).query))
    provider.nonce = params["nonce"]
    query = urllib.parse.urlencode({"code": "the-code", "state": state or params["state"]})
    return browser.get(f"/api/auth/sso/callback?{query}", follow_redirects=False)


@pytest.fixture
def anonymous(client):
    return TestClient(client.app)


def test_config_announces_the_provider(anonymous, provider):
    assert anonymous.get("/api/config").json()["sso"] == {"enabled": True, "label": "Keycloak"}


def test_sso_is_off_without_configuration(anonymous):
    assert anonymous.get("/api/config").json()["sso"]["enabled"] is False
    assert anonymous.get("/api/auth/sso/login", follow_redirects=False).status_code == 404


def test_login_page_of_the_provider_gets_pkce_state_and_nonce(anonymous, provider):
    response = anonymous.get("/api/auth/sso/login", follow_redirects=False)
    location = urllib.parse.urlsplit(response.headers["location"])
    params = dict(urllib.parse.parse_qsl(location.query))
    assert f"{location.scheme}://{location.netloc}{location.path}" == f"{ISSUER}/auth"
    assert params["client_id"] == "subtitle-app"
    assert params["code_challenge_method"] == "S256"
    assert params["redirect_uri"].endswith("/api/auth/sso/callback")
    assert params["state"] and params["nonce"]
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "path=/api/auth/sso" in cookie


def test_first_login_creates_an_account_without_password(anonymous, provider):
    response = _login_through_provider(anonymous, provider)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert anonymous.get("/api/auth/me").json() == {"username": "marie", "role": "user"}
    # The PKCE verifier and the client secret went to the token endpoint.
    form = provider.token_requests[0]
    assert form["client_secret"] == "secret" and len(form["code_verifier"]) >= 43

    account = anonymous.get("/api/account").json()
    assert account["display_name"] == "Marie Curie"
    assert account["email"] == "marie.curie@example.org"
    assert account["has_password"] is False
    assert [i["provider"] for i in account["identities"]] == ["keycloak"]
    # No password: the username alone opens nothing.
    login = anonymous.post("/api/auth/login", json={"username": "marie", "password": "whatever1"})
    assert login.status_code == 401


def test_next_logins_reuse_the_same_account(anonymous, provider, client):
    _login_through_provider(anonymous, provider)
    other_browser = TestClient(client.app)
    _login_through_provider(other_browser, provider)
    with session_scope() as session:
        assert session.query(User).filter(User.username.like("marie%")).count() == 1


def test_taken_username_gets_a_suffix(anonymous, provider):
    provider.claims = {"preferred_username": "alice"}  # alice exists already (fixture)
    _login_through_provider(anonymous, provider)
    assert anonymous.get("/api/auth/me").json()["username"] == "alice2"


def test_same_email_does_not_take_over_an_existing_account(client, anonymous, provider):
    client.patch("/api/account", json={"email": "marie.curie@example.org"})
    _login_through_provider(anonymous, provider)
    assert anonymous.get("/api/auth/me").json()["username"] == "marie"


def test_wrong_state_is_refused(anonymous, provider):
    response = _login_through_provider(anonymous, provider, state="forged")
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login.html?error=")
    assert anonymous.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("claims", [
    {"iss": "http://evil.example"},
    {"aud": "another-app"},
    {"exp": time.time() - 3600},
    {"nonce": "replayed"},
])
def test_untrustworthy_id_token_is_refused(anonymous, provider, claims):
    provider.claims = claims
    response = _login_through_provider(anonymous, provider)
    assert response.headers["location"].startswith("/login.html?error=")
    assert anonymous.get("/api/auth/me").status_code == 401


def test_callback_without_attempt_is_refused(anonymous, provider):
    response = anonymous.get("/api/auth/sso/callback?code=x&state=y", follow_redirects=False)
    assert response.headers["location"].startswith("/login.html?error=")


def test_cancelled_on_the_provider_page(anonymous, provider):
    anonymous.get("/api/auth/sso/login", follow_redirects=False)
    response = anonymous.get("/api/auth/sso/callback?error=access_denied", follow_redirects=False)
    assert "Connexion+annul" in response.headers["location"]


def test_disabled_account_cannot_log_in_through_the_provider(anonymous, provider, client):
    _login_through_provider(anonymous, provider)
    with session_scope() as session:
        session.query(User).filter_by(username="marie").one().disabled_at = utcnow()
    other = TestClient(client.app)
    response = _login_through_provider(other, provider)
    assert "d%C3%A9sactiv" in response.headers["location"]


def test_logged_in_user_links_then_logs_in_with_the_provider(client, provider):
    response = _login_through_provider(client, provider, mode="link")
    assert response.headers["location"] == "/account.html?linked=1"
    assert [i["provider"] for i in client.get("/api/account").json()["identities"]] == ["keycloak"]

    browser = TestClient(client.app)
    _login_through_provider(browser, provider)
    assert browser.get("/api/auth/me").json()["username"] == "alice"


def test_provider_account_linked_elsewhere_cannot_be_linked_again(client, anonymous, provider):
    _login_through_provider(anonymous, provider)  # creates "marie" with this provider account
    response = _login_through_provider(client, provider, mode="link")
    assert response.headers["location"].startswith("/account.html?error=")
    with session_scope() as session:
        assert session.query(UserIdentity).count() == 1


def test_unlink_needs_a_password_to_stay_reachable(anonymous, provider):
    _login_through_provider(anonymous, provider)
    assert anonymous.delete("/api/account/identities/keycloak").status_code == 409

    assert anonymous.post("/api/account/password", json={"new_password": USER_PASSWORD}).status_code == 200
    assert anonymous.delete("/api/account/identities/keycloak").status_code == 204
    login = anonymous.post("/api/auth/login", json={"username": "marie", "password": USER_PASSWORD})
    assert login.status_code == 200


def test_unreachable_provider_is_reported(anonymous, provider, monkeypatch):
    def down(url, form=None):
        raise sso.SsoError("Fournisseur d'identité injoignable : refused")

    monkeypatch.setattr(sso, "_http_json", down)
    response = anonymous.get("/api/auth/sso/login", follow_redirects=False)
    assert response.headers["location"].startswith("/login.html?error=Fournisseur")
