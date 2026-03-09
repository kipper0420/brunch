# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox
import json
import urllib.request
import urllib.error

BACKEND_URL = "http://127.0.0.1:5000"
NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def api_get(path: str, timeout=8):
    with NO_PROXY_OPENER.open(BACKEND_URL + path, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def api_post(path: str, payload: dict, timeout=8):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        BACKEND_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with NO_PROXY_OPENER.open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def calc_discount(subtotal: int) -> int:
    if subtotal >= 500:
        return int(subtotal * 0.15)
    if subtotal >= 300:
        return int(subtotal * 0.05)
    return 0


def fetch_menu_from_backend():
    return api_get("/api/menu")


root = tk.Tk()
root.title("點餐系統")
root.geometry("460x800")

style = ttk.Style()
try:
    style.theme_use("clam")
except Exception:
    pass

order_no_var = tk.StringVar(value="1")
total_var = tk.StringVar(value="總金額：0 元")

items = {}
DISPLAY = {}
MENU = []
CATEGORIES = []
tabs = {}
notebook = None


def refresh_order_number():
    try:
        data = api_get("/api/orders/next_number")
        next_number = data.get("next_number", 1)
        order_no_var.set(str(next_number))
    except Exception:
        order_no_var.set("讀取失敗")


def recalc_total():
    subtotal = 0
    for _, data in items.items():
        if data["checked"].get() == 1:
            subtotal += data["price"] * data["qty_var"].get()

    discount = calc_discount(subtotal)
    total = subtotal - discount

    if discount > 0:
        total_var.set(f"小計：{subtotal} 元  折扣：-{discount} 元\n應付：{total} 元")
    else:
        total_var.set(f"總金額：{total} 元")


def get_cart_summary():
    lines = []
    subtotal = 0

    for key, data in items.items():
        if data["checked"].get() == 1:
            qty = data["qty_var"].get()
            if qty <= 0:
                continue
            price = data["price"]
            name = DISPLAY.get(key, key)
            line_total = price * qty
            lines.append((key, name, price, qty, line_total))
            subtotal += line_total

    discount = calc_discount(subtotal)
    total = subtotal - discount
    return lines, subtotal, discount, total


def on_toggle(key):
    data = items[key]
    if data["checked"].get() == 1:
        if data["qty_var"].get() == 0:
            data["qty_var"].set(1)
    else:
        data["qty_var"].set(0)
    recalc_total()


def add_qty(key):
    data = items[key]
    if data["checked"].get() == 0:
        data["checked"].set(1)
    data["qty_var"].set(data["qty_var"].get() + 1)
    recalc_total()


def sub_qty(key):
    data = items[key]
    q = data["qty_var"].get()
    if q > 0:
        data["qty_var"].set(q - 1)
    if data["qty_var"].get() == 0:
        data["checked"].set(0)
    recalc_total()


def clear_all():
    for _, data in items.items():
        data["checked"].set(0)
        data["qty_var"].set(0)
    recalc_total()


def submit_order_to_backend():
    lines, subtotal, discount, total = get_cart_summary()
    if not lines:
        messagebox.showwarning("提醒", "目前沒有點餐內容，無法送出")
        return False

    payload = {
        "subtotal": subtotal,
        "discount": discount,
        "total": total,
        "items": [
            {"key": key, "name": name, "price": price, "qty": qty, "line_total": line_total}
            for (key, name, price, qty, line_total) in lines
        ]
    }

    try:
        result = api_post("/api/orders", payload, timeout=10)
    except urllib.error.URLError as e:
        messagebox.showerror("錯誤", f"送出失敗：無法連線後端\n{e}")
        return False
    except Exception as e:
        messagebox.showerror("錯誤", f"送出失敗：{e}")
        return False

    order_id = result.get("order_id")
    messagebox.showinfo("成功", f"訂單已送出！系統流水號：{order_id}")
    clear_all()
    refresh_order_number()
    return True


top = ttk.Frame(root, padding=12)
top.pack(fill="x")

ttk.Label(
    top,
    text="✅ 勾選或用 +/- 調整數量（可多選）",
    font=("Microsoft JhengHei", 10, "bold")
).pack(anchor="w")

ttk.Label(
    top,
    text="(滿300 95折!!!!  滿500 85折!!!!)",
    font=("Microsoft JhengHei", 10, "bold")
).pack(anchor="w")

frame_order = ttk.Frame(top)
frame_order.pack(anchor="w", pady=(4, 0))

ttk.Label(
    frame_order,
    text="你的訂單編號為：",
    font=("Microsoft JhengHei", 10, "bold")
).pack(side="left")

ttk.Label(
    frame_order,
    textvariable=order_no_var,
    font=("Microsoft JhengHei", 10, "bold")
).pack(side="left")

ttk.Label(
    top,
    textvariable=total_var,
    font=("Microsoft JhengHei", 10, "bold")
).pack(side="left")

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True, padx=12, pady=6)


def build_menu_ui(menu_rows):
    global MENU, DISPLAY, CATEGORIES, items, tabs

    for tab_id in notebook.tabs():
        notebook.forget(tab_id)

    tabs.clear()
    items.clear()
    DISPLAY.clear()
    MENU.clear()

    category_order_map = {
        "漢堡": 1,
        "吐司": 2,
        "蛋餅": 3,
        "單點": 4,
        "飲品": 5
    }

    sorted_rows = sorted(
        menu_rows,
        key=lambda r: (
            category_order_map.get(r["category"], 999),
            int(r["price"]),
            r["name"]
        )
    )

    for r in sorted_rows:
        key = r["item_key"]
        name = r["name"]
        cat = r["category"]
        price = int(r["price"])

        DISPLAY[key] = name
        MENU.append((key, price, cat))

    category_order = ["漢堡", "吐司", "蛋餅", "單點", "飲品"]
    existing_categories = {cat for _, _, cat in MENU}
    CATEGORIES[:] = [cat for cat in category_order if cat in existing_categories]
    CATEGORIES += [cat for cat in existing_categories if cat not in category_order]

    for cat in CATEGORIES:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text=cat)
        tabs[cat] = frame

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=0)
        frame.columnconfigure(2, weight=0)
        frame.columnconfigure(3, weight=0)
        frame.columnconfigure(4, weight=0)

        ttk.Label(frame, text="品項", font=("Microsoft JhengHei", 10, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(frame, text="單價", font=("Microsoft JhengHei", 10, "bold")).grid(row=0, column=1, sticky="e", pady=(0, 6))
        ttk.Label(frame, text="數量", font=("Microsoft JhengHei", 10, "bold")).grid(row=0, column=2, sticky="e", pady=(0, 6))

    row_index = {cat: 1 for cat in CATEGORIES}

    for key, price, cat in MENU:
        frame = tabs[cat]
        r = row_index[cat]

        checked = tk.IntVar(value=0)
        qty_var = tk.IntVar(value=0)
        items[key] = {
            "price": price,
            "name": DISPLAY.get(key, key),
            "category": cat,
            "checked": checked,
            "qty_var": qty_var
        }

        cb = ttk.Checkbutton(
            frame,
            text=DISPLAY.get(key, key),
            variable=checked,
            command=lambda k=key: on_toggle(k)
        )
        cb.grid(row=r, column=0, sticky="w", pady=4)

        ttk.Label(frame, text=f"{price}", width=6, anchor="e").grid(row=r, column=1, sticky="e", padx=(6, 0))
        ttk.Label(frame, textvariable=qty_var, width=4, anchor="e").grid(row=r, column=2, sticky="e", padx=(6, 0))

        ttk.Button(frame, text="＋", width=3, command=lambda k=key: add_qty(k)).grid(row=r, column=3, padx=(10, 2))
        ttk.Button(frame, text="－", width=3, command=lambda k=key: sub_qty(k)).grid(row=r, column=4)

        row_index[cat] += 1

    recalc_total()


def open_cart():
    win = tk.Toplevel(root)
    win.title("🛒 購物車")
    win.geometry("480x650")
    win.transient(root)

    topf = ttk.Frame(win, padding=12)
    topf.pack(fill="x")
    ttk.Label(topf, text="已點餐點明細", font=("Microsoft JhengHei", 12, "bold")).pack(anchor="w")

    tablef = ttk.Frame(win, padding=12)
    tablef.pack(fill="both", expand=True)

    cols = ("name", "price", "qty", "sum")
    tv = ttk.Treeview(tablef, columns=cols, show="headings", height=12, selectmode="browse")
    tv.pack(side="left", fill="both", expand=True)

    tv.heading("name", text="品項")
    tv.heading("price", text="單價")
    tv.heading("qty", text="數量")
    tv.heading("sum", text="小計")

    tv.column("name", width=220, anchor="w")
    tv.column("price", width=70, anchor="e")
    tv.column("qty", width=70, anchor="e")
    tv.column("sum", width=80, anchor="e")

    scrollbar = ttk.Scrollbar(tablef, orient="vertical", command=tv.yview)
    scrollbar.pack(side="right", fill="y")
    tv.configure(yscrollcommand=scrollbar.set)

    botf = ttk.Frame(win, padding=12)
    botf.pack(fill="x")

    subtotal_var = tk.StringVar(value="0 元")
    discount_var = tk.StringVar(value="-0 元")
    total_pay_var = tk.StringVar(value="0 元")

    ttk.Label(botf, text="小計：", font=("Microsoft JhengHei", 10, "bold")).grid(row=0, column=0, sticky="e", padx=(0, 10))
    ttk.Label(botf, textvariable=subtotal_var, font=("Microsoft JhengHei", 10, "bold")).grid(row=0, column=1, sticky="e")

    ttk.Label(botf, text="折扣：", font=("Microsoft JhengHei", 10, "bold")).grid(row=1, column=0, sticky="e", padx=(0, 10))
    ttk.Label(botf, textvariable=discount_var, font=("Microsoft JhengHei", 10, "bold")).grid(row=1, column=1, sticky="e")

    ttk.Label(botf, text="應付：", font=("Microsoft JhengHei", 10, "bold")).grid(row=2, column=0, sticky="e", padx=(0, 10))
    ttk.Label(botf, textvariable=total_pay_var, font=("Microsoft JhengHei", 10, "bold")).grid(row=2, column=1, sticky="e")

    def refresh_cart():
        tv.delete(*tv.get_children())
        lines, subtotal, discount, total = get_cart_summary()

        if not lines:
            tv.insert("", "end", iid="__empty__", values=("（目前尚未點餐）", "", "", ""))
        else:
            for key, name, price, qty, line_total in lines:
                tv.insert("", "end", iid=key, values=(name, price, qty, line_total))

        subtotal_var.set(f"{subtotal} 元")
        discount_var.set(f"-{discount} 元")
        total_pay_var.set(f"{total} 元")
        recalc_total()

    def get_selected_key():
        sel = tv.selection()
        if not sel:
            return None
        key = sel[0]
        if key == "__empty__":
            return None
        return key

    def cart_add():
        key = get_selected_key()
        if not key:
            messagebox.showwarning("提醒", "請先選擇一個品項")
            return
        add_qty(key)
        refresh_cart()

    def cart_sub():
        key = get_selected_key()
        if not key:
            messagebox.showwarning("提醒", "請先選擇一個品項")
            return
        sub_qty(key)
        refresh_cart()

    def cart_delete():
        key = get_selected_key()
        if not key:
            messagebox.showwarning("提醒", "請先選擇一個品項")
            return
        items[key]["checked"].set(0)
        items[key]["qty_var"].set(0)
        refresh_cart()

    def on_double_click(_):
        key = get_selected_key()
        if key:
            add_qty(key)
            refresh_cart()

    tv.bind("<Double-1>", on_double_click)

    actionf = ttk.Frame(win, padding=(12, 0, 12, 12))
    actionf.pack(fill="x")
    ttk.Button(actionf, text="＋ 數量", command=cart_add).pack(side="left")
    ttk.Button(actionf, text="－ 數量", command=cart_sub).pack(side="left", padx=(6, 0))
    ttk.Button(actionf, text="🗑 刪除", command=cart_delete).pack(side="left", padx=(6, 0))

    btnf = ttk.Frame(win, padding=12)
    btnf.pack(fill="x")

    ttk.Button(btnf, text="返回選單", command=win.destroy).pack(side="left")

    def do_submit():
        ok = submit_order_to_backend()
        if ok:
            win.destroy()

    ttk.Button(btnf, text="送出", command=do_submit).pack(side="right")

    refresh_cart()


def refresh_menu():
    try:
        menu_rows = fetch_menu_from_backend()
    except Exception as e:
        messagebox.showerror("錯誤", f"抓取菜單失敗：\n{e}\n\n請確認 backend.py 有在跑。")
        return

    if not menu_rows:
        messagebox.showwarning("提醒", "後端菜單是空的，請先用後台新增菜單。")
    build_menu_ui(menu_rows)
    refresh_order_number()


bottom = ttk.Frame(root, padding=12)
bottom.pack(fill="x")

ttk.Button(bottom, text="清空全部", command=clear_all).pack(side="left")
ttk.Button(bottom, text="🔄 刷新菜單", command=refresh_menu).pack(side="left", padx=(8, 0))
ttk.Button(bottom, text="購物車", command=open_cart).pack(side="right")

try:
    rows = fetch_menu_from_backend()
    if not rows:
        messagebox.showwarning("提醒", "後端菜單目前是空的，請先開 admin_gui 新增菜單。")
    build_menu_ui(rows)
    refresh_order_number()
except Exception as e:
    messagebox.showerror("錯誤", f"無法連線後端抓菜單：\n{e}\n\n請先啟動 backend.py")
    root.destroy()

root.mainloop()