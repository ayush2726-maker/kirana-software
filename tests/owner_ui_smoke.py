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


def wait_for_app(page) -> None:
    page.wait_for_selector("#app:not(.hidden)", timeout=20_000)


def wait_for_owner(page) -> None:
    wait_for_app(page)
    page.wait_for_selector("#page-home.active", timeout=12_000)


def add_item(page, name: str, size: str, sale_price: str, purchase_price: str, stock: str) -> None:
    page.locator('[data-action="new-item"]').first.click()
    page.wait_for_selector("#item-modal:not(.hidden)", timeout=5_000)
    form = page.locator("#item-form")
    form.locator('[name="name"]').fill(name)
    form.locator('[name="size"]').fill(size)
    form.locator('[name="unit"]').select_option("kg")
    form.locator('[name="sale_price"]').fill(sale_price)
    form.locator('[name="purchase_price"]').fill(purchase_price)
    form.locator('[name="stock"]').fill(stock)
    form.locator('button[type="submit"]').click()
    page.wait_for_selector("#modal-backdrop.hidden", timeout=8_000)
    page.wait_for_selector(f"#items-list >> text={name}", timeout=8_000)


def add_party(page, name: str, party_type: str, phone: str) -> None:
    page.locator('[data-action="new-party"]').click()
    page.wait_for_selector("#party-modal:not(.hidden)", timeout=5_000)
    form = page.locator("#party-form")
    form.locator('[name="name"]').fill(name)
    form.locator('[name="type"]').select_option(party_type)
    form.locator('[name="phone"]').fill(phone)
    form.locator('button[type="submit"]').click()
    page.wait_for_selector("#modal-backdrop.hidden", timeout=8_000)
    page.wait_for_selector(f"#parties-list >> text={name}", timeout=8_000)


def assert_typing_keeps_focus(page, locator, value: str) -> None:
    locator.click()
    locator.press("Control+A")
    locator.type(value, delay=80)
    assert locator.evaluate("element => document.activeElement === element")
    assert locator.input_value() == value


def open_transaction_center(page) -> None:
    page.locator('[data-page="menu"]').last.click()
    page.wait_for_selector("#page-menu.active", timeout=8_000)
    page.locator('#page-menu [data-txn-action="open-center"]').click()
    page.wait_for_selector("#txn-center:not(.hidden)", timeout=8_000)


def test_bulk_items_and_back_stack(page) -> None:
    page.locator("#bulk-items-toggle").click()
    page.wait_for_selector("#bulk-items-toolbar:not(.hidden)", timeout=5_000)
    rice_card = page.locator('.item-card:has-text("Test Rice")').first
    delete_card = page.locator('.item-card:has-text("Test Delete")').first
    rice_card.locator('[data-bulk-select]').check()
    delete_card.locator('[data-bulk-select]').check()
    page.wait_for_selector("#bulk-selected-count >> text=2 items selected", timeout=5_000)
    page.locator('[data-bulk-action="edit"]').click()
    page.wait_for_selector("#bulk-editor:not(.hidden)", timeout=8_000)
    first_rate = page.locator('#bulk-editor-list [data-bulk-field="sale_price"]').first
    assert_typing_keeps_focus(page, first_rate, "91")
    page.locator('#bulk-editor footer [data-bulk-action="save"]').click()
    page.wait_for_timeout(1200)
    wait_for_app(page)
    page.wait_for_selector("#page-items.active", timeout=15_000)

    page.locator("#bulk-items-toggle").click()
    page.wait_for_selector("#bulk-items-toolbar:not(.hidden)", timeout=5_000)
    delete_card = page.locator('.item-card:has-text("Test Delete")').first
    delete_card.locator('[data-bulk-select]').check()
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator('[data-bulk-action="delete"]').click()
    page.wait_for_timeout(1500)
    wait_for_app(page)
    page.wait_for_selector("#page-items.active", timeout=15_000)
    assert page.locator('.item-card:has-text("Test Delete")').count() == 0

    page.locator('[data-page="home"]').last.click()
    page.wait_for_selector("#page-home.active", timeout=8_000)
    page.locator('.bottom-nav [data-page="dashboard"]').click()
    page.wait_for_selector("#page-dashboard.active", timeout=8_000)
    page.locator('.bottom-nav [data-page="items"]').click()
    page.wait_for_selector("#page-items.active", timeout=8_000)

    assert page.evaluate("window.KiranaBack.handle()") == "handled"
    page.wait_for_selector("#page-dashboard.active", timeout=8_000)
    assert page.evaluate("window.KiranaBack.handle()") == "handled"
    page.wait_for_selector("#page-home.active", timeout=8_000)
    assert page.evaluate("window.KiranaBack.handle()") == "home"


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
        wait_for_owner(page)
        assert page.locator("#business-name").inner_text() == "Smoke Test Store"

        page.locator('.bottom-nav [data-page="dashboard"]').click()
        page.wait_for_selector("#page-dashboard.active", timeout=8_000)
        assert page.locator("#dash-sales").is_visible()

        page.locator('.topbar [data-page="reports"]').click()
        page.wait_for_selector("#page-reports.active", timeout=8_000)
        page.wait_for_selector("#report-content:not(.hidden)", timeout=12_000)
        assert page.locator("#report-net-sales").is_visible()
        assert page.locator("#report-net-purchases").is_visible()

        page.locator('.bottom-nav [data-page="items"]').click()
        page.wait_for_selector("#page-items.active", timeout=8_000)
        add_item(page, "Test Rice", "1 kg", "80", "60", "20")
        add_item(page, "Test Delete", "2 kg", "40", "30", "5")
        test_bulk_items_and_back_stack(page)

        page.locator('[data-page="menu"]').last.click()
        page.wait_for_selector("#page-menu.active", timeout=8_000)
        page.locator('#page-menu [data-page="parties"]').click()
        page.wait_for_selector("#page-parties.active", timeout=8_000)
        add_party(page, "Test Customer", "customer", "9876543210")
        add_party(page, "Test Supplier", "supplier", "9876543211")

        page.locator('[data-page="home"]').last.click()
        page.wait_for_selector("#page-home.active", timeout=8_000)
        page.locator('.primary-fab[data-page="sale"]').click()
        page.wait_for_selector("#page-sale.active", timeout=8_000)
        page.locator("#sale-item-search").fill("Test Rice")
        page.wait_for_selector('[data-action="add-sale-item"]', timeout=5_000)
        page.locator('[data-action="add-sale-item"]').first.click()
        page.wait_for_selector("#sale-lines >> text=Test Rice", timeout=5_000)
        assert_typing_keeps_focus(page, page.locator('[data-sale-field="qty"]'), "2")
        page.locator("#save-sale").click()
        page.wait_for_selector("#page-home.active", timeout=12_000)
        page.wait_for_selector("#activity-list >> text=Cash Customer", timeout=12_000)

        open_transaction_center(page)
        page.locator('[data-txn-action="purchase"]').click()
        page.wait_for_selector("#txn-form-screen:not(.hidden)", timeout=10_000)
        page.locator("#txn-bill-party").select_option(label="Test Supplier · 9876543211")
        page.locator("#txn-bill-reference").fill("SUP-TEST-1")
        page.locator("#txn-item-search").fill("Test Rice")
        page.wait_for_selector('[data-txn-add-item]', timeout=8_000)
        page.locator('[data-txn-add-item]').first.click()
        page.wait_for_selector("#txn-cart >> text=Test Rice", timeout=8_000)
        assert_typing_keeps_focus(page, page.locator('[data-txn-field="qty"]'), "3")
        page.locator("#txn-save-bill").click()
        wait_for_owner(page)

        open_transaction_center(page)
        page.locator('[data-txn-action="payment-out"]').click()
        page.wait_for_selector("#txn-payment-form", timeout=10_000)
        payment_form = page.locator("#txn-payment-form")
        payment_form.locator('[name="party_id"]').select_option(label="Test Supplier · 9876543211")
        payment_form.locator('[name="amount"]').fill("10")
        payment_form.locator('button[type="submit"]').click()
        wait_for_owner(page)

        open_transaction_center(page)
        page.locator('[data-txn-action="expense"]').click()
        page.wait_for_selector("#txn-entry-form", timeout=10_000)
        entry_form = page.locator("#txn-entry-form")
        entry_form.locator('[name="title"]').fill("Smoke Test Expense")
        entry_form.locator('[name="amount"]').fill("5")
        entry_form.locator('button[type="submit"]').click()
        wait_for_owner(page)

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
