import asyncio
import base64
import json
import os
import time
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_GRAPHQL_ORIGIN = "https://gql.test.mutualart.com"
DEFAULT_TOKEN_URL = f"{DEFAULT_GRAPHQL_ORIGIN}/token"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_FALLBACK_TTL_SECONDS = 15 * 60
TOKEN_EXPIRY_SAFETY_WINDOW_SECONDS = 60


def _env_as_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _ensure_bearer_prefix(token: str) -> str:
    if token.startswith("Bearer "):
        return token
    return f"Bearer {token}"


def _extract_jwt_exp(token: str) -> float | None:
    parts = token.split(".")
    if len(parts) < 2:
        return None

    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding).decode("utf-8")
        parsed = json.loads(decoded)
    except (ValueError, json.JSONDecodeError):
        return None

    exp = parsed.get("exp")
    if isinstance(exp, (int, float)):
        return float(exp)
    return None


class MutualArtAuthManager:
    """
    Manages short-lived MutualArt access tokens.

    Login flow mirrors the GraphQL host login page:
    POST /token with form fields grantType, username, password.
    """

    def __init__(
        self,
        token_url: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._token_url = token_url or os.environ.get("MUTUALART_TOKEN_URL", DEFAULT_TOKEN_URL)
        self._grant_type = os.environ.get("MUTUALART_GRANT_TYPE", "password")
        self._username = os.environ.get("MUTUALART_API_USERNAME", "").strip()
        self._password = os.environ.get("MUTUALART_API_PASSWORD", "").strip()
        self._verify_ssl = _env_as_bool("MUTUALART_VERIFY_SSL", default=False)
        self._fallback_ttl_seconds = int(
            os.environ.get("MUTUALART_TOKEN_FALLBACK_TTL_SECONDS", DEFAULT_FALLBACK_TTL_SECONDS)
        )
        self._timeout_seconds = timeout_seconds

        if not self._username or not self._password:
            raise ValueError(
                "Missing MutualArt credentials. Set MUTUALART_API_USERNAME and "
                "MUTUALART_API_PASSWORD via environment variables."
            )

        self._cached_token: str = ""
        self._token_expires_at: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def verify_ssl(self) -> bool:
        return self._verify_ssl

    @property
    def timeout_seconds(self) -> float:
        return self._timeout_seconds

    def _token_is_valid(self) -> bool:
        if not self._cached_token:
            return False
        return time.time() < (self._token_expires_at - TOKEN_EXPIRY_SAFETY_WINDOW_SECONDS)

    async def get_authorization_header(self, force_refresh: bool = False) -> str:
        token = await self._get_token(force_refresh=force_refresh)
        return _ensure_bearer_prefix(token)

    async def _get_token(self, force_refresh: bool = False) -> str:
        if not force_refresh and self._token_is_valid():
            return self._cached_token

        async with self._lock:
            if not force_refresh and self._token_is_valid():
                return self._cached_token

            await self._refresh_token()
            return self._cached_token

    async def _refresh_token(self) -> None:
        payload = {
            "grantType": self._grant_type,
            "username": self._username,
            "password": self._password,
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        async with httpx.AsyncClient(verify=self._verify_ssl, timeout=self._timeout_seconds) as client:
            response = await client.post(self._token_url, data=payload, headers=headers)

        if response.status_code >= 400:
            raise ValueError(
                f"MutualArt login failed ({response.status_code}). "
                "Verify credentials and login endpoint configuration."
            )

        token = self._extract_token_from_response(response)
        if not token:
            raise ValueError("MutualArt login succeeded but returned an empty token.")

        self._cached_token = token
        self._token_expires_at = self._compute_expiry_epoch(token)

    def _compute_expiry_epoch(self, token: str) -> float:
        exp_from_jwt = _extract_jwt_exp(token)
        if exp_from_jwt:
            return exp_from_jwt
        return time.time() + self._fallback_ttl_seconds

    @staticmethod
    def _extract_token_from_response(response: httpx.Response) -> str:
        content_type = response.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            try:
                payload: Any = response.json()
            except json.JSONDecodeError:
                payload = {}
            if isinstance(payload, dict):
                for key in ("access_token", "accessToken", "token"):
                    value = payload.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()

        token = response.text.strip()
        if token.startswith('"') and token.endswith('"'):
            token = token[1:-1].strip()
        return token


_auth_manager: MutualArtAuthManager | None = None


def get_auth_manager() -> MutualArtAuthManager:
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = MutualArtAuthManager()
    return _auth_manager
