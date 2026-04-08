import unittest
from unittest.mock import AsyncMock, patch

import httpx

from services.prompt_builder import _execute_graphql_request


class _FakeClient:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = responses
        self.headers: dict[str, str] = {}

    async def post(self, _url: str, json: dict) -> httpx.Response:
        _ = json
        return self._responses.pop(0)


class PromptBuilderAuthRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_retries_once_on_401(self) -> None:
        request = httpx.Request("POST", "https://gql.test.mutualart.com/api/graphql")
        responses = [
            httpx.Response(401, text="", request=request),
            httpx.Response(200, json={"data": {"ok": True}}, request=request),
        ]
        client = _FakeClient(responses)

        with patch("services.prompt_builder._refresh_client_auth_header", new=AsyncMock()) as refresh_mock:
            data = await _execute_graphql_request(client, "query { __typename }", {})

        self.assertEqual(data, {"data": {"ok": True}})
        refresh_mock.assert_awaited_once()

    async def test_retries_once_on_auth_graphql_error(self) -> None:
        request = httpx.Request("POST", "https://gql.test.mutualart.com/api/graphql")
        responses = [
            httpx.Response(200, json={"errors": [{"message": "invalid_token"}]}, request=request),
            httpx.Response(200, json={"data": {"ok": True}}, request=request),
        ]
        client = _FakeClient(responses)

        with patch("services.prompt_builder._refresh_client_auth_header", new=AsyncMock()) as refresh_mock:
            data = await _execute_graphql_request(client, "query { __typename }", {})

        self.assertEqual(data, {"data": {"ok": True}})
        refresh_mock.assert_awaited_once()

    async def test_raises_on_non_auth_graphql_error(self) -> None:
        request = httpx.Request("POST", "https://gql.test.mutualart.com/api/graphql")
        responses = [
            httpx.Response(200, json={"errors": [{"message": "schema changed"}]}, request=request),
        ]
        client = _FakeClient(responses)

        with patch("services.prompt_builder._refresh_client_auth_header", new=AsyncMock()) as refresh_mock:
            with self.assertRaises(Exception):
                await _execute_graphql_request(client, "query { __typename }", {})

        refresh_mock.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
