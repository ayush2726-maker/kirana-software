from pathlib import Path

from fastapi.testclient import TestClient

import backend.app as app_module
import backend.order_portal_ext as order_module
import backend.saas_ext as saas_module
import backend.customer_self_register_ext  # noqa: F401
import backend.customer_link_fix_ext  # noqa: F401


def test_old_customer_link_redirects_to_primary_shop(tmp_path: Path):
    app_module.DB_PATH = tmp_path / "customer-link-fix.db"
    app_module.init_db()
    order_module.ensure_order_schema()
    client = TestClient(app_module.app)

    setup = client.post(
        "/api/setup",
        json={
            "business_name": "Kishore Traders",
            "owner_name": "Ayush",
            "phone": "9981082113",
            "username": "admin",
            "password": "1234",
        },
    )
    assert setup.status_code == 200, setup.text
    saas_module.ensure_saas_schema()

    default_shop = client.get("/api/saas/default-business")
    assert default_shop.status_code == 200, default_shop.text
    assert default_shop.json()["slug"] == "kishore-traders"
    assert default_shop.json()["customer_order_path"] == "/customer?shop=kishore-traders"

    old_link = client.get("/customer", follow_redirects=False)
    assert old_link.status_code == 307
    assert "shop=kishore-traders" in old_link.headers["location"]

    corrected = client.get(old_link.headers["location"])
    assert corrected.status_code == 200
    assert "Dukaan ka customer link galat hai" not in corrected.text
