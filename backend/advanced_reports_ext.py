from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import Depends, HTTPException

from backend.app import app, current_user, db, normalize_date, today_iso


VERSION = "174"


REPORT_TITLES = {
    "sale_report": "Sale Report",
    "purchase_report": "Purchase Report",
    "day_book": "Day Book",
    "all_transactions": "All Transactions",
    "bill_wise_profit": "Bill Wise Profit & Loss",
    "profit_loss": "Profit & Loss",
    "sale_aging": "Sale Aging Report",
    "purchase_aging": "Purchase Aging Report",
    "cash_flow": "Cash Flow",
    "trial_balance": "Trial Balance",
    "balance_sheet": "Balance Sheet",
    "party_statement": "Party Statement",
    "all_party_report": "All Party Report",
    "party_profit": "Party Wise Profit & Loss",
    "party_item": "Party Wise Item Report",
    "party_sales": "Sale / Purchase by Party",
    "gst_sales": "GSTR-1",
    "gst_purchase": "GSTR-2",
    "gstr2b": "GSTR-2B",
    "gst_transactions": "GST Transaction Report",
    "gstr3b": "GSTR-3B Summary",
    "hsn_summary": "Sale Summary by HSN",
    "tax_summary": "GST Rate Summary",
    "stock_summary": "Stock Summary Report",
    "item_party": "Item Report by Party",
    "item_profit": "Item Wise Profit & Loss",
    "low_stock": "Low Stock Summary Report",
    "item_detail": "Item Detail Report",
    "stock_detail": "Stock Detail Report",
    "category_trades": "Sale / Purchase by Item Category",
    "category_stock": "Stock Summary by Item Category",
    "item_movement": "Item Movement Report",
    "item_discount": "Item Wise Discount",
    "item_serial": "Item Serial / Barcode Report",
    "manufacturing": "Manufacturing Report",
    "consumption": "Consumption Report",
    "stock_transfer": "Stock Transfer Report",
    "bank_statement": "Bank & Cash Statement",
    "receivable_payable": "Receivable / Payable Report",
    "gst_report": "GST Report",
    "gst_rate_report": "GST Rate Report",
    "tcs_receivable": "TCS Receivable",
    "tds_payable": "TDS Payable",
    "tds_receivable": "TDS Receivable",
    "expense_transactions": "Expense Transaction Report",
    "expense_category": "Expense Category Report",
    "order_transactions": "Sale / Purchase Order Report",
    "challan_report": "Sale / Purchase Challan Report",
    "loan_statement": "Loan Statement",
}


ALIASES = {
    "all_party_report": "party_statement",
    "gstr2b": "gst_purchase",
    "gst_report": "gst_transactions",
    "gst_rate_report": "tax_summary",
}


def _period(date_from: str, date_to: str) -> tuple[str, str]:
    start = normalize_date(date_from) if date_from else date.today().replace(day=1).isoformat()
    end = normalize_date(date_to) if date_to else today_iso()
    if start > end:
        raise HTTPException(status_code=400, detail="From date cannot be after To date")
    return start, end


def _dicts(rows: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _sum(rows: list[dict[str, Any]], key: str) -> float:
    return round(sum(float(row.get(key) or 0) for row in rows), 2)


def _scalar(conn: Any, sql: str, args: tuple[Any, ...]) -> float:
    row = conn.execute(sql, args).fetchone()
    return round(float(row[0] or 0), 2) if row else 0.0


def _columns(*items: tuple[str, str, str]) -> list[dict[str, str]]:
    return [{"key": key, "label": label, "format": fmt} for key, label, fmt in items]


def _result(
    requested: str,
    start: str,
    end: str,
    columns: list[dict[str, str]],
    rows: list[dict[str, Any]],
    totals: list[dict[str, Any]] | None = None,
    note: str = "",
) -> dict[str, Any]:
    total_rows = len(rows)
    if total_rows > 5000:
        rows = rows[:5000]
        suffix = "Showing the first 5,000 rows to keep the mobile app responsive."
        note = f"{note} {suffix}".strip()
    return {
        "report": requested,
        "title": REPORT_TITLES[requested],
        "date_from": start,
        "date_to": end,
        "columns": columns,
        "rows": rows,
        "total_rows": total_rows,
        "totals": totals or [],
        "note": note,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "version": VERSION,
    }


def _transaction_report(conn: Any, bid: int, kind: str, start: str, end: str) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], str]:
    table = "sales" if kind == "sale" else "purchases"
    rows = _dicts(
        conn.execute(
            f"""
            SELECT invoice_date AS report_date,invoice_no,party_name,subtotal,discount,tax,total,paid,due,payment_mode
            FROM {table}
            WHERE business_id=? AND invoice_date BETWEEN ? AND ?
            ORDER BY invoice_date DESC,id DESC
            """,
            (bid, start, end),
        ).fetchall()
    )
    columns = _columns(
        ("report_date", "Date", "date"),
        ("invoice_no", "Bill No.", "text"),
        ("party_name", "Party", "text"),
        ("total", "Total", "money"),
        ("paid", "Paid", "money"),
        ("due", "Due", "money"),
        ("payment_mode", "Mode", "text"),
    )
    totals = [
        {"label": "Bills", "value": len(rows), "format": "number"},
        {"label": "Total", "value": _sum(rows, "total"), "format": "money"},
        {"label": "Due", "value": _sum(rows, "due"), "format": "money"},
    ]
    return columns, rows, totals, ""


def _day_book(conn: Any, bid: int, start: str, end: str) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], str]:
    rows = _dicts(
        conn.execute(
            """
            SELECT * FROM (
              SELECT invoice_date AS report_date,'Sale' AS transaction_type,invoice_no AS reference,party_name AS party,total AS amount,paid AS money_in,0 AS money_out
              FROM sales WHERE business_id=? AND invoice_date BETWEEN ? AND ?
              UNION ALL
              SELECT invoice_date,'Purchase',invoice_no,party_name,total,0,paid
              FROM purchases WHERE business_id=? AND invoice_date BETWEEN ? AND ?
              UNION ALL
              SELECT return_date,CASE WHEN kind='sale_return' THEN 'Sale Return' ELSE 'Purchase Return' END,return_no,party_name,total,
                     CASE WHEN kind='purchase_return' THEN paid ELSE 0 END,
                     CASE WHEN kind='sale_return' THEN paid ELSE 0 END
              FROM returns WHERE business_id=? AND return_date BETWEEN ? AND ?
              UNION ALL
              SELECT entry_date,replace(entry_type,'_',' '),title,party_name,amount,
                     CASE WHEN entry_type IN ('cash_in','cheque_received','loan_in','asset_sale') THEN amount ELSE 0 END,
                     CASE WHEN entry_type IN ('expense','cash_out','cheque_paid','loan_out','asset_purchase') THEN amount ELSE 0 END
              FROM business_entries WHERE business_id=? AND entry_date BETWEEN ? AND ?
              UNION ALL
              SELECT doc_date,replace(kind,'_',' '),doc_no,party_name,amount,0,0
              FROM documents WHERE business_id=? AND doc_date BETWEEN ? AND ?
            ) ORDER BY report_date DESC,reference DESC
            """,
            (bid, start, end, bid, start, end, bid, start, end, bid, start, end, bid, start, end),
        ).fetchall()
    )
    columns = _columns(
        ("report_date", "Date", "date"),
        ("transaction_type", "Type", "text"),
        ("reference", "Reference", "text"),
        ("party", "Party / Details", "text"),
        ("amount", "Amount", "money"),
        ("money_in", "Money In", "money"),
        ("money_out", "Money Out", "money"),
    )
    totals = [
        {"label": "Entries", "value": len(rows), "format": "number"},
        {"label": "Money In", "value": _sum(rows, "money_in"), "format": "money"},
        {"label": "Money Out", "value": _sum(rows, "money_out"), "format": "money"},
    ]
    return columns, rows, totals, "Includes bills, returns, account entries and orders/challans."


def _bill_profit(conn: Any, bid: int, start: str, end: str) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], str]:
    rows = _dicts(
        conn.execute(
            """
            SELECT s.invoice_date AS report_date,s.invoice_no,s.party_name,
                   ROUND(s.subtotal-s.discount,2) AS sale_value,
                   ROUND(SUM(si.qty*COALESCE(i.purchase_price,0)),2) AS cost_estimate,
                   ROUND((s.subtotal-s.discount)-SUM(si.qty*COALESCE(i.purchase_price,0)),2) AS profit_estimate
            FROM sales s
            JOIN sale_items si ON si.sale_id=s.id
            LEFT JOIN items i ON i.id=si.item_id
            WHERE s.business_id=? AND s.invoice_date BETWEEN ? AND ?
            GROUP BY s.id,s.invoice_date,s.invoice_no,s.party_name,s.subtotal,s.discount
            ORDER BY s.invoice_date DESC,s.id DESC
            """,
            (bid, start, end),
        ).fetchall()
    )
    columns = _columns(
        ("report_date", "Date", "date"),
        ("invoice_no", "Bill No.", "text"),
        ("party_name", "Party", "text"),
        ("sale_value", "Sale", "money"),
        ("cost_estimate", "Cost", "money"),
        ("profit_estimate", "Profit / Loss", "money"),
    )
    totals = [
        {"label": "Sale Value", "value": _sum(rows, "sale_value"), "format": "money"},
        {"label": "Estimated Cost", "value": _sum(rows, "cost_estimate"), "format": "money"},
        {"label": "Estimated Profit", "value": _sum(rows, "profit_estimate"), "format": "money"},
    ]
    return columns, rows, totals, "Profit uses each item's current purchase rate because historical cost is not stored separately."


def _profit_loss(conn: Any, bid: int, start: str, end: str) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], str]:
    sales = _scalar(conn, "SELECT COALESCE(SUM(subtotal-discount),0) FROM sales WHERE business_id=? AND invoice_date BETWEEN ? AND ?", (bid, start, end))
    sale_returns = _scalar(conn, "SELECT COALESCE(SUM(subtotal-discount),0) FROM returns WHERE business_id=? AND kind='sale_return' AND return_date BETWEEN ? AND ?", (bid, start, end))
    purchases = _scalar(conn, "SELECT COALESCE(SUM(subtotal-discount),0) FROM purchases WHERE business_id=? AND invoice_date BETWEEN ? AND ?", (bid, start, end))
    cost = _scalar(
        conn,
        """SELECT COALESCE(SUM(si.qty*COALESCE(i.purchase_price,0)),0) FROM sale_items si JOIN sales s ON s.id=si.sale_id LEFT JOIN items i ON i.id=si.item_id WHERE s.business_id=? AND s.invoice_date BETWEEN ? AND ?""",
        (bid, start, end),
    )
    expenses = _scalar(conn, "SELECT COALESCE(SUM(amount),0) FROM business_entries WHERE business_id=? AND entry_type='expense' AND entry_date BETWEEN ? AND ?", (bid, start, end))
    net_revenue = round(sales - sale_returns, 2)
    gross_profit = round(net_revenue - cost, 2)
    net_profit = round(gross_profit - expenses, 2)
    rows = [
        {"particular": "Gross Sales (before tax)", "amount": sales},
        {"particular": "Less: Sale Returns", "amount": -sale_returns},
        {"particular": "Net Revenue", "amount": net_revenue},
        {"particular": "Estimated Cost of Goods Sold", "amount": -cost},
        {"particular": "Gross Profit", "amount": gross_profit},
        {"particular": "Less: Expenses", "amount": -expenses},
        {"particular": "Net Profit / Loss", "amount": net_profit},
        {"particular": "Purchases recorded (reference)", "amount": purchases},
    ]
    columns = _columns(("particular", "Particular", "text"), ("amount", "Amount", "money"))
    totals = [{"label": "Net Profit / Loss", "value": net_profit, "format": "money"}]
    return columns, rows, totals, "Cost of goods sold is estimated from current item purchase rates."


def _aging(conn: Any, bid: int, kind: str, start: str, end: str) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], str]:
    table = "sales" if kind == "sale" else "purchases"
    rows = _dicts(
        conn.execute(
            f"""
            SELECT invoice_date AS report_date,invoice_no,party_name,total,due,
                   CAST(MAX(0,julianday(?)-julianday(invoice_date)) AS INTEGER) AS pending_days,
                   CASE
                     WHEN julianday(?)-julianday(invoice_date)<=30 THEN '0-30 days'
                     WHEN julianday(?)-julianday(invoice_date)<=60 THEN '31-60 days'
                     WHEN julianday(?)-julianday(invoice_date)<=90 THEN '61-90 days'
                     ELSE '90+ days' END AS age_bucket
            FROM {table}
            WHERE business_id=? AND due>0 AND invoice_date BETWEEN ? AND ?
            ORDER BY pending_days DESC,due DESC
            """,
            (end, end, end, end, bid, start, end),
        ).fetchall()
    )
    columns = _columns(
        ("report_date", "Bill Date", "date"),
        ("invoice_no", "Bill No.", "text"),
        ("party_name", "Party", "text"),
        ("due", "Pending", "money"),
        ("pending_days", "Days", "number"),
        ("age_bucket", "Age", "text"),
    )
    totals = [
        {"label": "Pending Bills", "value": len(rows), "format": "number"},
        {"label": "Outstanding", "value": _sum(rows, "due"), "format": "money"},
    ]
    return columns, rows, totals, "Only credit bills with a pending balance are shown."


def _cash_flow(conn: Any, bid: int, start: str, end: str) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], str]:
    rows = _dicts(
        conn.execute(
            """
            SELECT * FROM (
              SELECT invoice_date AS report_date,'Sale receipt' AS source,invoice_no AS reference,paid AS money_in,0 AS money_out FROM sales WHERE business_id=? AND paid>0 AND invoice_date BETWEEN ? AND ?
              UNION ALL SELECT invoice_date,'Purchase payment',invoice_no,0,paid FROM purchases WHERE business_id=? AND paid>0 AND invoice_date BETWEEN ? AND ?
              UNION ALL SELECT entry_date,replace(entry_type,'_',' '),title,
                CASE WHEN entry_type IN ('cash_in','cheque_received','loan_in','asset_sale') THEN amount ELSE 0 END,
                CASE WHEN entry_type IN ('expense','cash_out','cheque_paid','loan_out','asset_purchase') THEN amount ELSE 0 END
                FROM business_entries WHERE business_id=? AND entry_date BETWEEN ? AND ?
            ) ORDER BY report_date,reference
            """,
            (bid, start, end, bid, start, end, bid, start, end),
        ).fetchall()
    )
    running = 0.0
    for row in rows:
        running = round(running + float(row.get("money_in") or 0) - float(row.get("money_out") or 0), 2)
        row["running_balance"] = running
    columns = _columns(
        ("report_date", "Date", "date"),
        ("source", "Source", "text"),
        ("reference", "Reference", "text"),
        ("money_in", "Cash In", "money"),
        ("money_out", "Cash Out", "money"),
        ("running_balance", "Running", "money"),
    )
    totals = [
        {"label": "Cash In", "value": _sum(rows, "money_in"), "format": "money"},
        {"label": "Cash Out", "value": _sum(rows, "money_out"), "format": "money"},
        {"label": "Net Flow", "value": running, "format": "money"},
    ]
    return columns, rows, totals, "Running balance starts from zero for the selected period."


def _balance_sheet(conn: Any, bid: int, start: str, end: str) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], str]:
    stock = _scalar(conn, "SELECT COALESCE(SUM(stock*purchase_price),0) FROM items WHERE business_id=?", (bid,))
    receivable = _scalar(conn, "SELECT COALESCE(SUM(due),0) FROM sales WHERE business_id=? AND invoice_date<=?", (bid, end))
    payable = _scalar(conn, "SELECT COALESCE(SUM(due),0) FROM purchases WHERE business_id=? AND invoice_date<=?", (bid, end))
    accounts = _scalar(conn, "SELECT COALESCE(SUM(balance),0) FROM accounts WHERE business_id=?", (bid,))
    loan_in = _scalar(conn, "SELECT COALESCE(SUM(amount),0) FROM business_entries WHERE business_id=? AND entry_type='loan_in' AND entry_date<=?", (bid, end))
    loan_out = _scalar(conn, "SELECT COALESCE(SUM(amount),0) FROM business_entries WHERE business_id=? AND entry_type='loan_out' AND entry_date<=?", (bid, end))
    assets = round(stock + receivable + accounts + loan_out, 2)
    liabilities = round(payable + loan_in, 2)
    rows = [
        {"section": "Asset", "particular": "Stock at purchase value", "amount": stock},
        {"section": "Asset", "particular": "Trade receivables", "amount": receivable},
        {"section": "Asset", "particular": "Cash and bank accounts", "amount": accounts},
        {"section": "Asset", "particular": "Loans given", "amount": loan_out},
        {"section": "Liability", "particular": "Trade payables", "amount": payable},
        {"section": "Liability", "particular": "Loans received", "amount": loan_in},
        {"section": "Net Worth", "particular": "Estimated net business value", "amount": round(assets - liabilities, 2)},
    ]
    columns = _columns(("section", "Section", "text"), ("particular", "Particular", "text"), ("amount", "Amount", "money"))
    totals = [
        {"label": "Assets", "value": assets, "format": "money"},
        {"label": "Liabilities", "value": liabilities, "format": "money"},
        {"label": "Net Worth", "value": round(assets - liabilities, 2), "format": "money"},
    ]
    return columns, rows, totals, "Snapshot is calculated up to the selected To date."


def _trial_balance(conn: Any, bid: int, start: str, end: str) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], str]:
    rows = _dicts(
        conn.execute(
            """
            SELECT name AS account,CASE WHEN type='supplier' THEN 'Payable' ELSE 'Receivable' END AS account_type,
                   CASE WHEN type='supplier' THEN 0 ELSE balance END AS debit,
                   CASE WHEN type='supplier' THEN balance ELSE 0 END AS credit
            FROM parties WHERE business_id=?
            UNION ALL
            SELECT name,upper(account_type),CASE WHEN balance>=0 THEN balance ELSE 0 END,CASE WHEN balance<0 THEN ABS(balance) ELSE 0 END
            FROM accounts WHERE business_id=?
            ORDER BY account_type,account
            """,
            (bid, bid),
        ).fetchall()
    )
    columns = _columns(("account", "Account", "text"), ("account_type", "Type", "text"), ("debit", "Debit", "money"), ("credit", "Credit", "money"))
    totals = [
        {"label": "Total Debit", "value": _sum(rows, "debit"), "format": "money"},
        {"label": "Total Credit", "value": _sum(rows, "credit"), "format": "money"},
    ]
    return columns, rows, totals, "Party and cash/bank closing balances."


def _party_report(conn: Any, bid: int, mode: str, start: str, end: str) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], str]:
    if mode == "statement":
        rows = _dicts(conn.execute("SELECT name,type,phone,opening_balance,balance FROM parties WHERE business_id=? ORDER BY ABS(balance) DESC,name", (bid,)).fetchall())
        columns = _columns(("name", "Party", "text"), ("type", "Type", "text"), ("phone", "Mobile", "text"), ("opening_balance", "Opening", "money"), ("balance", "Current Balance", "money"))
        totals = [{"label": "Parties", "value": len(rows), "format": "number"}, {"label": "Net Balance", "value": _sum(rows, "balance"), "format": "money"}]
        return columns, rows, totals, "Tap/search a party from the Parties section for its complete bill ledger."
    if mode == "profit":
        rows = _dicts(
            conn.execute(
                """
                SELECT COALESCE(NULLIF(s.party_name,''),'Cash Customer') AS party,
                       ROUND(SUM(s.subtotal-s.discount),2) AS sale_value,
                       ROUND(SUM(COALESCE(cost.cost_value,0)),2) AS cost_estimate,
                       ROUND(SUM(s.subtotal-s.discount-COALESCE(cost.cost_value,0)),2) AS profit_estimate
                FROM sales s
                LEFT JOIN (SELECT si.sale_id,SUM(si.qty*COALESCE(i.purchase_price,0)) AS cost_value FROM sale_items si LEFT JOIN items i ON i.id=si.item_id GROUP BY si.sale_id) cost ON cost.sale_id=s.id
                WHERE s.business_id=? AND s.invoice_date BETWEEN ? AND ?
                GROUP BY COALESCE(NULLIF(s.party_name,''),'Cash Customer') ORDER BY profit_estimate DESC
                """,
                (bid, start, end),
            ).fetchall()
        )
        columns = _columns(("party", "Party", "text"), ("sale_value", "Sales", "money"), ("cost_estimate", "Cost", "money"), ("profit_estimate", "Profit / Loss", "money"))
        totals = [{"label": "Sales", "value": _sum(rows, "sale_value"), "format": "money"}, {"label": "Estimated Profit", "value": _sum(rows, "profit_estimate"), "format": "money"}]
        return columns, rows, totals, "Profit uses current item purchase rates."
    if mode == "item":
        rows = _dicts(
            conn.execute(
                """
                SELECT party,item_name,size,ROUND(SUM(sale_qty),3) AS sale_qty,ROUND(SUM(purchase_qty),3) AS purchase_qty,ROUND(SUM(amount),2) AS amount FROM (
                  SELECT COALESCE(NULLIF(s.party_name,''),'Cash Customer') AS party,si.item_name,si.size,si.qty AS sale_qty,0 AS purchase_qty,si.line_total AS amount
                  FROM sale_items si JOIN sales s ON s.id=si.sale_id WHERE s.business_id=? AND s.invoice_date BETWEEN ? AND ?
                  UNION ALL
                  SELECT COALESCE(NULLIF(p.party_name,''),'Cash Supplier'),pi.item_name,pi.size,0,pi.qty,pi.line_total
                  FROM purchase_items pi JOIN purchases p ON p.id=pi.purchase_id WHERE p.business_id=? AND p.invoice_date BETWEEN ? AND ?
                ) GROUP BY party,item_name,size ORDER BY amount DESC
                """,
                (bid, start, end, bid, start, end),
            ).fetchall()
        )
        columns = _columns(("party", "Party", "text"), ("item_name", "Item", "text"), ("size", "Size", "text"), ("sale_qty", "Sale Qty", "number"), ("purchase_qty", "Purchase Qty", "number"), ("amount", "Value", "money"))
        totals = [{"label": "Rows", "value": len(rows), "format": "number"}, {"label": "Value", "value": _sum(rows, "amount"), "format": "money"}]
        return columns, rows, totals, ""
    rows = _dicts(
        conn.execute(
            """
            SELECT party,ROUND(SUM(sales),2) AS sales,ROUND(SUM(purchases),2) AS purchases,ROUND(SUM(receivable),2) AS receivable,ROUND(SUM(payable),2) AS payable FROM (
              SELECT COALESCE(NULLIF(party_name,''),'Cash Customer') AS party,total AS sales,0 AS purchases,due AS receivable,0 AS payable FROM sales WHERE business_id=? AND invoice_date BETWEEN ? AND ?
              UNION ALL SELECT COALESCE(NULLIF(party_name,''),'Cash Supplier'),0,total,0,due FROM purchases WHERE business_id=? AND invoice_date BETWEEN ? AND ?
            ) GROUP BY party ORDER BY sales+purchases DESC
            """,
            (bid, start, end, bid, start, end),
        ).fetchall()
    )
    columns = _columns(("party", "Party", "text"), ("sales", "Sales", "money"), ("purchases", "Purchases", "money"), ("receivable", "Receivable", "money"), ("payable", "Payable", "money"))
    totals = [{"label": "Sales", "value": _sum(rows, "sales"), "format": "money"}, {"label": "Purchases", "value": _sum(rows, "purchases"), "format": "money"}]
    return columns, rows, totals, ""


def _gst_report(conn: Any, bid: int, mode: str, start: str, end: str) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], str]:
    if mode in {"sales", "purchase"}:
        table = "sales" if mode == "sales" else "purchases"
        rows = _dicts(
            conn.execute(
                f"""
                SELECT t.invoice_date AS report_date,t.invoice_no,t.party_name,COALESCE(pa.gstin,'') AS gstin,
                       ROUND(t.subtotal-t.discount,2) AS taxable_value,t.tax,t.total
                FROM {table} t LEFT JOIN parties pa ON pa.id=t.party_id
                WHERE t.business_id=? AND t.invoice_date BETWEEN ? AND ?
                ORDER BY t.invoice_date,t.id
                """,
                (bid, start, end),
            ).fetchall()
        )
        columns = _columns(("report_date", "Date", "date"), ("invoice_no", "Invoice", "text"), ("party_name", "Party", "text"), ("gstin", "GSTIN", "text"), ("taxable_value", "Taxable Value", "money"), ("tax", "GST", "money"), ("total", "Invoice Value", "money"))
        totals = [{"label": "Taxable Value", "value": _sum(rows, "taxable_value"), "format": "money"}, {"label": "GST", "value": _sum(rows, "tax"), "format": "money"}]
        return columns, rows, totals, "GSTR working report; verify GSTIN and tax treatment with your accountant before filing."
    if mode == "transactions":
        rows = _dicts(
            conn.execute(
                """
                SELECT * FROM (
                  SELECT invoice_date AS report_date,'Sale' AS transaction_type,invoice_no AS reference,party_name,subtotal-discount AS taxable_value,tax,total FROM sales WHERE business_id=? AND invoice_date BETWEEN ? AND ?
                  UNION ALL SELECT invoice_date,'Purchase',invoice_no,party_name,subtotal-discount,tax,total FROM purchases WHERE business_id=? AND invoice_date BETWEEN ? AND ?
                  UNION ALL SELECT return_date,CASE WHEN kind='sale_return' THEN 'Sale Return' ELSE 'Purchase Return' END,return_no,party_name,-(subtotal-discount),-tax,-total FROM returns WHERE business_id=? AND return_date BETWEEN ? AND ?
                ) ORDER BY report_date,reference
                """,
                (bid, start, end, bid, start, end, bid, start, end),
            ).fetchall()
        )
        columns = _columns(("report_date", "Date", "date"), ("transaction_type", "Type", "text"), ("reference", "Reference", "text"), ("party_name", "Party", "text"), ("taxable_value", "Taxable", "money"), ("tax", "GST", "money"), ("total", "Total", "money"))
        totals = [{"label": "Taxable Value", "value": _sum(rows, "taxable_value"), "format": "money"}, {"label": "Net GST", "value": _sum(rows, "tax"), "format": "money"}]
        return columns, rows, totals, ""
    if mode == "gstr3b":
        outward = _scalar(conn, "SELECT COALESCE(SUM(subtotal-discount),0) FROM sales WHERE business_id=? AND invoice_date BETWEEN ? AND ?", (bid, start, end))
        outward_tax = _scalar(conn, "SELECT COALESCE(SUM(tax),0) FROM sales WHERE business_id=? AND invoice_date BETWEEN ? AND ?", (bid, start, end))
        inward = _scalar(conn, "SELECT COALESCE(SUM(subtotal-discount),0) FROM purchases WHERE business_id=? AND invoice_date BETWEEN ? AND ?", (bid, start, end))
        inward_tax = _scalar(conn, "SELECT COALESCE(SUM(tax),0) FROM purchases WHERE business_id=? AND invoice_date BETWEEN ? AND ?", (bid, start, end))
        rows = [
            {"section": "3.1", "particular": "Outward taxable supplies", "taxable_value": outward, "tax_amount": outward_tax},
            {"section": "4", "particular": "Eligible inward supplies / ITC working", "taxable_value": inward, "tax_amount": inward_tax},
            {"section": "Net", "particular": "Estimated GST payable", "taxable_value": 0, "tax_amount": round(outward_tax-inward_tax, 2)},
        ]
        columns = _columns(("section", "Section", "text"), ("particular", "Particular", "text"), ("taxable_value", "Taxable Value", "money"), ("tax_amount", "Tax", "money"))
        totals = [{"label": "Output GST", "value": outward_tax, "format": "money"}, {"label": "Input GST", "value": inward_tax, "format": "money"}, {"label": "Estimated Payable", "value": round(outward_tax-inward_tax, 2), "format": "money"}]
        return columns, rows, totals, "Working summary only; confirm ITC eligibility and return values with your accountant."
    if mode == "hsn":
        rows = _dicts(
            conn.execute(
                """
                SELECT COALESCE(NULLIF(i.hsn,''),'Unspecified') AS hsn,si.gst_rate,ROUND(SUM(si.qty),3) AS qty,ROUND(SUM(si.line_subtotal),2) AS taxable_value,ROUND(SUM(si.line_tax),2) AS tax,ROUND(SUM(si.line_total),2) AS total
                FROM sale_items si JOIN sales s ON s.id=si.sale_id LEFT JOIN items i ON i.id=si.item_id
                WHERE s.business_id=? AND s.invoice_date BETWEEN ? AND ?
                GROUP BY COALESCE(NULLIF(i.hsn,''),'Unspecified'),si.gst_rate ORDER BY taxable_value DESC
                """,
                (bid, start, end),
            ).fetchall()
        )
        columns = _columns(("hsn", "HSN", "text"), ("gst_rate", "GST Rate", "percent"), ("qty", "Qty", "number"), ("taxable_value", "Taxable", "money"), ("tax", "GST", "money"), ("total", "Total", "money"))
        totals = [{"label": "Taxable Value", "value": _sum(rows, "taxable_value"), "format": "money"}, {"label": "GST", "value": _sum(rows, "tax"), "format": "money"}]
        return columns, rows, totals, ""
    rows = _dicts(
        conn.execute(
            """
            SELECT gst_rate,ROUND(SUM(sale_taxable),2) AS sale_taxable,ROUND(SUM(sale_tax),2) AS sale_tax,ROUND(SUM(purchase_taxable),2) AS purchase_taxable,ROUND(SUM(purchase_tax),2) AS purchase_tax FROM (
              SELECT si.gst_rate,si.line_subtotal AS sale_taxable,si.line_tax AS sale_tax,0 AS purchase_taxable,0 AS purchase_tax FROM sale_items si JOIN sales s ON s.id=si.sale_id WHERE s.business_id=? AND s.invoice_date BETWEEN ? AND ?
              UNION ALL SELECT pi.gst_rate,0,0,pi.line_subtotal,pi.line_tax FROM purchase_items pi JOIN purchases p ON p.id=pi.purchase_id WHERE p.business_id=? AND p.invoice_date BETWEEN ? AND ?
            ) GROUP BY gst_rate ORDER BY gst_rate
            """,
            (bid, start, end, bid, start, end),
        ).fetchall()
    )
    columns = _columns(("gst_rate", "GST Rate", "percent"), ("sale_taxable", "Sale Taxable", "money"), ("sale_tax", "Output GST", "money"), ("purchase_taxable", "Purchase Taxable", "money"), ("purchase_tax", "Input GST", "money"))
    totals = [{"label": "Output GST", "value": _sum(rows, "sale_tax"), "format": "money"}, {"label": "Input GST", "value": _sum(rows, "purchase_tax"), "format": "money"}]
    return columns, rows, totals, ""


def _stock_report(conn: Any, bid: int, mode: str, start: str, end: str) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], str]:
    if mode in {"summary", "low", "detail"}:
        extra = " AND stock<=min_stock" if mode == "low" else ""
        rows = _dicts(
            conn.execute(
                f"""SELECT name,item_code,size,unit,category,stock,min_stock,purchase_price,sale_price,ROUND(stock*purchase_price,2) AS stock_value FROM (SELECT i.*,COALESCE(NULLIF(i.sku,''),NULLIF(i.barcode,''),'—') AS item_code FROM items i WHERE business_id=?) WHERE 1=1 {extra} ORDER BY name,size""",
                (bid,),
            ).fetchall()
        )
        columns = _columns(("name", "Item", "text"), ("size", "Size", "text"), ("item_code", "Code", "text"), ("stock", "Stock", "number"), ("unit", "Unit", "text"), ("purchase_price", "Purchase Rate", "money"), ("sale_price", "Sale Rate", "money"), ("stock_value", "Stock Value", "money"))
        totals = [{"label": "Items", "value": len(rows), "format": "number"}, {"label": "Stock Value", "value": _sum(rows, "stock_value"), "format": "money"}]
        note = "Only items at or below their minimum stock level." if mode == "low" else "Current stock snapshot; date range does not change closing stock."
        return columns, rows, totals, note
    if mode in {"movement", "manufacturing", "consumption", "transfer"}:
        filters = ""
        args: list[Any] = [bid, start, end]
        if mode == "manufacturing":
            filters = " AND lower(sm.kind) LIKE '%manufact%'"
        elif mode == "consumption":
            filters = " AND (lower(sm.kind) LIKE '%consum%' OR lower(sm.kind) LIKE '%production_out%')"
        elif mode == "transfer":
            filters = " AND lower(sm.kind) LIKE '%transfer%'"
        rows = _dicts(
            conn.execute(
                f"""
                SELECT sm.movement_date AS report_date,i.name AS item_name,i.size,sm.kind,sm.qty,sm.reference_type,sm.reference_id,sm.note
                FROM stock_movements sm JOIN items i ON i.id=sm.item_id
                WHERE sm.business_id=? AND sm.movement_date BETWEEN ? AND ? {filters}
                ORDER BY sm.movement_date DESC,sm.id DESC
                """,
                tuple(args),
            ).fetchall()
        )
        columns = _columns(("report_date", "Date", "date"), ("item_name", "Item", "text"), ("size", "Size", "text"), ("kind", "Movement", "text"), ("qty", "Qty Change", "number"), ("reference_type", "Reference", "text"), ("note", "Note", "text"))
        totals = [{"label": "Movements", "value": len(rows), "format": "number"}, {"label": "Net Qty", "value": _sum(rows, "qty"), "format": "number"}]
        return columns, rows, totals, "No rows appear until this movement type is recorded in stock history."
    if mode == "category_stock":
        rows = _dicts(conn.execute("SELECT COALESCE(NULLIF(category,''),'Uncategorised') AS category,COUNT(*) AS items,ROUND(SUM(stock),3) AS stock_qty,ROUND(SUM(stock*purchase_price),2) AS stock_value FROM items WHERE business_id=? GROUP BY COALESCE(NULLIF(category,''),'Uncategorised') ORDER BY stock_value DESC", (bid,)).fetchall())
        columns = _columns(("category", "Category", "text"), ("items", "Items", "number"), ("stock_qty", "Stock Qty", "number"), ("stock_value", "Stock Value", "money"))
        totals = [{"label": "Categories", "value": len(rows), "format": "number"}, {"label": "Stock Value", "value": _sum(rows, "stock_value"), "format": "money"}]
        return columns, rows, totals, ""
    if mode == "category_trades":
        rows = _dicts(
            conn.execute(
                """
                SELECT category,ROUND(SUM(sales),2) AS sales,ROUND(SUM(purchases),2) AS purchases FROM (
                  SELECT COALESCE(NULLIF(i.category,''),'Uncategorised') AS category,si.line_total AS sales,0 AS purchases FROM sale_items si JOIN sales s ON s.id=si.sale_id LEFT JOIN items i ON i.id=si.item_id WHERE s.business_id=? AND s.invoice_date BETWEEN ? AND ?
                  UNION ALL SELECT COALESCE(NULLIF(i.category,''),'Uncategorised'),0,pi.line_total FROM purchase_items pi JOIN purchases p ON p.id=pi.purchase_id LEFT JOIN items i ON i.id=pi.item_id WHERE p.business_id=? AND p.invoice_date BETWEEN ? AND ?
                ) GROUP BY category ORDER BY sales+purchases DESC
                """,
                (bid, start, end, bid, start, end),
            ).fetchall()
        )
        columns = _columns(("category", "Category", "text"), ("sales", "Sales", "money"), ("purchases", "Purchases", "money"))
        totals = [{"label": "Sales", "value": _sum(rows, "sales"), "format": "money"}, {"label": "Purchases", "value": _sum(rows, "purchases"), "format": "money"}]
        return columns, rows, totals, ""
    if mode == "item_party":
        columns, rows, totals, note = _party_report(conn, bid, "item", start, end)
        return columns, rows, totals, note
    if mode == "profit":
        rows = _dicts(
            conn.execute(
                """
                SELECT si.item_name,si.size,ROUND(SUM(si.qty),3) AS qty,ROUND(SUM(si.line_subtotal),2) AS sale_value,
                       ROUND(SUM(si.qty*COALESCE(i.purchase_price,0)),2) AS cost_estimate,
                       ROUND(SUM(si.line_subtotal-si.qty*COALESCE(i.purchase_price,0)),2) AS profit_estimate
                FROM sale_items si JOIN sales s ON s.id=si.sale_id LEFT JOIN items i ON i.id=si.item_id
                WHERE s.business_id=? AND s.invoice_date BETWEEN ? AND ?
                GROUP BY si.item_name,si.size ORDER BY profit_estimate DESC
                """,
                (bid, start, end),
            ).fetchall()
        )
        columns = _columns(("item_name", "Item", "text"), ("size", "Size", "text"), ("qty", "Qty", "number"), ("sale_value", "Sales", "money"), ("cost_estimate", "Cost", "money"), ("profit_estimate", "Profit / Loss", "money"))
        totals = [{"label": "Sales", "value": _sum(rows, "sale_value"), "format": "money"}, {"label": "Estimated Profit", "value": _sum(rows, "profit_estimate"), "format": "money"}]
        return columns, rows, totals, "Profit uses current purchase rates."
    if mode == "discount":
        rows = _dicts(
            conn.execute(
                """
                SELECT si.item_name,si.size,ROUND(SUM(si.line_subtotal),2) AS gross_value,
                       ROUND(SUM(CASE WHEN s.subtotal>0 THEN s.discount*(si.line_subtotal/s.subtotal) ELSE 0 END),2) AS allocated_discount,
                       ROUND(SUM(si.line_subtotal-CASE WHEN s.subtotal>0 THEN s.discount*(si.line_subtotal/s.subtotal) ELSE 0 END),2) AS net_value
                FROM sale_items si JOIN sales s ON s.id=si.sale_id
                WHERE s.business_id=? AND s.invoice_date BETWEEN ? AND ?
                GROUP BY si.item_name,si.size ORDER BY allocated_discount DESC
                """,
                (bid, start, end),
            ).fetchall()
        )
        columns = _columns(("item_name", "Item", "text"), ("size", "Size", "text"), ("gross_value", "Gross", "money"), ("allocated_discount", "Discount", "money"), ("net_value", "Net", "money"))
        totals = [{"label": "Allocated Discount", "value": _sum(rows, "allocated_discount"), "format": "money"}, {"label": "Net Value", "value": _sum(rows, "net_value"), "format": "money"}]
        return columns, rows, totals, "Bill-level discounts are allocated proportionally across item lines."
    rows = _dicts(conn.execute("SELECT name,size,sku,barcode,category,unit,stock,sale_price FROM items WHERE business_id=? ORDER BY name,size", (bid,)).fetchall())
    columns = _columns(("name", "Item", "text"), ("size", "Size", "text"), ("sku", "SKU / Serial", "text"), ("barcode", "Barcode", "text"), ("category", "Category", "text"), ("stock", "Stock", "number"), ("sale_price", "Sale Rate", "money"))
    totals = [{"label": "Items", "value": len(rows), "format": "number"}]
    return columns, rows, totals, ""


def _bank_report(conn: Any, bid: int, start: str, end: str) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], str]:
    rows = _dicts(
        conn.execute(
            """
            SELECT e.entry_date AS report_date,COALESCE(a.name,'Unassigned') AS account,replace(e.entry_type,'_',' ') AS entry_type,e.title,e.mode,e.amount,e.status
            FROM business_entries e LEFT JOIN accounts a ON a.id=e.account_id
            WHERE e.business_id=? AND e.entry_date BETWEEN ? AND ? ORDER BY e.entry_date DESC,e.id DESC
            """,
            (bid, start, end),
        ).fetchall()
    )
    columns = _columns(("report_date", "Date", "date"), ("account", "Account", "text"), ("entry_type", "Type", "text"), ("title", "Details", "text"), ("mode", "Mode", "text"), ("amount", "Amount", "money"), ("status", "Status", "text"))
    balance = _scalar(conn, "SELECT COALESCE(SUM(balance),0) FROM accounts WHERE business_id=?", (bid,))
    totals = [{"label": "Entries", "value": len(rows), "format": "number"}, {"label": "Current Account Balance", "value": balance, "format": "money"}]
    return columns, rows, totals, ""


def _receivable_payable(conn: Any, bid: int, start: str, end: str) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], str]:
    rows = _dicts(conn.execute("SELECT name AS party,type,phone,balance,CASE WHEN type='supplier' THEN 'Payable' ELSE 'Receivable' END AS balance_type FROM parties WHERE business_id=? AND ABS(balance)>0.004 ORDER BY ABS(balance) DESC", (bid,)).fetchall())
    columns = _columns(("party", "Party", "text"), ("type", "Party Type", "text"), ("phone", "Mobile", "text"), ("balance_type", "Balance Type", "text"), ("balance", "Balance", "money"))
    receivable = round(sum(float(r.get("balance") or 0) for r in rows if r.get("balance_type") == "Receivable"), 2)
    payable = round(sum(float(r.get("balance") or 0) for r in rows if r.get("balance_type") == "Payable"), 2)
    totals = [{"label": "Receivable", "value": receivable, "format": "money"}, {"label": "Payable", "value": payable, "format": "money"}]
    return columns, rows, totals, "Current party balances."


def _tax_deduction(conn: Any, bid: int, kind: str, start: str, end: str) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], str]:
    needle = "%" + kind.lower() + "%"
    rows = _dicts(conn.execute("SELECT entry_date AS report_date,replace(entry_type,'_',' ') AS entry_type,title,party_name,amount,status,note FROM business_entries WHERE business_id=? AND entry_date BETWEEN ? AND ? AND (lower(title) LIKE ? OR lower(note) LIKE ? OR lower(entry_type) LIKE ?) ORDER BY entry_date DESC,id DESC", (bid, start, end, needle, needle, needle)).fetchall())
    columns = _columns(("report_date", "Date", "date"), ("entry_type", "Type", "text"), ("title", "Details", "text"), ("party_name", "Party", "text"), ("amount", "Amount", "money"), ("status", "Status", "text"))
    totals = [{"label": "Entries", "value": len(rows), "format": "number"}, {"label": "Amount", "value": _sum(rows, "amount"), "format": "money"}]
    return columns, rows, totals, f"Shows account entries whose type, title or note contains {kind.upper()}."


def _expense_report(conn: Any, bid: int, grouped: bool, start: str, end: str) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], str]:
    if grouped:
        rows = _dicts(conn.execute("SELECT COALESCE(NULLIF(title,''),'Other Expense') AS category,COUNT(*) AS entries,ROUND(SUM(amount),2) AS amount FROM business_entries WHERE business_id=? AND entry_type='expense' AND entry_date BETWEEN ? AND ? GROUP BY COALESCE(NULLIF(title,''),'Other Expense') ORDER BY amount DESC", (bid, start, end)).fetchall())
        columns = _columns(("category", "Expense Category", "text"), ("entries", "Entries", "number"), ("amount", "Amount", "money"))
    else:
        rows = _dicts(conn.execute("SELECT entry_date AS report_date,title,party_name,mode,amount,status,note FROM business_entries WHERE business_id=? AND entry_type='expense' AND entry_date BETWEEN ? AND ? ORDER BY entry_date DESC,id DESC", (bid, start, end)).fetchall())
        columns = _columns(("report_date", "Date", "date"), ("title", "Expense", "text"), ("party_name", "Party", "text"), ("mode", "Mode", "text"), ("amount", "Amount", "money"), ("note", "Note", "text"))
    totals = [{"label": "Entries", "value": len(rows), "format": "number"}, {"label": "Total Expense", "value": _sum(rows, "amount"), "format": "money"}]
    return columns, rows, totals, ""


def _document_report(conn: Any, bid: int, challan: bool, start: str, end: str) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], str]:
    kinds = ("delivery_challan",) if challan else ("sale_order", "purchase_order")
    placeholders = ",".join("?" for _ in kinds)
    rows = _dicts(conn.execute(f"SELECT doc_date AS report_date,replace(kind,'_',' ') AS document_type,doc_no,party_name,amount,status,note FROM documents WHERE business_id=? AND kind IN ({placeholders}) AND doc_date BETWEEN ? AND ? ORDER BY doc_date DESC,id DESC", (bid, *kinds, start, end)).fetchall())
    columns = _columns(("report_date", "Date", "date"), ("document_type", "Type", "text"), ("doc_no", "Document No.", "text"), ("party_name", "Party", "text"), ("amount", "Amount", "money"), ("status", "Status", "text"))
    totals = [{"label": "Documents", "value": len(rows), "format": "number"}, {"label": "Amount", "value": _sum(rows, "amount"), "format": "money"}]
    return columns, rows, totals, ""


def _loan_report(conn: Any, bid: int, start: str, end: str) -> tuple[list[dict[str, str]], list[dict[str, Any]], list[dict[str, Any]], str]:
    rows = _dicts(conn.execute("SELECT entry_date AS report_date,CASE WHEN entry_type='loan_in' THEN 'Loan Received' ELSE 'Loan Given' END AS loan_type,title,party_name,amount,status,note FROM business_entries WHERE business_id=? AND entry_type IN ('loan_in','loan_out') AND entry_date BETWEEN ? AND ? ORDER BY entry_date DESC,id DESC", (bid, start, end)).fetchall())
    columns = _columns(("report_date", "Date", "date"), ("loan_type", "Type", "text"), ("title", "Loan / Account", "text"), ("party_name", "Party", "text"), ("amount", "Amount", "money"), ("status", "Status", "text"))
    received = round(sum(float(r.get("amount") or 0) for r in rows if r.get("loan_type") == "Loan Received"), 2)
    given = round(sum(float(r.get("amount") or 0) for r in rows if r.get("loan_type") == "Loan Given"), 2)
    totals = [{"label": "Loan Received", "value": received, "format": "money"}, {"label": "Loan Given", "value": given, "format": "money"}, {"label": "Net Loan", "value": round(received-given, 2), "format": "money"}]
    return columns, rows, totals, ""


@app.get("/api/reports/detail")
def advanced_report_detail(
    report: str,
    date_from: str = "",
    date_to: str = "",
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    requested = str(report or "").strip().lower()
    if requested not in REPORT_TITLES:
        raise HTTPException(status_code=404, detail="Report not found")
    resolved = ALIASES.get(requested, requested)
    start, end = _period(date_from, date_to)
    bid = int(user["business_id"])
    with db() as conn:
        if resolved == "sale_report":
            columns, rows, totals, note = _transaction_report(conn, bid, "sale", start, end)
        elif resolved == "purchase_report":
            columns, rows, totals, note = _transaction_report(conn, bid, "purchase", start, end)
        elif resolved in {"day_book", "all_transactions"}:
            columns, rows, totals, note = _day_book(conn, bid, start, end)
        elif resolved == "bill_wise_profit":
            columns, rows, totals, note = _bill_profit(conn, bid, start, end)
        elif resolved == "profit_loss":
            columns, rows, totals, note = _profit_loss(conn, bid, start, end)
        elif resolved == "sale_aging":
            columns, rows, totals, note = _aging(conn, bid, "sale", start, end)
        elif resolved == "purchase_aging":
            columns, rows, totals, note = _aging(conn, bid, "purchase", start, end)
        elif resolved == "cash_flow":
            columns, rows, totals, note = _cash_flow(conn, bid, start, end)
        elif resolved == "trial_balance":
            columns, rows, totals, note = _trial_balance(conn, bid, start, end)
        elif resolved == "balance_sheet":
            columns, rows, totals, note = _balance_sheet(conn, bid, start, end)
        elif resolved == "party_statement":
            columns, rows, totals, note = _party_report(conn, bid, "statement", start, end)
        elif resolved == "party_profit":
            columns, rows, totals, note = _party_report(conn, bid, "profit", start, end)
        elif resolved == "party_item":
            columns, rows, totals, note = _party_report(conn, bid, "item", start, end)
        elif resolved == "party_sales":
            columns, rows, totals, note = _party_report(conn, bid, "sales", start, end)
        elif resolved == "gst_sales":
            columns, rows, totals, note = _gst_report(conn, bid, "sales", start, end)
        elif resolved == "gst_purchase":
            columns, rows, totals, note = _gst_report(conn, bid, "purchase", start, end)
        elif resolved == "gst_transactions":
            columns, rows, totals, note = _gst_report(conn, bid, "transactions", start, end)
        elif resolved == "gstr3b":
            columns, rows, totals, note = _gst_report(conn, bid, "gstr3b", start, end)
        elif resolved == "hsn_summary":
            columns, rows, totals, note = _gst_report(conn, bid, "hsn", start, end)
        elif resolved == "tax_summary":
            columns, rows, totals, note = _gst_report(conn, bid, "rates", start, end)
        elif resolved == "stock_summary":
            columns, rows, totals, note = _stock_report(conn, bid, "summary", start, end)
        elif resolved == "item_party":
            columns, rows, totals, note = _stock_report(conn, bid, "item_party", start, end)
        elif resolved == "item_profit":
            columns, rows, totals, note = _stock_report(conn, bid, "profit", start, end)
        elif resolved == "low_stock":
            columns, rows, totals, note = _stock_report(conn, bid, "low", start, end)
        elif resolved == "item_detail":
            columns, rows, totals, note = _stock_report(conn, bid, "detail", start, end)
        elif resolved in {"stock_detail", "item_movement"}:
            columns, rows, totals, note = _stock_report(conn, bid, "movement", start, end)
        elif resolved == "category_trades":
            columns, rows, totals, note = _stock_report(conn, bid, "category_trades", start, end)
        elif resolved == "category_stock":
            columns, rows, totals, note = _stock_report(conn, bid, "category_stock", start, end)
        elif resolved == "item_discount":
            columns, rows, totals, note = _stock_report(conn, bid, "discount", start, end)
        elif resolved == "item_serial":
            columns, rows, totals, note = _stock_report(conn, bid, "serial", start, end)
        elif resolved == "manufacturing":
            columns, rows, totals, note = _stock_report(conn, bid, "manufacturing", start, end)
        elif resolved == "consumption":
            columns, rows, totals, note = _stock_report(conn, bid, "consumption", start, end)
        elif resolved == "stock_transfer":
            columns, rows, totals, note = _stock_report(conn, bid, "transfer", start, end)
        elif resolved == "bank_statement":
            columns, rows, totals, note = _bank_report(conn, bid, start, end)
        elif resolved == "receivable_payable":
            columns, rows, totals, note = _receivable_payable(conn, bid, start, end)
        elif resolved in {"tcs_receivable", "tds_payable", "tds_receivable"}:
            columns, rows, totals, note = _tax_deduction(conn, bid, resolved.split("_")[0], start, end)
        elif resolved == "expense_transactions":
            columns, rows, totals, note = _expense_report(conn, bid, False, start, end)
        elif resolved == "expense_category":
            columns, rows, totals, note = _expense_report(conn, bid, True, start, end)
        elif resolved == "order_transactions":
            columns, rows, totals, note = _document_report(conn, bid, False, start, end)
        elif resolved == "challan_report":
            columns, rows, totals, note = _document_report(conn, bid, True, start, end)
        elif resolved == "loan_statement":
            columns, rows, totals, note = _loan_report(conn, bid, start, end)
        else:
            raise HTTPException(status_code=404, detail="Report is not available")
    return _result(requested, start, end, columns, rows, totals, note)


# backend.app registers a catch-all frontend route. Keep this API before it.
_paths = {"/api/reports/detail"}
_routes = [route for route in list(app.router.routes) if getattr(route, "path", None) in _paths]
for _route in _routes:
    app.router.routes.remove(_route)
_fallback_index = next(
    (index for index, route in enumerate(app.router.routes) if getattr(route, "path", None) == "/{path:path}"),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _routes
