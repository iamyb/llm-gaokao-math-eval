"""
PDF 转图片脚本
用法:
    python pdf_to_images.py <pdf_path> <output_images_dir>
    python pdf_to_images.py  # 交互模式，选择PDF

支持跨页合并：将指定的页面垂直拼接为一张图片，
用于处理题目跨页的情况（如题干在第1页，选项在第2页）。
"""
import fitz
from PIL import Image
import io
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


def merge_pixmap_vertical(*pixmaps):
    """垂直拼接多个 fitz.Pixmap 为一个，返回 PIL Image"""
    images = []
    for pix in pixmaps:
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        images.append(img)

    widths = [img.width for img in images]
    max_width = max(widths)
    total_height = sum(img.height for img in images)

    # 统一宽度（水平居中，填充白色）
    unified = []
    for img in images:
        if img.width < max_width:
            new_img = Image.new("RGB", (max_width, img.height), (255, 255, 255))
            offset_x = (max_width - img.width) // 2
            new_img.paste(img, (offset_x, 0))
            unified.append(new_img)
        else:
            unified.append(img)

    # 垂直拼接
    result = Image.new("RGB", (max_width, total_height), (255, 255, 255))
    offset_y = 0
    for img in unified:
        result.paste(img, (0, offset_y))
        offset_y += img.height

    return result


def pdf_to_images(pdf_path, output_dir, zoom=PDF_ZOOM, merge_pages=None):
    """
    将 PDF 转为图片，返回图片数量

    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录
        zoom: 缩放倍数
        merge_pages: 要合并的页码列表（1-based），如 [1, 2] 表示合并第1页和第2页
    """
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
    mat = fitz.Matrix(zoom, zoom)

    # 如果有合并需求，先渲染合并页
    merged_page_nums = set()
    if merge_pages:
        log(f"合并页面: {merge_pages}")
        pixmaps = []
        for p in merge_pages:
            if p - 1 < page_count:
                page = doc[p - 1]
                pixmaps.append(page.get_pixmap(matrix=mat))
                merged_page_nums.add(p)
                log(f"  渲染合并页 {p}/{page_count}...")
            else:
                log(f"  ⚠ 页码 {p} 超出范围，跳过")

        if pixmaps:
            merged_img = merge_pixmap_vertical(*pixmaps)
            page_ids = "_".join(str(p) for p in merge_pages)
            out_path = os.path.join(output_dir, f"page_merged_{page_ids}.png")
            merged_img.save(out_path, "PNG")
            log(f"  ✓ 合并图片已保存: {out_path}")

    # 渲染单页（如果有合并图，跳过被合并的页）
    for page_num in range(page_count):
        if merge_pages and (page_num + 1) in merged_page_nums:
            log(f"  [跳过] page {page_num + 1} (已在合并图中)")
            continue
        log(f"  Processing page {page_num + 1}/{page_count}...")
        page = doc[page_num]
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
    import argparse
    parser = argparse.ArgumentParser(description="PDF 转图片，支持跨页合并")
    parser.add_argument("pdf_path", nargs="?", help="PDF 文件路径")
    parser.add_argument("output_dir", nargs="?", help="输出目录")
    parser.add_argument("--merge-pages", type=int, nargs="+", default=None,
                        help="合并指定的页面（1-based），如 --merge-pages 1 2")
    args = parser.parse_args()

    if args.pdf_path and args.output_dir:
        pdf_path = args.pdf_path
        output_dir = args.output_dir
        count = pdf_to_images(pdf_path, output_dir, merge_pages=args.merge_pages)
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
    count = pdf_to_images(pdf_path, output_dir, merge_pages=[1, 2])
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
