from pathlib import Path

import backend.app as app_module
import backend.corrupt_x00_item_cleanup_ext as cleanup_module
import backend.order_portal_ext as order_module


def add_item(conn, business_id: int, name: str, sku: str = "", size: str = "", barcode: str = "") -> int:
    cursor = conn.execute(
        """
        INSERT INTO items(
            business_id,name,sku,barcode,unit,size,sale_price,created_at,updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?)
        """,
        (
            business_id,
            name,
            sku,
            barcode,
            "kg",
            size,
            50,
            app_module.now_iso(),
            app_module.now_iso(),
        ),
    )
    return int(cursor.lastrowid)


def test_x00_items_are_deleted_and_order_totals_recalculate(tmp_path: Path):
    app_module.DB_PATH = tmp_path / "x00-cleanup.db"
    app_module.init_db()
    order_module.ensure_order_schema()

    with app_module.db() as conn:
        business_id = int(
            conn.execute(
                "INSERT INTO businesses(name,created_at) VALUES(?,?)",
                ("Darbar Home Pack", app_module.now_iso()),
            ).lastrowid
        )
        party_id = int(
            conn.execute(
                """
                INSERT INTO parties(
                    business_id,name,type,created_at,updated_at
                ) VALUES(?,?,?,?,?)
                """,
                (business_id, "Ayush", "customer", app_module.now_iso(), app_module.now_iso()),
            ).lastrowid
        )
        clean_id = add_item(conn, business_id, "Ajwain", sku="AJW-1")
        bad_name_id = add_item(conn, business_id, "Ajwain (_x0005_अजवाइन)", sku="BAD-1")
        bad_sku_id = add_item(conn, business_id, "Aaroroot", sku="x0006-BAD")

        order_id = int(
            conn.execute(
                """
                INSERT INTO orders(
                    business_id,order_no,party_id,party_name,order_date,source,
                    subtotal,tax,total,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    business_id,
                    "DHP-1",
                    party_id,
                    "Ayush",
                    app_module.today_iso(),
                    "customer",
                    150,
                    0,
                    150,
                    app_module.now_iso(),
                    app_module.now_iso(),
                ),
            ).lastrowid
        )
        conn.execute(
            """
            INSERT INTO order_items(
                order_id,item_id,item_name,qty,rate,line_subtotal,line_tax,line_total
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (order_id, clean_id, "Ajwain", 1, 50, 50, 0, 50),
        )
        conn.execute(
            """
            INSERT INTO order_items(
                order_id,item_id,item_name,qty,rate,line_subtotal,line_tax,line_total
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (order_id, bad_name_id, "Ajwain (_x0005_अजवाइन)", 2, 50, 100, 0, 100),
        )

    result = cleanup_module.cleanup_corrupt_x00_items(business_id)
    assert result["deleted_count"] == 2

    with app_module.db() as conn:
        remaining = conn.execute(
            "SELECT id,name,sku FROM items WHERE business_id=? ORDER BY id",
            (business_id,),
        ).fetchall()
        assert [(row["id"], row["name"]) for row in remaining] == [(clean_id, "Ajwain")]
        assert not conn.execute("SELECT 1 FROM items WHERE id=?", (bad_sku_id,)).fetchone()

        order = conn.execute("SELECT subtotal,tax,total FROM orders WHERE id=?", (order_id,)).fetchone()
        assert order is not None
        assert order["subtotal"] == 50
        assert order["tax"] == 0
        assert order["total"] == 50
        lines = conn.execute("SELECT item_id FROM order_items WHERE order_id=?", (order_id,)).fetchall()
        assert [row["item_id"] for row in lines] == [clean_id]

        logs = conn.execute(
            "SELECT old_item_id FROM corrupt_item_cleanup_log ORDER BY old_item_id"
        ).fetchall()
        assert [row["old_item_id"] for row in logs] == sorted([bad_name_id, bad_sku_id])


def test_future_x00_item_insert_is_ignored(tmp_path: Path):
    app_module.DB_PATH = tmp_path / "x00-trigger.db"
    app_module.init_db()
    cleanup_module.ensure_corrupt_item_cleanup_schema()

    with app_module.db() as conn:
        business_id = int(
            conn.execute(
                "INSERT INTO businesses(name,created_at) VALUES(?,?)",
                ("Darbar Home Pack", app_module.now_iso()),
            ).lastrowid
        )
        add_item(conn, business_id, "Clean Product", sku="CLEAN-1")
        add_item(conn, business_id, "Bad x000D Product", sku="BAD-2")
        rows = conn.execute(
            "SELECT name FROM items WHERE business_id=? ORDER BY id",
            (business_id,),
        ).fetchall()
        assert [row["name"] for row in rows] == ["Clean Product"]
