import argparse
import json
import os
import sys
import glob
from io import BytesIO

from weasyprint import HTML, CSS
from PIL import Image
import fitz  # PyMuPDF

def extract_pages_as_jpeg(pdf_path):
    """將 PDF 所有頁面轉為 JPEG 格式在記憶體中，並回傳 (bytes, width, height) 的列表"""
    doc = fitz.open(pdf_path)
    if not doc:
        raise ValueError(f"無法開啟 PDF: {pdf_path}")
    
    pages_data = []
    # 使用 2.0 縮放倍率以獲得較好的解析度
    matrix = fitz.Matrix(2.0, 2.0)
    
    for page in doc:
        pix = page.get_pixmap(matrix=matrix)
        img_bytes = pix.tobytes("jpeg")
        pages_data.append((img_bytes, page.rect.width, page.rect.height))
        
    return pages_data

def generate_multi_page_html(json_data, pages_info):
    """
    將多頁 JSON (格式 {"1": [...], "2": [...]}) 與多頁背景資訊合併轉換為 HTML
    pages_info 格式為 list of dict: [{'source': bytes/str, 'is_bytes': bool, 'width': int, 'height': int}]
    """
    import base64
    
    css_parts = ["""
    body {
        margin: 0;
        padding: 0;
        font-family: sans-serif;
    }
    .pdf-page {
        position: relative;
        margin: 0;
        padding: 0;
        /* WeasyPrint uses this to start a new PDF page */
        page-break-after: always;
        overflow: hidden;
    }
    /* 最後一頁不需要分頁符號 */
    .pdf-page:last-child {
        page-break-after: auto;
    }
    .invisible-text {
        position: absolute;
        color: transparent;
        margin: 0;
        padding: 0;
        line-height: 1;
        opacity: 0.01; 
    }
    table.structure-table {
        border-collapse: collapse;
        margin: 0;
        padding: 0;
        border: none;
    }
    """]
    
    html_parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-TW">',
        "<head>",
        '<meta charset="UTF-8">',
        "<title>Accessible Document</title>"
    ]
    
    body_parts = ["<body>"]
    
    for idx, page_info in enumerate(pages_info):
        page_num_str = str(idx + 1)
        bg_source = page_info['source']
        is_bytes = page_info['is_bytes']
        img_width = page_info['width']
        img_height = page_info['height']
        
        # 建立專屬這頁的 @page 樣式和背景
        if is_bytes:
            b64_img = base64.b64encode(bg_source).decode('utf-8')
            bg_url = f"data:image/jpeg;base64,{b64_img}"
        else:
            abs_path = os.path.abspath(bg_source)
            bg_url = f"file://{abs_path}"

        page_class = f"page-{page_num_str}"
        
        # WeasyPrint 規定不同的 @page 尺寸設定需要命名 page，然後套用到元素上
        css_parts.append(f"""
        @page {page_class} {{
            size: {img_width}px {img_height}px;
            margin: 0;
        }}
        .{page_class} {{
            page: {page_class};
            width: {img_width}px;
            height: {img_height}px;
            background-image: url("{bg_url}");
            background-size: {img_width}px {img_height}px;
            background-repeat: no-repeat;
        }}
        """)
        
        body_parts.append(f'<section class="pdf-page {page_class}">')
        
        # 寫入這頁的文字 DOM
        page_json = json_data.get(page_num_str, [])
        if not page_json:
            print(f"⚠️ 警告：第 {page_num_str} 頁無文字資料，將視為空白頁")
            
        for item in page_json:
            x_type = item.get("type", "P")
            text = item.get("text", "")
            top = item.get("top", 0)
            left = item.get("left", 0)
            width = item.get("width", 100)
            height = item.get("height", 20)
            
            font_size = max(10, int(height * 0.8))
            style = f"top: {top}px; left: {left}px; width: {width}px; height: {height}px; font-size: {font_size}px;"

            if x_type.upper() == "TABLE":
                body_parts.append('<table class="structure-table">')
                rows = item.get("rows", [])
                for row in rows:
                    if row.get("type", "").upper() != "TR":
                        continue
                    body_parts.append("<tr>")
                    for cell in row.get("cells", []):
                        c_type = cell.get("type", "TD").lower()
                        c_text = cell.get("text", "")
                        c_top = cell.get("top", 0)
                        c_left = cell.get("left", 0)
                        c_width = cell.get("width", 50)
                        c_height = cell.get("height", 20)
                        c_fs = max(10, int(c_height * 0.8))
                        
                        c_style = f"top: {c_top}px; left: {c_left}px; width: {c_width}px; height: {c_height}px; font-size: {c_fs}px;"
                        body_parts.append(f'<{c_type} class="invisible-text" style="{c_style}">{c_text}</{c_type}>')
                    body_parts.append("</tr>")
                body_parts.append('</table>')
            elif x_type.upper() in ["H1", "H2", "H3", "H4", "H5", "H6"]:
                tag = x_type.lower()
                body_parts.append(f'<{tag} class="invisible-text" style="{style}">{text}</{tag}>')
            else:
                body_parts.append(f'<p class="invisible-text" style="{style}">{text}</p>')
                
        body_parts.append('</section>')

    body_parts.append("</body>")
    html_parts.append(f"<style>{''.join(css_parts)}</style>")
    html_parts.append("</head>")
    html_parts.extend(body_parts)
    html_parts.append("</html>")
    
    return "\n".join(html_parts)

def main():
    parser = argparse.ArgumentParser(description="產生多頁 PDF/UA-1 隱形文字無障礙 PDF")
    parser.add_argument("background", help="背景影像 (支援萬用字元如 '*.jpg') 或單一 PDF 檔案路徑")
    parser.add_argument("json_file", help="單一/多頁結構化文字的 JSON 檔案路徑")
    parser.add_argument("-o", "--output", default="output_accessible.pdf", help="輸出的 PDF 檔案路徑")
    args = parser.parse_args()

    # 處理輸入背景
    is_pdf_bg = args.background.lower().endswith(".pdf")
    pages_info = []

    if is_pdf_bg:
        if not os.path.exists(args.background):
            print(f"找不到 PDF 檔案: {args.background}")
            sys.exit(1)
        print(f"從 PDF 轉換背景圖片: {args.background}")
        extracted_pages = extract_pages_as_jpeg(args.background)
        for img_bytes, w, h in extracted_pages:
            pages_info.append({
                'source': img_bytes,
                'is_bytes': True,
                'width': w,
                'height': h
            })
    else:
        # 處理圖片序列 (Glob 或是單張)
        image_files = sorted(glob.glob(args.background))
        if not image_files: # 如果 glob 沒抓到，可能就是直接傳檔名
            if os.path.exists(args.background):
                image_files = [args.background]
            else:
                print(f"找不到或無法匹配圖片檔案: {args.background}")
                sys.exit(1)
                
        print(f"找到 {len(image_files)} 張背景圖片")
        for img_path in image_files:
            try:
                with Image.open(img_path) as img:
                    img_width, img_height = img.size
                pages_info.append({
                    'source': img_path,
                    'is_bytes': False,
                    'width': img_width,
                    'height': img_height
                })
            except Exception as e:
                print(f"無法讀取圖片尺寸 {img_path}: {e}")
                sys.exit(1)

    # 讀取 JSON 並自動升級格式
    if not os.path.exists(args.json_file):
        print(f"找不到 JSON 檔案: {args.json_file}")
        sys.exit(1)

    with open(args.json_file, "r", encoding="utf-8") as f:
        try:
            raw_json_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"JSON 格式錯誤: {e}")
            sys.exit(1)

    # 格式轉換：如果頂層是 list，表示是舊版單頁格式，自動將其包裝成 {"1": [...]}
    if isinstance(raw_json_data, list):
        json_data = {"1": raw_json_data}
        print("偵測到單頁 JSON 陣列格式，自動升級為多頁格式 {'1': [...]}")
    elif isinstance(raw_json_data, dict):
        json_data = raw_json_data
    else:
        print("不支援的 JSON 根部結構（需為陣列或字典）")
        sys.exit(1)

    print(f"共要產生 {len(pages_info)} 頁的 PDF 文件...")
    html_str = generate_multi_page_html(json_data, pages_info)

    # 儲存中間產物方便除錯 (可選)
    debug_html_path = args.output + ".debug.html"
    with open(debug_html_path, "w", encoding="utf-8") as f:
        f.write(html_str)
    print(f"產生中間 HTML: {debug_html_path}")

    print(f"使用 WeasyPrint 產生 PDF/UA-1 檔案中...")
    try:
        # 產生 Tagged PDF
        HTML(string=html_str, base_url=os.path.dirname(os.path.abspath(args.json_file))).write_pdf(
            args.output,
            pdf_variant='pdf/ua-1',
            presentational_hints=True
        )
        print(f"✅ 成功產出無障礙 PDF: {args.output}")
            
    except Exception as e:
        print(f"❌ 產生 PDF 失敗: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
