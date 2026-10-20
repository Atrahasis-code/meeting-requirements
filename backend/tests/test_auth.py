import time
from urllib.parse import parse_qs, urlparse
import pytest
from app import auth
from app.config import settings


def test_registration_pkce_and_tokens_never_reach_frontend(client):
    result = client.post("/api/auth/chatgpt/start")
    assert result.status_code == 200
    assert "auth.openai.com" not in result.text
    authorize = client.get(result.json()["redirect"], follow_redirects=False)
    params = parse_qs(urlparse(authorize.headers["location"]).query)
    assert params["client_id"] == ["dynamic_agent_client"]
    assert params["redirect_uri"] == ["http://127.0.0.1:8080/auth/callback"]
    assert params["code_challenge_method"] == ["S256"]
    assert "chatgpt.tokens.use.direct" in params["scope"][0]
    stored = settings.directory("auth") / "credentials.json"
    assert stored.stat().st_mode & 0o777 == 0o600
    status = client.get("/api/auth/chatgpt/status").json()
    assert "access_token" not in status and "refresh_token" not in status
    assert (
        client.get("/auth/callback?state=forged&code=invalid", follow_redirects=False)
        .headers["location"]
        .endswith("connection=failed")
    )


def test_authorize_rejects_other_browser(client):
    result = client.post("/api/auth/chatgpt/start").json()
    client.cookies.clear()
    assert client.get(result["redirect"], follow_redirects=False).status_code == 409


def test_add_account_keeps_existing_session_and_reuses_registration(client):
    with auth.credentials() as data:
        data["active"] = "existing"
        data["profiles"]["existing"] = dict(
            client_id="issued", email="previous@example.test", access_token="private", scopes=[]
        )
        data["registration"] = {"issued": {"host_id": data["host_id"]}}
    result = client.post("/api/auth/chatgpt/add-account").json()
    params = parse_qs(
        urlparse(client.get(result["redirect"], follow_redirects=False).headers["location"]).query
    )
    assert params["client_id"] == ["issued"]
    assert "id_token_hint" not in params and "login_hint" not in params
    with auth.credentials() as data:
        assert data["active"] == "existing"
        assert next(iter(data["pending"].values()))["selected"] is None


def test_failed_callback_is_consumed_and_cannot_be_replayed(client):
    result = client.post("/api/auth/chatgpt/start").json()
    state = result["redirect"].rsplit("/", 1)[1]
    response = client.get(
        "/auth/callback", params={"state": state, "error": "access_denied"}, follow_redirects=False
    )
    assert response.headers["location"].endswith("connection=failed")
    assert client.get(result["redirect"], follow_redirects=False).status_code == 409


def test_concurrent_refresh_uses_rotating_token_once(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    with auth.credentials() as data:
        data["active"] = "existing"
        data["profiles"]["existing"] = dict(
            client_id="issued",
            email="private@example.test",
            access_token="expired",
            refresh_token="old",
            scopes=["chatgpt.tokens.use.direct"],
            expires_at=0,
            credits_zero_confirmed=True,
        )
    calls = []

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def post(self, url, data):
            assert data["refresh_token"] == "old"
            calls.append(url)
            time.sleep(0.02)
            return type(
                "Response",
                (),
                {
                    "status_code": 200,
                    "json": lambda _: dict(access_token="new", refresh_token="rotated", expires_in=3600),
                },
            )()

    monkeypatch.setattr(auth, "client", Client)
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(lambda _: auth.token(), range(4))) == ["new"] * 4
    assert len(calls) == 1


def test_quota_and_zero_credit_policy_block_without_api_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-never-be-used")
    with auth.credentials() as data:
        data["active"] = "profile"
        data["profiles"]["profile"] = dict(
            client_id="issued",
            subject="user",
            issuer=auth.ISSUER,
            email="local@example.test",
            access_token="application-owned",
            scopes=["chatgpt.tokens.use.direct"],
            expires_at=time.time() + 3600,
            credits_zero_confirmed=False,
        )
    with pytest.raises(auth.AuthFailure, match="créditos"):
        auth.token()
    auth.update_profile(credits_zero_confirmed=True, quota_blocked=True)
    with pytest.raises(auth.AuthFailure, match="cuota"):
        auth.token()
    auth.update_profile(quota_blocked=False)
    assert auth.token() == "application-owned"
    assert "application-owned" not in str(auth.status())


def test_identity_nonce_signature_and_audience_validation(monkeypatch):
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"issuer": auth.ISSUER, "jwks_uri": auth.ISSUER + "/jwks"}

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def get(self, *_, **__):
            return Response()

    monkeypatch.setattr(auth, "client", Client)

    class Keys:
        def __init__(self, *_):
            pass

        def get_signing_key_from_jwt(self, *_):
            from types import SimpleNamespace

            return SimpleNamespace(key=key.public_key())

    monkeypatch.setattr(jwt, "PyJWKClient", Keys)
    encoded = jwt.encode(
        dict(
            iss=auth.ISSUER,
            sub="user",
            aud="issued",
            exp=int(time.time()) + 300,
            iat=int(time.time()),
            nonce="expected",
        ),
        key,
        algorithm="RS256",
    )
    assert auth.verify_identity(encoded, "issued", "expected")["sub"] == "user"
    with pytest.raises(auth.AuthFailure):
        auth.verify_identity(encoded, "issued", "wrong")
    with pytest.raises(jwt.InvalidAudienceError):
        auth.verify_identity(encoded, "other", "expected")


def test_account_change_invalidates_authorized_snapshot():
    with auth.credentials() as data:
        data["active"] = "different"
        data["profiles"]["different"] = {"email": "different@example.test"}
    with pytest.raises(auth.AuthFailure, match="Cambió la cuenta"):
        auth.token(account_id="authorized-account")
    with auth.credentials() as data:
        data["profiles"]["authorized-account"] = {"email": "original@example.test"}
    auth.update_profile(account_id="authorized-account", inference_verified=True)
    with auth.credentials() as data:
        assert data["profiles"]["authorized-account"]["inference_verified"] is True
        assert "inference_verified" not in data["profiles"]["different"]


def test_missing_plan_scope_is_rejected_before_inference():
    with auth.credentials() as data:
        data["active"] = "profile"
        data["profiles"]["profile"] = dict(
            client_id="issued",
            email="offline@example.test",
            access_token="private",
            scopes=["openid"],
            expires_at=time.time() + 3600,
            credits_zero_confirmed=True,
        )
    with pytest.raises(auth.AuthFailure) as failure:
        auth.token()
    assert failure.value.code == "plan_not_authorized"
    assert auth.status()["plan_authorized"] is False


def test_revoked_refresh_requires_new_connection_and_keeps_no_tokens(monkeypatch):
    with auth.credentials() as data:
        data["active"] = "profile"
        data["profiles"]["profile"] = dict(
            client_id="issued",
            email="offline@example.test",
            access_token="expired",
            refresh_token="revoked",
            id_token="old-identity",
            scopes=["chatgpt.tokens.use.direct"],
            expires_at=0,
            credits_zero_confirmed=True,
        )

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def post(self, *_, **__):
            return type(
                "Response",
                (),
                {
                    "status_code": 400,
                    "headers": {"content-type": "application/json"},
                    "json": lambda _: {"error": "invalid_grant"},
                },
            )()

    monkeypatch.setattr(auth, "client", Client)
    with pytest.raises(auth.AuthFailure):
        auth.token()
    assert auth.status()["connected"] is False
    with auth.credentials() as data:
        assert not {"access_token", "refresh_token", "id_token"} & data["profiles"]["profile"].keys()
