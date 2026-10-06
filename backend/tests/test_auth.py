import asyncio

from tests.conftest import ClientFactory
from tests.helpers import PASSWORD, Browser


async def test_register_creates_owner_session(browser: Browser) -> None:
    body = await browser.register()

    assert body["user"]["email"] == "ana@fazenda.com.br"
    assert body["organization"]["name"] == "Fazenda Boa Vista"
    assert body["role"] == "owner"
    assert "members:manage" in body["permissions"]
    assert body["csrf_token"]

    cookie = browser.http.cookies.jar
    session_cookie = next(c for c in cookie if c.name == "georgos_session")
    assert session_cookie.has_nonstandard_attr("HttpOnly")

    me = await browser.get("/auth/session")
    assert me.status_code == 200
    assert me.json()["user"]["full_name"] == "Ana Souza"


async def test_register_normalizes_email(browser: Browser) -> None:
    body = await browser.register("  Ana@Fazenda.COM.br ".strip())
    assert body["user"]["email"] == "ana@fazenda.com.br"


async def test_register_rejects_duplicate_email(make_browser: ClientFactory) -> None:
    async with make_browser() as first, make_browser() as second:
        await first.register()
        response = await second.post(
            "/auth/register",
            {
                "organization_name": "Outra",
                "full_name": "Outro",
                "email": "ANA@fazenda.com.br",
                "password": PASSWORD,
            },
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_register_enforces_password_policy_without_echoing_it(browser: Browser) -> None:
    response = await browser.post(
        "/auth/register",
        {
            "organization_name": "Fazenda",
            "full_name": "Ana",
            "email": "ana@fazenda.com.br",
            "password": "curta",
        },
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert {"loc": ["body", "password"], "message": "Use pelo menos 12 caracteres."} in error[
        "fields"
    ]
    assert "curta" not in response.text


async def test_validation_messages_are_localized(browser: Browser) -> None:
    response = await browser.post(
        "/auth/register",
        {"organization_name": "F", "full_name": "Ana", "email": "ana@fazenda.test"},
    )
    fields = {field["loc"][-1]: field["message"] for field in response.json()["error"]["fields"]}
    assert fields == {
        "organization_name": "Use pelo menos 2 caracteres.",
        "email": "Informe um e-mail válido.",
        "password": "Campo obrigatório.",
    }


async def test_register_rejects_unknown_fields(browser: Browser) -> None:
    response = await browser.post(
        "/auth/register",
        {
            "organization_name": "Fazenda",
            "full_name": "Ana",
            "email": "ana@fazenda.com.br",
            "password": PASSWORD,
            "role": "owner",
        },
    )
    assert response.status_code == 422


async def test_login_success_and_generic_failures(make_browser: ClientFactory) -> None:
    async with make_browser() as owner:
        await owner.register()

    async with make_browser() as visitor:
        wrong_password = await visitor.login("ana@fazenda.com.br", "senha-errada-123")
        unknown_email = await visitor.login("ninguem@fazenda.com.br")
        assert wrong_password.status_code == unknown_email.status_code == 401
        # Identical responses: no account enumeration through login.
        assert wrong_password.json()["error"]["message"] == unknown_email.json()["error"]["message"]

        ok = await visitor.login("ana@fazenda.com.br")
        assert ok.status_code == 200
        assert ok.json()["role"] == "owner"


async def test_login_locks_account_after_repeated_failures(make_browser: ClientFactory) -> None:
    async with make_browser() as owner:
        await owner.register()

    async with make_browser(ip="198.51.100.7") as attacker:
        statuses = [
            (await attacker.login("ana@fazenda.com.br", f"tentativa-{i:04}")).status_code
            for i in range(9)
        ]
        assert statuses[:8] == [401] * 8
        assert statuses[8] == 429
        # Even the right password is refused while the account is throttled.
        locked = await attacker.login("ana@fazenda.com.br")
        assert locked.status_code == 429
        assert int(locked.headers["Retry-After"]) > 0


async def test_parallel_guesses_cannot_exceed_the_failure_budget(
    make_browser: ClientFactory,
) -> None:
    # Regression: checking the budget and recording the failure must be one atomic step,
    # or a burst of parallel requests gets far more than 8 guesses.
    async with make_browser() as owner:
        await owner.register()

    browsers = [make_browser(ip=f"198.51.100.{i}") for i in range(14)]
    responses = await asyncio.gather(
        *(b.login("ana@fazenda.com.br", f"palpite-paralelo-{i:03}") for i, b in enumerate(browsers))
    )
    for b in browsers:
        await b.http.aclose()

    statuses = sorted(r.status_code for r in responses)
    assert statuses.count(401) == 8
    assert statuses.count(429) == 6


async def test_successful_login_resets_the_failure_budget(make_browser: ClientFactory) -> None:
    async with make_browser() as owner:
        await owner.register()
    async with make_browser() as user:
        for i in range(7):
            assert (await user.login("ana@fazenda.com.br", f"errada-{i:05}")).status_code == 401
        assert (await user.login("ana@fazenda.com.br")).status_code == 200
        for i in range(7):
            assert (await user.login("ana@fazenda.com.br", f"errada-{i:05}")).status_code == 401


async def test_session_requires_cookie(browser: Browser) -> None:
    response = await browser.get("/auth/session")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


async def test_logout_revokes_session(browser: Browser) -> None:
    await browser.register()
    cookies = dict(browser.http.cookies)

    assert (await browser.post("/auth/logout")).status_code == 204
    assert (await browser.get("/auth/session")).status_code == 401

    # Replaying the old cookie does not work either: revocation is server-side.
    browser.http.cookies.update(cookies)
    assert (await browser.get("/auth/session")).status_code == 401


async def test_state_changing_requests_require_csrf_token(browser: Browser) -> None:
    await browser.register()

    response = await browser.post("/auth/logout", csrf=False)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"

    browser.csrf = "0" * 64
    assert (await browser.post("/auth/logout")).status_code == 403


async def test_cross_site_requests_are_rejected(browser: Browser) -> None:
    response = await browser.http.post(
        "/api/v1/auth/login",
        json={"email": "ana@fazenda.com.br", "password": PASSWORD},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "origin_rejected"

    fetch_metadata = await browser.http.post(
        "/api/v1/auth/login",
        json={"email": "ana@fazenda.com.br", "password": PASSWORD},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert fetch_metadata.status_code == 403


async def test_same_origin_with_port_passes_origin_guard(browser: Browser) -> None:
    # Regression: the reverse proxy must forward Host with its port, and the guard must
    # compare host:port, or the app blocks its own frontend.
    response = await browser.http.post(
        "/api/v1/auth/login",
        json={"email": "ana@fazenda.com.br", "password": PASSWORD},
        headers={"Origin": "http://localhost:8080", "Host": "localhost:8080"},
    )
    assert response.status_code == 401

    mismatched = await browser.http.post(
        "/api/v1/auth/login",
        json={"email": "ana@fazenda.com.br", "password": PASSWORD},
        headers={"Origin": "http://localhost:8080", "Host": "localhost"},
    )
    assert mismatched.status_code == 403


async def test_allowed_origin_passes_origin_guard(browser: Browser) -> None:
    response = await browser.http.post(
        "/api/v1/auth/login",
        json={"email": "ana@fazenda.com.br", "password": PASSWORD},
        headers={"Origin": "https://partner.example.com"},
    )
    assert response.status_code == 401


async def test_change_password_signs_out_other_devices(make_browser: ClientFactory) -> None:
    async with make_browser() as laptop, make_browser() as phone:
        await laptop.register()
        assert (await phone.login("ana@fazenda.com.br")).status_code == 200

        wrong = await laptop.post(
            "/auth/password",
            {"current_password": "nao-e-a-senha", "new_password": "uma senha nova e longa"},
        )
        assert wrong.status_code == 400
        assert wrong.json()["error"]["code"] == "incorrect_password"

        changed = await laptop.post(
            "/auth/password",
            {"current_password": PASSWORD, "new_password": "uma senha nova e longa"},
        )
        assert changed.status_code == 204

        assert (await laptop.get("/auth/session")).status_code == 200
        assert (await phone.get("/auth/session")).status_code == 401

    async with make_browser() as fresh:
        assert (await fresh.login("ana@fazenda.com.br")).status_code == 401
        assert (
            await fresh.login("ana@fazenda.com.br", "uma senha nova e longa")
        ).status_code == 200


async def test_list_and_revoke_sessions(make_browser: ClientFactory) -> None:
    async with make_browser() as laptop, make_browser(ip="192.0.2.55") as phone:
        await laptop.register()
        await phone.login("ana@fazenda.com.br")

        sessions = (await laptop.get("/auth/sessions")).json()
        assert len(sessions) == 2
        current = [s for s in sessions if s["current"]]
        other = [s for s in sessions if not s["current"]]
        assert len(current) == 1
        assert other[0]["ip_address"] == "192.0.2.55"

        assert (await laptop.delete(f"/auth/sessions/{other[0]['id']}")).status_code == 204
        assert (await phone.get("/auth/session")).status_code == 401
        assert len((await laptop.get("/auth/sessions")).json()) == 1


async def test_revoke_other_sessions(make_browser: ClientFactory) -> None:
    async with make_browser() as laptop, make_browser() as phone, make_browser() as tablet:
        await laptop.register()
        await phone.login("ana@fazenda.com.br")
        await tablet.login("ana@fazenda.com.br")

        assert (await laptop.post("/auth/sessions/revoke-others")).status_code == 204
        assert (await laptop.get("/auth/session")).status_code == 200
        assert (await phone.get("/auth/session")).status_code == 401
        assert (await tablet.get("/auth/session")).status_code == 401


async def test_cannot_revoke_someone_elses_session(make_browser: ClientFactory) -> None:
    async with make_browser() as ana, make_browser() as bruno:
        await ana.register()
        await bruno.register("bruno@sitio.com.br", organization="Sítio Esperança")
        bruno_session = (await bruno.get("/auth/sessions")).json()[0]["id"]

        assert (await ana.delete(f"/auth/sessions/{bruno_session}")).status_code == 404
        assert (await bruno.get("/auth/session")).status_code == 200
