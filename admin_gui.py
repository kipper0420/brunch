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

#(GET 請求 API 並將 JSON 回傳轉為 Python 物件)
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
    #(初始化歷史訂單視窗)
    #-------------------------------------------------------------------------------------------
    def __init__(self, master):
        super().__init__(master)
        self.title("歷史訂單查詢")
        self.geometry("760x560")
        self.transient(master)
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.summary_var = tk.StringVar(value="日期：-    營收：0 元")
        self.build_ui()
        self.query_orders()

    #(建立歷史訂單查詢 UI)
    #-------------------------------------------------------------------------------------------
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

    #(依日期查詢歷史訂單)
    #-------------------------------------------------------------------------------------------
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

    #(刪除指定日期歷史訂單)
    #-------------------------------------------------------------------------------------------
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
        deleted_count = result.get("deleted_count", 0)
        messagebox.showinfo("完成", f"已刪除 {query_date} 的 {deleted_count} 筆歷史訂單。")
        self.query_orders()
        if hasattr(self.master, "refresh_orders"):
            self.master.refresh_orders()

#(主後台管理視窗)
#-------------------------------------------------------------------------------------------
class AdminApp(tk.Tk):
    #(初始化主視窗)
    #-------------------------------------------------------------------------------------------
    def __init__(self):
        super().__init__()
        self.title("後台管理（API 控制）")
        self.geometry("900x720")
        self.auto_refresh_job = None
        self._build_ui()
        self.refresh_orders()
        self.refresh_menu()
        self.start_auto_refresh()
        
    #(建立主UI)
    #-------------------------------------------------------------------------------------------
    def _build_ui(self):

        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="🧩 後台管理（API）", font=("Microsoft JhengHei", 14, "bold")).pack(side="left")
        ttk.Label(top, text="後端：").pack(side="left", padx=(20, 0))
        self.backend_var = tk.StringVar(value=BACKEND_URL)
        ttk.Entry(top, textvariable=self.backend_var, width=35).pack(side="left")
        #(切換後端API網址)
        #-------------------------------------------------------------------------------------------
        def apply_backend():
            global BACKEND_URL
            BACKEND_URL = self.backend_var.get().strip()
            self.refresh_orders()
            self.refresh_menu()
            messagebox.showinfo("完成", f"已切換後端為：{BACKEND_URL}")
        ttk.Button(top, text="套用後端網址", command=apply_backend).pack(side="left", padx=(8, 0))
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_orders = ttk.Frame(self.nb, padding=10)
        self.tab_menu = ttk.Frame(self.nb, padding=10)
        self.nb.add(self.tab_orders, text="訂單管理")
        self.nb.add(self.tab_menu, text="菜單管理")
        self._build_orders_tab()
        self._build_menu_tab()
        
    #(開啟歷史訂單查詢視窗)
    #-------------------------------------------------------------------------------------------
    def open_history_window(self):
        HistoryWindow(self)
        
    #(取得今日營收)
    #-------------------------------------------------------------------------------------------
    def refresh_today_revenue(self):
        try:
            data = api_get("/api/orders/today_revenue")
            revenue = data.get("today_revenue", 0)
            self.today_revenue_var.set(f"今日營收：{revenue} 元")
        except Exception:
            self.today_revenue_var.set("今日營收：讀取失敗")
            
    #(刷新訂單列表)
    #-------------------------------------------------------------------------------------------
    def refresh_orders(self):
        try:
            rows = api_get("/api/orders?limit=200")
        except Exception:
            self.today_revenue_var.set("今日營收：讀取失敗")
            return
        current_selection = self.tv_orders.selection()
        selected_id = current_selection[0] if current_selection else None
        self.tv_orders.delete(*self.tv_orders.get_children())
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
        if selected_id and self.tv_orders.exists(selected_id):
            self.tv_orders.selection_set(selected_id)
            self.tv_orders.focus(selected_id)
            self.on_select_order()
        self.refresh_today_revenue()
    #(每5秒自動刷新訂單)
    #-------------------------------------------------------------------------------------------
    def start_auto_refresh(self):
        self.refresh_orders()
        self.auto_refresh_job = self.after(5000, self.start_auto_refresh)

#(程式入口)
#-------------------------------------------------------------------------------------------
if __name__ == "__main__":
    AdminApp().mainloop()
