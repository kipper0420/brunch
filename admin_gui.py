# -*- coding: utf-8 -*-

#(tkinter 圖形介面主套件建立視窗 tk 樣式元件與訊息視窗 urllib.request HTTP請求 datetime 取日期)
#-------------------------------------------------------------------------------------------
import tkinter as tk
from tkinter import ttk, messagebox
import json
import urllib.request
from datetime import datetime

#(設定API)
#-------------------------------------------------------------------------------------------
BACKEND_URL = "http://127.0.0.1:5000"
NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

#(JSON回傳PYTHON)
#-------------------------------------------------------------------------------------------
def api_get(path: str, timeout=8):
    with NO_PROXY_OPENER.open(BACKEND_URL + path, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))

#(API POST 函式：傳入路徑與 payload 字典，送出 JSON 資料給後端)
#-------------------------------------------------------------------------------------------
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

#(歷史訂單查詢視窗)
#-------------------------------------------------------------------------------------------
class HistoryWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)

        self.title("歷史訂單查詢")
        self.geometry("760x560")
        self.transient(master)
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.summary_var = tk.StringVar(value="日期：-    營收：0 元")
        self.build_ui()
        self.query_orders()

    def build_ui(self):
        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")
        ttk.Label(top, text="查詢日期（YYYY-MM-DD）：").pack(side="left")
        ttk.Entry(top, textvariable=self.date_var, width=14).pack(side="left")
        ttk.Button(top, text="查詢", command=self.query_orders).pack(side="left", padx=(8, 0))
        ttk.Button(top, text="🗑 刪除該日期歷史資料", command=self.delete_by_date).pack(side="left", padx=(8, 0))
        ttk.Label(
            self,
            textvariable=self.summary_var,
            font=("Microsoft JhengHei", 11, "bold"),
            foreground="blue"
        ).pack(anchor="w", padx=12, pady=(0, 10))
        cols = ("history_id", "created_at", "total", "status")
        self.tv = ttk.Treeview(self, columns=cols, show="headings", height=20)
        self.tv.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.tv.heading("history_id", text="歷史單號")
        self.tv.heading("created_at", text="日期時間")
        self.tv.heading("total", text="應付")
        self.tv.heading("status", text="狀態")
        self.tv.column("history_id", width=80, anchor="e")
        self.tv.column("created_at", width=220, anchor="w")
        self.tv.column("total", width=100, anchor="e")
        self.tv.column("status", width=100, anchor="center")
        self.tv.tag_configure("served", background="#dff0d8")
        self.tv.tag_configure("normal", background="white")

    def query_orders(self):
        query_date = self.date_var.get().strip()
        if not query_date:
            messagebox.showwarning("提醒", "請輸入日期，例如 2026-03-06")
            return
        try:
            data = api_get(f"/api/history/by_date?date={query_date}")
        except Exception as e:
            messagebox.showerror("錯誤", f"查詢失敗：\n{e}")
            return
        self.tv.delete(*self.tv.get_children())
        revenue = data.get("revenue", 0)
        self.summary_var.set(f"日期：{query_date}    營收：{revenue} 元")
        orders = data.get("orders", [])
        for r in orders:
            served = int(r.get("is_served", 0))
            tag = "served" if served == 1 else "normal"
            status_text = "已出餐" if served == 1 else "未出餐"
            self.tv.insert(
                "",
                "end",
                iid=str(r["history_id"]),
                values=(r["history_id"], r["created_at"], r["total"], status_text),
                tags=(tag,)
            )

    def delete_by_date(self):
        query_date = self.date_var.get().strip()
        if not query_date:
            messagebox.showwarning("提醒", "請先輸入日期")
            return
        if not messagebox.askyesno("確認刪除", f"確定要刪除 {query_date} 的所有歷史訂單資料嗎？"):
            return
        try:
            result = api_post("/api/history/delete_by_date", {"date": query_date})
        except Exception as e:
            messagebox.showerror("錯誤", f"刪除失敗：\n{e}")
            return

        #(取得刪除筆數) 
        deleted_count = result.get("deleted_count", 0)

        #(顯示刪除完成訊息) 
        messagebox.showinfo("完成", f"已刪除 {query_date} 的 {deleted_count} 筆歷史訂單。")

        #(刪除後重新查詢一次畫面) 
        self.query_orders()

        #(如果主視窗有 refresh_orders 方法，也一併刷新主畫面) 
        if hasattr(self.master, "refresh_orders"):
            self.master.refresh_orders()


#(主視窗：後台管理系統，繼承 tk.Tk，代表整個程式的主應用視窗) 
class AdminApp(tk.Tk):
    #(初始化主視窗) 
    def __init__(self):
        super().__init__()

        #(設定主視窗標題) 
        self.title("後台管理（API 控制）")

        #(設定視窗大小) 
        self.geometry("900x720")

        #(記錄自動刷新工作 ID，方便之後取消或追蹤) 
        self.auto_refresh_job = None

        #(建立 UI) 
        self._build_ui()

        #(初次載入時先讀取訂單) 
        self.refresh_orders()

        #(初次載入時讀取菜單) 
        self.refresh_menu()

        #(啟動每 5 秒自動刷新) 
        self.start_auto_refresh()

    #(建立整個主視窗的 UI 版面) 
    def _build_ui(self):
        #(最上方工具區) 
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        #(標題文字) 
        ttk.Label(top, text="🧩 後台管理（API）", font=("Microsoft JhengHei", 14, "bold")).pack(side="left")

        #(顯示後端網址文字) 
        ttk.Label(top, text="後端：").pack(side="left", padx=(20, 0))

        #(後端網址輸入欄位，預設為目前 BACKEND_URL) 
        self.backend_var = tk.StringVar(value=BACKEND_URL)
        ttk.Entry(top, textvariable=self.backend_var, width=35).pack(side="left")

        #(內部函式：套用新後端網址) 
        def apply_backend():
            #(使用 global 代表要修改全域變數 BACKEND_URL) 
            global BACKEND_URL

            #(把輸入框內容更新回全域後端網址) 
            BACKEND_URL = self.backend_var.get().strip()

            #(切換後立刻刷新訂單與菜單) 
            self.refresh_orders()
            self.refresh_menu()

            #(提示使用者已切換完成) 
            messagebox.showinfo("完成", f"已切換後端為：{BACKEND_URL}")

        #(套用後端按鈕) 
        ttk.Button(top, text="套用後端網址", command=apply_backend).pack(side="left", padx=(8, 0))

        #(Notebook 分頁容器) 
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)

        #(建立兩個分頁：訂單管理 / 菜單管理) 
        self.tab_orders = ttk.Frame(self.nb, padding=10)
        self.tab_menu = ttk.Frame(self.nb, padding=10)

        #(加入分頁到 Notebook) 
        self.nb.add(self.tab_orders, text="訂單管理")
        self.nb.add(self.tab_menu, text="菜單管理")

        #(建立訂單頁面) 
        self._build_orders_tab()

        #(建立菜單頁面) 
        self._build_menu_tab()

    #(建立「訂單管理」分頁內容) 
    def _build_orders_tab(self):
        #(工具列區塊) 
        toolbar = ttk.Frame(self.tab_orders)
        toolbar.pack(fill="x")

        #(刷新訂單按鈕) 
        ttk.Button(toolbar, text="🔄 刷新訂單", command=self.refresh_orders).pack(side="left")

        #(標記已出餐按鈕) 
        ttk.Button(toolbar, text="🍽 已出餐", command=self.mark_selected_served).pack(side="left", padx=(8, 0))

        #(取消出餐按鈕) 
        ttk.Button(toolbar, text="↩ 取消出餐", command=self.unmark_selected_served).pack(side="left", padx=(8, 0))

        #(開啟歷史訂單查詢視窗按鈕) 
        ttk.Button(toolbar, text="📜 歷史訂單查詢", command=self.open_history_window).pack(side="left", padx=(8, 0))

        #(日結清空 + 單號重製按鈕) 
        ttk.Button(toolbar, text="🧹 日結清空 + 單號重製", command=self.close_day_reset).pack(side="left", padx=(8, 0))

        #(今日營收顯示區) 
        summary_bar = ttk.Frame(self.tab_orders, padding=(0, 8, 0, 8))
        summary_bar.pack(fill="x")

        #(今日營收變數) 
        self.today_revenue_var = tk.StringVar(value="今日營收：0 元")

        #(今日營收標籤) 
        ttk.Label(
            summary_bar,
            textvariable=self.today_revenue_var,
            font=("Microsoft JhengHei", 11, "bold"),
            foreground="blue"
        ).pack(anchor="w")

        #(中間區塊，左右分成訂單列表與餐點明細) 
        mid = ttk.Frame(self.tab_orders)
        mid.pack(fill="both", expand=True, pady=(10, 0))

        #(左邊：訂單清單區) 
        left = ttk.Frame(mid)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        #(右邊：明細區) 
        right = ttk.Frame(mid)
        right.pack(side="left", fill="both", expand=True)

        #(左側標題) 
        ttk.Label(left, text="當前訂單（每 5 秒自動刷新）", font=("Microsoft JhengHei", 11, "bold")).pack(anchor="w")

        #(建立訂單清單欄位) 
        order_cols = ("id", "created_at", "total", "status")
        self.tv_orders = ttk.Treeview(left, columns=order_cols, show="headings", height=18)
        self.tv_orders.pack(fill="both", expand=True, pady=(6, 0))

        #(設定訂單清單表頭) 
        self.tv_orders.heading("id", text="單號")
        self.tv_orders.heading("created_at", text="日期")
        self.tv_orders.heading("total", text="應付")
        self.tv_orders.heading("status", text="狀態")

        #(設定訂單清單欄寬與對齊) 
        self.tv_orders.column("id", width=60, anchor="e")
        self.tv_orders.column("created_at", width=150, anchor="w")
        self.tv_orders.column("total", width=70, anchor="e")
        self.tv_orders.column("status", width=70, anchor="center")

        #(設定已出餐列底色) 
        self.tv_orders.tag_configure("served", background="#dff0d8")

        #(設定未出餐列底色) 
        self.tv_orders.tag_configure("normal", background="white")

        #(加上垂直捲軸) 
        sb1 = ttk.Scrollbar(left, orient="vertical", command=self.tv_orders.yview)
        sb1.pack(side="right", fill="y")
        self.tv_orders.configure(yscrollcommand=sb1.set)

        #(當使用者選到某張訂單時，觸發 on_select_order 顯示明細) 
        self.tv_orders.bind("<<TreeviewSelect>>", self.on_select_order)

        #(右側標題) 
        ttk.Label(right, text="餐點明細", font=("Microsoft JhengHei", 11, "bold")).pack(anchor="w")

        #(建立餐點明細欄位) 
        item_cols = ("name", "price", "qty", "line_total")
        self.tv_items = ttk.Treeview(right, columns=item_cols, show="headings", height=14)
        self.tv_items.pack(fill="both", expand=True, pady=(6, 0))

        #(設定明細表頭) 
        self.tv_items.heading("name", text="品項")
        self.tv_items.heading("price", text="單價")
        self.tv_items.heading("qty", text="數量")
        self.tv_items.heading("line_total", text="小計")

        #(設定明細欄位大小與對齊) 
        self.tv_items.column("name", width=180, anchor="w")
        self.tv_items.column("price", width=60, anchor="e")
        self.tv_items.column("qty", width=60, anchor="e")
        self.tv_items.column("line_total", width=80, anchor="e")

        #(加入明細捲軸) 
        sb2 = ttk.Scrollbar(right, orient="vertical", command=self.tv_items.yview)
        sb2.pack(side="right", fill="y")
        self.tv_items.configure(yscrollcommand=sb2.set)

        #(右下角訂單摘要資訊區) 
        info = ttk.Frame(right, padding=(0, 10, 0, 0))
        info.pack(fill="x")

        #(建立顯示用變數) 
        self.subtotal_var = tk.StringVar(value="0")
        self.discount_var = tk.StringVar(value="0")
        self.total_var = tk.StringVar(value="0")
        self.order_id_var = tk.StringVar(value="-")
        self.date_var = tk.StringVar(value="-")

        #(以下是訂單摘要顯示欄位) 
        ttk.Label(info, text="單號：", font=("Microsoft JhengHei", 10, "bold")).grid(row=0, column=0, sticky="e", padx=(0, 8))
        ttk.Label(info, textvariable=self.order_id_var).grid(row=0, column=1, sticky="w")

        ttk.Label(info, text="日期：", font=("Microsoft JhengHei", 10, "bold")).grid(row=1, column=0, sticky="e", padx=(0, 8))
        ttk.Label(info, textvariable=self.date_var).grid(row=1, column=1, sticky="w")

        ttk.Label(info, text="小計：", font=("Microsoft JhengHei", 10, "bold")).grid(row=2, column=0, sticky="e", padx=(0, 8))
        ttk.Label(info, textvariable=self.subtotal_var).grid(row=2, column=1, sticky="w")

        ttk.Label(info, text="折扣：", font=("Microsoft JhengHei", 10, "bold")).grid(row=3, column=0, sticky="e", padx=(0, 8))
        ttk.Label(info, textvariable=self.discount_var).grid(row=3, column=1, sticky="w")

        ttk.Label(info, text="應付：", font=("Microsoft JhengHei", 10, "bold")).grid(row=4, column=0, sticky="e", padx=(0, 8))
        ttk.Label(info, textvariable=self.total_var).grid(row=4, column=1, sticky="w")

    #(開啟歷史訂單查詢子視窗) 
    def open_history_window(self):
        HistoryWindow(self)

    #(刷新今日營收顯示) 
    def refresh_today_revenue(self):
        try:
            #(向後端取得今日營收) 
            data = api_get("/api/orders/today_revenue")
            revenue = data.get("today_revenue", 0)
            self.today_revenue_var.set(f"今日營收：{revenue} 元")
        except Exception:
            #(若讀取失敗，顯示錯誤字樣) 
            self.today_revenue_var.set("今日營收：讀取失敗")

    #(刷新目前訂單清單) 
    def refresh_orders(self):
        try:
            #(向後端取得最多 200 筆訂單) 
            rows = api_get("/api/orders?limit=200")
        except Exception:
            self.today_revenue_var.set("今日營收：讀取失敗")
            return

        #(記住目前有沒有選中的訂單，刷新後盡量維持選取狀態) 
        current_selection = self.tv_orders.selection()
        selected_id = current_selection[0] if current_selection else None

        #(清空舊資料) 
        self.tv_orders.delete(*self.tv_orders.get_children())

        #(逐筆重新加入訂單) 
        for r in rows:
            served = int(r.get("is_served", 0))
            tag = "served" if served == 1 else "normal"
            status_text = "已出餐" if served == 1 else "未出餐"

            self.tv_orders.insert(
                "",
                "end",
                iid=str(r["id"]),
                values=(r["id"], r["created_at"], r["total"], status_text),
                tags=(tag,)
            )

        #(如果剛剛有選取的那筆刷新後還存在，就重新選回去) 
        if selected_id and self.tv_orders.exists(selected_id):
            self.tv_orders.selection_set(selected_id)
            self.tv_orders.focus(selected_id)
            self.on_select_order()

        #(順便更新今日營收) 
        self.refresh_today_revenue()

    #(每 5 秒自動刷新一次訂單資料) 
    def start_auto_refresh(self):
        #(先刷新一次) 
        self.refresh_orders()

        #(5 秒後再次呼叫自己，形成循環刷新) 
        self.auto_refresh_job = self.after(5000, self.start_auto_refresh)

    #(當使用者選取某筆訂單時，讀取其明細資料) 
    def on_select_order(self, _=None):
        #(取得目前被選中的訂單) 
        sel = self.tv_orders.selection()

        #(如果沒有選任何訂單，就把右邊明細清空) 
        if not sel:
            self.tv_items.delete(*self.tv_items.get_children())
            self.order_id_var.set("-")
            self.date_var.set("-")
            self.subtotal_var.set("0")
            self.discount_var.set("0")
            self.total_var.set("0")
            return

        #(Treeview 的 iid 就是訂單 id，所以直接轉成 int) 
        order_id = int(sel[0])

        #(呼叫後端查詢該筆訂單詳細資料) 
        try:
            data = api_get(f"/api/orders/{order_id}")
        except Exception as e:
            messagebox.showerror("錯誤", f"讀取明細失敗：\n{e}")
            return

        #(後端預期回傳 order 與 items) 
        order = data["order"]
        items = data["items"]

        #(先清空明細表格) 
        self.tv_items.delete(*self.tv_items.get_children())

        #(更新右下角摘要資訊) 
        self.order_id_var.set(str(order["id"]))
        self.date_var.set(order["created_at"])
        self.subtotal_var.set(str(order["subtotal"]))
        self.discount_var.set(f"-{order['discount']}")
        self.total_var.set(str(order["total"]))

        #(如果沒有餐點明細，就顯示無明細) 
        if not items:
            self.tv_items.insert("", "end", values=("（無明細）", "", "", ""))
            return

        #(逐筆顯示餐點明細) 
        for it in items:
            self.tv_items.insert("", "end", values=(it["name"], it["price"], it["qty"], it["line_total"]))

    #(把選到的訂單標記成已出餐) 
    def mark_selected_served(self):
        sel = self.tv_orders.selection()
        if not sel:
            messagebox.showwarning("提醒", "請先選擇一筆訂單")
            return

        order_id = int(sel[0])

        try:
            #(送給後端：此單 is_served 設成 1) 
            api_post("/api/orders/mark_served", {"order_id": order_id, "is_served": 1})
        except Exception as e:
            messagebox.showerror("錯誤", f"標記已出餐失敗：\n{e}")
            return

        #(成功後刷新畫面) 
        self.refresh_orders()

    #(把選到的訂單取消已出餐狀態) 
    def unmark_selected_served(self):
        sel = self.tv_orders.selection()
        if not sel:
            messagebox.showwarning("提醒", "請先選擇一筆訂單")
            return

        order_id = int(sel[0])

        try:
            #(送給後端：此單 is_served 設成 0) 
            api_post("/api/orders/mark_served", {"order_id": order_id, "is_served": 0})
        except Exception as e:
            messagebox.showerror("錯誤", f"取消出餐失敗：\n{e}")
            return

        self.refresh_orders()

    #(執行日結：把目前訂單搬到歷史資料，並清空當前訂單、重製單號) 
    def close_day_reset(self):
        msg = (
            "確定要『日結清空 + 單號重製』嗎？\n\n"
            "目前訂單會搬到歷史資料，然後清空當前訂單。\n"
            "歷史資料會永久保留。"
        )

        #(先詢問確認) 
        if not messagebox.askyesno("確認", msg):
            return

        try:
            #(呼叫後端執行日結) 
            result = api_post("/api/admin/close_day_reset", {})
        except Exception as e:
            messagebox.showerror("錯誤", f"日結失敗：\n{e}")
            return

        #(取得搬移到歷史的筆數) 
        moved_count = result.get("moved_count", 0)

        #(提示完成) 
        messagebox.showinfo("完成", f"日結完成，已搬移 {moved_count} 筆訂單到歷史資料。")

        #(刷新畫面) 
        self.refresh_orders()

    #(建立「菜單管理」分頁內容) 
    def _build_menu_tab(self):
        #(菜單工具列) 
        toolbar = ttk.Frame(self.tab_menu)
        toolbar.pack(fill="x")

        ttk.Button(toolbar, text="🔄 刷新菜單", command=self.refresh_menu).pack(side="left")
        ttk.Button(toolbar, text="✅ 上架", command=lambda: self.toggle_selected(1)).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="🚫 下架", command=lambda: self.toggle_selected(0)).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="🗑 刪除菜單", command=self.delete_selected_menu).pack(side="left", padx=(8, 0))

        #(中間左右區塊) 
        mid = ttk.Frame(self.tab_menu)
        mid.pack(fill="both", expand=True, pady=(10, 0))

        #(左邊菜單列表) 
        left = ttk.Frame(mid)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))

        #(右邊表單區) 
        right = ttk.Frame(mid)
        right.pack(side="left", fill="y")

        #(左側標題) 
        ttk.Label(left, text="菜單列表（含下架）", font=("Microsoft JhengHei", 11, "bold")).pack(anchor="w")

        #(建立菜單清單欄位) 
        cols = ("item_key", "name", "category", "price", "is_active")
        self.tv_menu = ttk.Treeview(left, columns=cols, show="headings", height=18, selectmode="browse")
        self.tv_menu.pack(fill="both", expand=True, pady=(6, 0))

        #(表頭設定) 
        self.tv_menu.heading("item_key", text="Key")
        self.tv_menu.heading("name", text="品名")
        self.tv_menu.heading("category", text="分類")
        self.tv_menu.heading("price", text="價格")
        self.tv_menu.heading("is_active", text="狀態")

        #(欄位大小與對齊) 
        self.tv_menu.column("item_key", width=90, anchor="w")
        self.tv_menu.column("name", width=140, anchor="w")
        self.tv_menu.column("category", width=70, anchor="w")
        self.tv_menu.column("price", width=60, anchor="e")
        self.tv_menu.column("is_active", width=60, anchor="center")

        #(加入捲軸) 
        sb = ttk.Scrollbar(left, orient="vertical", command=self.tv_menu.yview)
        sb.pack(side="right", fill="y")
        self.tv_menu.configure(yscrollcommand=sb.set)

        #(選取某菜單時，載入到右邊表單) 
        self.tv_menu.bind("<<TreeviewSelect>>", self.on_select_menu)

        #(右側標題) 
        ttk.Label(right, text="新增 / 修改", font=("Microsoft JhengHei", 11, "bold")).pack(anchor="w")

        #(表單區) 
        form = ttk.Frame(right, padding=(0, 6, 0, 0))
        form.pack(fill="x")

        #(建立表單變數) 
        self.mk_key = tk.StringVar()
        self.mk_name = tk.StringVar()
        self.mk_cat = tk.StringVar()
        self.mk_price = tk.StringVar()
        self.mk_active = tk.IntVar(value=1)

        #(內部小函式：建立一列標籤+輸入框) 
        def row(label, var, r, entry_width=24):
            ttk.Label(form, text=label).grid(row=r, column=0, sticky="e", pady=4, padx=(0, 8))
            ttk.Entry(form, textvariable=var, width=entry_width).grid(row=r, column=1, sticky="w", pady=4)

        #(建立四個輸入欄位) 
        row("Key：", self.mk_key, 0)
        row("品名：", self.mk_name, 1)
        row("分類：", self.mk_cat, 2)
        row("價格：", self.mk_price, 3)

        #(上架勾選框) 
        ttk.Checkbutton(form, text="上架", variable=self.mk_active).grid(row=4, column=1, sticky="w", pady=6)

        #(操作說明文字) 
        tip = (
            "說明：\n"
            "1) Key 可留空，系統會自動產生 item_1、item_2...\n"
            "2) 若要修改既有資料，可先點左邊菜單再儲存\n"
            "3) 分類請用：漢堡 / 吐司 / 蛋餅 / 單點 / 飲品"
        )
        ttk.Label(form, text=tip, foreground="gray").grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))

        #(下方按鈕區) 
        btns = ttk.Frame(right, padding=(0, 10, 0, 0))
        btns.pack(fill="x")
        ttk.Button(btns, text="💾 儲存（新增/修改）", command=self.save_menu).pack(fill="x")
        ttk.Button(btns, text="🧼 清空表單", command=self.clear_menu_form).pack(fill="x", pady=(6, 0))

    #(刷新菜單列表) 
    def refresh_menu(self):
        try:
            #(向後端取得全部菜單，包含下架資料) 
            rows = api_get("/api/menu/all")
        except Exception as e:
            messagebox.showerror("錯誤", f"讀取菜單失敗：\n{e}")
            return

        #(清空舊菜單資料) 
        self.tv_menu.delete(*self.tv_menu.get_children())

        #(逐筆加入菜單列表) 
        for r in rows:
            status = "上架" if int(r["is_active"]) == 1 else "下架"
            self.tv_menu.insert(
                "",
                "end",
                iid=r["item_key"],
                values=(r["item_key"], r["name"], r["category"], r["price"], status)
            )

    #(當選取左邊菜單時，把資料帶入右邊表單方便修改) 
    def on_select_menu(self, _=None):
        sel = self.tv_menu.selection()
        if not sel:
            return

        #(取得被選到那筆的 iid) 
        iid = sel[0]

        #(取得該列 values) 
        vals = self.tv_menu.item(iid, "values")

        #(將資料填入右邊欄位) 
        self.mk_key.set(vals[0])
        self.mk_name.set(vals[1])
        self.mk_cat.set(vals[2])
        self.mk_price.set(vals[3])
        self.mk_active.set(1 if vals[4] == "上架" else 0)

    #(清空菜單表單內容) 
    def clear_menu_form(self):
        self.mk_key.set("")
        self.mk_name.set("")
        self.mk_cat.set("")
        self.mk_price.set("")
        self.mk_active.set(1)

    #(儲存菜單，可同時用於新增與修改) 
    def save_menu(self):
        #(讀取表單內容並去除空白) 
        item_key = self.mk_key.get().strip()
        name = self.mk_name.get().strip()
        category = self.mk_cat.get().strip()
        price_str = self.mk_price.get().strip()

        #(基本欄位檢查) 
        if not name or not category or not price_str:
            messagebox.showwarning("提醒", "品名 / 分類 / 價格 都要填")
            return

        #(價格必須是正整數) 
        try:
            price = int(price_str)
            if price <= 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("提醒", "價格要是正整數")
            return

        #(組成送往後端的資料) 
        payload = {
            "item_key": item_key,
            "name": name,
            "category": category,
            "price": price,
            "is_active": int(self.mk_active.get())
        }

        #(呼叫後端 upsert API，讓後端自行判斷是新增還是修改) 
        try:
            result = api_post("/api/menu/upsert", payload)
        except Exception as e:
            messagebox.showerror("錯誤", f"儲存失敗：\n{e}")
            return

        #(如果後端有自動產生 key，就取回顯示) 
        auto_key = result.get("item_key", item_key)

        #(提示儲存完成) 
        messagebox.showinfo("完成", f"已儲存菜單。\nKey：{auto_key}")

        #(刷新清單並清空表單) 
        self.refresh_menu()
        self.clear_menu_form()

    #(切換所選菜單的上架/下架狀態) 
    def toggle_selected(self, is_active: int):
        sel = self.tv_menu.selection()
        if not sel:
            messagebox.showwarning("提醒", "請先選一筆菜單")
            return

        #(取得所選菜單的 key) 
        item_key = sel[0]

        try:
            #(送給後端更新狀態) 
            api_post("/api/menu/toggle", {"item_key": item_key, "is_active": is_active})
        except Exception as e:
            messagebox.showerror("錯誤", f"更新狀態失敗：\n{e}")
            return

        self.refresh_menu()

    #(刪除選取的菜單) 
    def delete_selected_menu(self):
        sel = self.tv_menu.selection()
        if not sel:
            messagebox.showwarning("提醒", "請先選一筆菜單")
            return

        #(取得菜單 key) 
        item_key = sel[0]

        #(取出顯示名稱，讓確認訊息更清楚) 
        vals = self.tv_menu.item(item_key, "values")
        item_name = vals[1] if len(vals) > 1 else item_key

        #(刪除前再次確認) 
        if not messagebox.askyesno("確認刪除", f"確定要刪除菜單：{item_name}（{item_key}）嗎？"):
            return

        try:
            #(呼叫後端刪除 API) 
            api_post("/api/menu/delete", {"item_key": item_key})
        except Exception as e:
            messagebox.showerror("錯誤", f"刪除失敗：\n{e}")
            return

        #(提示成功) 
        messagebox.showinfo("完成", "已刪除菜單。")

        #(刷新列表並清空表單) 
        self.refresh_menu()
        self.clear_menu_form()


#(Python 主程式入口，只有直接執行此檔案時才會啟動 GUI) 
if __name__ == "__main__":
    #(建立主視窗物件並進入事件迴圈，讓程式持續顯示與等待操作) 
    AdminApp().mainloop()