from pathlib import Path

from fastapi.testclient import TestClient

import backend.app as app_module
import backend.advanced_reports_ext as reports_module


def build_client(tmp_path: Path) -> TestClient:
    app_module.DB_PATH = tmp_path / "advanced-reports.db"
    app_module.init_db()
    return TestClient(app_module.app)


def setup_business(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/setup",
        json={
            "business_name": "Report Test Store",
            "owner_name": "Owner",
            "username": "admin",
            "password": "1234",
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_detailed_sale_profit_gst_and_stock_reports(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    headers = setup_business(client)
    item = client.post(
        "/api/items",
        headers=headers,
        json={
            "name": "Sugar",
            "sku": "SUGAR-1KG",
            "size": "1 kg",
            "unit": "packet",
            "purchase_price": 40,
            "sale_price": 60,
            "gst_rate": 5,
            "stock": 10,
            "min_stock": 2,
        },
    ).json()
    sale = client.post(
        "/api/sales",
        headers=headers,
        json={
            "invoice_date": "2026-08-05",
            "payment_mode": "credit",
            "items": [
                {
                    "item_id": item["id"],
                    "item_name": item["name"],
                    "size": item["size"],
                    "qty": 2,
                    "rate": 60,
                    "gst_rate": 5,
                }
            ],
        },
    )
    assert sale.status_code == 200, sale.text

    query = "&date_from=2026-08-01&date_to=2026-08-31"
    sale_report = client.get("/api/reports/detail?report=sale_report" + query, headers=headers)
    assert sale_report.status_code == 200, sale_report.text
    assert sale_report.json()["rows"][0]["total"] == 126

    profit = client.get("/api/reports/detail?report=bill_wise_profit" + query, headers=headers).json()
    assert profit["rows"][0]["cost_estimate"] == 80
    assert profit["rows"][0]["profit_estimate"] == 40

    gst = client.get("/api/reports/detail?report=gstr3b" + query, headers=headers).json()
    assert gst["totals"][0]["value"] == 6

    stock = client.get("/api/reports/detail?report=stock_summary" + query, headers=headers).json()
    assert stock["rows"][0]["stock"] == 8
    assert stock["rows"][0]["stock_value"] == 320


def test_unknown_report_and_invalid_period_are_rejected(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    headers = setup_business(client)
    assert client.get("/api/reports/detail?report=missing", headers=headers).status_code == 404
    response = client.get(
        "/api/reports/detail?report=sale_report&date_from=2026-08-31&date_to=2026-08-01",
        headers=headers,
    )
    assert response.status_code == 400


def test_every_catalog_report_opens_with_an_empty_business(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    headers = setup_business(client)
    query = "&date_from=2026-08-01&date_to=2026-08-31"

    for report in sorted(reports_module.REPORT_TITLES):
        response = client.get(f"/api/reports/detail?report={report}{query}", headers=headers)
        assert response.status_code == 200, f"{report}: {response.text}"
        payload = response.json()
        assert payload["report"] == report
        assert payload["title"] == reports_module.REPORT_TITLES[report]
        assert isinstance(payload["columns"], list)
        assert isinstance(payload["rows"], list)
