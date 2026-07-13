"""
将 questions.jsonl 转换为交互式 HTML 预览文件
用法:
    python view_questions.py <questions.jsonl> [output.html]
    python view_questions.py --all          # 批量生成所有预览
"""
import os
import sys
import json
import glob
import argparse
import html as html_lib
import re
from pathlib import Path
from config import BASE_DIR, OUTPUT_DIR


def sanitize_text(text):
    """修复 JSONL 中被误解析成控制字符的 LaTeX 反斜杠。"""
    return text.replace("\x08", "\\b") if text else text


RAW_MATH_RUN_RE = re.compile(r"[A-Za-z0-9\\{}_^=+\-*/().,\[\] <>∩∪≤≥≠≈±·×÷√π∞∈∉⊂⊆⊃⊇→←↔]+")
EXISTING_MATH_RE = re.compile(r"(\$\$.*?\$\$|\$.*?\$|\\\(.*?\\\)|\\\[.*?\\\])", re.S)
MATH_CUE_RE = re.compile(r"[\\_^=+\-*/<>∈∪≤≥≠≈±·×÷√π∞]")


def render_text_with_math(text):
    """将题干中的 LaTeX 片段包裹进 MathJax 分隔符，并保留普通文本。"""
    if not text:
        return ""

    def is_safe_math_segment(segment):
        if '"' in segment or "'" in segment:
            return False
        if segment.count("{") != segment.count("}"):
            return False
        return True

    def render_plain_segment(segment):
        rendered = []
        last_index = 0

        for match in RAW_MATH_RUN_RE.finditer(segment):
            if match.start() > last_index:
                rendered.append(html_lib.escape(segment[last_index:match.start()]))

            math_text = match.group(0)
            if re.fullmatch(r"[_\.\s]+", math_text) or "_____" in math_text:
                rendered.append(html_lib.escape(math_text))
                last_index = match.end()
                continue

            if MATH_CUE_RE.search(math_text) and is_safe_math_segment(math_text):
                rendered.append(f"\\({html_lib.escape(math_text)}\\)")
            else:
                rendered.append(html_lib.escape(math_text))
            last_index = match.end()

        if last_index < len(segment):
            rendered.append(html_lib.escape(segment[last_index:]))

        return "".join(rendered)

    rendered_parts = []
    last_index = 0

    for match in EXISTING_MATH_RE.finditer(text):
        if match.start() > last_index:
            for line_index, line in enumerate(text[last_index:match.start()].split("\n")):
                if line_index > 0:
                    rendered_parts.append("<br>")
                rendered_parts.append(render_plain_segment(line))

        rendered_parts.append(html_lib.escape(match.group(0)))
        last_index = match.end()

    if last_index < len(text):
        for line_index, line in enumerate(text[last_index:].split("\n")):
            if line_index > 0:
                rendered_parts.append("<br>")
            rendered_parts.append(render_plain_segment(line))

    return "".join(rendered_parts)


def load_questions(jsonl_path):
    """加载 JSONL 文件，按图片分组"""
    questions_by_image = {}
    all_questions = []

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                data["question"] = sanitize_text(data.get("question", ""))
                data["answer"] = sanitize_text(data.get("answer", ""))
                img = data.get("_image", "unknown")
                if img not in questions_by_image:
                    questions_by_image[img] = []
                questions_by_image[img].append(data)
                all_questions.append(data)
            except json.JSONDecodeError:
                continue

    return questions_by_image, all_questions


def generate_html(questions_by_image, all_questions, jsonl_path, output_path):
    """生成交互式 HTML 文件"""
    # 获取图片目录（jsonl 文件的同级 images/ 目录）
    base_dir = os.path.dirname(jsonl_path)
    images_dir = os.path.join(base_dir, "images")
    has_images = os.path.exists(images_dir)

    # 构建图片数据（转为 base64 嵌入 HTML）
    image_data = {}
    if has_images:
        for img_name in sorted(questions_by_image.keys()):
            img_path = os.path.join(images_dir, img_name)
            if os.path.exists(img_path):
                with open(img_path, "rb") as f:
                    import base64
                    img_data = base64.b64encode(f.read()).decode("utf-8")
                    ext = Path(img_name).suffix.lower()
                    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")
                    image_data[img_name] = f"data:{mime};base64,{img_data}"

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>题目预览 - {os.path.basename(base_dir)}</title>
    <script>
        window.MathJax = {{
            tex: {{
                inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
                displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']]
            }},
            options: {{
                skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
            }}
        }};
    </script>
    <script id="MathJax-script" async
        src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js">
    </script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 30px;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header h1 {{ font-size: 24px; margin-bottom: 8px; }}
        .header .stats {{ font-size: 14px; opacity: 0.9; }}
        .toolbar {{
            display: flex;
            gap: 10px;
            margin-top: 12px;
            align-items: center;
        }}
        .toolbar input {{
            flex: 1;
            max-width: 400px;
            padding: 8px 14px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            outline: none;
        }}
        .toolbar button {{
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            background: rgba(255,255,255,0.2);
            color: white;
            cursor: pointer;
            font-size: 13px;
            transition: background 0.2s;
        }}
        .toolbar button:hover {{ background: rgba(255,255,255,0.3); }}
        .toolbar button.active {{ background: rgba(255,255,255,0.5); }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
        .image-section {{
            background: white;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            overflow: hidden;
        }}
        .section-header {{
            background: #f8f9fa;
            padding: 14px 20px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #e9ecef;
            user-select: none;
            transition: background 0.2s;
        }}
        .section-header:hover {{ background: #e9ecef; }}
        .section-header h2 {{ font-size: 16px; color: #495057; }}
        .section-header .arrow {{
            transition: transform 0.3s;
            font-size: 12px;
            color: #868e96;
        }}
        .section-header.collapsed .arrow {{ transform: rotate(-90deg); }}
        .section-body {{ display: none; }}
        .section-body.open {{ display: block; }}
        .comparison {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 0;
        }}
        .comparison.no-image {{ grid-template-columns: 1fr; }}
        .original-image {{
            background: #f8f9fa;
            padding: 20px;
            border-right: 1px solid #e9ecef;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .original-image img {{
            max-width: 100%;
            max-height: none;
            object-fit: contain;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .questions-list {{ padding: 20px; }}
        .question-item {{
            padding: 16px;
            margin-bottom: 12px;
            background: #fafbfc;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            transition: all 0.2s;
        }}
        .question-item:hover {{
            background: #f0f3ff;
            border-left-color: #764ba2;
        }}
        .question-item.highlight {{
            background: #fff3cd;
            border-left-color: #ffc107;
        }}
        .question-text {{
            font-size: 15px;
            line-height: 1.8;
            margin-bottom: 8px;
        }}
        .question-answer {{
            font-size: 13px;
            color: #28a745;
            padding: 6px 10px;
            background: #d4edda;
            border-radius: 4px;
            display: inline-block;
        }}
        .question-answer.empty {{
            color: #868e96;
            background: #f1f3f5;
            font-style: italic;
        }}
        .no-results {{
            text-align: center;
            padding: 60px 20px;
            color: #868e96;
            font-size: 16px;
        }}
        .export-menu {{
            position: relative;
            display: inline-block;
        }}
        .export-dropdown {{
            display: none;
            position: absolute;
            right: 0;
            top: 100%;
            margin-top: 4px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            min-width: 160px;
            z-index: 200;
            overflow: hidden;
        }}
        .export-dropdown.show {{ display: block; }}
        .export-dropdown button {{
            display: block;
            width: 100%;
            padding: 10px 16px;
            border: none;
            background: white;
            color: #333;
            text-align: left;
            cursor: pointer;
            font-size: 13px;
        }}
        .export-dropdown button:hover {{ background: #f8f9fa; }}
        @media (max-width: 900px) {{
            .comparison {{ grid-template-columns: 1fr; }}
            .original-image {{ border-right: none; border-bottom: 1px solid #e9ecef; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📝 题目预览</h1>
        <div class="stats">
            {os.path.basename(base_dir)} | 共 {len(all_questions)} 道题 | {len(questions_by_image)} 张图片
        </div>
        <div class="toolbar">
            <input type="text" id="searchInput" placeholder="搜索题号、关键词..." oninput="filterQuestions()">
            <button onclick="toggleAllSections()" id="toggleBtn">全部展开</button>
            <button onclick="toggleView()" id="viewBtn">双栏视图</button>
            <div class="export-menu">
                <button onclick="toggleExportMenu()">导出 ▾</button>
                <div class="export-dropdown" id="exportDropdown">
                    <button onclick="exportMarkdown()">📄 Markdown</button>
                    <button onclick="exportText()">📝 纯文本</button>
                    <button onclick="exportJSON()">📊 JSON</button>
                </div>
            </div>
        </div>
    </div>

    <div class="container" id="container">
"""

    # 生成每个图片的区块
    for img_name in sorted(questions_by_image.keys()):
        questions = questions_by_image[img_name]
        img_data_uri = image_data.get(img_name, "")

        html += f"""        <div class="image-section" data-image="{img_name}">
            <div class="section-header" onclick="toggleSection(this)">
                <h2>📄 {img_name} <span style="color: #868e96; font-size: 13px;">({len(questions)} 道题)</span></h2>
                <span class="arrow">▼</span>
            </div>
            <div class="section-body open">
                <div class="comparison{' no-image' if not img_data_uri else ''}">
"""

        if img_data_uri:
            html += f"""                    <div class="original-image">
                        <img src="{img_data_uri}" alt="{img_name}">
                    </div>
"""

        html += """                    <div class="questions-list">
"""

        for q in questions:
            answer_class = "" if q.get("answer") else " empty"
            answer_text = q.get("answer") or "暂无答案"
            question_attr = html_lib.escape(q['question'], quote=True)
            question_html = render_text_with_math(q['question'])
            answer_html = render_text_with_math(answer_text)
            html += f"""                        <div class="question-item" data-question="{question_attr}">
                            <div class="question-text">{question_html}</div>
                            <div class="question-answer{answer_class}">答案: {answer_html}</div>
                        </div>
"""

        html += """                    </div>
                </div>
            </div>
        </div>
"""

    # 添加 JavaScript
    html += """    </div>

    <script>
        let allExpanded = true;
        let showImage = true;

        function toggleSection(header) {
            const body = header.nextElementSibling;
            const arrow = header.querySelector('.arrow');
            header.classList.toggle('collapsed');
            body.classList.toggle('open');
        }

        function toggleAllSections() {
            const sections = document.querySelectorAll('.section-body');
            const headers = document.querySelectorAll('.section-header');
            const btn = document.getElementById('toggleBtn');
            allExpanded = !allExpanded;

            sections.forEach((body, i) => {
                if (allExpanded) {
                    body.classList.add('open');
                    headers[i].classList.remove('collapsed');
                } else {
                    body.classList.remove('open');
                    headers[i].classList.add('collapsed');
                }
            });

            btn.textContent = allExpanded ? '全部折叠' : '全部展开';
        }

        function toggleView() {
            const comparisons = document.querySelectorAll('.comparison');
            const btn = document.getElementById('viewBtn');
            showImage = !showImage;

            comparisons.forEach(comp => {
                const imgDiv = comp.querySelector('.original-image');
                if (imgDiv) {
                    imgDiv.style.display = showImage ? 'flex' : 'none';
                }
            });

            btn.textContent = showImage ? '隐藏原图' : '显示原图';
            btn.classList.toggle('active', !showImage);
        }

        function filterQuestions() {
            const query = document.getElementById('searchInput').value.toLowerCase();
            const items = document.querySelectorAll('.question-item');
            const sections = document.querySelectorAll('.image-section');
            let visibleCount = 0;

            items.forEach(item => {
                const text = item.getAttribute('data-question').toLowerCase();
                const visible = !query || text.includes(query);
                item.style.display = visible ? 'block' : 'none';
                item.classList.toggle('highlight', !!query && visible);
                if (visible) visibleCount++;
            });

            // 隐藏没有可见题目的区块
            sections.forEach(section => {
                const visibleItems = section.querySelectorAll('.question-item[style="display: block"], .question-item:not([style])');
                const hasVisible = Array.from(visibleItems).some(i => i.style.display !== 'none');
                section.style.display = hasVisible ? 'block' : 'none';
            });

            if (query && visibleCount === 0) {
                let noResults = document.getElementById('noResults');
                if (!noResults) {
                    noResults = document.createElement('div');
                    noResults.id = 'noResults';
                    noResults.className = 'no-results';
                    document.getElementById('container').appendChild(noResults);
                }
                noResults.textContent = '未找到匹配的题目';
            } else {
                const noResults = document.getElementById('noResults');
                if (noResults) noResults.remove();
            }
        }

        function toggleExportMenu() {
            document.getElementById('exportDropdown').classList.toggle('show');
        }

        document.addEventListener('click', function(e) {
            if (!e.target.closest('.export-menu')) {
                document.getElementById('exportDropdown').classList.remove('show');
            }
        });

        function exportMarkdown() {
            const items = document.querySelectorAll('.question-item');
            let md = '# 题目列表\\n\\n';
            items.forEach(item => {
                const q = item.querySelector('.question-text').textContent;
                const a = item.querySelector('.question-answer').textContent.replace('答案: ', '');
                md += `## ${q}\\n\\n**答案:** ${a}\\n\\n---\\n\\n`;
            });
            downloadFile('questions.md', md, 'text/markdown');
        }

        function exportText() {
            const items = document.querySelectorAll('.question-item');
            let text = '';
            items.forEach((item, i) => {
                const q = item.querySelector('.question-text').textContent;
                const a = item.querySelector('.question-answer').textContent.replace('答案: ', '');
                text += `${q}\\n答案: ${a}\\n\\n`;
            });
            downloadFile('questions.txt', text, 'text/plain');
        }

        function exportJSON() {
            const items = document.querySelectorAll('.question-item');
            const data = Array.from(items).map(item => ({
                question: item.querySelector('.question-text').textContent,
                answer: item.querySelector('.question-answer').textContent.replace('答案: ', '')
            }));
            downloadFile('questions.json', JSON.stringify(data, null, 2), 'application/json');
        }

        function downloadFile(filename, content, mimeType) {
            const blob = new Blob([content], {{ type: mimeType + ';charset=utf-8' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            a.click();
            URL.revokeObjectURL(url);
        }

        // 重新渲染 MathJax
        if (typeof MathJax !== 'undefined') {{
            MathJax.typesetPromise().catch(err => console.log('MathJax error:', err));
        }}
    </script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    parser = argparse.ArgumentParser(description="将 questions.jsonl 转换为 HTML 预览")
    parser.add_argument("jsonl", nargs="?", help="JSONL 文件路径")
    parser.add_argument("output", nargs="?", help="输出 HTML 路径（默认：同级目录 questions.html）")
    parser.add_argument("--all", action="store_true", help="批量生成所有预览")
    args = parser.parse_args()

    if args.all:
        # 批量模式：扫描 output/ 下所有 questions.jsonl
        pattern = os.path.join(OUTPUT_DIR, "**", "questions.jsonl")
        jsonl_files = glob.glob(pattern, recursive=True)

        if not jsonl_files:
            print("✗ 未找到 questions.jsonl 文件")
            sys.exit(1)

        print(f"找到 {len(jsonl_files)} 个 questions.jsonl 文件")
        for jsonl_path in jsonl_files:
            output_path = os.path.join(os.path.dirname(jsonl_path), "questions.html")
            print(f"\n→ 处理: {os.path.relpath(jsonl_path, BASE_DIR)}")
            try:
                questions_by_image, all_questions = load_questions(jsonl_path)
                generate_html(questions_by_image, all_questions, jsonl_path, output_path)
                print(f"  ✓ 生成: {os.path.relpath(output_path, BASE_DIR)} ({len(all_questions)} 道题)")
            except Exception as e:
                print(f"  ✗ 失败: {e}")

        print(f"\n✓ 批量生成完成")
        return

    if not args.jsonl:
        parser.print_help()
        sys.exit(1)

    jsonl_path = os.path.abspath(args.jsonl)
    if not os.path.exists(jsonl_path):
        print(f"✗ 文件不存在: {jsonl_path}")
        sys.exit(1)

    output_path = args.output or os.path.join(os.path.dirname(jsonl_path), "questions.html")

    questions_by_image, all_questions = load_questions(jsonl_path)
    generate_html(questions_by_image, all_questions, jsonl_path, output_path)

    print(f"✓ 生成完成!")
    print(f"  输入: {os.path.relpath(jsonl_path, BASE_DIR)}")
    print(f"  输出: {os.path.relpath(output_path, BASE_DIR)}")
    print(f"  题目: {len(all_questions)} 道")
    print(f"  图片: {len(questions_by_image)} 张")
    print(f"\n在浏览器中打开: {output_path}")


if __name__ == "__main__":
    main()
