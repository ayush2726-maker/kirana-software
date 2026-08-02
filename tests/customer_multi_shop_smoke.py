from __future__ import annotations

import os
import time

import requests


BASE_URL = os.getenv("OWNER_UI_BASE_URL", "http://127.0.0.1:8000")
CUSTOMER_PHONE = "9811122233"
PIN_ONE = "2468"
PIN_TWO = "8642"


def json_ok(response: requests.Response) -> dict | list:
    try:
        data = response.json()
    except ValueError as exc:
        raise AssertionError(f"Non-JSON response {response.status_code}: {response.text[:500]}") from exc
    assert response.ok, f"{response.status_code}: {data}"
    return data


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def owner_one() -> tuple[requests.Session, dict]:
    session = requests.Session()
    login = session.post(
        f"{BASE_URL}/owner-login",
        data={"username": "admin", "password": "1234"},
        allow_redirects=True,
        timeout=20,
    )
    assert login.ok, login.text[:500]
    return session, json_ok(session.get(f"{BASE_URL}/api/saas/me", timeout=20))


def ensure_party(session: requests.Session, phone: str, name: str) -> dict:
    parties = json_ok(session.get(f"{BASE_URL}/api/parties", timeout=20))
    existing = next((row for row in parties if str(row.get("phone") or "").endswith(phone)), None)
    if existing:
        return existing
    return json_ok(
        session.post(
            f"{BASE_URL}/api/parties",
            json={
                "name": name,
                "type": "customer",
                "phone": phone,
                "opening_balance": 0,
                "gstin": "",
                "address": "",
            },
            timeout=20,
        )
    )


def ensure_item(session: requests.Session, name: str, sku: str, rate: float) -> dict:
    items = json_ok(session.get(f"{BASE_URL}/api/items?limit=2000", timeout=20))
    existing = next((row for row in items if row.get("sku") == sku), None)
    if existing:
        return existing
    return json_ok(
        session.post(
            f"{BASE_URL}/api/items",
            json={
                "name": name,
                "size": "1 pcs",
                "unit": "pcs",
                "sku": sku,
                "category": "Multi Shop Test",
                "sale_price": rate,
                "purchase_price": max(0, rate - 1),
                "stock": 100,
                "min_stock": 0,
                "gst_rate": 0,
                "mrp": rate,
                "barcode": "",
                "hsn": "",
            },
            timeout=20,
        )
    )


def main() -> None:
    first_owner, first_shop = owner_one()
    first_party = ensure_party(first_owner, CUSTOMER_PHONE, "Same Customer Shop One")
    first_item = ensure_item(first_owner, "Shop One Exclusive Item", "SHOP-ONE-ONLY", 11)
    json_ok(
        first_owner.post(
            f"{BASE_URL}/api/customer-access",
            json={
                "party_id": first_party["id"],
                "phone": CUSTOMER_PHONE,
                "pin": PIN_ONE,
                "is_active": True,
            },
            timeout=20,
        )
    )

    suffix = str(int(time.time() * 1000))[-8:]
    second_signup = json_ok(
        requests.post(
            f"{BASE_URL}/api/saas/register-business",
            json={
                "business_name": f"Second Test Shop {suffix}",
                "owner_name": "Second Owner",
                "phone": "9899001122",
                "gstin": "",
                "address": "",
                "username": f"owner_{suffix}",
                "password": "5678",
            },
            timeout=20,
        )
    )
    second_token = str(second_signup["token"])
    second_headers = bearer(second_token)
    second_owner = requests.Session()
    second_owner.headers.update(second_headers)

    second_party = json_ok(
        second_owner.post(
            f"{BASE_URL}/api/parties",
            json={
                "name": "Same Customer Shop Two",
                "type": "customer",
                "phone": CUSTOMER_PHONE,
                "opening_balance": 0,
                "gstin": "",
                "address": "",
            },
            timeout=20,
        )
    )
    second_item = json_ok(
        second_owner.post(
            f"{BASE_URL}/api/items",
            json={
                "name": "Shop Two Exclusive Item",
                "size": "1 pcs",
                "unit": "pcs",
                "sku": f"SHOP-TWO-{suffix}",
                "category": "Multi Shop Test",
                "sale_price": 22,
                "purchase_price": 20,
                "stock": 100,
                "min_stock": 0,
                "gst_rate": 0,
                "mrp": 22,
                "barcode": "",
                "hsn": "",
            },
            timeout=20,
        )
    )
    json_ok(
        second_owner.post(
            f"{BASE_URL}/api/customer-access",
            json={
                "party_id": second_party["id"],
                "phone": CUSTOMER_PHONE,
                "pin": PIN_TWO,
                "is_active": True,
            },
            timeout=20,
        )
    )

    slug_one = str(first_shop["slug"])
    slug_two = str(second_signup["slug"])
    assert slug_one != slug_two

    login_one = json_ok(
        requests.post(
            f"{BASE_URL}/api/customer/login",
            json={"phone": CUSTOMER_PHONE, "pin": PIN_ONE, "shop_slug": slug_one},
            timeout=20,
        )
    )
    login_two = json_ok(
        requests.post(
            f"{BASE_URL}/api/customer/login",
            json={"phone": CUSTOMER_PHONE, "pin": PIN_TWO, "shop_slug": slug_two},
            timeout=20,
        )
    )
    assert login_one["shop_slug"] == slug_one
    assert login_two["shop_slug"] == slug_two
    assert login_one["token"] != login_two["token"]

    wrong_one = requests.post(
        f"{BASE_URL}/api/customer/login",
        json={"phone": CUSTOMER_PHONE, "pin": PIN_TWO, "shop_slug": slug_one},
        timeout=20,
    )
    wrong_two = requests.post(
        f"{BASE_URL}/api/customer/login",
        json={"phone": CUSTOMER_PHONE, "pin": PIN_ONE, "shop_slug": slug_two},
        timeout=20,
    )
    assert wrong_one.status_code == 401, wrong_one.text
    assert wrong_two.status_code == 401, wrong_two.text

    customer_one_headers = bearer(str(login_one["token"]))
    customer_two_headers = bearer(str(login_two["token"]))
    me_one = json_ok(requests.get(f"{BASE_URL}/api/customer/me", headers=customer_one_headers, timeout=20))
    me_two = json_ok(requests.get(f"{BASE_URL}/api/customer/me", headers=customer_two_headers, timeout=20))
    assert int(me_one["party_id"]) == int(first_party["id"])
    assert int(me_two["party_id"]) == int(second_party["id"])
    assert me_one["business_name"] != me_two["business_name"]

    catalog_one = json_ok(requests.get(f"{BASE_URL}/api/customer/catalog", headers=customer_one_headers, timeout=20))
    catalog_two = json_ok(requests.get(f"{BASE_URL}/api/customer/catalog", headers=customer_two_headers, timeout=20))
    names_one = {row["name"] for row in catalog_one}
    names_two = {row["name"] for row in catalog_two}
    assert first_item["name"] in names_one
    assert second_item["name"] not in names_one
    assert second_item["name"] in names_two
    assert first_item["name"] not in names_two

    order_one = json_ok(
        requests.post(
            f"{BASE_URL}/api/customer/orders",
            headers=customer_one_headers,
            json={"notes": "Shop one order", "items": [{"item_id": first_item["id"], "qty": 1}]},
            timeout=20,
        )
    )
    order_two = json_ok(
        requests.post(
            f"{BASE_URL}/api/customer/orders",
            headers=customer_two_headers,
            json={"notes": "Shop two order", "items": [{"item_id": second_item["id"], "qty": 1}]},
            timeout=20,
        )
    )
    orders_one = json_ok(requests.get(f"{BASE_URL}/api/customer/orders", headers=customer_one_headers, timeout=20))
    orders_two = json_ok(requests.get(f"{BASE_URL}/api/customer/orders", headers=customer_two_headers, timeout=20))
    assert any(row["order_no"] == order_one["order_no"] for row in orders_one)
    assert all(row["order_no"] != order_two["order_no"] for row in orders_one)
    assert any(row["order_no"] == order_two["order_no"] for row in orders_two)
    assert all(row["order_no"] != order_one["order_no"] for row in orders_two)

    otp_one = json_ok(
        requests.post(
            f"{BASE_URL}/api/customer/register/request-otp",
            json={"phone": CUSTOMER_PHONE, "shop_slug": slug_one},
            timeout=20,
        )
    )
    otp_two = json_ok(
        requests.post(
            f"{BASE_URL}/api/customer/register/request-otp",
            json={"phone": CUSTOMER_PHONE, "shop_slug": slug_two},
            timeout=20,
        )
    )
    assert otp_one["request_id"] != otp_two["request_id"]
    owner_one_otps = json_ok(first_owner.get(f"{BASE_URL}/api/customer/otp-requests", timeout=20))
    owner_two_otps = json_ok(second_owner.get(f"{BASE_URL}/api/customer/otp-requests", timeout=20))
    ids_one = {int(row["id"]) for row in owner_one_otps}
    ids_two = {int(row["id"]) for row in owner_two_otps}
    assert int(otp_one["request_id"]) in ids_one
    assert int(otp_two["request_id"]) not in ids_one
    assert int(otp_two["request_id"]) in ids_two
    assert int(otp_one["request_id"]) not in ids_two

    customer_script = requests.get(f"{BASE_URL}/customer-order.js?v=112", timeout=20)
    assert customer_script.ok
    assert "ks_customer_token:${storageSuffix}" in customer_script.text
    assert "Other shop sessions remain saved" in customer_script.text

    print("CUSTOMER_MULTI_SHOP_SMOKE_OK")


if __name__ == "__main__":
    main()
