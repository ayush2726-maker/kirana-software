from __future__ import annotations

import json
import os
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright


BASE_URL = os.getenv("OWNER_UI_BASE_URL", "http://127.0.0.1:8000")
ARTIFACT_DIR = Path(os.getenv("OWNER_UI_ARTIFACT_DIR", "test-artifacts"))
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def setup_business() -> None:
    status = requests.get(f"{BASE_URL}/api/setup/status", timeout=15)
    status.raise_for_status()
    if status.json().get("setup_complete"):
        return
    response = requests.post(
        f"{BASE_URL}/api/setup",
        json={
            "business_name": "Smoke Test Store",
            "owner_name": "Test Owner",
            "phone": "9999999999",
            "gstin": "",
            "address": "Test Address",
            "username": "admin",
            "password": "1234",
        },
        timeout=20,
    )
    response.raise_for_status()


def main() -> None:
    setup_business()
    browser_errors: list[str] = []
    console_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=1,
            is_mobile=True,
            has_touch=True,
        )
        page = context.new_page()
        page.on("pageerror", lambda error: browser_errors.append(str(error)))
        page.on(
            "console",
            lambda message: console_errors.append(message.text)
            if message.type == "error"
            else None,
        )

        page.goto(f"{BASE_URL}/owner-login", wait_until="domcontentloaded")
        page.locator('input[name="username"]').fill("admin")
        page.locator('input[name="password"]').fill("1234")
        page.locator('button[type="submit"]').click()
        page.wait_for_selector("#app:not(.hidden)", timeout=20_000)
        page.wait_for_selector("#page-home.active", timeout=10_000)
        assert page.locator("#business-name").inner_text() == "Smoke Test Store"

        page.locator('.bottom-nav [data-page="dashboard"]').click()
        page.wait_for_selector("#page-dashboard.active", timeout=8_000)
        assert page.locator("#dash-sales").is_visible()

        page.locator('.bottom-nav [data-page="items"]').click()
        page.wait_for_selector("#page-items.active", timeout=8_000)
        page.locator('[data-action="new-item"]').first.click()
        page.wait_for_selector("#item-modal:not(.hidden)", timeout=5_000)
        item_form = page.locator("#item-form")
        item_form.locator('[name="name"]').fill("Test Rice")
        item_form.locator('[name="size"]').fill("1 kg")
        item_form.locator('[name="unit"]').select_option("kg")
        item_form.locator('[name="sale_price"]').fill("80")
        item_form.locator('[name="purchase_price"]').fill("60")
        item_form.locator('[name="stock"]').fill("20")
        item_form.locator('button[type="submit"]').click()
        page.wait_for_selector("#modal-backdrop.hidden", timeout=8_000)
        page.wait_for_selector("#items-list >> text=Test Rice", timeout=8_000)

        page.locator('[data-page="menu"]').last.click()
        page.wait_for_selector("#page-menu.active", timeout=8_000)
        page.locator('#page-menu [data-page="parties"]').click()
        page.wait_for_selector("#page-parties.active", timeout=8_000)
        page.locator('[data-action="new-party"]').click()
        page.wait_for_selector("#party-modal:not(.hidden)", timeout=5_000)
        party_form = page.locator("#party-form")
        party_form.locator('[name="name"]').fill("Test Customer")
        party_form.locator('[name="phone"]').fill("9876543210")
        party_form.locator('button[type="submit"]').click()
        page.wait_for_selector("#modal-backdrop.hidden", timeout=8_000)
        page.wait_for_selector("#parties-list >> text=Test Customer", timeout=8_000)

        page.locator('[data-page="home"]').last.click()
        page.wait_for_selector("#page-home.active", timeout=8_000)
        page.locator('.primary-fab[data-page="sale"]').click()
        page.wait_for_selector("#page-sale.active", timeout=8_000)
        page.locator("#sale-item-search").fill("Test Rice")
        page.wait_for_selector('[data-action="add-sale-item"]', timeout=5_000)
        page.locator('[data-action="add-sale-item"]').first.click()
        page.wait_for_selector("#sale-lines >> text=Test Rice", timeout=5_000)
        page.locator("#save-sale").click()
        page.wait_for_selector("#page-home.active", timeout=12_000)
        page.wait_for_selector("#activity-list >> text=Cash Customer", timeout=12_000)

        page.screenshot(path=str(ARTIFACT_DIR / "owner-ui-smoke.png"), full_page=True)
        context.close()
        browser.close()

    fatal_errors = [
        error
        for error in browser_errors + console_errors
        if "favicon" not in error.lower() and "service worker" not in error.lower()
    ]
    if fatal_errors:
        raise AssertionError("Browser errors: " + json.dumps(fatal_errors, ensure_ascii=False))

    print("OWNER_UI_SMOKE_OK")


if __name__ == "__main__":
    main()
