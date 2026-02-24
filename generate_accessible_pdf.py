import argparse
import json
import os
import sys
from io import BytesIO

from weasyprint import HTML, CSS
from PIL import Image
import fitz  # PyMuPDF

def extract_first_page_as_jpeg(pdf_path):
    """將 PDF 第一頁轉為 JPEG 格式在記憶體中，並回傳 bytes"""
    doc = fitz.open(pdf_path)
    if not doc:
        raise ValueError(f"無法開啟 PDF: {pdf_path}")
    
    page = doc[0]
    # 使用 2.0 縮放倍率以獲得較好的解析度
    matrix = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=matrix)
    img_bytes = pix.tobytes("jpeg")
    return img_bytes, page.rect.width, page.rect.height

def generate_html_from_json(json_data, image_path_or_bytes, is_bytes=False, img_width=1000, img_height=1414):
    """
    將 JSON 轉換為包含透明文字與絕對定位的 HTML
    如果背景圖由 PDF 轉換而來，將放入 Base64 Data URI
    """
    
    # 基本 CSS：移除預設邊距，設定背景圖片大小覆蓋全頁
    
    if is_bytes:
        import base64
        b64_img = base64.b64encode(image_path_or_bytes).decode('utf-8')
        bg_url = f"data:image/jpeg;base64,{b64_img}"
    else:
        # 取得絕對路徑或使用 file:///
        abs_path = os.path.abspath(image_path_or_bytes)
        bg_url = f"file://{abs_path}"

    css = f"""
    @page {{
        size: {img_width}px {img_height}px;
        margin: 0;
    }}
    body {{
        margin: 0;
        padding: 0;
        width: {img_width}px;
        height: {img_height}px;
        background-image: url("{bg_url}");
        background-size: {img_width}px {img_height}px;
        background-repeat: no-repeat;
        position: relative;
        font-family: sans-serif;
    }}
    /* 所有文字將看不見，但可用於選擇與報讀 */
    .invisible-text {{
        position: absolute;
        color: transparent;
        margin: 0;
        padding: 0;
        line-height: 1;
        /* 避免影響視覺排版，但保留語意 */
        opacity: 0.01; 
    }}
    table.structure-table {{
        border-collapse: collapse;
        margin: 0;
        padding: 0;
        border: none;
        /* 外層 Table 不需要絕對定位 */
    }}
    """

    html_parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-TW">',
        "<head>",
        '<meta charset="UTF-8">',
        "<title>Accessible Document</title>",
        f"<style>{css}</style>",
        "</head>",
        "<body>"
    ]

    for item in json_data:
        x_type = item.get("type", "P")
        text = item.get("text", "")
        top = item.get("top", 0)
        left = item.get("left", 0)
        width = item.get("width", 100)
        height = item.get("height", 20)
        
        # 根據高度粗略推算字體大小
        font_size = max(10, int(height * 0.8))
        
        style = f"top: {top}px; left: {left}px; width: {width}px; height: {height}px; font-size: {font_size}px;"

        if x_type.upper() == "TABLE":
            html_parts.append('<table class="structure-table">')
            rows = item.get("rows", [])
            for row in rows:
                if row.get("type", "").upper() != "TR":
                    continue
                html_parts.append("<tr>")
                for cell in row.get("cells", []):
                    c_type = cell.get("type", "TD").lower() # th 或 td
                    c_text = cell.get("text", "")
                    c_top = cell.get("top", 0)
                    c_left = cell.get("left", 0)
                    c_width = cell.get("width", 50)
                    c_height = cell.get("height", 20)
                    c_fs = max(10, int(c_height * 0.8))
                    
                    c_style = f"top: {c_top}px; left: {c_left}px; width: {c_width}px; height: {c_height}px; font-size: {c_fs}px;"
                    # 將 table cell 設定為絕對定位
                    html_parts.append(f'<{c_type} class="invisible-text" style="{c_style}">{c_text}</{c_type}>')
                html_parts.append("</tr>")
            html_parts.append('</table>')
        elif x_type.upper() in ["H1", "H2", "H3", "H4", "H5", "H6"]:
            tag = x_type.lower()
            html_parts.append(f'<{tag} class="invisible-text" style="{style}">{text}</{tag}>')
        else:
            # 預設為 P
            html_parts.append(f'<p class="invisible-text" style="{style}">{text}</p>')

    html_parts.append("</body></html>")
    return "\n".join(html_parts)

def main():
    parser = argparse.ArgumentParser(description="產生 PDF/UA-1 隱形文字無障礙 PDF")
    parser.add_argument("background", help="背景影像 (jpg/png) 或 PDF 檔案路徑")
    parser.add_argument("json_file", help="包含結構化文字的 JSON 檔案路徑")
    parser.add_argument("-o", "--output", default="output_accessible.pdf", help="輸出的 PDF 檔案路徑")
    args = parser.parse_args()

    # 檢查檔案
    if not os.path.exists(args.background):
        print(f"找不到背景檔案: {args.background}")
        sys.exit(1)
    if not os.path.exists(args.json_file):
        print(f"找不到 JSON 檔案: {args.json_file}")
        sys.exit(1)

    # 讀取 JSON
    with open(args.json_file, "r", encoding="utf-8") as f:
        try:
            json_data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"JSON 格式錯誤: {e}")
            sys.exit(1)

    # 處理背景
    is_pdf_bg = args.background.lower().endswith(".pdf")
    img_width = 1000
    img_height = 1414
    
    if is_pdf_bg:
        print(f"從 PDF 轉換背景圖片: {args.background}")
        img_bytes, w, h = extract_first_page_as_jpeg(args.background)
        # 用 PyMuPDF 取出的寬高做為畫布尺寸
        html_str = generate_html_from_json(json_data, img_bytes, is_bytes=True, img_width=w, img_height=h)
    else:
        # 從圖片取得尺寸
        try:
            with Image.open(args.background) as img:
                img_width, img_height = img.size
        except Exception as e:
            print(f"無法讀取圖片尺寸: {e}")
            sys.exit(1)
            
        print(f"使用背景圖片: {args.background} ({img_width}x{img_height})")
        html_str = generate_html_from_json(json_data, args.background, is_bytes=False, img_width=img_width, img_height=img_height)

    # 儲存中間產物方便除錯 (可選)
    debug_html_path = args.output + ".debug.html"
    with open(debug_html_path, "w", encoding="utf-8") as f:
        f.write(html_str)
    print(f"產生中間 HTML: {debug_html_path}")

    print(f"使用 WeasyPrint 產生 PDF/UA-1 檔案中...")
    try:
        # 產生 Tagged PDF
        pdf_bytes = HTML(string=html_str, base_url=os.path.dirname(os.path.abspath(args.json_file))).write_pdf(
            pdf_variant='pdf/ua-1',
            presentational_hints=True
        )
        
        with open(args.output, "wb") as f:
            f.write(pdf_bytes)
        print(f"✅ 成功產出無障礙 PDF: {args.output}")
            
    except Exception as e:
        print(f"❌ 產生 PDF 失敗: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
