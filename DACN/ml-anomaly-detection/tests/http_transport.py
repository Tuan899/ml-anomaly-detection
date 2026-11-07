"""Send the frontend's HTTP requests through the actual ASGI application in tests."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api import app


class APITransport:
    """Keep multipart/query/JSON handling real without binding a network port.

    Only the network boundary is replaced. In particular, the frontend API
    client, FastAPI validation, and backend detection pipeline all run normally.
    """

    def __enter__(self):
        self.client = TestClient(app)
        self.client.__enter__()
        self.requests = []
        self.patcher = patch("frontend.api_client.httpx.post", side_effect=self.post)
        self.mock_post = self.patcher.start()
        return self

    def post(self, url, **kwargs):
        # These govern real network connections, not TestClient's ASGI transport.
        kwargs.pop("timeout", None)
        kwargs.pop("trust_env", None)
        response = self.client.post(url, **kwargs)
        self.requests.append(response.request)
        return response

    def __exit__(self, exc_type, exc_value, traceback):
        self.patcher.stop()
        return self.client.__exit__(exc_type, exc_value, traceback)
