import os
import pytest
import jwt
from datetime import datetime, timedelta, timezone

os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-pytest-32bytes!!")
os.environ.setdefault("AUTH_LOGIN_URL", "https://apps.streamflows.org/login")
os.environ.setdefault("AUTH_PORTAL_URL", "https://apps.streamflows.org/")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATAOPS_API_URL", "http://localhost:8000")
os.environ.setdefault("DATAOPS_API_TOKEN", "test-token")

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import server


def _make_token(groups, secret="test-jwt-secret-for-pytest-32bytes!!", expired=False):
    now = datetime.now(timezone.utc)
    exp = now - timedelta(hours=1) if expired else now + timedelta(hours=8)
    return jwt.encode({"sub": "testuser", "groups": groups, "iat": now, "exp": exp}, secret, algorithm="HS256")


@pytest.fixture
def client():
    server.config["TESTING"] = True
    # SERVER_NAME must be the apex domain so werkzeug delivers the
    # .streamflows.org domain-scoped SSO cookie during tests.
    server.config["SERVER_NAME"] = "streamflows.org"
    with server.test_client() as c:
        yield c


def test_no_cookie_redirects_to_login(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "apps.streamflows.org/login" in resp.headers["Location"]


def test_redirect_includes_next_param(client):
    resp = client.get("/")
    assert "next=" in resp.headers["Location"]


def test_valid_streamflow_token_passes(client):
    token = _make_token(["streamflow"])
    client.set_cookie("streamflows_auth", token, domain=".streamflows.org")
    resp = client.get("/")
    assert resp.status_code != 302


def test_admin_token_passes(client):
    """admin group bypasses required_group check."""
    token = _make_token(["admin"])
    client.set_cookie("streamflows_auth", token, domain=".streamflows.org")
    resp = client.get("/")
    assert resp.status_code != 302


def test_expired_token_redirects_to_login(client):
    token = _make_token(["streamflow"], expired=True)
    client.set_cookie("streamflows_auth", token, domain=".streamflows.org")
    resp = client.get("/")
    assert resp.status_code == 302
    assert "apps.streamflows.org/login" in resp.headers["Location"]


def test_wrong_group_redirects_to_portal(client):
    token = _make_token(["econ"])
    client.set_cookie("streamflows_auth", token, domain=".streamflows.org")
    resp = client.get("/")
    assert resp.status_code == 302
    assert "apps.streamflows.org" in resp.headers["Location"]


def test_dash_internal_routes_exempt(client):
    """Dash callback routes must not require auth — they're AJAX calls."""
    resp = client.post("/_dash-update-component")
    assert resp.status_code != 302


def test_assets_exempt(client):
    resp = client.get("/assets/spinner.css")
    assert resp.status_code != 302
