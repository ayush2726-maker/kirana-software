from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

import backend.app as app_module
import backend.order_portal_ext as order_module
import backend.saas_ext as saas_module
import backend.saas_guard_ext  # noqa: F401


def test_expired_trial_blocks_business_apis_but_allows_plan_page(tmp_path: Path):
    app_module.DB_PATH = tmp_path / "saas-expired.db"
    app_module.init_db()
    order_module.ensure_order_schema()
    saas_module.ensure_saas_schema()
    client = TestClient(app_module.app)

    signup = client.post(
        "/api/saas/register-business",
        json={
            "business_name": "Trial Shop",
            "owner_name": "Owner",
            "phone": "9999999991",
            "username": "trial-owner",
            "password": "1234",
        },
    )
    assert signup.status_code == 200, signup.text
    result = signup.json()
    headers = {"Authorization": f"Bearer {result['token']}"}

    expired_at = (datetime.now() - timedelta(minutes=1)).replace(microsecond=0).isoformat()
    with app_module.db() as conn:
        conn.execute(
            "UPDATE saas_businesses SET subscription_status='trial',trial_ends_at=? WHERE business_id=?",
            (expired_at, result["business_id"]),
        )

    blocked = client.get("/api/items", headers=headers)
    assert blocked.status_code == 402, blocked.text
    assert blocked.json()["subscription_status"] == "expired"

    plan = client.get("/api/saas/me", headers=headers)
    assert plan.status_code == 200, plan.text
    assert plan.json()["subscription_status"] == "expired"


def test_legacy_business_remains_active_without_paid_until(tmp_path: Path):
    app_module.DB_PATH = tmp_path / "saas-legacy.db"
    app_module.init_db()
    client = TestClient(app_module.app)

    setup = client.post(
        "/api/setup",
        json={
            "business_name": "Kishore Traders",
            "owner_name": "Ayush",
            "phone": "9999999999",
            "username": "admin",
            "password": "1234",
        },
    )
    assert setup.status_code == 200, setup.text
    headers = {"Authorization": f"Bearer {setup.json()['token']}"}

    saas_module.ensure_saas_schema()
    items = client.get("/api/items", headers=headers)
    assert items.status_code == 200, items.text
    plan = client.get("/api/saas/me", headers=headers)
    assert plan.status_code == 200
    assert plan.json()["subscription_status"] == "active"
    assert plan.json()["plan"] == "legacy"
