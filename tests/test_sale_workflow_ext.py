from backend.sale_workflow_ext import _merge_all_summary_items


def test_line_level_transaction_numbers_are_grouped_by_bill_summary():
    items = []
    for index, (name, amount) in enumerate(
        [("Item A", 100), ("Item B", 200), ("Item C", 300), ("Item D", 400)],
        start=1,
    ):
        items.append(
            {
                "invoice_no": f"LINE-TXN-{index}",
                "invoice_date": "2026-07-24",
                "name": "Cash Customer",
                "item_name": name,
                "qty": 1,
                "rate": amount,
                "gst_rate": 0,
                "line_total": amount,
                "source_index": index,
            }
        )

    summaries = [
        {
            "invoice_no": "16687",
            "invoice_date": "2026-07-24",
            "name": "Cash Customer",
            "total": 300,
            "paid": 0,
            "payment_mode": "credit",
            "source_index": 101,
        },
        {
            "invoice_no": "16688",
            "invoice_date": "2026-07-24",
            "name": "Cash Customer",
            "total": 700,
            "paid": 0,
            "payment_mode": "credit",
            "source_index": 102,
        },
    ]

    result = _merge_all_summary_items(items, summaries, "sales")
    grouped = {}
    for row in result:
        grouped.setdefault(row["invoice_no"], []).append(row["item_name"])

    assert grouped == {
        "16687": ["Item A", "Item B"],
        "16688": ["Item C", "Item D"],
    }
