"""
PDF/UA Accessible PDF Generator — GUI 前端
使用 tkinter + ttkbootstrap (可選) + tkinterdnd2 (可選)
"""
import os
import sys
import threading
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# --- 可選依賴：ttkbootstrap (美化主題) ---
try:
    import ttkbootstrap as ttkb
    from ttkbootstrap.constants import *
    HAS_TTKBOOTSTRAP = True
except ImportError:
    HAS_TTKBOOTSTRAP = False

# --- 可選依賴：tkinterdnd2 (拖放) ---
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

# --- 核心 PDF 產生邏輯 ---
from generate_accessible_pdf import generate_pdf

# --- AI 輔助 Prompt (內嵌，避免讀取外部檔案) ---
AI_PROMPT = r"""請扮演專業的「文件無障礙與結構分析師」。我將提供一系列文件圖片/PDF給您進行多頁辨識。假設每張圖片/頁面的寬度為 1000px，高度為 1414px（標準 A4 比例）。請辨識內容，並將結果輸出成一個包含絕對座標的「多頁 JSON 字典結構」，並將此結構放在單一的 Markdown 程式碼區塊內 (```json ... ```)。請注意這可能是一系列的對話，未來可能會有其他圖片/PDF需要辨識。

【處理規則】
- 排除干擾：忽略頁首、頁尾、浮水印、頁碼與LOGO/CIS視覺設計等裝飾性元素。
- 判斷語意：為每一段文字標註合適的 type（如：H1, H2, H3, P, Table）。
- 閱讀順序：嚴格依照人類由左至右、由上至下的自然閱讀順序來排序陣列。
- 座標定位：請針對每一個元素估算在 1000x1414 畫布上的精準位置，包含對應欄位 top, left, width, height。數值請直接寫整數的 px 值。
- 表格重建：當發現多個視覺文字框(需有框線)構成一個表格時，將它打包成巢狀 "Table" 結構，該節點必須包含 "rows" 陣列代表每一列(TR)；每一列含 "cells" 陣列代表儲存格(TH或TD)。並保留各個儲存格原本的座標與數值。
- 空白頁處理：若有一頁完全沒有需要標記的文字，則傳回空白陣列。
- 輸出：不要包含除了 JSON 程式碼區塊之外的 Markdown 標記或文字解釋。

【預期多頁 JSON 結構格式範例】
```json
{
  "1": [
    { 
      "type": "H2", 
      "text": "第三季營收報表", 
      "top": 100, "left": 50, "width": 200, "height": 30 
    },
    {
      "type": "Table",
      "top": 150, "left": 50, "width": 400, "height": 100,
      "rows": [
        {
          "type": "TR",
          "cells": [
            { "type": "TH", "text": "月份", "top": 150, "left": 50, "width": 200, "height": 50 },
            { "type": "TH", "text": "營收 (萬元)", "top": 150, "left": 250, "width": 200, "height": 50 }
          ]
        },
        {
          "type": "TR",
          "cells": [
            { "type": "TD", "text": "七月", "top": 200, "left": 50, "width": 200, "height": 50 },
            { "type": "TD", "text": "1,250", "top": 200, "left": 250, "width": 200, "height": 50 }
          ]
        }
      ]
    },
    { 
      "type": "P", 
      "text": "上表顯示七月份營收達標。", 
      "top": 280, "left": 50, "width": 300, "height": 30 
    }
  ],
  "2": [
    { 
      "type": "H2", 
      "text": "第四季預估報表", 
      "top": 100, "left": 50, "width": 200, "height": 30 
    },
    { 
      "type": "P", 
      "text": "預計第四季營收成長 15%。", 
      "top": 150, "left": 50, "width": 300, "height": 30 
    }
  ],
  "3": []
}
```"""

# ──────────────────────── 任務資料結構 ────────────────────────

class TaskItem:
    """代表一筆批次任務：背景檔 + JSON 檔 → 輸出 PDF"""
    STATUS_PENDING = "⏳ 待處理"
    STATUS_RUNNING = "⚙️ 執行中"
    STATUS_DONE    = "✅ 完成"
    STATUS_ERROR   = "❌ 錯誤"
    STATUS_NO_JSON = "⚠️ 缺 JSON"

    def __init__(self, bg_path, json_path=None):
        self.bg_path = bg_path
        self.json_path = json_path
        self.status = self.STATUS_PENDING if json_path else self.STATUS_NO_JSON


# ──────────────────────── 主視窗 ────────────────────────

class AccessiblePdfApp:
    APP_TITLE = "PDF/UA Accessible PDF Generator"
    APP_VERSION = "1.0"

    def __init__(self):
        # 依據可用套件建立根視窗
        # 優先使用 TkinterDnD.Tk() 以支援拖放，再套用 ttkbootstrap 主題
        if HAS_DND:
            self.root = TkinterDnD.Tk()
            self.root.title(f"{self.APP_TITLE}  v{self.APP_VERSION}")
            self.root.geometry("820x720")
            if HAS_TTKBOOTSTRAP:
                ttkb.Style(theme="cosmo")  # 套用主題到已存在的 Tk root
        elif HAS_TTKBOOTSTRAP:
            self.root = ttkb.Window(
                title=f"{self.APP_TITLE}  v{self.APP_VERSION}",
                themename="cosmo",
                size=(820, 720),
            )
        else:
            self.root = tk.Tk()
            self.root.title(f"{self.APP_TITLE}  v{self.APP_VERSION}")
            self.root.geometry("820x720")

        self.tasks: list[TaskItem] = []
        self.output_dir = tk.StringVar(value=os.path.expanduser("~"))
        self.is_running = False   # 防止重複按執行

        self._configure_fonts()
        self._build_ui()
        self._load_intro()

    # ───── 啟動說明設定 ─────

    def _load_intro(self):
        """讀取 Intro.md 並顯示在執行日誌區作為操作指引"""
        # 定位內嵌檔案（支援 PyInstaller 打包路徑）
        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        intro_path = os.path.join(base_dir, 'Intro.md')

        if os.path.exists(intro_path):
            try:
                with open(intro_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                
                if content:
                    self.log_text.configure(state="normal")
                    self.log_text.insert("end", content + "\n\n" + "═" * 40 + "\n\n")
                    self.log_text.see("end")
                    self.log_text.configure(state="disabled")
            except Exception as e:
                self._log(f"[WARNING] 無法讀取說明檔 ({intro_path}): {e}")
        else:
            self._log(f"[WARNING] 找不到說明檔 ({intro_path})")

    # ───── 字型設定 ─────

    # 內嵌字型檔名（放在專案 fonts/ 目錄中，PyInstaller 會一併打包）
    BUNDLED_FONT_FILE = "NotoSansTC-Regular.otf"

    def _configure_fonts(self):
        """偵測並設定 CJK 字型，避免中文顯示為方塊。

        策略：
        1. 掃描系統已安裝的 CJK 字型
        2. 若找不到，將內嵌字型安裝到使用者字型目錄後重新掃描
        3. 仍然失敗則印出終端警告
        """
        import tkinter.font as tkfont

        chosen = self._find_cjk_font()

        if not chosen:
            # 嘗試安裝內嵌字型後重新偵測
            if self._install_bundled_font():
                # 重建 root 以刷新字型快取（Tk 啟動時讀取一次 fontconfig）
                # 此處僅重新查詢字型列表
                chosen = self._find_cjk_font()

        if chosen:
            self._apply_font(chosen)
        else:
            print("[WARNING] 找不到任何 CJK 字型，中文可能顯示為方塊。")
            available = tkfont.families(self.root)
            print(f"  Tk 可見字型數: {len(available)}")
            print("  建議: 安裝 Noto Sans CJK TC 字型")
            print("    Linux:   sudo apt install fonts-noto-cjk")
            print("    conda:   conda install -c conda-forge tk fontconfig freetype libxft")

    def _find_cjk_font(self) -> str | None:
        """在 Tk 可見字型中尋找 CJK 字型，回傳字型名稱或 None"""
        import tkinter.font as tkfont

        cjk_candidates = [
            "Noto Sans CJK TC",    # Linux (繁體優先)
            "Noto Sans CJK SC",    # Linux (簡體)
            "Noto Sans CJK JP",    # Linux (日文)
            "WenQuanYi Micro Hei", # Linux 替代
            "Microsoft JhengHei",  # Windows 正黑體
            "微軟正黑體",            # Windows 中文名
            "PingFang TC",         # macOS
            "Heiti TC",            # macOS 替代
        ]

        available = tkfont.families(self.root)
        for candidate in cjk_candidates:
            if candidate in available:
                return candidate

        # 模糊搜尋
        for fam in available:
            if "CJK" in fam or "Hei" in fam or "黑" in fam:
                return fam
        return None

    def _apply_font(self, family: str):
        """將指定字型套用到所有 tkinter 預設字型"""
        import tkinter.font as tkfont
        for font_name in ("TkDefaultFont", "TkTextFont", "TkMenuFont",
                          "TkHeadingFont", "TkCaptionFont", "TkTooltipFont"):
            try:
                f = tkfont.nametofont(font_name)
                f.configure(family=family)
            except Exception:
                pass

    def _install_bundled_font(self) -> bool:
        """將內嵌字型複製到使用者字型目錄（僅首次），回傳是否成功"""
        import shutil

        # 定位內嵌字型（支援 PyInstaller 打包路徑）
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.dirname(os.path.abspath(__file__))

        font_src = os.path.join(base, 'fonts', self.BUNDLED_FONT_FILE)
        if not os.path.exists(font_src):
            return False

        # 各平臺使用者字型目錄
        if sys.platform == 'win32':
            font_dir = os.path.join(
                os.environ.get('LOCALAPPDATA', ''),
                'Microsoft', 'Windows', 'Fonts',
            )
        elif sys.platform == 'darwin':
            font_dir = os.path.expanduser('~/Library/Fonts')
        else:
            font_dir = os.path.expanduser('~/.local/share/fonts')

        try:
            os.makedirs(font_dir, exist_ok=True)
            dest = os.path.join(font_dir, self.BUNDLED_FONT_FILE)
            if not os.path.exists(dest):
                shutil.copy2(font_src, dest)
                print(f"[INFO] 已安裝內嵌字型: {dest}")
                # Linux / macOS 需要重建字型快取
                if not sys.platform.startswith('win'):
                    os.system('fc-cache -f 2>/dev/null')
            return True
        except OSError as e:
            print(f"[WARNING] 無法安裝內嵌字型: {e}")
            return False

    # ───── UI 建置 ─────

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}
        root = self.root

        # ---- 1. Prompt 區 ----
        frm_prompt = ttk.LabelFrame(root, text="📎 AI 輔助 Prompt", padding=8)
        frm_prompt.pack(fill="x", **pad)

        lbl_preview = ttk.Label(
            frm_prompt,
            text=AI_PROMPT[:100].replace("\n", " ") + "…",
            wraplength=700,
            foreground="gray",
        )
        lbl_preview.pack(side="left", fill="x", expand=True)

        btn_copy = ttk.Button(frm_prompt, text="複製 📋", command=self._copy_prompt)
        btn_copy.pack(side="right")

        # ---- 2. 批次任務表格 ----
        frm_table = ttk.LabelFrame(root, text="📥 批次任務列表", padding=8)
        frm_table.pack(fill="both", expand=True, **pad)

        cols = ("idx", "bg", "json", "status")
        self.tree = ttk.Treeview(
            frm_table, columns=cols, show="headings", height=8, selectmode="extended"
        )
        self.tree.heading("idx",    text="#",     anchor="center")
        self.tree.heading("bg",     text="背景檔案",  anchor="w")
        self.tree.heading("json",   text="JSON 檔案", anchor="w")
        self.tree.heading("status", text="狀態",    anchor="center")
        self.tree.column("idx",    width=40,  stretch=False, anchor="center")
        self.tree.column("bg",     width=300, stretch=True)
        self.tree.column("json",   width=280, stretch=True)
        self.tree.column("status", width=100, stretch=False, anchor="center")

        scroll = ttk.Scrollbar(frm_table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # 雙擊 JSON 欄位 → 手動指定
        self.tree.bind("<Double-1>", self._on_tree_double_click)

        # ---- 3. 拖放區 / 按鈕列 ----
        frm_drop = ttk.Frame(root, padding=4)
        frm_drop.pack(fill="x", **pad)

        if HAS_DND:
            self.drop_label = ttk.Label(
                frm_drop,
                text="📥  拖曳 PDF / JPG 檔案到視窗任意位置即可新增任務",
                anchor="center",
                relief="groove",
                padding=12,
            )
            self.drop_label.pack(fill="x", pady=(0, 5))
            # 綁定拖放到整個視窗
            try:
                self.root.drop_target_register(DND_FILES)
                self.root.dnd_bind("<<Drop>>", self._on_drop)
            except Exception:
                pass  # 降級

        btn_frame = ttk.Frame(frm_drop)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="瀏覽背景檔案…", command=self._browse_bg).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="瀏覽 JSON…",    command=self._browse_json_for_selected).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="🗑 移除選取",   command=self._remove_selected).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="🗑 清除全部",   command=self._clear_all).pack(side="left", padx=2)

        # ---- 4. 輸出目錄 ----
        frm_out = ttk.LabelFrame(root, text="📂 輸出目錄", padding=8)
        frm_out.pack(fill="x", **pad)

        ttk.Entry(frm_out, textvariable=self.output_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(frm_out, text="選擇目錄…", command=self._browse_output_dir).pack(side="right", padx=(5, 0))

        # ---- 5. 執行按鈕 ----
        frm_exec = ttk.Frame(root)
        frm_exec.pack(fill="x", **pad)

        self.btn_run = ttk.Button(
            frm_exec, text="▶  全部執行", command=self._run_all
        )
        self.btn_run.pack(fill="x", ipady=6)

        # ---- 6. 執行日誌 ----
        frm_log = ttk.LabelFrame(root, text="📝 執行日誌", padding=8)
        frm_log.pack(fill="both", expand=True, **pad)

        self.log_text = tk.Text(frm_log, height=6, state="disabled", wrap="word")
        log_scroll = ttk.Scrollbar(frm_log, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

    # ───── Prompt 複製 ─────

    def _copy_prompt(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(AI_PROMPT)
        self._log("已複製 AI 輔助 Prompt 到剪貼簿 ✅")

    # ───── 拖放處理 ─────

    def _on_drop(self, event):
        """處理拖放進來的檔案"""
        raw = event.data
        # tkinterdnd2 會以空格分隔，含大括號的路徑用 {} 包起來
        paths = self._parse_dropped_paths(raw)
        self._add_bg_files(paths)

    @staticmethod
    def _parse_dropped_paths(raw: str) -> list[str]:
        """解析 tkinterdnd2 的拖放路徑字串"""
        paths = []
        current = []
        in_brace = False
        for char in raw:
            if char == '{':
                in_brace = True
            elif char == '}':
                in_brace = False
            elif char == ' ' and not in_brace:
                if current:
                    paths.append(''.join(current))
                    current = []
                continue
            else:
                current.append(char)
        if current:
            paths.append(''.join(current))
        return paths

    # ───── 瀏覽按鈕 ─────

    def _browse_bg(self):
        """瀏覽選擇背景檔案 (PDF / JPG / PNG)"""
        files = filedialog.askopenfilenames(
            title="選擇背景檔案",
            filetypes=[
                ("PDF / 圖片", "*.pdf *.jpg *.jpeg *.png *.bmp *.tiff"),
                ("所有檔案", "*.*"),
            ],
        )
        if files:
            self._add_bg_files(list(files))

    def _browse_json_for_selected(self):
        """為選取的任務手動指定 JSON"""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "請先在列表中選取一筆任務")
            return
        fpath = filedialog.askopenfilename(
            title="選擇 JSON 結構檔",
            filetypes=[("JSON 檔案", "*.json"), ("所有檔案", "*.*")],
        )
        if not fpath:
            return
        for item_id in sel:
            idx = int(self.tree.item(item_id, "values")[0]) - 1
            self.tasks[idx].json_path = fpath
            self.tasks[idx].status = TaskItem.STATUS_PENDING
        self._refresh_table()

    def _browse_output_dir(self):
        d = filedialog.askdirectory(title="選擇輸出目錄")
        if d:
            self.output_dir.set(d)

    # ───── 任務管理 ─────

    def _add_bg_files(self, paths: list[str]):
        """加入背景檔案並嘗試自動偵測對應 JSON"""
        valid_exts = {".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
        added = 0
        for p in paths:
            ext = os.path.splitext(p)[1].lower()
            if ext not in valid_exts:
                self._log(f"⚠️ 略過非支援檔案: {os.path.basename(p)}")
                continue

            # 自動尋找同名 .json
            base = os.path.splitext(p)[0]
            json_candidate = base + ".json"
            json_path = json_candidate if os.path.exists(json_candidate) else None

            task = TaskItem(p, json_path)
            self.tasks.append(task)
            added += 1

            if json_path:
                self._log(f"新增: {os.path.basename(p)} → 自動偵測 JSON: {os.path.basename(json_path)}")
            else:
                self._log(f"新增: {os.path.basename(p)} → ⚠️ 未找到同名 JSON，請手動指定")

        if added:
            self._refresh_table()
            # 自動將輸出目錄設為第一個檔案的所在目錄
            if self.output_dir.get() == os.path.expanduser("~"):
                self.output_dir.set(os.path.dirname(paths[0]))

    def _remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        indices = sorted(
            [int(self.tree.item(s, "values")[0]) - 1 for s in sel], reverse=True
        )
        for i in indices:
            self.tasks.pop(i)
        self._refresh_table()

    def _clear_all(self):
        self.tasks.clear()
        self._refresh_table()

    def _refresh_table(self):
        """重繪整個任務表格"""
        self.tree.delete(*self.tree.get_children())
        for i, t in enumerate(self.tasks):
            self.tree.insert(
                "", "end",
                values=(
                    i + 1,
                    os.path.basename(t.bg_path),
                    os.path.basename(t.json_path) if t.json_path else "(未指定)",
                    t.status,
                ),
            )

    def _on_tree_double_click(self, event):
        """雙擊任務列表 → 手動指定該筆 JSON"""
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        # col == '#3' 是 JSON 欄
        if col != "#3":
            return
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        fpath = filedialog.askopenfilename(
            title="選擇 JSON 結構檔",
            filetypes=[("JSON 檔案", "*.json"), ("所有檔案", "*.*")],
        )
        if fpath:
            idx = int(self.tree.item(item_id, "values")[0]) - 1
            self.tasks[idx].json_path = fpath
            self.tasks[idx].status = TaskItem.STATUS_PENDING
            self._refresh_table()

    # ───── 執行 ─────

    def _run_all(self):
        """在子執行緒逐筆處理所有任務"""
        if self.is_running:
            return

        runnable = [t for t in self.tasks if t.json_path and t.status != TaskItem.STATUS_DONE]
        if not runnable:
            messagebox.showinfo("提示", "沒有可執行的任務。請確認每筆任務都有對應的 JSON 檔案。")
            return

        out_dir = self.output_dir.get()
        if not os.path.isdir(out_dir):
            messagebox.showerror("錯誤", f"輸出目錄不存在: {out_dir}")
            return

        self.is_running = True
        self.btn_run.configure(state="disabled")
        self._log(f"═══════ 開始批次執行 ({len(runnable)} 筆) ═══════")

        thread = threading.Thread(target=self._run_worker, args=(runnable, out_dir), daemon=True)
        thread.start()

    def _run_worker(self, runnable: list[TaskItem], out_dir: str):
        """背景執行緒"""
        total = len(runnable)
        for idx, task in enumerate(runnable):
            task.status = TaskItem.STATUS_RUNNING
            self.root.after(0, self._refresh_table)

            # 決定輸出檔名
            bg_basename = os.path.splitext(os.path.basename(task.bg_path))[0]
            output_name = f"{bg_basename}_accessible.pdf"
            output_path = os.path.join(out_dir, output_name)

            self._log_safe(f"[{idx+1}/{total}] 正在處理: {os.path.basename(task.bg_path)}")

            try:
                generate_pdf(
                    background=task.bg_path,
                    json_file=task.json_path,
                    output=output_path,
                    callback=lambda msg: self._log_safe(f"  {msg}"),
                )
                task.status = TaskItem.STATUS_DONE
                self._log_safe(f"[{idx+1}/{total}] ✅ 完成 → {output_name}")
            except Exception as e:
                task.status = f"❌ {e}"
                self._log_safe(f"[{idx+1}/{total}] ❌ 失敗: {e}")

            self.root.after(0, self._refresh_table)

        self._log_safe("═══════ 批次執行完畢 ═══════")
        self.root.after(0, self._on_run_finished)

    def _on_run_finished(self):
        self.is_running = False
        self.btn_run.configure(state="normal")

    # ───── 日誌 ─────

    def _log(self, msg: str):
        """在主執行緒寫入日誌"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {msg}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _log_safe(self, msg: str):
        """從子執行緒安全寫入日誌 (透過 after 排程)"""
        self.root.after(0, self._log, msg)

    # ───── 啟動 ─────

    def run(self):
        self.root.mainloop()


# ──────────────────────── 入口 ────────────────────────

def main():
    app = AccessiblePdfApp()
    app.run()


if __name__ == "__main__":
    main()
