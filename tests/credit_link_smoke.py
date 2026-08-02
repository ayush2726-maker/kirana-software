from __future__ import annotations

import os

from playwright.sync_api import sync_playwright


BASE_URL = os.getenv("OWNER_UI_BASE_URL", "http://127.0.0.1:8000")


def login(page) -> None:
    page.goto(f"{BASE_URL}/owner-login", wait_until="domcontentloaded")
    page.locator('input[name="username"]').fill("admin")
    page.locator('input[name="password"]').fill("1234")
    page.locator('button[type="submit"]').click()
    page.wait_for_selector("#app:not(.hidden)", timeout=20_000)
    page.wait_for_selector("#page-home.active", timeout=12_000)


def open_center(page) -> None:
    page.locator('.bottom-nav [data-page="menu"]').click()
    page.wait_for_selector("#page-menu.active", timeout=8_000)
    page.locator('#page-menu [data-txn-action="open-center"]').click()
    page.wait_for_selector("#txn-center:not(.hidden)", timeout=8_000)


def pick_search_result(page, input_selector: str, text: str, result_selector: str) -> None:
    field = page.locator(input_selector)
    field.fill(text)
    page.wait_for_selector(result_selector, timeout=8_000)
    page.locator(result_selector).first.click()


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        page = context.new_page()
        login(page)

        page.locator('.primary-fab[data-page="sale"]').click()
        page.wait_for_selector("#page-sale.active", timeout=8_000)
        page.wait_for_selector("#sale-credit-note", timeout=8_000)
        assert page.locator("#sale-payment-mode").input_value() == "credit"
        assert page.locator("#sale-payment-mode").is_disabled()
        assert page.locator("#sale-paid").input_value() == "0"
        assert page.locator("#sale-paid").get_attribute("readonly") is not None
        pick_search_result(
            page,
            "#page-sale .party-search-input",
            "Test Customer",
            '#page-sale [data-party-id]:has-text("Test Customer")',
        )
        page.locator("#sale-item-search").fill("Test Rice")
        page.wait_for_selector('[data-action="add-sale-item"]', timeout=8_000)
        page.locator('[data-action="add-sale-item"]').first.click()
        page.locator("#save-sale").click()
        page.wait_for_selector("#page-home.active", timeout=12_000)

        open_center(page)
        page.locator('[data-txn-action="purchase"]').click()
        page.wait_for_selector("#txn-form-screen:not(.hidden)", timeout=8_000)
        page.wait_for_selector("#txn-credit-note", timeout=8_000)
        assert page.locator("#txn-payment-mode").input_value() == "credit"
        assert page.locator("#txn-payment-mode").is_disabled()
        assert page.locator("#txn-paid").input_value() == "0"
        pick_search_result(
            page,
            "#txn-form-screen .party-search-input",
            "Test Supplier",
            '#txn-form-screen [data-party-id]:has-text("Test Supplier")',
        )
        page.locator("#txn-bill-reference").fill("SUP-CREDIT-LINK")
        page.locator("#txn-item-search").fill("Test Rice")
        page.wait_for_selector("[data-txn-add-item]", timeout=8_000)
        page.locator("[data-txn-add-item]").first.click()
        page.locator("#txn-save-bill").click()
        page.wait_for_selector("#page-home.active", timeout=12_000)

        open_center(page)
        page.locator('[data-txn-action="payment-in"]').click()
        page.wait_for_selector('#txn-payment-form[data-linked="1"]', timeout=10_000)
        pick_search_result(page, "#link-party-search", "Test Customer", '[data-link-party]:has-text("Test Customer")')
        page.wait_for_selector(".linked-bill-row", timeout=10_000)
        page.locator("#link-pay-amount").fill("20")
        page.locator('[data-link-action="auto"]').click()
        assert "20.00" in page.locator("#link-allocated").inner_text()
        page.locator('#txn-payment-form button[type="submit"]').click()
        page.wait_for_selector("#page-home.active", timeout=12_000)

        open_center(page)
        page.locator('[data-txn-action="payment-out"]').click()
        page.wait_for_selector('#txn-payment-form[data-linked="1"]', timeout=10_000)
        pick_search_result(page, "#link-party-search", "Test Supplier", '[data-link-party]:has-text("Test Supplier")')
        page.wait_for_selector(".linked-bill-row", timeout=10_000)
        page.locator("#link-pay-amount").fill("15")
        page.locator('[data-link-action="auto"]').click()
        assert "15.00" in page.locator("#link-allocated").inner_text()
        page.locator('#txn-payment-form button[type="submit"]').click()
        page.wait_for_selector("#page-home.active", timeout=12_000)

        context.close()
        browser.close()

    print("CREDIT_LINK_SMOKE_OK")


if __name__ == "__main__":
    main()
