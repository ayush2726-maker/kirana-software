from pathlib import Path

from fastapi.testclient import TestClient

import backend.app as app_module


def build_client(tmp_path: Path):
    app_module.DB_PATH = tmp_path / "test.db"
    app_module.init_db()
    return TestClient(app_module.app)


def setup_and_headers(client: TestClient):
    response = client.post(
        "/api/setup",
        json={
            "business_name": "Kishore Traders",
            "owner_name": "Ayush",
            "username": "admin",
            "password": "1234",
        },
    )
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_sale_updates_stock_and_ledger(tmp_path):
    client = build_client(tmp_path)
    headers = setup_and_headers(client)

    item = client.post(
        "/api/items",
        headers=headers,
        json={
            "name": "Sugar 1kg",
            "sku": "SUGAR-1",
            "unit": "packet",
            "size": "1 kg",
            "purchase_price": 42,
            "sale_price": 50,
            "gst_rate": 5,
            "stock": 10,
            "min_stock": 2,
        },
    ).json()
    party = client.post(
        "/api/parties",
        headers=headers,
        json={"name": "Ramesh", "type": "customer", "opening_balance": 100},
    ).json()

    sale_response = client.post(
        "/api/sales",
        headers=headers,
        json={
            "party_id": party["id"],
            "invoice_date": "2026-07-23",
            "discount": 5,
            "paid": 50,
            "payment_mode": "cash",
            "items": [
                {
                    "item_id": item["id"],
                    "item_name": item["name"],
                    "size": item["size"],
                    "qty": 2,
                    "rate": 50,
                    "gst_rate": 5,
                }
            ],
        },
    )
    assert sale_response.status_code == 200, sale_response.text
    sale = sale_response.json()
    assert sale["subtotal"] == 100
    assert sale["tax"] == 5
    assert sale["total"] == 100
    assert sale["due"] == 50
    assert sale["items"][0]["size"] == "1 kg"

    items = client.get("/api/items", headers=headers).json()
    assert items[0]["stock"] == 8

    ledger = client.get(f"/api/parties/{party['id']}/ledger", headers=headers).json()
    assert ledger["party"]["balance"] == 150
    assert any(entry["entry_type"] == "sale" for entry in ledger["entries"])


def test_purchase_updates_stock_and_supplier_balance(tmp_path):
    client = build_client(tmp_path)
    headers = setup_and_headers(client)
    item = client.post("/api/items", headers=headers, json={"name": "Rice", "sku": "RICE", "stock": 5}).json()
    supplier = client.post("/api/parties", headers=headers, json={"name": "Wholesale Mart", "type": "supplier"}).json()

    response = client.post(
        "/api/purchases",
        headers=headers,
        json={
            "party_id": supplier["id"],
            "paid": 200,
            "items": [{"item_id": item["id"], "item_name": "Rice", "qty": 10, "rate": 30, "gst_rate": 0}],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["due"] == 100
    updated_item = client.get("/api/items", headers=headers).json()[0]
    assert updated_item["stock"] == 15
    updated_supplier = client.get(f"/api/parties/{supplier['id']}/ledger", headers=headers).json()["party"]
    assert updated_supplier["balance"] == 100


def test_vyapar_item_csv_import(tmp_path):
    client = build_client(tmp_path)
    headers = setup_and_headers(client)
    csv_bytes = (
        "Item Name,Item Code,Sale Price,Purchase Price,Current Stock,Tax Rate,Unit,Size\n"
        "Tea 250g,TEA250,140,110,20,5,packet,250 gm\n"
        "Salt 1kg,SALT1,25,20,30,0,packet,1 kg\n"
    ).encode()
    response = client.post(
        "/api/import/vyapar",
        headers=headers,
        data={"entity_type": "items", "dry_run": "false"},
        files={"file": ("vyapar-items.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["rows_imported"] == 2
    items = client.get("/api/items", headers=headers).json()
    assert len(items) == 2
    tea = next(i for i in items if i["sku"] == "TEA250")
    assert tea["sale_price"] == 140
    assert tea["stock"] == 20
    assert tea["size"] == "250 gm"


def test_login_and_dashboard(tmp_path):
    client = build_client(tmp_path)
    headers = setup_and_headers(client)
    login = client.post("/api/login", json={"username": "admin", "password": "1234"})
    assert login.status_code == 200
    dashboard = client.get("/api/dashboard", headers=headers)
    assert dashboard.status_code == 200
    data = dashboard.json()
    assert data["sales_today"] == 0
    assert data["item_count"] == 0


def test_accounts_entries_documents_and_activity(tmp_path):
    client = build_client(tmp_path)
    headers = setup_and_headers(client)

    accounts = client.get('/api/accounts', headers=headers)
    assert accounts.status_code == 200
    cash = accounts.json()[0]
    assert cash['account_type'] == 'cash'

    bank = client.post('/api/accounts', headers=headers, json={
        'name': 'Current Account', 'account_type': 'bank', 'opening_balance': 5000
    })
    assert bank.status_code == 200
    bank_id = bank.json()['id']

    expense = client.post('/api/entries', headers=headers, json={
        'entry_type': 'expense', 'entry_date': '2026-07-23', 'title': 'Electricity',
        'account_id': bank_id, 'amount': 750, 'mode': 'bank'
    })
    assert expense.status_code == 200, expense.text

    transfer = client.post('/api/entries', headers=headers, json={
        'entry_type': 'transfer', 'entry_date': '2026-07-23', 'title': 'Cash withdrawal',
        'account_id': bank_id, 'to_account_id': cash['id'], 'amount': 1000, 'mode': 'bank'
    })
    assert transfer.status_code == 200, transfer.text

    quotation = client.post('/api/documents', headers=headers, json={
        'kind': 'estimate', 'doc_date': '2026-07-23', 'amount': 3500,
        'status': 'open', 'note': 'Test quotation'
    })
    assert quotation.status_code == 200, quotation.text
    assert quotation.json()['doc_no'].startswith('EST-')

    updated_accounts = client.get('/api/accounts', headers=headers).json()
    bank_row = next(x for x in updated_accounts if x['id'] == bank_id)
    cash_row = next(x for x in updated_accounts if x['id'] == cash['id'])
    assert bank_row['balance'] == 3250
    assert cash_row['balance'] == 1000

    activity = client.get('/api/activity', headers=headers)
    assert activity.status_code == 200
    kinds = {x['kind'] for x in activity.json()}
    assert {'expense', 'transfer', 'estimate'} <= kinds

    dashboard = client.get('/api/dashboard', headers=headers).json()
    assert dashboard['expenses_month'] == 750
    assert dashboard['bank_balance'] == 3250
    assert dashboard['cash_balance'] == 1000
    assert dashboard['open_documents']['count'] == 1


def test_item_name_pack_is_split_and_print_data_is_separate(tmp_path):
    client = build_client(tmp_path)
    headers = setup_and_headers(client)
    item = client.post(
        "/api/items",
        headers=headers,
        json={
            "name": "Barik Souff 500 (बारिक सौंफ)",
            "sku": "BS500",
            "unit": "packet",
            "size": "100",
            "sale_price": 180,
            "stock": 10,
        },
    ).json()
    assert item["name"] == "Barik Souff (बारिक सौंफ)"
    assert item["size"] == "500"

    sale = client.post(
        "/api/sales",
        headers=headers,
        json={
            "items": [{
                "item_id": item["id"],
                "item_name": "Barik Souff 500 (बारिक सौंफ)",
                "size": "100",
                "qty": 1,
                "rate": 180,
                "gst_rate": 0,
            }]
        },
    )
    assert sale.status_code == 200, sale.text
    line = sale.json()["items"][0]
    assert line["item_name"] == "Barik Souff (बारिक सौंफ)"
    assert line["size"] == "500"


def test_existing_items_are_cleaned_during_startup(tmp_path):
    client = build_client(tmp_path)
    headers = setup_and_headers(client)
    with app_module.db() as conn:
        conn.execute(
            "INSERT INTO items(business_id,name,sku,unit,size,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (1, "Barik Souff 100 (बारिक सौंफ)", "BS100", "packet", "999", app_module.now_iso(), app_module.now_iso()),
        )
    app_module.init_db()
    rows = client.get("/api/items", headers=headers).json()
    row = next(x for x in rows if x["sku"] == "BS100")
    assert row["name"] == "Barik Souff (बारिक सौंफ)"
    assert row["size"] == "100"


def test_sale_and_purchase_returns_update_stock_party_and_activity(tmp_path):
    client = build_client(tmp_path)
    headers = setup_and_headers(client)
    item = client.post('/api/items', headers=headers, json={
        'name': 'Barik Souff', 'sku': 'BS500', 'size': '500', 'unit': 'packet',
        'stock': 10, 'sale_price': 100, 'purchase_price': 70, 'gst_rate': 5,
    }).json()
    customer = client.post('/api/parties', headers=headers, json={
        'name': 'Customer A', 'type': 'customer', 'opening_balance': 300,
    }).json()
    supplier = client.post('/api/parties', headers=headers, json={
        'name': 'Supplier A', 'type': 'supplier', 'opening_balance': 300,
    }).json()

    sale_return = client.post('/api/returns', headers=headers, json={
        'kind': 'sale_return', 'party_id': customer['id'], 'return_date': '2026-07-23',
        'reference_no': 'KS-S-1', 'paid': 0,
        'items': [{'item_id': item['id'], 'item_name': 'Barik Souff', 'size': '500', 'qty': 2, 'rate': 100, 'gst_rate': 5}],
    })
    assert sale_return.status_code == 200, sale_return.text
    assert sale_return.json()['total'] == 210
    assert sale_return.json()['due'] == 210
    assert client.get('/api/items', headers=headers).json()[0]['stock'] == 12
    assert client.get(f"/api/parties/{customer['id']}/ledger", headers=headers).json()['party']['balance'] == 90

    purchase_return = client.post('/api/returns', headers=headers, json={
        'kind': 'purchase_return', 'party_id': supplier['id'], 'return_date': '2026-07-23',
        'reference_no': 'SUP-9', 'paid': 73.5, 'payment_mode': 'cash',
        'items': [{'item_id': item['id'], 'item_name': 'Barik Souff', 'size': '500', 'qty': 1, 'rate': 70, 'gst_rate': 5}],
    })
    assert purchase_return.status_code == 200, purchase_return.text
    assert purchase_return.json()['due'] == 0
    assert client.get('/api/items', headers=headers).json()[0]['stock'] == 11
    assert client.get(f"/api/parties/{supplier['id']}/ledger", headers=headers).json()['party']['balance'] == 300

    activity = client.get('/api/activity', headers=headers).json()
    kinds = {row['kind'] for row in activity}
    assert {'sale_return', 'purchase_return'} <= kinds


def test_reports_exports_and_backup(tmp_path):
    client = build_client(tmp_path)
    headers = setup_and_headers(client)
    item = client.post('/api/items', headers=headers, json={
        'name': 'Tea', 'sku': 'TEA250', 'size': '250 gm', 'stock': 5, 'sale_price': 120,
    }).json()
    client.post('/api/sales', headers=headers, json={
        'invoice_date': '2026-07-23',
        'items': [{'item_id': item['id'], 'item_name': 'Tea', 'size': '250 gm', 'qty': 1, 'rate': 120, 'gst_rate': 0}],
    })
    client.post('/api/returns', headers=headers, json={
        'kind': 'sale_return', 'return_date': '2026-07-23',
        'items': [{'item_id': item['id'], 'item_name': 'Tea', 'size': '250 gm', 'qty': 1, 'rate': 20, 'gst_rate': 0}],
    })
    report = client.get('/api/reports/summary?date_from=2026-07-01&date_to=2026-07-31', headers=headers).json()
    assert report['sales']['amount'] == 120
    assert report['sale_returns']['amount'] == 20
    assert report['net_sales'] == 100

    items_csv = client.get('/api/export/items.csv', headers=headers)
    assert items_csv.status_code == 200
    assert 'size' in items_csv.text.splitlines()[0]
    sales_csv = client.get('/api/export/sales.csv', headers=headers)
    assert sales_csv.status_code == 200
    assert 'TEA250' not in sales_csv.text  # export is invoice-line data, not SKU data
    backup = client.get('/api/backup/database', headers=headers)
    assert backup.status_code == 200
    assert backup.content.startswith(b'SQLite format 3')


def test_vyapar_import_keeps_same_name_different_sizes_as_variants(tmp_path):
    client = build_client(tmp_path)
    headers = setup_and_headers(client)
    csv_data = (
        "item_name,item_code,unit,sale_price,stock\n"
        "Barik Souff 100,,packet,50,12\n"
        "Barik Souff 500,,packet,200,8\n"
    )
    response = client.post(
        "/api/import/vyapar",
        headers=headers,
        data={"entity_type": "items", "dry_run": "false"},
        files={"file": ("items.csv", csv_data.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["rows_imported"] == 2
    items = client.get("/api/items", headers=headers).json()
    variants = sorted((row["name"], row["size"]) for row in items if row["name"] == "Barik Souff")
    assert variants == [("Barik Souff", "100"), ("Barik Souff", "500")]
