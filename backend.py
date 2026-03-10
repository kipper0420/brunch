# -*- coding: utf-8 -*-
#(套件)
#---------------------------------------------------------
from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime

DB_PATH = "orders.db"
app = Flask(__name__)


#(資料庫連線)
#---------------------------------------------------------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


#(初始化資料庫)
#---------------------------------------------------------
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

#(終端機顯示訂單)
#---------------------------------------------------------
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
    print(f"總金額: {order['total']} 元")
    print("-" * 42)
    print("餐點明細:")
    for it in items:
        print(f"- {it['name']} {it['price']} x{it['qty']} = {it['line_total']}")

    print("-" * 42)
    print(f"小計: {order['subtotal']}  折扣: -{order['discount']}  應付: {order['total']}")
    print("=" * 42 + "\n")

#(健康檢查API)
#---------------------------------------------------------
@app.get("/api/health")
def health():
    return jsonify({"ok": True})

#(取得菜單)
#---------------------------------------------------------
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

#(取得全部菜單)
#---------------------------------------------------------
@app.get("/api/menu/all")
def get_menu_all():

    conn = db()
    cur = conn.cursor()

    cur.execute("""
        SELECT item_key, name, category, price, is_active
        FROM menu
    """)

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    return jsonify(rows)

#(新增或更新菜單)
#---------------------------------------------------------
@app.post("/api/menu/upsert")
def upsert_menu():

    data = request.get_json(force=True)

    item_key = str(data.get("item_key", "")).strip()
    name = str(data.get("name", "")).strip()
    category = str(data.get("category", "")).strip()
    price = int(data.get("price", 0))
    is_active = int(data.get("is_active", 1))

    if not name or not category or price <= 0:
        return jsonify({"error": "invalid payload"}), 400

    conn = db()
    cur = conn.cursor()

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

#(啟用/停用菜單)
#---------------------------------------------------------
@app.post("/api/menu/toggle")
def toggle_menu():

    data = request.get_json(force=True)
    item_key = str(data.get("item_key", "")).strip()
    is_active = int(data.get("is_active", 1))

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE menu SET is_active=? WHERE item_key=?",
        (is_active, item_key)
    )

    conn.commit()
    conn.close()

    return jsonify({"ok": True})
    
#(建立訂單)
#---------------------------------------------------------
@app.post("/api/orders")
def create_order():

    data = request.get_json(force=True)

    items = data.get("items", [])
    subtotal = int(data.get("subtotal", 0))
    discount = int(data.get("discount", 0))
    total = int(data.get("total", 0))

    if not items:
        return jsonify({"error": "empty order"}), 400

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

#(取得訂單列表)
#---------------------------------------------------------
@app.get("/api/orders")
def list_orders():

    conn = db()
    cur = conn.cursor()

    cur.execute("""
    SELECT id, created_at, subtotal, discount, total, is_served
    FROM orders
    ORDER BY id DESC
    """)

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    return jsonify(rows)

#(日結並清空訂單)
#---------------------------------------------------------
@app.post("/api/admin/close_day_reset")
def close_day_reset():

    conn = db()
    cur = conn.cursor()

    cur.execute("DELETE FROM order_items")
    cur.execute("DELETE FROM orders")

    cur.execute("DELETE FROM sqlite_sequence WHERE name='orders'")
    cur.execute("DELETE FROM sqlite_sequence WHERE name='order_items'")

    conn.commit()
    conn.close()

    return jsonify({"ok": True})

#(主程式啟動)
#---------------------------------------------------------
if __name__ == "__main__":
    init_db()
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False
    )
