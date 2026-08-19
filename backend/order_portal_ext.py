from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta
from typing import Any, Literal

from fastapi import Depends, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from backend.app import (
    TransactionIn,
    app,
    current_user,
    db,
    hash_password,
    insert_sale,
    now_iso,
    today_iso,
    verify_password,
)


ORDER_STATUSES = {"pending", "confirmed", "processing", "dispatched", "delivered", "cancelled"}


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    return digits[-10:] if len(digits) > 10 else digits


def ensure_order_schema() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS customer_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                party_id INTEGER NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
                phone TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(business_id, party_id),
                UNIQUE(business_id, phone)
            );
            CREATE INDEX IF NOT EXISTS idx_customer_accounts_business ON customer_accounts(business_id, is_active);

            CREATE TABLE IF NOT EXISTS customer_sessions (
                token TEXT PRIMARY KEY,
                customer_account_id INTEGER NOT NULL REFERENCES customer_accounts(id) ON DELETE CASCADE,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS customer_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                party_id INTEGER NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
                item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
                rate REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(business_id, party_id, item_id)
            );
            CREATE INDEX IF NOT EXISTS idx_customer_prices_lookup ON customer_prices(business_id, party_id, item_id);

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                order_no TEXT NOT NULL,
                party_id INTEGER NOT NULL REFERENCES parties(id) ON DELETE RESTRICT,
                party_name TEXT NOT NULL,
                order_date TEXT NOT NULL,
                source TEXT NOT NULL CHECK(source IN ('owner','customer')),
                status TEXT NOT NULL DEFAULT 'pending',
                subtotal REAL NOT NULL DEFAULT 0,
                tax REAL NOT NULL DEFAULT 0,
                total REAL NOT NULL DEFAULT 0,
                notes TEXT DEFAULT '',
                created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                customer_account_id INTEGER REFERENCES customer_accounts(id) ON DELETE SET NULL,
                sale_id INTEGER REFERENCES sales(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(business_id, order_no)
            );
            CREATE INDEX IF NOT EXISTS idx_orders_business_status ON orders(business_id, status, id DESC);
            CREATE INDEX IF NOT EXISTS idx_orders_party ON orders(party_id, id DESC);

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
                item_name TEXT NOT NULL,
                size TEXT DEFAULT '',
                qty REAL NOT NULL,
                rate REAL NOT NULL,
                rate_source TEXT NOT NULL DEFAULT 'default',
                gst_rate REAL NOT NULL DEFAULT 0,
                line_subtotal REAL NOT NULL,
                line_tax REAL NOT NULL,
                line_total REAL NOT NULL
            );
            """
        )


@app.on_event("startup")
def startup_order_portal() -> None:
    ensure_order_schema()


class CustomerAccessIn(BaseModel):
    party_id: int
    pin: str = Field(min_length=4, max_length=128)
    phone: str = ""
    is_active: bool = True


class CustomerLoginIn(BaseModel):
    phone: str
    pin: str


class CustomerPriceIn(BaseModel):
    party_id: int
    item_id: int
    rate: float = Field(ge=0)


class OrderLineIn(BaseModel):
    item_id: int
    qty: float = Field(gt=0)
    rate: float | None = Field(default=None, ge=0)
    save_as_customer_rate: bool = False


class OrderCreateIn(BaseModel):
    party_id: int | None = None
    order_date: str = Field(default_factory=today_iso)
    notes: str = ""
    items: list[OrderLineIn] = Field(min_items=1)


class OrderStatusIn(BaseModel):
    status: Literal["pending", "confirmed", "processing", "dispatched", "delivered", "cancelled"]


def customer_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    ensure_order_schema()
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Customer login required")
    token = authorization.split(" ", 1)[1].strip()
    with db() as conn:
        row = conn.execute(
            """
            SELECT ca.id AS customer_account_id, ca.business_id, ca.party_id, ca.phone,
                   p.name AS party_name, p.balance, b.name AS business_name
            FROM customer_sessions cs
            JOIN customer_accounts ca ON ca.id=cs.customer_account_id
            JOIN parties p ON p.id=ca.party_id
            JOIN businesses b ON b.id=ca.business_id
            WHERE cs.token=? AND cs.expires_at>? AND ca.is_active=1
            """,
            (token, now_iso()),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Customer session expired")
    return dict(row)


def last_bill_rate(conn, business_id: int, party_id: int, item_id: int) -> float | None:
    row = conn.execute(
        """
        SELECT si.rate
        FROM sale_items si
        JOIN sales s ON s.id=si.sale_id
        WHERE s.business_id=? AND s.party_id=? AND si.item_id=?
        ORDER BY s.invoice_date DESC, s.id DESC, si.id DESC
        LIMIT 1
        """,
        (business_id, party_id, item_id),
    ).fetchone()
    return round(float(row["rate"]), 2) if row else None


def recommended_rate(conn, business_id: int, party_id: int, item_id: int) -> dict[str, Any]:
    item = conn.execute(
        "SELECT id,name,size,unit,gst_rate,sale_price,mrp,stock FROM items WHERE id=? AND business_id=?",
        (item_id, business_id),
    ).fetchone()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    fixed = conn.execute(
        "SELECT rate FROM customer_prices WHERE business_id=? AND party_id=? AND item_id=?",
        (business_id, party_id, item_id),
    ).fetchone()
    if fixed:
        rate = round(float(fixed["rate"]), 2)
        source = "fixed"
    else:
        previous = last_bill_rate(conn, business_id, party_id, item_id)
        if previous is not None:
            rate = previous
            source = "last_bill"
        else:
            rate = round(float(item["sale_price"] or 0), 2)
            source = "default"
    result = dict(item)
    result.update({"rate": rate, "rate_source": source})
    return result


def next_order_no(conn, business_id: int) -> str:
    business = conn.execute("SELECT invoice_prefix FROM businesses WHERE id=?", (business_id,)).fetchone()
    prefix = str((business["invoice_prefix"] if business else "KS") or "KS").upper()[:8]
    year = datetime.now().strftime("%y")
    base = f"{prefix}-O-{year}-"
    row = conn.execute(
        "SELECT order_no FROM orders WHERE business_id=? AND order_no LIKE ? ORDER BY id DESC LIMIT 1",
        (business_id, f"{base}%"),
    ).fetchone()
    sequence = 1
    if row:
        try:
            sequence = int(str(row["order_no"]).rsplit("-", 1)[-1]) + 1
        except ValueError:
            pass
    return f"{base}{sequence:05d}"


def order_detail(conn, business_id: int, order_id: int) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM orders WHERE id=? AND business_id=?", (order_id, business_id)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    result = dict(row)
    result["items"] = [dict(r) for r in conn.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY id", (order_id,)).fetchall()]
    if result.get("sale_id"):
        sale = conn.execute("SELECT invoice_no FROM sales WHERE id=?", (result["sale_id"],)).fetchone()
        result["invoice_no"] = sale["invoice_no"] if sale else ""
    return result


def create_order_record(
    payload: OrderCreateIn,
    business_id: int,
    party_id: int,
    source: str,
    created_by_user_id: int | None = None,
    customer_account_id: int | None = None,
) -> dict[str, Any]:
    ensure_order_schema()
    with db() as conn:
        party = conn.execute(
            "SELECT * FROM parties WHERE id=? AND business_id=? AND type IN ('customer','both')",
            (party_id, business_id),
        ).fetchone()
        if not party:
            raise HTTPException(status_code=404, detail="Customer not found")

        prepared: list[dict[str, Any]] = []
        subtotal = 0.0
        tax = 0.0
        for line in payload.items:
            recommendation = recommended_rate(conn, business_id, party_id, line.item_id)
            selected_rate = recommendation["rate"]
            rate_source = recommendation["rate_source"]
            if source == "owner" and line.rate is not None:
                selected_rate = round(float(line.rate), 2)
                if selected_rate != recommendation["rate"]:
                    rate_source = "manual"
                if line.save_as_customer_rate:
                    conn.execute(
                        """
                        INSERT INTO customer_prices(business_id,party_id,item_id,rate,created_at,updated_at)
                        VALUES(?,?,?,?,?,?)
                        ON CONFLICT(business_id,party_id,item_id)
                        DO UPDATE SET rate=excluded.rate,updated_at=excluded.updated_at
                        """,
                        (business_id, party_id, line.item_id, selected_rate, now_iso(), now_iso()),
                    )
                    rate_source = "fixed"
            line_subtotal = round(line.qty * selected_rate, 2)
            line_tax = round(line_subtotal * float(recommendation["gst_rate"] or 0) / 100, 2)
            line_total = round(line_subtotal + line_tax, 2)
            subtotal += line_subtotal
            tax += line_tax
            prepared.append(
                {
                    "item_id": line.item_id,
                    "item_name": recommendation["name"],
                    "size": recommendation["size"] or "",
                    "qty": line.qty,
                    "rate": selected_rate,
                    "rate_source": rate_source,
                    "gst_rate": float(recommendation["gst_rate"] or 0),
                    "line_subtotal": line_subtotal,
                    "line_tax": line_tax,
                    "line_total": line_total,
                }
            )

        subtotal = round(subtotal, 2)
        tax = round(tax, 2)
        total = round(subtotal + tax, 2)
        order_no = next_order_no(conn, business_id)
        cursor = conn.execute(
            """
            INSERT INTO orders(
                business_id,order_no,party_id,party_name,order_date,source,status,
                subtotal,tax,total,notes,created_by_user_id,customer_account_id,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                business_id,
                order_no,
                party_id,
                party["name"],
                payload.order_date or today_iso(),
                source,
                "pending",
                subtotal,
                tax,
                total,
                payload.notes.strip(),
                created_by_user_id,
                customer_account_id,
                now_iso(),
                now_iso(),
            ),
        )
        order_id = int(cursor.lastrowid)
        for line in prepared:
            conn.execute(
                """
                INSERT INTO order_items(
                    order_id,item_id,item_name,size,qty,rate,rate_source,gst_rate,line_subtotal,line_tax,line_total
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    order_id,
                    line["item_id"],
                    line["item_name"],
                    line["size"],
                    line["qty"],
                    line["rate"],
                    line["rate_source"],
                    line["gst_rate"],
                    line["line_subtotal"],
                    line["line_tax"],
                    line["line_total"],
                ),
            )
        return order_detail(conn, business_id, order_id)


@app.get("/api/order-rate")
def get_order_rate(
    party_id: int,
    item_id: int,
    user: dict[str, Any] = Depends(current_user),
) -> dict[str, Any]:
    ensure_order_schema()
    with db() as conn:
        party = conn.execute("SELECT id FROM parties WHERE id=? AND business_id=?", (party_id, user["business_id"])).fetchone()
        if not party:
            raise HTTPException(status_code=404, detail="Customer not found")
        return recommended_rate(conn, user["business_id"], party_id, item_id)


@app.get("/api/customer-access")
def list_customer_access(user: dict[str, Any] = Depends(current_user)) -> list[dict[str, Any]]:
    ensure_order_schema()
    with db() as conn:
        return [
            dict(r)
            for r in conn.execute(
                """
                SELECT ca.id,ca.party_id,ca.phone,ca.is_active,ca.created_at,ca.updated_at,p.name AS party_name
                FROM customer_accounts ca JOIN parties p ON p.id=ca.party_id
                WHERE ca.business_id=? ORDER BY p.name
                """,
                (user["business_id"],),
            ).fetchall()
        ]


@app.post("/api/customer-access")
def save_customer_access(payload: CustomerAccessIn, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    ensure_order_schema()
    with db() as conn:
        party = conn.execute(
            "SELECT * FROM parties WHERE id=? AND business_id=? AND type IN ('customer','both')",
            (payload.party_id, user["business_id"]),
        ).fetchone()
        if not party:
            raise HTTPException(status_code=404, detail="Customer not found")
        phone = normalize_phone(payload.phone or party["phone"])
        if len(phone) < 10:
            raise HTTPException(status_code=400, detail="Customer ka valid 10 digit mobile number required hai")
        try:
            conn.execute(
                """
                INSERT INTO customer_accounts(business_id,party_id,phone,password_hash,is_active,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(business_id,party_id)
                DO UPDATE SET phone=excluded.phone,password_hash=excluded.password_hash,is_active=excluded.is_active,updated_at=excluded.updated_at
                """,
                (user["business_id"], payload.party_id, phone, hash_password(payload.pin), 1 if payload.is_active else 0, now_iso(), now_iso()),
            )
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise HTTPException(status_code=409, detail="Ye mobile number kisi aur customer login me use ho raha hai") from exc
            raise
        row = conn.execute(
            """
            SELECT ca.id,ca.party_id,ca.phone,ca.is_active,ca.created_at,ca.updated_at,p.name AS party_name
            FROM customer_accounts ca JOIN parties p ON p.id=ca.party_id
            WHERE ca.business_id=? AND ca.party_id=?
            """,
            (user["business_id"], payload.party_id),
        ).fetchone()
        return dict(row)


@app.post("/api/customer-prices")
def save_customer_price(payload: CustomerPriceIn, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    ensure_order_schema()
    with db() as conn:
        party = conn.execute("SELECT id FROM parties WHERE id=? AND business_id=?", (payload.party_id, user["business_id"])).fetchone()
        item = conn.execute("SELECT id FROM items WHERE id=? AND business_id=?", (payload.item_id, user["business_id"])).fetchone()
        if not party or not item:
            raise HTTPException(status_code=404, detail="Customer or item not found")
        conn.execute(
            """
            INSERT INTO customer_prices(business_id,party_id,item_id,rate,created_at,updated_at)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(business_id,party_id,item_id)
            DO UPDATE SET rate=excluded.rate,updated_at=excluded.updated_at
            """,
            (user["business_id"], payload.party_id, payload.item_id, round(payload.rate, 2), now_iso(), now_iso()),
        )
        return recommended_rate(conn, user["business_id"], payload.party_id, payload.item_id)


@app.delete("/api/customer-prices/{party_id}/{item_id}")
def delete_customer_price(party_id: int, item_id: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, bool]:
    ensure_order_schema()
    with db() as conn:
        conn.execute(
            "DELETE FROM customer_prices WHERE business_id=? AND party_id=? AND item_id=?",
            (user["business_id"], party_id, item_id),
        )
    return {"ok": True}


@app.post("/api/orders")
def owner_create_order(payload: OrderCreateIn, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    if not payload.party_id:
        raise HTTPException(status_code=400, detail="Customer select karein")
    return create_order_record(
        payload,
        user["business_id"],
        payload.party_id,
        "owner",
        created_by_user_id=user["user_id"],
    )


@app.get("/api/orders")
def owner_list_orders(
    status: str = "",
    party_id: int | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    user: dict[str, Any] = Depends(current_user),
) -> list[dict[str, Any]]:
    ensure_order_schema()
    sql = "SELECT id FROM orders WHERE business_id=?"
    args: list[Any] = [user["business_id"]]
    if status:
        sql += " AND status=?"
        args.append(status)
    if party_id:
        sql += " AND party_id=?"
        args.append(party_id)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with db() as conn:
        ids = [int(r["id"]) for r in conn.execute(sql, args).fetchall()]
        return [order_detail(conn, user["business_id"], order_id) for order_id in ids]


@app.put("/api/orders/{order_id}/status")
def update_order_status(order_id: int, payload: OrderStatusIn, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    ensure_order_schema()
    with db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id=? AND business_id=?", (order_id, user["business_id"])).fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        if order["status"] == "converted":
            raise HTTPException(status_code=409, detail="Bill ban chuka hai; order status change nahi ho sakta")
        conn.execute("UPDATE orders SET status=?,updated_at=? WHERE id=?", (payload.status, now_iso(), order_id))
        return order_detail(conn, user["business_id"], order_id)


@app.post("/api/orders/{order_id}/convert-to-sale")
def convert_order_to_sale(order_id: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
    ensure_order_schema()
    with db() as conn:
        order = conn.execute("SELECT * FROM orders WHERE id=? AND business_id=?", (order_id, user["business_id"])).fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        if order["status"] == "converted" or order["sale_id"]:
            raise HTTPException(status_code=409, detail="Is order ka bill pehle hi ban chuka hai")
        if order["status"] == "cancelled":
            raise HTTPException(status_code=409, detail="Cancelled order ka bill nahi ban sakta")
        lines = [dict(r) for r in conn.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY id", (order_id,)).fetchall()]
        payload = TransactionIn(
            party_id=order["party_id"],
            invoice_date=today_iso(),
            paid=0,
            payment_mode="credit",
            notes=f"Order {order['order_no']} se bill",
            items=[
                {
                    "item_id": line["item_id"],
                    "item_name": line["item_name"],
                    "size": line["size"],
                    "qty": line["qty"],
                    "rate": line["rate"],
                    "gst_rate": line["gst_rate"],
                }
                for line in lines
            ],
        )
        sale = insert_sale(conn, user["business_id"], payload)
        conn.execute(
            "UPDATE orders SET status='converted',sale_id=?,updated_at=? WHERE id=?",
            (sale["id"], now_iso(), order_id),
        )
        return {"order": order_detail(conn, user["business_id"], order_id), "sale": sale}


@app.post("/api/customer/login")
def customer_login(payload: CustomerLoginIn) -> dict[str, Any]:
    ensure_order_schema()
    phone = normalize_phone(payload.phone)
    with db() as conn:
        row = conn.execute(
            "SELECT ca.*,p.name AS party_name,b.name AS business_name FROM customer_accounts ca JOIN parties p ON p.id=ca.party_id JOIN businesses b ON b.id=ca.business_id WHERE ca.phone=? AND ca.is_active=1",
            (phone,),
        ).fetchone()
        if not row or not verify_password(payload.pin, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Mobile number ya PIN galat hai")
        token = secrets.token_urlsafe(40)
        expires_at = (datetime.now() + timedelta(days=30)).replace(microsecond=0).isoformat()
        conn.execute("DELETE FROM customer_sessions WHERE expires_at<=?", (now_iso(),))
        conn.execute(
            "INSERT INTO customer_sessions(token,customer_account_id,expires_at,created_at) VALUES(?,?,?,?)",
            (token, row["id"], expires_at, now_iso()),
        )
        return {
            "token": token,
            "customer": {"party_id": row["party_id"], "party_name": row["party_name"], "phone": row["phone"]},
            "business_name": row["business_name"],
        }


@app.post("/api/customer/logout")
def customer_logout(
    customer: dict[str, Any] = Depends(customer_user),
    authorization: str | None = Header(default=None),
) -> dict[str, bool]:
    token = authorization.split(" ", 1)[1].strip() if authorization else ""
    with db() as conn:
        conn.execute("DELETE FROM customer_sessions WHERE token=?", (token,))
    return {"ok": True}


@app.get("/api/customer/me")
def customer_me(customer: dict[str, Any] = Depends(customer_user)) -> dict[str, Any]:
    return customer


@app.get("/api/customer/catalog")
def customer_catalog(customer: dict[str, Any] = Depends(customer_user)) -> list[dict[str, Any]]:
    ensure_order_schema()
    with db() as conn:
        item_ids = [int(r["id"]) for r in conn.execute("SELECT id FROM items WHERE business_id=? AND COALESCE(archived_at,'')='' ORDER BY name,size", (customer["business_id"],)).fetchall()]
        return [recommended_rate(conn, customer["business_id"], customer["party_id"], item_id) for item_id in item_ids]


@app.post("/api/customer/orders")
def customer_create_order(payload: OrderCreateIn, customer: dict[str, Any] = Depends(customer_user)) -> dict[str, Any]:
    return create_order_record(
        payload,
        customer["business_id"],
        customer["party_id"],
        "customer",
        customer_account_id=customer["customer_account_id"],
    )


@app.get("/api/customer/orders")
def customer_list_orders(
    limit: int = Query(default=100, ge=1, le=500),
    customer: dict[str, Any] = Depends(customer_user),
) -> list[dict[str, Any]]:
    ensure_order_schema()
    with db() as conn:
        ids = [
            int(r["id"])
            for r in conn.execute(
                "SELECT id FROM orders WHERE business_id=? AND party_id=? ORDER BY id DESC LIMIT ?",
                (customer["business_id"], customer["party_id"], limit),
            ).fetchall()
        ]
        return [order_detail(conn, customer["business_id"], order_id) for order_id in ids]


CUSTOMER_PORTAL_HTML = """<!doctype html>
<html lang="hi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="theme-color" content="#0b7bc1" />
  <title>Customer Order</title>
  <link rel="stylesheet" href="/customer-order.css?v=060" />
</head>
<body>
  <div id="customer-toast" class="customer-toast"></div>
  <section id="customer-login" class="customer-auth">
    <div class="customer-auth-card">
      <div class="customer-logo">K</div>
      <h1>Online Order</h1>
      <p>Apna mobile number aur dukaan se mila PIN daalein.</p>
      <form id="customer-login-form">
        <label>Mobile number<input name="phone" inputmode="tel" required maxlength="15" /></label>
        <label>PIN<input name="pin" type="password" inputmode="numeric" required minlength="4" /></label>
        <button type="submit">Login</button>
      </form>
    </div>
  </section>
  <div id="customer-app" class="customer-app hidden">
    <header><div><strong id="customer-business">Order</strong><small id="customer-name"></small></div><button id="customer-logout">Logout</button></header>
    <main>
      <div class="customer-tabs"><button data-customer-tab="shop" class="active">Products</button><button data-customer-tab="cart">Cart <span id="customer-cart-count">0</span></button><button data-customer-tab="orders">My Orders</button></div>
      <section id="customer-tab-shop" class="customer-tab active"><input id="customer-search" class="customer-search" placeholder="Product search karein" /><div id="customer-products" class="customer-products"></div></section>
      <section id="customer-tab-cart" class="customer-tab"><div id="customer-cart"></div><label class="customer-note">Order note<textarea id="customer-order-note" rows="2" placeholder="Delivery ya packing note"></textarea></label><div class="customer-total"><span>Total</span><strong id="customer-total">₹0.00</strong></div><button id="customer-place-order" class="customer-primary">Order Place Karein</button></section>
      <section id="customer-tab-orders" class="customer-tab"><div id="customer-orders"></div></section>
    </main>
  </div>
  <script src="/customer-order.js?v=060"></script>
</body>
</html>"""


@app.middleware("http")
async def serve_customer_order_portal(request: Request, call_next):
    if request.method == "GET" and request.url.path.rstrip("/") == "/customer":
        return HTMLResponse(
            CUSTOMER_PORTAL_HTML,
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache"},
        )
    return await call_next(request)


# Extensions are imported after backend.app, whose SPA fallback route is already
# registered. Move every new API route ahead of that fallback.
_order_paths = {
    "/api/order-rate",
    "/api/customer-access",
    "/api/customer-prices",
    "/api/customer-prices/{party_id}/{item_id}",
    "/api/orders",
    "/api/orders/{order_id}/status",
    "/api/orders/{order_id}/convert-to-sale",
    "/api/customer/login",
    "/api/customer/logout",
    "/api/customer/me",
    "/api/customer/catalog",
    "/api/customer/orders",
}
_order_routes = [route for route in app.router.routes if getattr(route, "path", None) in _order_paths]
for route in _order_routes:
    app.router.routes.remove(route)
_fallback_index = next(
    (index for index, route in enumerate(app.router.routes) if getattr(route, "path", None) == "/{path:path}"),
    len(app.router.routes),
)
app.router.routes[_fallback_index:_fallback_index] = _order_routes
