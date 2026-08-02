from __future__ import annotations

import os
import time
from datetime import date, timedelta

import requests


BASE_URL = os.getenv("OWNER_UI_BASE_URL", "http://127.0.0.1:8000")


def expect_ok(response: requests.Response) -> dict | list:
    try:
        data = response.json()
    except ValueError as exc:
        raise AssertionError(f"Non-JSON response {response.status_code}: {response.text[:500]}") from exc
    assert response.ok, f"{response.status_code}: {data}"
    assert data is not None, f"Null JSON response from {response.url}"
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

    suffix = str(int(time.time()))[-7:]
    item = expect_ok(
        owner.post(
            f"{BASE_URL}/api/items",
            json={
                "name": f"Catalog 15 Day Item {suffix}",
                "size": "1 pcs",
                "unit": "pcs",
                "sku": f"CAT15-{suffix}",
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

    phone = "98" + suffix.zfill(8)[-8:]
    party = expect_ok(
        owner.post(
            f"{BASE_URL}/api/parties",
            json={
                "name": f"Catalog 15 Day Customer {suffix}",
                "type": "customer",
                "phone": phone,
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
                "phone": phone,
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
    assert isinstance(manager, dict)
    assert isinstance(manager.get("products"), list)
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
            json={"phone": phone, "pin": "7788"},
            timeout=20,
        )
    )
    customer_headers = {"Authorization": f"Bearer {login['token']}"}

    save(visible=True, default_rate=72, customer_rate=None)

    old_date = (date.today() - timedelta(days=16)).isoformat()
    expect_ok(
        owner.post(
            f"{BASE_URL}/api/sales",
            json={
                "party_id": party["id"],
                "invoice_date": old_date,
                "discount": 0,
                "paid": 0,
                "payment_mode": "credit",
                "notes": "Old rate must be ignored by 15-day catalog rule",
                "items": [
                    {
                        "item_id": item["id"],
                        "item_name": item["name"],
                        "size": item.get("size", ""),
                        "qty": 1,
                        "rate": 61,
                        "gst_rate": 0,
                    }
                ],
            },
            timeout=20,
        )
    )

    catalog = expect_ok(
        requests.get(f"{BASE_URL}/api/customer/catalog", headers=customer_headers, timeout=20)
    )
    default_product = next(row for row in catalog if row["id"] == item["id"])
    assert default_product["rate"] == 72
    assert default_product["rate_source"] == "catalog"

    recent_date = date.today().isoformat()
    recent_sale = expect_ok(
        owner.post(
            f"{BASE_URL}/api/sales",
            json={
                "party_id": party["id"],
                "invoice_date": recent_date,
                "discount": 0,
                "paid": 0,
                "payment_mode": "credit",
                "notes": "Recent rate must be used by customer catalog",
                "items": [
                    {
                        "item_id": item["id"],
                        "item_name": item["name"],
                        "size": item.get("size", ""),
                        "qty": 1,
                        "rate": 66,
                        "gst_rate": 0,
                    }
                ],
            },
            timeout=20,
        )
    )

    catalog = expect_ok(
        requests.get(f"{BASE_URL}/api/customer/catalog", headers=customer_headers, timeout=20)
    )
    recent_product = next(row for row in catalog if row["id"] == item["id"])
    assert recent_product["rate"] == 66
    assert recent_product["rate_source"] == "recent_15_days"
    assert recent_product["recent_bill_date"] == recent_date

    manager = expect_ok(
        owner.get(
            f"{BASE_URL}/api/customer-catalog-manager",
            params={"party_id": party["id"]},
            timeout=20,
        )
    )
    managed_product = next(row for row in manager["products"] if row["item_id"] == item["id"])
    assert managed_product["recent_bill_rate"] == 66
    assert managed_product["effective_rate"] == 66
    assert managed_product["rate_source"] == "recent_15_days"
    assert managed_product["recent_bill_invoice"] == recent_sale["invoice_no"]

    save(visible=True, default_rate=72, customer_rate=65)
    catalog = expect_ok(
        requests.get(f"{BASE_URL}/api/customer/catalog", headers=customer_headers, timeout=20)
    )
    special_product = next(row for row in catalog if row["id"] == item["id"])
    assert special_product["rate"] == 65
    assert special_product["rate_source"] == "fixed"

    save(visible=False, default_rate=72, customer_rate=None)
    catalog = expect_ok(
        requests.get(f"{BASE_URL}/api/customer/catalog", headers=customer_headers, timeout=20)
    )
    assert not any(row["id"] == item["id"] for row in catalog)

    blocked = requests.post(
        f"{BASE_URL}/api/customer/orders",
        headers=customer_headers,
        json={
            "order_date": date.today().isoformat(),
            "notes": "Hidden product test",
            "items": [{"item_id": item["id"], "qty": 1}],
        },
        timeout=20,
    )
    assert blocked.status_code == 403, blocked.text

    print("CUSTOMER_CATALOG_15_DAY_SMOKE_OK")


if __name__ == "__main__":
    main()
