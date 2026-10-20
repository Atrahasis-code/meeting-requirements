"""Application-owned SIWC registration. Never imports another client's credentials."""

import base64
import contextlib
import fcntl
import hashlib
import json
import os
import secrets
import time
import uuid
from urllib.parse import urlencode, urlparse
import httpx
import jwt
from .config import settings

ISSUER = "https://auth.openai.com"
AUTHORIZE = ISSUER + "/api/accounts/authorize"
TOKEN = ISSUER + "/api/accounts/oauth/token"
RESOURCE = "https://api.openai.com/v1"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
USAGE_URL = "https://chatgpt.com/#settings/Usage"


class AuthFailure(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)


def client():
    return httpx.Client(timeout=20, follow_redirects=False)


@contextlib.contextmanager
def credentials():
    directory = settings.directory("auth")
    directory.mkdir(exist_ok=True, mode=0o700)
    lock = os.open(directory / "credentials.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = directory / "credentials.json"
        data = (
            json.loads(path.read_text())
            if path.exists()
            else {"host_id": "urn:uuid:" + str(uuid.uuid4()), "profiles": {}, "active": None, "pending": {}}
        )
        try:
            yield data
        finally:
            temporary = directory / ("credentials-" + secrets.token_hex(8) + ".tmp")
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as stream:
                json.dump(data, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            os.chmod(path, 0o600)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        os.close(lock)


def profile(data):
    return data["profiles"].get(data.get("active"))


def begin(browser_session, *, new_account=False):
    state, nonce, verifier = (secrets.token_urlsafe(40) for _ in range(3))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    with credentials() as data:
        active = None if new_account else profile(data)
        # A registration belongs to this installation and can be reused after an
        # expired code exchange. Adding an account must not disconnect the old one.
        issued = active["client_id"] if active else next(iter(data.get("registration", {})), None)
        params = dict(
            client_id=issued or "dynamic_agent_client",
            ext_agent_host_id=data["host_id"],
            response_type="code",
            redirect_uri=settings.callback_url,
            scope=SCOPES,
            resource=RESOURCE,
            state=state,
            nonce=nonce,
            code_challenge_method="S256",
            code_challenge=challenge,
        )
        if issued:
            if active and active.get("id_token"):
                params["id_token_hint"] = active["id_token"]
            if active:
                params["login_hint"] = active.get("email", "")
        else:
            params["agent_name_hint"] = "Meeting Requirements AI"
        pending = {k: v for k, v in data["pending"].items() if v["expires"] > time.time()}
        pending[state] = dict(
            nonce=nonce,
            verifier=verifier,
            browser=hashlib.sha256(browser_session.encode()).hexdigest(),
            expires=time.time() + 600,
            redirect_uri=settings.callback_url,
            client_id=issued,
            selected=None if new_account else data.get("active"),
            url=AUTHORIZE + "?" + urlencode(params),
        )
        data["pending"] = pending
    # Frontend receives only a local opaque redirect, never an ID-token hint.
    return "/api/auth/chatgpt/authorize/" + state


def authorize_url(state, browser_session):
    with credentials() as data:
        pending = data["pending"].get(state)
        if (
            not pending
            or pending["expires"] < time.time()
            or not secrets.compare_digest(
                pending["browser"], hashlib.sha256(browser_session.encode()).hexdigest()
            )
        ):
            raise AuthFailure("invalid_state", "Intento de conexión expirado o ajeno a este navegador")
        return pending["url"]


def verify_identity(encoded, audience, nonce):
    with client() as http:
        response = http.get(ISSUER + "/.well-known/openid-configuration")
        response.raise_for_status()
        metadata = response.json()
    jwks_uri = metadata["jwks_uri"]
    if (
        metadata["issuer"] != ISSUER
        or urlparse(jwks_uri).hostname != "auth.openai.com"
        or not jwks_uri.startswith("https://")
    ):
        raise AuthFailure("invalid_issuer", "Metadatos de identidad no válidos")
    key = jwt.PyJWKClient(jwks_uri).get_signing_key_from_jwt(encoded).key
    identity = jwt.decode(
        encoded,
        key,
        algorithms=["RS256"],
        audience=audience,
        issuer=ISSUER,
        options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]},
    )
    if not secrets.compare_digest(str(identity["nonce"]), nonce):
        raise AuthFailure("invalid_nonce", "La identidad no corresponde al intento iniciado")
    return identity


def callback(query, browser_session):
    state = query.get("state", "")
    with credentials() as data:
        pending = data["pending"].get(state)
        if (
            not pending
            or pending["expires"] < time.time()
            or not secrets.compare_digest(
                pending["browser"], hashlib.sha256(browser_session.encode()).hexdigest()
            )
        ):
            raise AuthFailure("invalid_state", "Callback inválido o expirado")
        del data["pending"][state]
        issued = pending["client_id"] or query.get("client_id")
        if pending["client_id"] and query.get("client_id", issued) != issued:
            raise AuthFailure("invalid_client", "El cliente recibido no coincide")
        if query.get("error"):
            raise AuthFailure("access_denied", "No se autorizó la conexión")
        if not issued or issued == "dynamic_agent_client" or not query.get("code"):
            raise AuthFailure("invalid_registration", "Registro incompleto")
        # Persist the newly issued registration even if code exchange later expires.
        data.setdefault("registration", {})[issued] = {"host_id": data["host_id"]}
    with client() as http:
        response = http.post(
            TOKEN,
            data=dict(
                grant_type="authorization_code",
                client_id=issued,
                code=query["code"],
                code_verifier=pending["verifier"],
                redirect_uri=pending["redirect_uri"],
                resource=RESOURCE,
            ),
        )
        if response.status_code != 200:
            raise AuthFailure(
                "token_exchange_failed", "No se pudo completar el intercambio; inicia un intento nuevo"
            )
        tokens = response.json()
    identity = verify_identity(tokens["id_token"], issued, pending["nonce"])
    identity_key = hashlib.sha256(
        (issued + "|" + identity["iss"] + "|" + identity["sub"]).encode()
    ).hexdigest()
    with credentials() as data:
        previous = data["profiles"].get(pending["selected"])
        if previous and (previous["subject"] != identity["sub"] or previous["client_id"] != issued):
            raise AuthFailure("identity_changed", "La cuenta no coincide con la seleccionada")
        data["profiles"][identity_key] = dict(
            client_id=issued,
            subject=identity["sub"],
            issuer=identity["iss"],
            email=identity.get("email", "Cuenta ChatGPT"),
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            id_token=tokens["id_token"],
            scopes=tokens.get("scope", "").split(),
            expires_at=time.time() + tokens.get("expires_in", 3600),
            credits_zero_confirmed=False,
            quota_blocked=False,
            inference_verified=False,
            error=None,
        )
        data["active"] = identity_key


def token(require_policy=True, *, account_id=None):
    failure = None
    access = None
    with credentials() as data:
        if account_id is not None and data.get("active") != account_id:
            raise AuthFailure("account_changed", "Cambió la cuenta; revisa la entrada y autoriza nuevamente")
        selected = profile(data)
        if not selected or not selected.get("access_token"):
            raise AuthFailure("authentication_required", "Conecta tu cuenta de ChatGPT")
        if "chatgpt.tokens.use.direct" not in selected["scopes"]:
            raise AuthFailure("plan_not_authorized", "La cuenta está conectada sin permiso de uso del plan")
        if require_policy and not selected.get("credits_zero_confirmed"):
            raise AuthFailure(
                "credits_confirmation_required", "Confirma el límite de créditos de cero en ChatGPT"
            )
        if require_policy and selected.get("quota_blocked"):
            raise AuthFailure("quota_exceeded", "Análisis bloqueados por cuota; revisa Uso en ChatGPT")
        if selected["expires_at"] <= time.time() + 90:
            with client() as http:
                response = http.post(
                    TOKEN,
                    data=dict(
                        grant_type="refresh_token",
                        client_id=selected["client_id"],
                        refresh_token=selected.get("refresh_token", ""),
                        resource=RESOURCE,
                    ),
                )
            if response.status_code == 200:
                refreshed = response.json()
                selected.update(
                    access_token=refreshed["access_token"],
                    expires_at=time.time() + refreshed.get("expires_in", 3600),
                    refresh_token=refreshed.get("refresh_token", selected.get("refresh_token")),
                    scopes=refreshed.get("scope", " ".join(selected["scopes"])).split(),
                )
            else:
                code = (
                    response.json().get("error", "refresh_failed")
                    if response.headers.get("content-type", "").startswith("application/json")
                    else "refresh_failed"
                )
                if isinstance(code, dict):
                    code = code.get("code", "refresh_failed")
                if code in {
                    "invalid_grant",
                    "invalid_refresh_token",
                    "refresh_token_expired",
                    "refresh_token_reused",
                    "refresh_token_invalidated",
                    "refresh_token_invalid",
                    "token_expired",
                }:
                    for name in ("access_token", "refresh_token", "id_token"):
                        selected.pop(name, None)
                selected["error"] = str(code)
                failure = AuthFailure("refresh_failed", "No se pudo renovar la sesión; revisa la conexión")
        access = selected.get("access_token")
        if not failure and "chatgpt.tokens.use.direct" not in selected["scopes"]:
            failure = AuthFailure("plan_not_authorized", "El permiso del plan ya no está disponible")
    if failure:
        raise failure
    return access


def status():
    with credentials() as data:
        selected = profile(data)
        return dict(
            connected=bool(selected and selected.get("access_token")),
            account_id=data.get("active"),
            accounts=[
                dict(id=k, email=p["email"], connected=bool(p.get("access_token")))
                for k, p in data["profiles"].items()
            ],
            email=selected.get("email") if selected else None,
            plan_authorized=bool(selected and "chatgpt.tokens.use.direct" in selected["scopes"]),
            credits_zero_confirmed=bool(selected and selected.get("credits_zero_confirmed")),
            quota_blocked=bool(selected and selected.get("quota_blocked")),
            inference_verified=bool(selected and selected.get("inference_verified")),
            last_inference_at=selected.get("last_inference_at") if selected else None,
            last_inference_model=selected.get("last_inference_model") if selected else None,
            error=selected.get("error") if selected else None,
            usage_url=USAGE_URL,
            policy_verification="manual_user_confirmation",
        )


def update_profile(*, account_id=None, **updates):
    with credentials() as data:
        selected = data["profiles"].get(account_id) if account_id is not None else profile(data)
        if not selected:
            raise AuthFailure("authentication_required", "Conecta ChatGPT primero")
        selected.update(updates)


def disconnect():
    confirmed = False
    with credentials() as data:
        selected = profile(data)
        if selected and selected.get("refresh_token"):
            try:
                with client() as http:
                    metadata = http.get(ISSUER + "/.well-known/openid-configuration").json()
                    endpoint = metadata["revocation_endpoint"]
                    if urlparse(endpoint).hostname != "auth.openai.com" or not endpoint.startswith(
                        "https://"
                    ):
                        raise ValueError("Invalid revocation endpoint")
                    confirmed = (
                        http.post(
                            endpoint,
                            data=dict(
                                token=selected["refresh_token"],
                                token_type_hint="refresh_token",
                                client_id=selected["client_id"],
                            ),
                        ).status_code
                        == 200
                    )
            except (httpx.HTTPError, ValueError, KeyError):
                pass
        if selected:
            for key in ("access_token", "refresh_token", "id_token"):
                selected.pop(key, None)
            selected.update(credits_zero_confirmed=False, inference_verified=False)
    return {"remote_revocation_confirmed": confirmed}


def models():
    access = token(require_policy=False)
    with client() as http:
        response = http.get(RESOURCE + "/models", headers={"Authorization": "Bearer " + access})
        if response.status_code != 200:
            raise AuthFailure("catalog_unavailable", "No se pudo consultar el catálogo de esta cuenta")
        return [
            dict(slug=item["slug"], display_name=item["display_name"])
            for item in response.json().get("models", [])
            if item.get("visibility") == "list"
        ]
