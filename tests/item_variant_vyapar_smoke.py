from __future__ import annotations

import io
import os
import time

import requests
from openpyxl import Workbook


BASE_URL = os.getenv("OWNER_UI_BASE_URL", "http://127.0.0.1:8000")


def expect_ok(response: requests.Response) -> dict | list:
    try:
        data = response.json()
    except ValueError as exc:
        raise AssertionError(f"Non-JSON response {response.status_code}: {response.text[:500]}") from exc
    assert response.ok, f"{response.status_code}: {data}"
    assert data is not None
    return data


def report_bytes(invoice_no: str, product_name: str, item_code: str) -> bytes:
    workbook = Workbook()
    summary = workbook.active
    summary.title = "Sale Report"
    summary.append(["Generated for size variant smoke test"])
    summary.append([])
    summary.append([])
    summary.append([
        "Date", "Order No", "Invoice No", "Party Name", "GSTIN", "Party Phone No.",
        "Transaction Type", "Total Amount", "Payment Type", "Received/Paid Amount",
        "Balance Due", "Due Date", "Status", "Description",
    ])
    summary.append([
        "02/08/2026", "", invoice_no, "Variant Test Customer", "", "9999999999",
        "Sale", 330, "Credit", 0, 330, "09/08/2026", "Unpaid", "",
    ])

    details = workbook.create_sheet("Item Details")
    details.append(["Generated for size variant smoke test"])
    details.append([])
    details.append([
        "Date", "Invoice No./Txn No.", "Party Name", "Item Name", "Item Code", "HSN/SAC",
        "Category", "Challan/Order No.", "size", "Quantity", "Unit", "UnitPrice",
        "Discount Percent", "Discount", "Tax Percent", "Tax", "Transaction Type", "Amount",
    ])
    details.append([])
    details.append([
        "02/08/2026", invoice_no, "Variant Test Customer", f"{product_name} (काबली चना)", item_code,
        "", "Grains", "", "", 1, "Kg", 100, 0, 0, 0, 0, "Sale", 100,
    ])
    details.append([
        "02/08/2026", invoice_no, "Variant Test Customer", f"{product_name} 500 (काबली चना)", item_code,
        "", "Grains", "", "500", 1, "Kg", 110, 0, 0, 0, 0, "Sale", 110,
    ])
    details.append([
        "02/08/2026", invoice_no, "Variant Test Customer", f"{product_name} M (काबली चना)", item_code,
        "", "Grains", "", "", 1, "Kg", 120, 0, 0, 0, 0, "Sale", 120,
    ])

    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def upload(owner: requests.Session, invoice_no: str, product_name: str, item_code: str) -> dict:
    filename = f"SaleReport_{invoice_no}.xlsx"
    return expect_ok(
        owner.post(
            f"{BASE_URL}/api/import/vyapar",
            data={"entity_type": "sales", "dry_run": "false"},
            files={
                "file": (
                    filename,
                    report_bytes(invoice_no, product_name, item_code),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            timeout=60,
        )
    )


def main() -> None:
    owner = requests.Session()
    login = owner.post(
        f"{BASE_URL}/owner-login",
        data={"username": "admin", "password": "1234"},
        allow_redirects=True,
        timeout=20,
    )
    assert login.ok

    suffix = str(int(time.time()))[-7:]
    product_name = f"Variant Kabli {suffix}"
    item_code = f"VAR-{suffix}"

    first = upload(owner, f"V-{suffix}-1", product_name, item_code)
    assert first["rows_imported"] == 1, first

    items = expect_ok(owner.get(f"{BASE_URL}/api/items?limit=3000", timeout=30))
    variants = [row for row in items if product_name.lower() in str(row.get("name", "")).lower()]
    assert len(variants) == 3, variants
    assert {str(row.get("size") or "") for row in variants} == {"", "500 Kg", "M"}, variants
    assert len({row["sku"] for row in variants}) == 3, variants
    assert {row["name"] for row in variants} == {f"{product_name} (काबली चना)"}, variants

    second = upload(owner, f"V-{suffix}-2", product_name, item_code)
    assert second["rows_imported"] == 1, second
    items = expect_ok(owner.get(f"{BASE_URL}/api/items?limit=3000", timeout=30))
    variants_after = [row for row in items if product_name.lower() in str(row.get("name", "")).lower()]
    assert len(variants_after) == 3, variants_after

    owner_page = owner.get(f"{BASE_URL}/", timeout=30)
    assert owner_page.ok
    assert "Vyapar item-size variants v126" in owner_page.text
    assert "item-product-card" in owner_page.text
    assert "SELECT SIZE / BATCH" in owner_page.text

    print("ITEM_VARIANT_VYAPAR_SMOKE_OK")


if __name__ == "__main__":
    main()
