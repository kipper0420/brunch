import tkinter as tk
from tkinter import messagebox
import random
from collections import deque


class Minesweeper:
    # difficulty_name: (rows, cols, mines)
    DIFFICULTIES = {
        "初": (9, 9, 10),
        "中": (16, 16, 1),
        "高": (16, 30, 99),
    }

    def __init__(self, root):
        self.root = root
        self.root.title("Minesweeper - 踩地雷")

        # ---- Top UI ----
        top = tk.Frame(root)
        top.pack(padx=10, pady=(10, 6), fill="x")

        self.diff_var = tk.StringVar(value="初")
        tk.Label(top, text="難度：").pack(side="left")

        self.diff_menu = tk.OptionMenu(
            top,
            self.diff_var,
            *self.DIFFICULTIES.keys(),
            command=lambda _=None: self.start_new_game()
        )
        self.diff_menu.pack(side="left")

        self.mines_var = tk.StringVar()
        self.status_var = tk.StringVar(value="左鍵開格，右鍵插旗（首點安全）")

        tk.Label(top, textvariable=self.mines_var, anchor="w").pack(side="left", padx=12)
        tk.Label(top, textvariable=self.status_var, anchor="e").pack(side="right")

        btn_bar = tk.Frame(root)
        btn_bar.pack(padx=10, pady=(0, 10), fill="x")
        tk.Button(btn_bar, text="重新開始", command=self.start_new_game).pack(side="left")

        # Board frame (will be rebuilt on difficulty change)
        self.board_frame = tk.Frame(root)
        self.board_frame.pack(padx=10, pady=(0, 10))

        # Game state placeholders
        self.rows = self.cols = self.total_mines = 0
        self.buttons = []
        self.is_mine = []
        self.adj = []
        self.revealed = []
        self.flagged = []

        self.game_over = False
        self.flags_used = 0
        self.cells_to_reveal = 0

        # first click safe: mines are placed only after first reveal
        self.mines_placed = False
        self.first_click = True

        self.start_new_game()

    # -----------------------
    # Game initialization
    # -----------------------
    def start_new_game(self):
        self._apply_difficulty(self.diff_var.get())
        self._rebuild_board_ui()
        self._reset_board_data()

        self.game_over = False
        self.flags_used = 0
        self.cells_to_reveal = self.rows * self.cols - self.total_mines
        self.mines_placed = False
        self.first_click = True

        self.mines_var.set(f"剩餘地雷(旗子): {self.total_mines}")
        self.status_var.set("左鍵開格，右鍵插旗（首點安全）")

    def _apply_difficulty(self, name: str):
        r, c, m = self.DIFFICULTIES[name]
        self.rows, self.cols, self.total_mines = r, c, m

    def _rebuild_board_ui(self):
        # destroy old buttons/frame content
        for w in self.board_frame.winfo_children():
            w.destroy()

        self.buttons = [[None for _ in range(self.cols)] for _ in range(self.rows)]

        # build new grid
        for r in range(self.rows):
            for c in range(self.cols):
                b = tk.Button(
                    self.board_frame,
                    width=2,
                    height=1,
                    text="",
                    relief="raised",
                    font=("Segoe UI", 11, "bold"),
                    command=lambda rr=r, cc=c: self.on_left_click(rr, cc),
                )
                b.grid(row=r, column=c, padx=1, pady=1)
                b.bind("<Button-3>", lambda e, rr=r, cc=c: self.on_right_click(rr, cc))
                self.buttons[r][c] = b

    def _reset_board_data(self):
        self.is_mine = [[False for _ in range(self.cols)] for _ in range(self.rows)]
        self.adj = [[0 for _ in range(self.cols)] for _ in range(self.rows)]
        self.revealed = [[False for _ in range(self.cols)] for _ in range(self.rows)]
        self.flagged = [[False for _ in range(self.cols)] for _ in range(self.rows)]

        for r in range(self.rows):
            for c in range(self.cols):
                self.buttons[r][c].config(
                    text="",
                    state="normal",
                    relief="raised",
                    bg=self.root.cget("bg"),
                )

    # -----------------------
    # Mine placement (first click safe)
    # -----------------------
    def _place_mines(self, safe_r, safe_c):
        """
        Place mines after first click:
        - Guarantee (safe_r, safe_c) is not a mine
        - Also avoid placing mines in the 8 neighbors around first click
          (makes first move nicer; remove this if you want only 1-cell safe)
        """
        forbidden = set()
        for rr in range(safe_r - 1, safe_r + 2):
            for cc in range(safe_c - 1, safe_c + 2):
                if 0 <= rr < self.rows and 0 <= cc < self.cols:
                    forbidden.add((rr, cc))

        positions = [(r, c) for r in range(self.rows) for c in range(self.cols) if (r, c) not in forbidden]
        random.shuffle(positions)

        # just in case (very small boards): ensure enough positions
        mines_to_place = min(self.total_mines, len(positions))

        for i in range(mines_to_place):
            r, c = positions[i]
            self.is_mine[r][c] = True

        # compute adjacency
        for r in range(self.rows):
            for c in range(self.cols):
                if self.is_mine[r][c]:
                    continue
                self.adj[r][c] = self._count_adjacent_mines(r, c)

        self.mines_placed = True

    def _count_adjacent_mines(self, r, c):
        cnt = 0
        for rr in range(r - 1, r + 2):
            for cc in range(c - 1, c + 2):
                if rr == r and cc == c:
                    continue
                if 0 <= rr < self.rows and 0 <= cc < self.cols:
                    if self.is_mine[rr][cc]:
                        cnt += 1
        return cnt

    # -----------------------
    # Input handlers
    # -----------------------
    def on_left_click(self, r, c):
        if self.game_over:
            return
        if self.flagged[r][c] or self.revealed[r][c]:
            return

        # First click: place mines with safety guarantee
        if not self.mines_placed:
            self._place_mines(r, c)

        if self.is_mine[r][c]:
            self._lose(r, c)
            return

        self._reveal_cell(r, c)
        if self.adj[r][c] == 0:
            self._flood_fill(r, c)

        self._check_win()

    def on_right_click(self, r, c):
        if self.game_over or self.revealed[r][c]:
            return

        if not self.flagged[r][c]:
            if self.flags_used >= self.total_mines:
                self.status_var.set("旗子用完了")
                return
            self.flagged[r][c] = True
            self.flags_used += 1
            self.buttons[r][c].config(text="🚩")
        else:
            self.flagged[r][c] = False
            self.flags_used -= 1
            self.buttons[r][c].config(text="")

        remaining = self.total_mines - self.flags_used
        self.mines_var.set(f"剩餘地雷(旗子): {remaining}")

    # -----------------------
    # Reveal logic
    # -----------------------
    def _reveal_cell(self, r, c):
        if self.revealed[r][c] or self.flagged[r][c]:
            return

        self.revealed[r][c] = True
        b = self.buttons[r][c]
        b.config(relief="sunken", state="disabled", bg="#e6e6e6")

        val = self.adj[r][c]
        b.config(text=str(val) if val > 0 else "")

        self.cells_to_reveal -= 1

    def _flood_fill(self, sr, sc):
        q = deque([(sr, sc)])
        visited = {(sr, sc)}

        while q:
            r, c = q.popleft()
            for rr in range(r - 1, r + 2):
                for cc in range(c - 1, c + 2):
                    if 0 <= rr < self.rows and 0 <= cc < self.cols:
                        if (rr, cc) in visited:
                            continue
                        visited.add((rr, cc))

                        if self.flagged[rr][cc] or self.revealed[rr][cc]:
                            continue
                        if self.is_mine[rr][cc]:
                            continue

                        self._reveal_cell(rr, cc)
                        if self.adj[rr][cc] == 0:
                            q.append((rr, cc))

    # -----------------------
    # Win/Lose
    # -----------------------
    def _lose(self, hit_r, hit_c):
        self.game_over = True
        self.status_var.set("你踩到地雷了！")

        for r in range(self.rows):
            for c in range(self.cols):
                if self.is_mine[r][c]:
                    self.buttons[r][c].config(text="💣", bg="#ffcccc")
                self.buttons[r][c].config(state="disabled")

        self.buttons[hit_r][hit_c].config(bg="#ff6666")
        messagebox.showinfo("Game Over", "你踩到地雷了！\n按「重新開始」或切換難度再玩一次。")

    def _check_win(self):
        if not self.game_over and self.cells_to_reveal == 0:
            self.game_over = True
            self.status_var.set("你贏了！")

            for r in range(self.rows):
                for c in range(self.cols):
                    self.buttons[r][c].config(state="disabled")

            messagebox.showinfo("You Win!", "恭喜你把所有安全格都開完了！")


def main():
    root = tk.Tk()
    Minesweeper(root)
    root.mainloop()


if __name__ == "__main__":
    main()