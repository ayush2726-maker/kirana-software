from __future__ import annotations

import os

import requests


BASE_URL = os.getenv("OWNER_UI_BASE_URL", "http://127.0.0.1:8000")


def expect_ok(response: requests.Response) -> dict | list:
    try:
        data = response.json()
    except ValueError as exc:
        raise AssertionError(f"Non-JSON response {response.status_code}: {response.text[:500]}") from exc
    assert response.ok, f"{response.status_code}: {data}"
    return data


def main() -> None:
    owner = requests.Session()
    response = owner.post(
        f"{BASE_URL}/owner-login",
        data={"username": "admin", "password": "1234"},
        allow_redirects=True,
        timeout=20,
    )
    assert response.ok

    items = expect_ok(owner.get(f"{BASE_URL}/api/items?limit=2000", timeout=20))
    item = next((row for row in items if row.get("name") == "Catalog Manager Item"), None)
    if item is None:
        item = expect_ok(
            owner.post(
                f"{BASE_URL}/api/items",
                json={
                    "name": "Catalog Manager Item",
                    "size": "1 pcs",
                    "unit": "pcs",
                    "sku": "CAT-MANAGER-1",
                    "category": "Test",
                    "sale_price": 50,
                    "purchase_price": 25,
                    "stock": 100,
                    "min_stock": 0,
                    "gst_rate": 0,
                    "mrp": 60,
                    "barcode": "",
                    "hsn": "",
                },
                timeout=20,
            )
        )

    parties = expect_ok(owner.get(f"{BASE_URL}/api/parties", timeout=20))
    party = next((row for row in parties if row.get("name") == "Catalog Manager Customer"), None)
    if party is None:
        party = expect_ok(
            owner.post(
                f"{BASE_URL}/api/parties",
                json={
                    "name": "Catalog Manager Customer",
                    "type": "customer",
                    "phone": "9811199900",
                    "opening_balance": 0,
                    "gstin": "",
                    "address": "",
                },
                timeout=20,
            )
        )

    expect_ok(
        owner.post(
            f"{BASE_URL}/api/customer-access",
            json={
                "party_id": party["id"],
                "phone": "9811199900",
                "pin": "7788",
                "is_active": True,
            },
            timeout=20,
        )
    )

    manager = expect_ok(
        owner.get(
            f"{BASE_URL}/api/customer-catalog-manager",
            params={"party_id": party["id"]},
            timeout=20,
        )
    )
    product = next(row for row in manager["products"] if row["item_id"] == item["id"])

    def save(*, visible: bool, default_rate: float | None, customer_rate: float | None) -> None:
        expect_ok(
            owner.post(
                f"{BASE_URL}/api/customer-catalog-manager",
                json={
                    "party_id": party["id"],
                    "items": [
                        {
                            "catalog_key": product["catalog_key"],
                            "item_id": product["item_id"],
                            "is_visible": visible,
                            "default_rate": default_rate,
                            "customer_rate": customer_rate,
                        }
                    ],
                },
                timeout=20,
            )
        )

    login = expect_ok(
        requests.post(
            f"{BASE_URL}/api/customer/login",
            json={"phone": "9811199900", "pin": "7788"},
            timeout=20,
        )
    )
    customer_headers = {"Authorization": f"Bearer {login['token']}"}

    save(visible=False, default_rate=72, customer_rate=65)
    catalog = expect_ok(
        requests.get(f"{BASE_URL}/api/customer/catalog", headers=customer_headers, timeout=20)
    )
    assert not any(row["id"] == item["id"] for row in catalog)

    blocked = requests.post(
        f"{BASE_URL}/api/customer/orders",
        headers=customer_headers,
        json={
            "order_date": "2026-08-02",
            "notes": "Hidden product test",
            "items": [{"item_id": item["id"], "qty": 1}],
        },
        timeout=20,
    )
    assert blocked.status_code == 403, blocked.text

    save(visible=True, default_rate=72, customer_rate=65)
    catalog = expect_ok(
        requests.get(f"{BASE_URL}/api/customer/catalog", headers=customer_headers, timeout=20)
    )
    visible_product = next(row for row in catalog if row["id"] == item["id"])
    assert visible_product["rate"] == 65
    assert visible_product["rate_source"] == "fixed"

    save(visible=True, default_rate=72, customer_rate=None)
    catalog = expect_ok(
        requests.get(f"{BASE_URL}/api/customer/catalog", headers=customer_headers, timeout=20)
    )
    default_product = next(row for row in catalog if row["id"] == item["id"])
    assert default_product["rate"] == 72
    assert default_product["rate_source"] == "catalog"

    print("CUSTOMER_CATALOG_MANAGER_SMOKE_OK")


if __name__ == "__main__":
    main()
