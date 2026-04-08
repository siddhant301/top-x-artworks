import os
import time
import unittest
from unittest.mock import patch

import httpx

from services.mutualart_auth import MutualArtAuthManager


class MutualArtAuthManagerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.env_patch = patch.dict(
            os.environ,
            {
                "MUTUALART_API_USERNAME": "demo-user",
                "MUTUALART_API_PASSWORD": "demo-pass",
            },
            clear=False,
        )
        self.env_patch.start()

    def tearDown(self) -> None:
        self.env_patch.stop()

    def test_extract_token_from_plain_text_response(self) -> None:
        response = httpx.Response(
            200,
            text="plain-token-value",
            request=httpx.Request("POST", "https://example.com/token"),
        )
        token = MutualArtAuthManager._extract_token_from_response(response)
        self.assertEqual(token, "plain-token-value")

    def test_extract_token_from_json_response(self) -> None:
        response = httpx.Response(
            200,
            json={"access_token": "json-token-value"},
            request=httpx.Request("POST", "https://example.com/token"),
        )
        token = MutualArtAuthManager._extract_token_from_response(response)
        self.assertEqual(token, "json-token-value")

    async def test_token_cache_reused_until_refresh(self) -> None:
        manager = MutualArtAuthManager(token_url="https://example.com/token")
        refresh_calls = 0

        async def fake_refresh_token() -> None:
            nonlocal refresh_calls
            refresh_calls += 1
            manager._cached_token = f"token-{refresh_calls}"
            manager._token_expires_at = time.time() + 600

        manager._refresh_token = fake_refresh_token  # type: ignore[method-assign]

        header_1 = await manager.get_authorization_header()
        header_2 = await manager.get_authorization_header()
        header_3 = await manager.get_authorization_header(force_refresh=True)

        self.assertEqual(header_1, "Bearer token-1")
        self.assertEqual(header_2, "Bearer token-1")
        self.assertEqual(header_3, "Bearer token-2")
        self.assertEqual(refresh_calls, 2)


if __name__ == "__main__":
    unittest.main()
