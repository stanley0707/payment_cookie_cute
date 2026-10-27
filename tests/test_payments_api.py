import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from payment_cookie_cute.db.models import Payment
from tests.factories import make_payment_create_payload

pytestmark = pytest.mark.anyio


class TestAuth:
    async def test_post_without_api_key_returns_401(
        self,
        client: AsyncClient,
        idempotency_headers: dict[str, str],
    ) -> None:
        headers = {k: v for k, v in idempotency_headers.items() if k != "X-API-Key"}
        resp = await client.post(
            "/api/v1/payments",
            json=make_payment_create_payload(),
            headers=headers,
        )
        assert resp.status_code == 401

    async def test_post_with_wrong_api_key_returns_401(
        self,
        client: AsyncClient,
        idempotency_headers: dict[str, str],
    ) -> None:
        headers = {**idempotency_headers, "X-API-Key": "wrong"}
        resp = await client.post(
            "/api/v1/payments",
            json=make_payment_create_payload(),
            headers=headers,
        )
        assert resp.status_code == 401

    async def test_get_without_api_key_returns_401(self, client: AsyncClient) -> None:
        resp = await client.get(f"/api/v1/payments/{uuid.uuid4()}")
        assert resp.status_code == 401


class TestCreatePayment:
    async def test_requires_idempotency_key(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/api/v1/payments",
            json=make_payment_create_payload(),
            headers=auth_headers,
        )
        assert resp.status_code == 422
        assert "Idempotency-Key" in str(resp.json())

    async def test_returns_202_with_payment(
        self,
        client: AsyncClient,
        idempotency_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/api/v1/payments",
            json=make_payment_create_payload(),
            headers=idempotency_headers,
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "id" in data
        assert data["status"] == "pending"
        assert "idempotency_key" not in data  # не утекло

    async def test_idempotent_returns_same_payment(
        self,
        client: AsyncClient,
        idempotency_headers: dict[str, str],
    ) -> None:
        r1 = await client.post(
            "/api/v1/payments",
            json=make_payment_create_payload(),
            headers=idempotency_headers,
        )
        r2 = await client.post(
            "/api/v1/payments",
            json=make_payment_create_payload(),
            headers=idempotency_headers,
        )
        assert r1.status_code == 202
        assert r2.status_code == 202
        assert r1.json()["id"] == r2.json()["id"]

    async def test_creates_exactly_one_payment_row(
        self,
        client: AsyncClient,
        idempotency_headers: dict[str, str],
        session: AsyncSession,
    ) -> None:
        """Идемпотентность проверяется в БД, а не только по ответу."""
        await client.post(
            "/api/v1/payments",
            json=make_payment_create_payload(),
            headers=idempotency_headers,
        )
        await client.post(
            "/api/v1/payments",
            json=make_payment_create_payload(),
            headers=idempotency_headers,
        )
        count = await session.scalar(select(func.count()).select_from(Payment))
        assert count == 1

    async def test_rejects_zero_amount(
        self,
        client: AsyncClient,
        idempotency_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/api/v1/payments",
            json=make_payment_create_payload(amount="0.00"),
            headers=idempotency_headers,
        )
        assert resp.status_code == 422

    async def test_rejects_unknown_currency(
        self,
        client: AsyncClient,
        idempotency_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/api/v1/payments",
            json=make_payment_create_payload(currency="GBP"),
            headers=idempotency_headers,
        )
        assert resp.status_code == 422

    async def test_rejects_extra_field(
        self,
        client: AsyncClient,
        idempotency_headers: dict[str, str],
    ) -> None:
        payload = make_payment_create_payload()
        payload["currnecy"] = "RUB"
        resp = await client.post(
            "/api/v1/payments",
            json=payload,
            headers=idempotency_headers,
        )
        assert resp.status_code == 422


class TestGetPayment:
    async def test_returns_payment_by_id(
        self,
        client: AsyncClient,
        idempotency_headers: dict[str, str],
        auth_headers: dict[str, str],
    ) -> None:
        created = await client.post(
            "/api/v1/payments",
            json=make_payment_create_payload(),
            headers=idempotency_headers,
        )
        payment_id = created.json()["id"]

        resp = await client.get(f"/api/v1/payments/{payment_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == payment_id
        assert resp.json()["status"] == "pending"

    async def test_returns_404_when_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await client.get(f"/api/v1/payments/{uuid.uuid4()}", headers=auth_headers)
        assert resp.status_code == 404

    async def test_rejects_invalid_uuid(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
    ) -> None:
        resp = await client.get("/api/v1/payments/not-a-uuid", headers=auth_headers)
        assert resp.status_code == 422
