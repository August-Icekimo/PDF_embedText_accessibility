#!/usr/bin/env python3

import fitz  # PyMuPDF
import json
import os
import sys

def embed_invisible_text(input_pdf_path, output_pdf_path, text_data):
    """
    將文字以隱形模式嵌入 PDF 指定頁面
    """
    doc = fitz.open(input_pdf_path)

    for page_num, content in text_data.items():
        # page_num 是從 0 開始 (0 是第 1 頁)
        if page_num >= len(doc):
            continue
            
        page = doc[page_num]
        
        # --- 核心技巧：使用 render_mode=3 (Invisible) ---
        # 這裡我們將文字插入到頁面中。
        # rect 參數定義文字插入的範圍 (x0, y0, x1, y1)
        # 為了讓閱讀順序正確，我們從頁面左上角開始寫入
        
        # 定義起始座標 (左邊界 50, 上邊界 50)
        insert_point = fitz.Point(50, 50)
        
        # 插入文字
        # render_mode=3 是 PDF 標準的 "Invisible" 屬性 (文字存在但不可見)
        # fontsize 設定適中即可，盲人點顯器或報讀軟體不看字體大小
        page.insert_text(
            insert_point,
            content,
            fontsize=12,
            fontname="helv", # 使用預設字型，支援英文。中文需載入字型，詳見下方說明
            render_mode=3,   # <--- 關鍵：3 代表隱形
            overlay=True     # 蓋在圖片上層 (雖然是隱形的)
        )

    doc.save(output_pdf_path)
    print(f"成功產出雙層 PDF: {output_pdf_path}")

# --- 準備這份 PDF 的正確文字內容 ---
# 為了避免中文字型問題，PyMuPDF 預設字型不支援中文顯示(即使是隱形也需要字型編碼)
# 實務上我們會用 "China-S" 或 "China-T" 或載入一個 .ttf 字型
# 這裡為了簡化示範，我示範如何載入系統中文字型來寫入隱形中文

def embed_invisible_text_with_chinese(input_pdf_path, text_data, output_pdf_path=None, font_path="/usr/share/fonts/truetype/arphic/ukai.ttc"):
    # 2. default output_pdf_path is input_pdf_path+"accessible".pdf
    if output_pdf_path is None:
        base, _ = os.path.splitext(input_pdf_path)
        output_pdf_path = f"{base}_accessible.pdf"

    doc = fitz.open(input_pdf_path)
    
    for page_num_key, content in text_data.items():
        page_num = int(page_num_key) # Ensure page_num is int (JSON keys are strings)
        if page_num >= len(doc): continue
        page = doc[page_num]
        
        # 建立一個 TextWriter 物件，比較好控制多行文字
        writer = fitz.TextWriter(page.rect)
        
        # 載入支援中文的字型 (例如微軟正黑體或標楷體)
        font = fitz.Font(fontfile=font_path)
        
        # 將內容依換行符號拆解，逐行寫入，確保閱讀順序
        lines = content.strip().split('\n')
        y_position = 50 # 起始高度
        
        for line in lines:
            if not line.strip(): continue
            # 寫入位置 (x=50, y=目前高度)
            writer.append((50, y_position), line, font=font, fontsize=10)
            y_position += 15 # 行距
            
        # 執行寫入，並設定 render_mode=3 (隱形)
        writer.write_text(page, render_mode=3)

    doc.subset_fonts()
    doc.save(output_pdf_path, garbage=4, deflate=True)
    print(f"成功產出含中文隱形文字的 PDF: {output_pdf_path}")

if __name__ == "__main__":
    # 1. read file for pdf_content replacement
    # Usage: python embedInvisibleText.py <input_pdf> <content_json> [font_path]
    if len(sys.argv) < 3:
        print("Usage: python embedInvisibleText.py <input_pdf> <content_json> [font_path]")
        sys.exit(1)

    input_pdf = sys.argv[1]
    content_file = sys.argv[2]
    # 3. default font path
    font_p = sys.argv[3] if len(sys.argv) > 3 else "/usr/share/fonts/truetype/arphic/ukai.ttc"

    try:
        with open(content_file, 'r', encoding='utf-8') as f:
            pdf_content = json.load(f)
        
        embed_invisible_text_with_chinese(input_pdf, pdf_content, font_path=font_p)
    except Exception as e:
        print(f"Error processing PDF: {e}")