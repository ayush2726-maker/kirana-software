from __future__ import annotations

import os

import requests


BASE_URL = os.getenv("OWNER_UI_BASE_URL", "http://127.0.0.1:8000")
PHONE = "9811199911"
PIN = "7788"


def expect_json(response: requests.Response) -> dict | list:
    try:
        data = response.json()
    except ValueError as exc:
        raise AssertionError(f"Non-JSON response {response.status_code}: {response.text[:500]}") from exc
    assert response.ok, f"{response.status_code}: {data}"
    return data


def main() -> None:
    owner = requests.Session()
    login = owner.post(
        f"{BASE_URL}/owner-login",
        data={"username": "admin", "password": "1234"},
        allow_redirects=True,
        timeout=20,
    )
    assert login.ok, login.text[:500]

    saas = expect_json(owner.get(f"{BASE_URL}/api/saas/me", timeout=20))
    slug = str(saas["slug"])
    business_name = str(saas["business_name"])

    parties = expect_json(owner.get(f"{BASE_URL}/api/parties", timeout=20))
    party = next((row for row in parties if row.get("phone") == PHONE), None)
    if party is None:
        party = expect_json(
            owner.post(
                f"{BASE_URL}/api/parties",
                json={
                    "name": "Customer Login Share Test",
                    "type": "customer",
                    "phone": PHONE,
                    "opening_balance": 0,
                    "gstin": "",
                    "address": "",
                },
                timeout=20,
            )
        )

    expect_json(
        owner.post(
            f"{BASE_URL}/api/customer-access",
            json={
                "party_id": party["id"],
                "phone": PHONE,
                "pin": PIN,
                "is_active": True,
            },
            timeout=20,
        )
    )

    wrong_shop = requests.post(
        f"{BASE_URL}/api/customer/login",
        json={"phone": PHONE, "pin": PIN, "shop_slug": "wrong-shop-link"},
        timeout=20,
    )
    assert wrong_shop.status_code == 404, wrong_shop.text

    customer_login = expect_json(
        requests.post(
            f"{BASE_URL}/api/customer/login",
            json={"phone": PHONE, "pin": PIN, "shop_slug": slug},
            timeout=20,
        )
    )
    assert customer_login["token"]
    assert customer_login["shop_slug"] == slug
    assert customer_login["business_name"] == business_name

    headers = {"Authorization": f"Bearer {customer_login['token']}"}
    me = expect_json(requests.get(f"{BASE_URL}/api/customer/me", headers=headers, timeout=20))
    assert int(me["party_id"]) == int(party["id"])
    assert me["business_name"] == business_name

    share = expect_json(owner.get(f"{BASE_URL}/api/customer/share-info", timeout=20))
    assert share["business_name"] == business_name
    assert share["shop_slug"] == slug
    assert share["customer_order_path"] == f"/customer?shop={slug}"

    portal = requests.get(f"{BASE_URL}/customer?shop={slug}", timeout=20)
    assert portal.ok, portal.text[:500]
    assert "/customer-order.js?v=110" in portal.text

    customer_script = requests.get(f"{BASE_URL}/customer-order.js?v=110", timeout=20)
    assert customer_script.ok
    assert "STALE_AUTH" in customer_script.text
    assert "path !== '/api/customer/login'" in customer_script.text
    assert "Signing in..." in customer_script.text

    owner_page = owner.get(f"{BASE_URL}/?page=orders", timeout=20)
    assert owner_page.ok
    assert "/owner-customer-share.js?v=109" in owner_page.text
    assert "/owner-customer-share.css?v=109" in owner_page.text

    share_script = owner.get(f"{BASE_URL}/owner-customer-share.js?v=109", timeout=20)
    assert share_script.ok
    assert "Share on WhatsApp" in share_script.text
    assert "ghar baithe order karein" in share_script.text
    assert "/api/customer/share-info" in share_script.text

    print("CUSTOMER_LOGIN_SHARE_SMOKE_OK")


if __name__ == "__main__":
    main()
