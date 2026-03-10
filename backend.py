#(套件)
#-------------------------------------------------------------------------------------------
from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime

DB_PATH = "orders.db"
app = Flask(__name__)

#(資料庫連線)
#-------------------------------------------------------------------------------------------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

#(建立資料庫表格)
#-------------------------------------------------------------------------------------------
def init_db():
    conn = db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        subtotal INTEGER NOT NULL,
        discount INTEGER NOT NULL,
        total INTEGER NOT NULL,
        is_served INTEGER NOT NULL DEFAULT 0
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        item_key TEXT NOT NULL,
        name TEXT NOT NULL,
        price INTEGER NOT NULL,
        qty INTEGER NOT NULL,
        line_total INTEGER NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS history_orders (
        history_id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_order_id INTEGER,
        created_at TEXT NOT NULL,
        subtotal INTEGER NOT NULL,
        discount INTEGER NOT NULL,
        total INTEGER NOT NULL,
        is_served INTEGER NOT NULL DEFAULT 0
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS history_order_items (
        history_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        history_order_id INTEGER NOT NULL,
        original_order_id INTEGER,
        item_key TEXT NOT NULL,
        name TEXT NOT NULL,
        price INTEGER NOT NULL,
        qty INTEGER NOT NULL,
        line_total INTEGER NOT NULL,
        FOREIGN KEY(history_order_id) REFERENCES history_orders(history_id)
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS menu (
        item_key TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price INTEGER NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1
    )
    """)
    try:
        cur.execute("ALTER TABLE orders ADD COLUMN is_served INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

#(訂單明細)
#-------------------------------------------------------------------------------------------
def print_order_to_console(order_id: int):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    SELECT id, created_at, subtotal, discount, total, is_served
    FROM orders
    WHERE id=?
    """, (order_id,))
    order = cur.fetchone()

    if not order:
        conn.close()
        return

    cur.execute("""
    SELECT name, price, qty, line_total
    FROM order_items
    WHERE order_id=?
    ORDER BY id ASC
    """, (order_id,))
    items = cur.fetchall()
    conn.close()

    print("\n" + "=" * 42)
    print(f"單號: {order['id']}")
    print(f"日期: {order['created_at']}")
    print(f": {order['total']} 元")
    print("-" * 42)
    print("餐點明細:")
    for it in items:
        print(f"- {it['name']}  {it['price']} x{it['qty']} = {it['line_total']}")
    print("-" * 42)
    print(f"小計: {order['subtotal']}  折扣: -{order['discount']}  應付: {order['total']}")
    print("=" * 42 + "\n")


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


#(菜單給予編號)
#-------------------------------------------------------------------------------------------
@app.get("/api/menu")
def get_menu_active():
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT item_key, name, category, price
        FROM menu
        WHERE is_active=1
        ORDER BY
            CASE category
                WHEN '漢堡' THEN 1
                WHEN '吐司' THEN 2
                WHEN '蛋餅' THEN 3
                WHEN '單點' THEN 4
                WHEN '飲品' THEN 5
                ELSE 999
            END,
            price ASC,
            name ASC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)

#(菜單給予編號)
#-------------------------------------------------------------------------------------------
@app.get("/api/menu/all")
def get_menu_all():
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT item_key, name, category, price, is_active
        FROM menu
        ORDER BY
            CASE category
                WHEN '漢堡' THEN 1
                WHEN '吐司' THEN 2
                WHEN '蛋餅' THEN 3
                WHEN '單點' THEN 4
                WHEN '飲品' THEN 5
                ELSE 999
            END,
            price ASC,
            name ASC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)

#(新增菜色)
#-------------------------------------------------------------------------------------------
@app.post("/api/menu/upsert")
def upsert_menu():
    data = request.get_json(force=True)

    item_key = str(data.get("item_key", "")).strip()
    name = str(data.get("name", "")).strip()
    category = str(data.get("category", "")).strip()

    try:
        price = int(data.get("price", 0))
    except Exception:
        price = 0

    try:
        is_active = int(data.get("is_active", 1))
    except Exception:
        is_active = 1

    if not name or not category or price <= 0:
        return jsonify({"error": "invalid payload"}), 400

    conn = db()
    cur = conn.cursor()

    if not item_key:
        cur.execute("""
            SELECT item_key
            FROM menu
            WHERE item_key LIKE 'item_%'
            ORDER BY CAST(SUBSTR(item_key, 6) AS INTEGER) DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            try:
                last_num = int(row["item_key"].split("_")[1])
            except Exception:
                last_num = 0
            item_key = f"item_{last_num + 1}"
        else:
            item_key = "item_1"

    cur.execute("""
        INSERT INTO menu(item_key, name, category, price, is_active)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(item_key) DO UPDATE SET
            name=excluded.name,
            category=excluded.category,
            price=excluded.price,
            is_active=excluded.is_active
    """, (item_key, name, category, price, is_active))

    conn.commit()
    conn.close()

    return jsonify({"ok": True, "item_key": item_key})

#(上下架)
#-------------------------------------------------------------------------------------------
@app.post("/api/menu/toggle")
def toggle_menu():
    data = request.get_json(force=True)
    item_key = str(data.get("item_key", "")).strip()

    try:
        is_active = int(data.get("is_active", 1))
    except Exception:
        is_active = 1

    if not item_key:
        return jsonify({"error": "missing item_key"}), 400

    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE menu SET is_active=? WHERE item_key=?", (is_active, item_key))
    conn.commit()
    conn.close()

    return jsonify({"ok": True})

#(刪除菜色)
#-------------------------------------------------------------------------------------------
@app.post("/api/menu/delete")
def delete_menu():
    data = request.get_json(force=True)
    item_key = str(data.get("item_key", "")).strip()

    if not item_key:
        return jsonify({"error": "missing item_key"}), 400

    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM menu WHERE item_key=?", (item_key,))
    conn.commit()
    conn.close()

    return jsonify({"ok": True})



#(點餐系統送出訂單)
#-------------------------------------------------------------------------------------------
@app.post("/api/orders")
def create_order():
    data = request.get_json(force=True)

    items = data.get("items", [])
    subtotal = int(data.get("subtotal", 0))
    discount = int(data.get("discount", 0))
    total = int(data.get("total", 0))

    if not items:
        return jsonify({"error": "empty order"}), 400

    calc_subtotal = sum(int(x.get("line_total", 0)) for x in items)
    if calc_subtotal != subtotal:
        return jsonify({"error": "subtotal mismatch", "calc_subtotal": calc_subtotal}), 400

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = db()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO orders(created_at, subtotal, discount, total, is_served)
    VALUES (?, ?, ?, ?, 0)
    """, (created_at, subtotal, discount, total))
    order_id = cur.lastrowid

    for it in items:
        cur.execute("""
        INSERT INTO order_items(order_id, item_key, name, price, qty, line_total)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            order_id,
            str(it.get("key", "")),
            str(it.get("name", "")),
            int(it.get("price", 0)),
            int(it.get("qty", 0)),
            int(it.get("line_total", 0))
        ))

    conn.commit()
    conn.close()

    print_order_to_console(order_id)
    return jsonify({"ok": True, "order_id": order_id})

#(取得目前所有訂單)
#-------------------------------------------------------------------------------------------
@app.get("/api/orders")
def list_orders():
    limit = int(request.args.get("limit", 200))
    conn = db()
    cur = conn.cursor()
    cur.execute("""
    SELECT id, created_at, subtotal, discount, total, is_served
    FROM orders
    ORDER BY id DESC
    LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)

#(後臺點擊訂單查看明細)
#-------------------------------------------------------------------------------------------
@app.get("/api/orders/<int:order_id>")
def get_order(order_id: int):
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    SELECT id, created_at, subtotal, discount, total, is_served
    FROM orders
    WHERE id=?
    """, (order_id,))
    order = cur.fetchone()
    if not order:
        conn.close()
        return jsonify({"error": "not found"}), 404

    cur.execute("""
    SELECT item_key, name, price, qty, line_total
    FROM order_items
    WHERE order_id=?
    ORDER BY id ASC
    """, (order_id,))
    items = [dict(r) for r in cur.fetchall()]
    conn.close()

    return jsonify({"order": dict(order), "items": items})

#(標記是否出餐)
#-------------------------------------------------------------------------------------------
@app.post("/api/orders/mark_served")
def mark_order_served():
    data = request.get_json(force=True)
    order_id = int(data.get("order_id", 0))
    is_served = int(data.get("is_served", 1))

    if order_id <= 0:
        return jsonify({"error": "invalid order_id"}), 400

    conn = db()
    cur = conn.cursor()
    cur.execute("UPDATE orders SET is_served=? WHERE id=?", (is_served, order_id))
    conn.commit()
    conn.close()

    return jsonify({"ok": True})

#(今日營收)
#-------------------------------------------------------------------------------------------
@app.get("/api/orders/today_revenue")
def today_revenue():
    conn = db()
    cur = conn.cursor()
    cur.execute("""
        SELECT COALESCE(SUM(total), 0) AS total_revenue
        FROM orders
        WHERE DATE(created_at) = DATE('now', 'localtime')
    """)
    row = cur.fetchone()
    conn.close()

    return jsonify({"today_revenue": row["total_revenue"]})

#(訂單編號計算)
    """
    不每日自動重置。
    只看當前訂單表的最大 id。
    日結清空後才會回到 1。
    """
#-------------------------------------------------------------------------------------------
@app.get("/api/orders/next_number")
def next_number():
    conn = db()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(MAX(id), 0) AS max_id FROM orders")
    row = cur.fetchone()
    conn.close()

    return jsonify({"next_number": int(row["max_id"]) + 1})

#(歷史訂單查詢)
#-------------------------------------------------------------------------------------------
@app.get("/api/history/by_date")
def history_by_date():
    query_date = request.args.get("date", "").strip()
    if not query_date:
        return jsonify({"error": "missing date"}), 400

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT COALESCE(SUM(total), 0) AS revenue
        FROM history_orders
        WHERE DATE(created_at) = ?
    """, (query_date,))
    revenue_row = cur.fetchone()

    cur.execute("""
        SELECT history_id, original_order_id, created_at, subtotal, discount, total, is_served
        FROM history_orders
        WHERE DATE(created_at) = ?
        ORDER BY history_id DESC
    """, (query_date,))
    orders = [dict(r) for r in cur.fetchall()]

    conn.close()

    return jsonify({
        "date": query_date,
        "revenue": revenue_row["revenue"],
        "orders": orders
    })

#(刪除歷史訂單(以日去做刪除))
#-------------------------------------------------------------------------------------------
@app.post("/api/history/delete_by_date")
def delete_history_by_date():
    data = request.get_json(force=True)
    query_date = str(data.get("date", "")).strip()

    if not query_date:
        return jsonify({"error": "missing date"}), 400

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT history_id
        FROM history_orders
        WHERE DATE(created_at) = ?
    """, (query_date,))
    rows = cur.fetchall()
    history_ids = [r["history_id"] for r in rows]

    if history_ids:
        placeholders = ",".join(["?"] * len(history_ids))

        cur.execute(f"""
            DELETE FROM history_order_items
            WHERE history_order_id IN ({placeholders})
        """, history_ids)

        cur.execute(f"""
            DELETE FROM history_orders
            WHERE history_id IN ({placeholders})
        """, history_ids)

        conn.commit()

    conn.close()

    return jsonify({
        "ok": True,
        "date": query_date,
        "deleted_count": len(history_ids)
    })


#(把當前訂單搬到歷史，再清空當前訂單，並重製單號 (日結的概念)
#-------------------------------------------------------------------------------------------
@app.post("/api/admin/close_day_reset")
def close_day_reset():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, created_at, subtotal, discount, total, is_served
        FROM orders
        ORDER BY id ASC
    """)
    current_orders = cur.fetchall()

    for order in current_orders:
        cur.execute("""
            INSERT INTO history_orders(
                original_order_id, created_at, subtotal, discount, total, is_served
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            order["id"],
            order["created_at"],
            order["subtotal"],
            order["discount"],
            order["total"],
            order["is_served"]
        ))
        history_order_id = cur.lastrowid

        cur.execute("""
            SELECT item_key, name, price, qty, line_total
            FROM order_items
            WHERE order_id=?
            ORDER BY id ASC
        """, (order["id"],))
        items = cur.fetchall()

        for it in items:
            cur.execute("""
                INSERT INTO history_order_items(
                    history_order_id, original_order_id, item_key, name, price, qty, line_total
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                history_order_id,
                order["id"],
                it["item_key"],
                it["name"],
                it["price"],
                it["qty"],
                it["line_total"]
            ))

    cur.execute("DELETE FROM order_items;")
    cur.execute("DELETE FROM orders;")
    cur.execute("DELETE FROM sqlite_sequence WHERE name='order_items';")
    cur.execute("DELETE FROM sqlite_sequence WHERE name='orders';")
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "moved_count": len(current_orders)})


if __name__ == "__main__":
    init_db()

    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

