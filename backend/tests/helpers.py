"""Test helpers: a browser-like client that behaves like the real frontend."""

from types import TracebackType
from typing import Any, Self

import httpx

PASSWORD = "correct horse battery staple"
API = "/api/v1"


class Browser:
    """Keeps cookies like a browser and sends the CSRF header like the SPA does."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http
        self.csrf: str | None = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.http.aclose()

    def _remember(self, response: httpx.Response) -> httpx.Response:
        if response.is_success and response.content:
            body = response.json()
            if isinstance(body, dict) and "csrf_token" in body:
                self.csrf = body["csrf_token"]
        return response

    def _headers(self, csrf: bool) -> dict[str, str]:
        return {"X-CSRF-Token": self.csrf} if csrf and self.csrf else {}

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._remember(await self.http.get(f"{API}{path}", **kwargs))

    async def post(self, path: str, json: Any = None, *, csrf: bool = True) -> httpx.Response:
        return self._remember(
            await self.http.post(f"{API}{path}", json=json, headers=self._headers(csrf))
        )

    async def patch(self, path: str, json: Any = None, *, csrf: bool = True) -> httpx.Response:
        return self._remember(
            await self.http.patch(f"{API}{path}", json=json, headers=self._headers(csrf))
        )

    async def delete(self, path: str, *, csrf: bool = True) -> httpx.Response:
        return await self.http.delete(f"{API}{path}", headers=self._headers(csrf))

    async def register(
        self,
        email: str = "ana@fazenda.com.br",
        *,
        organization: str = "Fazenda Boa Vista",
        name: str = "Ana Souza",
        password: str = PASSWORD,
    ) -> dict[str, Any]:
        response = await self.post(
            "/auth/register",
            {
                "organization_name": organization,
                "full_name": name,
                "email": email,
                "password": password,
            },
        )
        assert response.status_code == 201, response.text
        body: dict[str, Any] = response.json()
        return body

    async def login(self, email: str, password: str = PASSWORD) -> httpx.Response:
        return await self.post("/auth/login", {"email": email, "password": password})

    async def invite(self, email: str, role: str) -> str:
        response = await self.post("/organization/invitations", {"email": email, "role": role})
        assert response.status_code == 201, response.text
        token: str = response.json()["token"]
        return token

    async def accept(
        self, token: str, *, name: str | None = "Convidado", password: str = PASSWORD
    ) -> httpx.Response:
        payload: dict[str, Any] = {"token": token, "password": password}
        if name is not None:
            payload["full_name"] = name
        return await self.post("/invitations/accept", payload)
