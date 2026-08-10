#!/usr/bin/env python3
"""Regrade existing evaluation JSON files with an LLM grader.

This script never calls the evaluated model. It reads existing result JSON files,
calls only the configured grader, and writes regraded copies plus reports.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from run_eval import _regenerate_html, load_config  # noqa: E402


def _grader_config(config: dict[str, Any]) -> tuple[str, str]:
    grader_server = os.environ.get("EVAL_GRADER_SERVER") or config.get("global", {}).get("grader_server", "")
    grader_model = os.environ.get("EVAL_GRADER_MODEL") or config.get("global", {}).get("grader_model", "")
    if not grader_server or not grader_model:
        raise ValueError("Set EVAL_GRADER_SERVER and EVAL_GRADER_MODEL before regrading")
    return grader_server.rstrip("/"), grader_model


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end + 1]
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # Some graders put LaTeX such as \boxed{} directly in a JSON string.
        # Escape only backslashes that cannot begin a valid JSON escape.
        repaired = []
        index = 0
        while index < len(text):
            char = text[index]
            if char != "\\":
                repaired.append(char)
                index += 1
                continue
            next_char = text[index + 1] if index + 1 < len(text) else ""
            valid_escape = next_char in '"\\/'
            if next_char in "bfnrt":
                following = text[index + 2] if index + 2 < len(text) else ""
                valid_escape = not following.isalpha()
            valid_unicode = (
                next_char == "u"
                and index + 5 < len(text)
                and all(c in "0123456789abcdefABCDEF" for c in text[index + 2:index + 6])
            )
            repaired.append("\\" if valid_escape or valid_unicode else "\\\\")
            index += 1
        result = json.loads("".join(repaired))
    if not isinstance(result, dict):
        raise ValueError("grader response is not a JSON object")
    return result

def _extract_boxed_answer(text: str) -> str | None:
    """Extract the content of the last balanced \\boxed{...} expression."""
    marker = r"\boxed{"
    start = text.rfind(marker)
    if start < 0:
        return None

    opening_brace = start + len(marker) - 1
    depth = 0
    for index in range(opening_brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                answer = text[opening_brace + 1:index].strip()
                return answer or None
    return None


def grade_case(server: str, model: str, case: dict[str, Any]) -> dict[str, Any]:
    prompt = str(case.get("prompt", "") or "")
    response = str(case.get("response", "") or "")
    expected = str(case.get("expected", "") or "")
    answer = _extract_boxed_answer(response) or str(case.get("answer", "") or "")
    grader_prompt = f"""You are a strict mathematics evaluation judge. Judge the model response for both mathematical correctness and answer-format compliance.

Important rules:
1. Read the complete problem, options, expected answer, and complete model response. Do not rely only on string matching.
2. semantic_correct means the mathematical meaning is correct. Equivalent expressions, different variable names, and equivalent fill-in answers are acceptable.
3. format_correct means the response follows the required final-answer format. A format error must not change semantic_correct.
4. For single-choice questions, the final answer inside \\boxed{{}} must contain exactly one option letter: A, B, C, or D. Output such as \\boxed{{B (6)}}, \\boxed{{6}}, or \\boxed{{Option B}} is format_correct=false, even when the mathematical meaning is correct.
5. For multiple-choice questions, the final answer inside \\boxed{{}} must contain only the option letters, such as AB or ACD, with no option text or extra explanation.
6. Selecting the wrong or incomplete set of option letters is a semantic/content error, not a format error, when the selected answer is presented in the required form. For example, outputting \\boxed{{B}} when the expected answer is BC means semantic_correct=false but format_correct=true.
7. Do not set format_correct to false merely because the answer is mathematically wrong or does not match the expected answer. Set it to false when an explicit formatting requirement is violated, including a missing required \\boxed{{}} or extra content in a single-choice or multiple-choice answer box.
8. If the answer is ambiguous or information is insufficient, semantic_correct is false and the reason must explain why.
9. Return only one valid JSON object, with no Markdown or extra text.

Output format:
{{
  "semantic_correct": true,
  "format_correct": false,
    "normalized_answer": "ignored; extracted deterministically by the caller from the last boxed expression",
    "reason": "brief explanation"
}}

Problem and answer requirements:
---
{prompt}
---
Expected answer (option letter(s) or fill-in answer):
{expected}

Deterministically extracted answer (use only as a locating hint; do not rewrite):
{answer}

Complete model response:
---
{response}
---
"""
    data = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是可靠、保守的数学答案评测器。"},
            {"role": "user", "content": grader_prompt},
        ],
        "temperature": 0,
    }
    response_obj = requests.post(
        f"{server}/v1/chat/completions",
        headers={"Content-Type": "application/json"},
        json=data,
        timeout=180,
    )
    response_obj.raise_for_status()
    content = response_obj.json()["choices"][0]["message"]["content"]
    try:
        result = _extract_json(content)
    except Exception as exc:
        return {
            "semantic_correct": False,
            "format_correct": False,
            "normalized_answer": answer or None,
            "grader_reason": f"LLM grader error: {exc}",
            "grader_response": content,
        }
    semantic = result.get("semantic_correct") is True
    formatting = result.get("format_correct") is True
    return {
        "semantic_correct": semantic,
        "format_correct": formatting,
        "normalized_answer": answer or None,
        "grader_reason": str(result.get("reason", "") or ""),
        "grader_response": content,
    }


def regrade_file(source: Path, target: Path, server: str, model: str) -> tuple[int, int]:
    data = json.loads(source.read_text(encoding="utf-8"))
    cases = data.get("task_states", {}).get("cases", {})
    semantic_count = format_count = 0
    for case in cases.values():
        if case.get("status") != "ok":
            continue
        case["original_correct"] = bool(case.get("correct", False))
        result = grade_case(server, model, case)
        case.update(result)
        case["correct"] = result["semantic_correct"]
        if result["semantic_correct"]:
            semantic_count += 1
        if result["format_correct"]:
            format_count += 1

    completed = sum(1 for case in cases.values() if case.get("status") == "ok")
    task_states = data.setdefault("task_states", {})
    task_states["semantic_correct"] = semantic_count
    task_states["format_correct"] = format_count
    task_states["original_correct"] = sum(
        1 for case in cases.values()
        if case.get("status") == "ok" and case.get("original_correct", False)
    )
    task_states["correct"] = semantic_count
    task_states["regraded_by_llm"] = True
    task_states["regraded_completed"] = completed
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    target.with_name(target.name + ".html").write_text(_regenerate_html(data, target), encoding="utf-8")
    return semantic_count, format_count


def write_report(output_root: Path, year: str, paper: str, rows: list[dict[str, Any]]) -> None:
    rows.sort(key=lambda row: (-row["semantic_rate"], -row["format_rate"], row["model"]))
    lines = [
        "# LLM 重评分报告",
        "",
        f"> **试卷**: {paper}",
        "> **说明**: 本报告基于已有模型回答重新调用 LLM grader；未重新运行被测模型。",
        "",
        "| 排名 | 模型 | 运行文件 | 数学正确率 | 格式遵循率 |",
        "|:---:|---|:---:|---:|---:|",
    ]
    for index, row in enumerate(rows, 1):
        lines.append(
            f"| {index} | {row['model']} | {row['files']}（完成 {row['completed']}/{row['total']}） | "
            f"**{row['semantic_rate']:.0%}** ({row['semantic']}/{row['total']}) | "
            f"{row['format_rate']:.0%} ({row['format']}/{row['total']}) |"
        )
    lines.extend([
        "",
        "## 重评分多次运行指标",
        "",
        "> 以下指标基于重评分字段计算，计划题数作为分母；未完成 case 视为未通过。",
        "",
        "| 模型 | 语义 Pass@1 | 语义 Pass@3 | 语义 All-Pass@3 | 语义 Best@3 | 格式 Pass@1 | 格式 Pass@3 | 格式 All-Pass@3 | 格式 Best@3 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in rows:
        lines.append(
            f"| {row['model']} | {row['semantic_pass1']:.0%} | {row['semantic_pass3']:.0%} "
            f"({row['semantic_pass3_count']}/{row['total']}) | {row['semantic_allpass']:.0%} "
            f"({row['semantic_allpass_count']}/{row['total']}) | {row['semantic_best3']:.0%} | "
            f"{row['format_pass1']:.0%} | {row['format_pass3']:.0%} "
            f"({row['format_pass3_count']}/{row['total']}) | {row['format_allpass']:.0%} "
            f"({row['format_allpass_count']}/{row['total']}) | {row['format_best3']:.0%} |"
        )
    report_path = output_root / year / paper / "report.regraded.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Report generated: {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Regrade existing results with an LLM, without rerunning evaluated models")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-root", help="Default: <configured output_root>-regraded")
    args = parser.parse_args()

    config = load_config(args.config)
    global_cfg = config["global"]
    source_root = Path(global_cfg["output_root"])
    output_root = Path(args.output_root) if args.output_root else Path(str(source_root) + "-regraded")
    dataset_path = Path(global_cfg["dataset_path"])
    year, paper = dataset_path.parent.parent.name, dataset_path.parent.name
    server, model = _grader_config(config)

    rows = []
    source_paper = source_root / year / paper
    for model_dir in sorted(p for p in source_paper.iterdir() if p.is_dir()):
        source_files = sorted(p for p in model_dir.glob("*.json") if not p.name.endswith(".regraded.json"))
        if not source_files:
            continue
        semantic = formatting = completed = total = 0
        run_stats = []
        target_dir = output_root / year / paper / model_dir.name
        for source in source_files:
            target = target_dir / source.name
            print(f"Regrading {source}")
            semantic_i, format_i = regrade_file(source, target, server, model)
            data = json.loads(target.read_text(encoding="utf-8"))
            cases = data.get("task_states", {}).get("cases", {})
            completed_i = data.get("task_states", {}).get("regraded_completed", 0)
            semantic += semantic_i
            formatting += format_i
            completed += completed_i
            total += len(cases)
            run_stats.append({
                "cases": cases,
                "semantic": semantic_i,
                "format": format_i,
                "total": len(cases),
            })
        task_ids = set().union(*(set(run["cases"]) for run in run_stats))
        semantic_pass3_count = sum(
            any(run["cases"].get(task_id, {}).get("semantic_correct") is True for run in run_stats)
            for task_id in task_ids
        )
        semantic_allpass_count = sum(
            all(run["cases"].get(task_id, {}).get("status") == "ok"
                and run["cases"].get(task_id, {}).get("semantic_correct") is True for run in run_stats)
            for task_id in task_ids
        )
        format_pass3_count = sum(
            any(run["cases"].get(task_id, {}).get("format_correct") is True for run in run_stats)
            for task_id in task_ids
        )
        format_allpass_count = sum(
            all(run["cases"].get(task_id, {}).get("status") == "ok"
                and run["cases"].get(task_id, {}).get("format_correct") is True for run in run_stats)
            for task_id in task_ids
        )
        semantic_run_rates = [run["semantic"] / run["total"] if run["total"] else 0.0 for run in run_stats]
        format_run_rates = [run["format"] / run["total"] if run["total"] else 0.0 for run in run_stats]
        rows.append({
            "model": model_dir.name,
            "files": len(source_files),
            "semantic": semantic,
            "format": formatting,
            "completed": completed,
            "total": total,
            "semantic_rate": semantic / total if total else 0.0,
            "format_rate": formatting / total if total else 0.0,
            "semantic_pass1": sum(semantic_run_rates) / len(semantic_run_rates),
            "semantic_pass3": semantic_pass3_count / total if total else 0.0,
            "semantic_pass3_count": semantic_pass3_count,
            "semantic_allpass": semantic_allpass_count / total if total else 0.0,
            "semantic_allpass_count": semantic_allpass_count,
            "semantic_best3": max(semantic_run_rates, default=0.0),
            "format_pass1": sum(format_run_rates) / len(format_run_rates),
            "format_pass3": format_pass3_count / total if total else 0.0,
            "format_pass3_count": format_pass3_count,
            "format_allpass": format_allpass_count / total if total else 0.0,
            "format_allpass_count": format_allpass_count,
            "format_best3": max(format_run_rates, default=0.0),
        })
    write_report(output_root, year, paper, rows)


if __name__ == "__main__":
    main()
