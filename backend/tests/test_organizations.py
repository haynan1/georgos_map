import asyncio
from typing import Any

from tests.conftest import ClientFactory
from tests.helpers import PASSWORD, Browser


async def _members(browser: Browser) -> list[dict[str, Any]]:
    response = await browser.get("/organization/members")
    assert response.status_code == 200, response.text
    members: list[dict[str, Any]] = response.json()
    return members


def _membership_id(members: list[dict[str, Any]], email: str) -> str:
    return str(next(m["id"] for m in members if m["email"] == email))


async def test_invitation_onboards_new_member(make_browser: ClientFactory) -> None:
    async with make_browser() as owner, make_browser() as newcomer:
        await owner.register()
        token = await owner.invite("carlos@fazenda.com.br", "operator")

        preview = await newcomer.post("/invitations/preview", {"token": token})
        assert preview.status_code == 200
        assert preview.json() == {
            "organization_name": "Fazenda Boa Vista",
            "email": "carlos@fazenda.com.br",
            "role": "operator",
            "expires_at": preview.json()["expires_at"],
            "account_exists": False,
        }

        accepted = await newcomer.accept(token, name="Carlos Lima")
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["role"] == "operator"
        assert accepted.json()["organization"]["name"] == "Fazenda Boa Vista"

        emails = {m["email"]: m["role"] for m in await _members(owner)}
        assert emails == {"ana@fazenda.com.br": "owner", "carlos@fazenda.com.br": "operator"}

        # Single use.
        reuse = await newcomer.accept(token, name="Carlos Lima")
        assert reuse.status_code == 410


async def test_invitation_for_new_account_enforces_password_policy(
    make_browser: ClientFactory,
) -> None:
    async with make_browser() as owner, make_browser() as newcomer:
        await owner.register()
        token = await owner.invite("carlos@fazenda.com.br", "viewer")

        weak = await newcomer.accept(token, password="curta")
        assert weak.status_code == 422
        assert weak.json()["error"]["code"] == "weak_password"

        nameless = await newcomer.accept(token, name=None)
        assert nameless.status_code == 400


async def test_existing_account_must_prove_ownership(make_browser: ClientFactory) -> None:
    async with make_browser() as ana, make_browser() as bruno:
        await ana.register()
        await bruno.register("bruno@sitio.com.br", organization="Sítio Esperança")
        token = await ana.invite("bruno@sitio.com.br", "manager")

        preview = await bruno.post("/invitations/preview", {"token": token})
        assert preview.json()["account_exists"] is True

        wrong = await bruno.accept(token, name=None, password="nao-e-a-senha-dele")
        assert wrong.status_code == 401

        ok = await bruno.accept(token, name=None, password=PASSWORD)
        assert ok.status_code == 200
        body = ok.json()
        assert body["organization"]["name"] == "Fazenda Boa Vista"
        assert body["role"] == "manager"
        assert {org["name"] for org in body["organizations"]} == {
            "Fazenda Boa Vista",
            "Sítio Esperança",
        }


async def test_cannot_invite_existing_member(browser: Browser) -> None:
    await browser.register()
    response = await browser.post(
        "/organization/invitations", {"email": "ana@fazenda.com.br", "role": "viewer"}
    )
    assert response.status_code == 409


async def test_reinvite_supersedes_previous_link(make_browser: ClientFactory) -> None:
    async with make_browser() as owner, make_browser() as guest:
        await owner.register()
        first = await owner.invite("carlos@fazenda.com.br", "viewer")
        second = await owner.invite("carlos@fazenda.com.br", "operator")

        assert (await guest.post("/invitations/preview", {"token": first})).status_code == 410
        assert (await guest.post("/invitations/preview", {"token": second})).status_code == 200
        pending = (await owner.get("/organization/invitations")).json()
        assert [(i["email"], i["role"]) for i in pending] == [("carlos@fazenda.com.br", "operator")]


async def test_revoked_invitation_cannot_be_used(make_browser: ClientFactory) -> None:
    async with make_browser() as owner, make_browser() as guest:
        await owner.register()
        token = await owner.invite("carlos@fazenda.com.br", "viewer")
        invitation_id = (await owner.get("/organization/invitations")).json()[0]["id"]

        assert (await owner.delete(f"/organization/invitations/{invitation_id}")).status_code == 204
        assert (await guest.accept(token)).status_code == 410


async def test_role_hierarchy_is_enforced(make_browser: ClientFactory) -> None:
    async with make_browser() as owner, make_browser() as admin, make_browser() as viewer:
        await owner.register()
        await admin.accept(await owner.invite("admin@fazenda.com.br", "admin"), name="Admin")
        await viewer.accept(await owner.invite("viewer@fazenda.com.br", "viewer"), name="Viewer")
        members = await _members(owner)

        # Viewers can see the team but not manage it.
        assert len(await _members(viewer)) == 3
        denied = await viewer.post(
            "/organization/invitations", {"email": "x@fazenda.com.br", "role": "viewer"}
        )
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "permission_denied"

        # Admins cannot mint owners, nor touch the owner.
        no_escalation = await admin.post(
            "/organization/invitations", {"email": "x@fazenda.com.br", "role": "owner"}
        )
        assert no_escalation.status_code == 403
        owner_id = _membership_id(members, "ana@fazenda.com.br")
        assert (await admin.delete(f"/organization/members/{owner_id}")).status_code == 403

        # Admins manage roles below them.
        viewer_id = _membership_id(members, "viewer@fazenda.com.br")
        promoted = await admin.patch(f"/organization/members/{viewer_id}", {"role": "manager"})
        assert promoted.status_code == 204
        assert (await viewer.get("/auth/session")).json()["role"] == "manager"

        # Nobody changes their own role.
        admin_id = _membership_id(members, "admin@fazenda.com.br")
        assert (
            await admin.patch(f"/organization/members/{admin_id}", {"role": "owner"})
        ).status_code == 409


async def test_owners_removing_each_other_concurrently_keep_one_owner(
    make_browser: ClientFactory,
) -> None:
    async with make_browser() as ana, make_browser() as bruno:
        await ana.register()
        await bruno.accept(await ana.invite("bruno@fazenda.com.br", "owner"), name="Bruno")
        members = await _members(ana)
        ana_id = _membership_id(members, "ana@fazenda.com.br")
        bruno_id = _membership_id(members, "bruno@fazenda.com.br")

        results = await asyncio.gather(
            ana.delete(f"/organization/members/{bruno_id}"),
            bruno.delete(f"/organization/members/{ana_id}"),
        )

        assert sorted(r.status_code for r in results)[0] == 204
        assert sum(r.status_code == 204 for r in results) == 1

    async with make_browser() as check:
        survivor = "ana@fazenda.com.br" if results[0].status_code == 204 else "bruno@fazenda.com.br"
        assert (await check.login(survivor)).status_code == 200
        remaining = await _members(check)
        assert [(m["email"], m["role"]) for m in remaining] == [(survivor, "owner")]


async def test_removed_member_loses_access_immediately(make_browser: ClientFactory) -> None:
    async with make_browser() as owner, make_browser() as worker:
        await owner.register()
        await worker.accept(await owner.invite("worker@fazenda.com.br", "operator"), name="Wesley")
        assert (await worker.get("/auth/session")).status_code == 200

        worker_id = _membership_id(await _members(owner), "worker@fazenda.com.br")
        assert (await owner.delete(f"/organization/members/{worker_id}")).status_code == 204

        assert (await worker.get("/auth/session")).status_code == 401
        assert (await worker.login("worker@fazenda.com.br")).json()["error"]["code"] == (
            "no_organization"
        )


async def test_members_are_isolated_per_organization(make_browser: ClientFactory) -> None:
    async with make_browser() as ana, make_browser() as bruno:
        await ana.register()
        await bruno.register("bruno@sitio.com.br", organization="Sítio Esperança")

        assert [m["email"] for m in await _members(ana)] == ["ana@fazenda.com.br"]
        bruno_member = (await _members(bruno))[0]["id"]
        # Another tenant's ids are simply not found.
        response = await ana.patch(f"/organization/members/{bruno_member}", {"role": "viewer"})
        assert response.status_code == 404


async def test_switch_organization(make_browser: ClientFactory) -> None:
    async with make_browser() as ana, make_browser() as bruno:
        await ana.register()
        own_org = (await bruno.register("bruno@sitio.com.br", organization="Sítio"))[
            "organization"
        ]["id"]
        await bruno.accept(await ana.invite("bruno@sitio.com.br", "viewer"), name=None)
        assert (await bruno.get("/auth/session")).json()["organization"]["name"] == (
            "Fazenda Boa Vista"
        )

        switched = await bruno.post("/auth/switch-organization", {"organization_id": own_org})
        assert switched.status_code == 200
        assert switched.json()["organization"]["name"] == "Sítio"
        assert switched.json()["role"] == "owner"

        ana_org = (await ana.get("/auth/session")).json()["organization"]["id"]
        await bruno.post("/auth/switch-organization", {"organization_id": ana_org})
        ana_only = (await ana.get("/auth/session")).json()["organizations"]
        assert len(ana_only) == 1

        stranger_org = "01890000-0000-7000-8000-000000000000"
        response = await ana.post("/auth/switch-organization", {"organization_id": stranger_org})
        assert response.status_code == 404


async def test_update_organization_and_audit_trail(make_browser: ClientFactory) -> None:
    async with make_browser() as owner, make_browser() as viewer:
        await owner.register()
        await viewer.accept(await owner.invite("viewer@fazenda.com.br", "viewer"), name="Vera")

        renamed = await owner.patch("/organization", {"name": "Fazenda Boa Vista Ltda"})
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "Fazenda Boa Vista Ltda"
        assert (await viewer.patch("/organization", {"name": "Hack"})).status_code == 403

        events = (await owner.get("/organization/audit-events")).json()
        actions = [event["action"] for event in events]
        assert actions[0] == "organization.updated"
        assert {"organization.created", "invitation.created", "member.joined"} <= set(actions)
        assert events[0]["actor_name"] == "Ana Souza"

        page = await owner.get(f"/organization/audit-events?limit=1&before={events[0]['id']}")
        assert page.json()[0]["id"] == events[1]["id"]

        assert (await viewer.get("/organization/audit-events")).status_code == 403
