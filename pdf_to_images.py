"""
PDF 转图片脚本
用法:
    python pdf_to_images.py <pdf_path> <output_images_dir>
    python pdf_to_images.py  # 交互模式，选择PDF
"""
import fitz
import os
import sys
import glob
from config import BASE_DIR, PDF_INPUT_DIR, OUTPUT_DIR, PDF_ZOOM

log_lines = []

def log(msg):
    log_lines.append(str(msg))
    try:
        print(msg)
    except:
        pass


def pdf_to_images(pdf_path, output_dir, zoom=PDF_ZOOM):
    """将 PDF 转为图片，返回图片数量"""
    os.makedirs(output_dir, exist_ok=True)

    log(f"PDF path: {pdf_path}")
    log(f"File exists: {os.path.exists(pdf_path)}")

    if not os.path.exists(pdf_path):
        log(f"✗ PDF 文件不存在: {pdf_path}")
        return 0

    log("Opening PDF...")
    doc = fitz.open(pdf_path)
    log(f"PDF 共 {len(doc)} 页")

    page_count = len(doc)
    for page_num in range(page_count):
        log(f"  Processing page {page_num + 1}/{page_count}...")
        page = doc[page_num]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        out_path = os.path.join(output_dir, f"page_{page_num + 1:03d}.png")
        pix.save(out_path)

    doc.close()
    log(f"✓ 完成! 图片已保存到: {output_dir}")
    return page_count


def find_pdfs(year=None, pdf_name=None):
    """在 pdfs/ 目录下查找 PDF 文件"""
    if year:
        search_dir = os.path.join(PDF_INPUT_DIR, year)
    else:
        search_dir = PDF_INPUT_DIR

    if not os.path.exists(search_dir):
        log(f"✗ 目录不存在: {search_dir}")
        return []

    pattern = os.path.join(search_dir, "*.pdf")
    pdfs = sorted(glob.glob(pattern))

    if pdf_name:
        pdfs = [p for p in pdfs if pdf_name in os.path.basename(p)]

    return pdfs


def main():
    if len(sys.argv) >= 3:
        pdf_path = sys.argv[1]
        output_dir = sys.argv[2]
        count = pdf_to_images(pdf_path, output_dir)
        return count

    # 交互模式：列出可用 PDF
    pdfs = find_pdfs()
    if not pdfs:
        log("✗ 在 pdfs/ 目录下未找到 PDF 文件")
        log("   请将 PDF 放入 pdfs/<年份>/ 目录")
        sys.exit(1)

    log(f"找到 {len(pdfs)} 个 PDF 文件:")
    for i, p in enumerate(pdfs, 1):
        log(f"  {i}. {os.path.relpath(p, BASE_DIR)}")
    log(f"\n请输入要处理的 PDF 编号 (1-{len(pdfs)}):")

    try:
        choice = int(input("> "))
        if 1 <= choice <= len(pdfs):
            pdf_path = pdfs[choice - 1]
        else:
            log("✗ 无效编号")
            sys.exit(1)
    except ValueError:
        log("✗ 请输入数字")
        sys.exit(1)

    # 构建输出目录
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    # 从路径中提取年份
    rel_path = os.path.relpath(pdf_path, PDF_INPUT_DIR)
    year = rel_path.split(os.sep)[0] if os.sep in rel_path else "unknown"

    output_dir = os.path.join(OUTPUT_DIR, year, pdf_name, "images")
    count = pdf_to_images(pdf_path, output_dir)
    return count


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        log(traceback.format_exc())
        sys.exit(1)
    finally:
        with open(os.path.join(BASE_DIR, "run.log"), "w", encoding="utf-8") as f:
            f.write("\n".join(log_lines))
