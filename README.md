# PDF/UA Accessible PDF Generator

這是一個用 Python 撰寫的專案，主要透過 [WeasyPrint](https://weasyprint.org/) 將「原始文件的背景圖片」與「包含結構化文字的 JSON」，合併渲染成一份符合 PDF/UA-1 標準的無障礙（Accessible）PDF 檔案。產生出來的 PDF 視覺上只會顯示原本的背景圖片，但底層含有完整的透明文字與標籤結構（Tagged PDF），可供 NVDA 等螢幕報讀軟體正常讀取。

## 專案原理

1. **OCR / AI 辨識 (前置準備)：** 透過 AI（如 Gemini 等具備 Vision 功能的多模態語言模型）取得文件影像上的所有文字，並辨識其位置（Bounding Box）與語意（Heading, Paragraph, Table 等），輸出為結構化的 JSON 檔案。
2. **HTML / CSS 渲染引擎：** 腳本 `generate_accessible_pdf.py` 會讀取 JSON 與背景圖片後，動態生成一個 HTML 格式的 DOM 結構。
   - 使用 CSS `position: absolute` 把文字定位疊加。
   - 透過設定文字顏色的 CSS `color: transparent` 以及 `opacity: 0.01` 把實體字元隱藏，但在 DOM 結構中仍具體保留其存取性。
   - 透過 WeasyPrint 核心軟體引擎將 HTML 重新渲染成 PDF，並強制啟動 `pdf_variant='pdf/ua-1'` 產生滿足無障礙合規標準的標籤。

## 環境建置

專案建立於名為 `emBedTxt` 的獨立 conda 環境：

```bash
# 1. 建立與啟動 conda 環境
conda create -n emBedTxt python=3.11 -y
conda activate emBedTxt

# 2. 安裝必要的 Python 模組
pip install weasyprint PyMuPDF Pillow
```

## 使用方式

主程式為 `generate_accessible_pdf.py`，執行時需依照順序提供兩個參數：背景檔案（背景可以是一般影像圖或是舊版無結構的電子 PDF）以及結構化資料 JSON 檔。

### 語法

```bash
# 多頁 PDF
python generate_accessible_pdf.py document.pdf structure.json -o output.pdf

# 多張連續圖片 (透過模式比對或資料夾掃描)
python generate_accessible_pdf.py "examples/page-*.jpg" structure.json -o output.pdf
```

### 操作範例

專案以 `examples` 目錄作為展示使用，您可啟動虛擬環境後執行下方指令：

```bash
conda activate emBedTxt
python generate_accessible_pdf.py examples/background.jpg examples/structure.json -o examples/output.pdf
```
或者是
```bash
conda activate emBedTxt
python generate_accessible_pdf.py examples/溫室氣體查驗意見─安康廠區.pdf examples/溫室氣體查驗意見─安康廠區.json -o examples/溫室氣體查驗意見-安康廠區-NVDA.pdf
```

(您可以透過您慣用的 PDF 閱讀器開啟 `examples/output.pdf`。畫面上只會看到原本的背景底圖，但是文字因為變成透明，依然可以使用滑鼠框選複製，或者使用視障報讀軟體正常解析。)

---

## 輔助 Prompt (取得結構化 JSON)

您可以複製並使用以下 Prompt 行為腳本，讓主流視覺 AI 語言模型幫您一次性產出符合本專案能解析定位的純 JSON 結構陣列：

```
請扮演專業的「文件無障礙與結構分析師」。我將提供一系列文件圖片/PDF給您進行多頁辨識。假設每張圖片/頁面的寬度為 1000px，高度為 1414px（標準 A4 比例）。請辨識內容，並將結果輸出成一個包含絕對座標的「多頁 JSON 字典結構」，並將此結構放在單一的 Markdown 程式碼區塊內 (```json ... ```)。請注意這可能是一系列的對話，未來可能會有其他圖片/PDF需要辨識。

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
```
```
