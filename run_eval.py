#!/usr/bin/env python3
"""
Batch evaluation runner — YAML config driven, idempotent.
Supports: global → presets → model three-level parameter override.

Usage:
    python run_eval.py [--config eval_config.yaml]
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from math import sqrt
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip

import yaml


def _env_or(cfg: dict, key: str, env_var: str, default: str = "") -> str:
    """Read from env var first, fall back to YAML config value, then default."""
    val = os.environ.get(env_var)
    if val:
        return val
    val = cfg.get(key)
    if val:
        return str(val)
    return default


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_params(global_cfg: dict, presets: dict, model_cfg: dict) -> dict:
    """
    Parameter merge priority (low → high):
      global → preset → model-level fields
    """
    merged = {**global_cfg}

    # 1. Apply preset
    preset_name = model_cfg.get("preset")
    if preset_name and preset_name in presets:
        merged.update(presets[preset_name])

    # 2. Apply model-level overrides
    overridable = {
        "server", "temperature", "top_k", "top_p", "min_p", "seed",
        "threads", "reasoning_effort",
    }
    for key in overridable:
        if key in model_cfg:
            merged[key] = model_cfg[key]

    return merged


def compute_missing_runs(model_dir: Path, base_output: str, runs: int) -> list[str]:
    stem, suffix = Path(base_output).stem, Path(base_output).suffix
    wanted = [base_output] + [f"{stem}_{i}{suffix}" for i in range(1, runs)]
    existing = {f.name for f in model_dir.glob("*.json")}
    return [name for name in wanted if name not in existing]


def validate_reusable_result(filepath: Path, model_name: str, dataset_path: str) -> dict:
    """Load and validate a complete result that can be reused without inference."""
    data = load_run(filepath)
    if data.get("model_name") != model_name:
        raise ValueError(
            f"Model mismatch in reuse source {filepath}: "
            f"expected '{model_name}', found '{data.get('model_name')}'"
        )
    source_dataset = data.get("dataset_path")
    if source_dataset and Path(source_dataset).as_posix() != Path(dataset_path).as_posix():
        raise ValueError(
            f"Dataset mismatch in reuse source {filepath}: "
            f"expected '{dataset_path}', found '{source_dataset}'"
        )
    cases = data.get("task_states", {}).get("cases", {})
    tasks = data.get("tasks", [])
    if not tasks or len(cases) != len(tasks) or any(
        cases.get(task_id, {}).get("status") != "ok" for task_id in tasks
    ):
        raise ValueError(f"Reuse source is incomplete: {filepath}")
    return data


def reuse_result(source: Path, target: Path, model_name: str, dataset_path: str) -> None:
    """Copy a validated result and its HTML report into the current experiment."""
    data = validate_reusable_result(source, model_name, dataset_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    source_html = Path(str(source) + ".html")
    target_html = Path(str(target) + ".html")
    if source_html.exists():
        shutil.copy2(source_html, target_html)
    else:
        target_html.write_text(_regenerate_html(data, target), encoding="utf-8")


def load_run(filepath: Path) -> dict:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def wilson_interval(correct: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return (0.0, 1.0)
    p = correct / total
    z2 = z * z / total
    center = (p + z2 / 2) / (1 + z2)
    margin = z * sqrt((p * (1 - p) + z2 / 4) / total) / (1 + z2)
    return (center - margin, center + margin)


def _strip_wrappers(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""

    value = value.replace("，", ",").replace("；", ";").replace("、", ",")
    value = re.sub(r"^\$+|\$+$", "", value).strip()

    while True:
        unboxed = re.sub(r"^\\boxed\{(.*)\}$", r"\1", value)
        if unboxed == value:
            break
        value = unboxed.strip()

    return value


def _extract_boxed_answer(text: str) -> Optional[str]:
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


def _display_answer(response: str, fallback: str = "") -> str:
    answer = _extract_boxed_answer(response) or fallback
    return answer.strip()


def _normalize_piece(text: str) -> str:
    value = _strip_wrappers(text)
    value = re.sub(r"^\s*(?:\\?[A-Za-z]+(?:\([^)]*\))?)\s*=\s*", "", value)
    value = re.sub(r"\s+", "", value)
    return value


def _split_pieces(text: str) -> list[str]:
    value = _strip_wrappers(text)
    pieces = [piece.strip() for piece in re.split(r"[,，;；、\n]+", value) if piece.strip()]
    return [_normalize_piece(piece) for piece in pieces] if pieces else []


def _answers_equivalent(expected: str, candidate: str) -> tuple[bool, str]:
    expected_pieces = _split_pieces(expected)
    candidate_pieces = _split_pieces(candidate)
    if not expected_pieces or not candidate_pieces:
        return False, ""
    if len(expected_pieces) == len(candidate_pieces) and len(expected_pieces) > 1:
        return all(e == c for e, c in zip(expected_pieces, candidate_pieces)), ", ".join(candidate_pieces)
    return "".join(expected_pieces) == "".join(candidate_pieces), ", ".join(candidate_pieces)


def _escape_html(s: str) -> str:
    """HTML-escape string (same logic as llama-eval.py)."""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&#39;"))


def _regenerate_html(data: dict, json_path: Path) -> str:
    """
    Regenerate HTML report with the same format as llama-eval.py dump_html.
    Takes the JSON data dict and produces a full HTML report.
    """
    task_states = data.get("task_states", {})
    cases = task_states.get("cases", {})
    model_name = data.get("model_name", "N/A")
    dataset_type = data.get("id", "gaokao")
    sampling_config = data.get("sampling_config", {})
    total_time = task_states.get("total_time", 0.0)

    # Build tasks_to_save from cases keys (ordered)
    tasks_to_save = [(i, tid) for i, tid in enumerate(sorted(cases.keys()))]

    completed = {tid: c for tid, c in cases.items() if c.get("status") == "ok"}
    n_correct = sum(1 for c in completed.values() if c.get("correct", False))
    n_incorrect = len(completed) - n_correct
    n_pending = len(tasks_to_save) - len(completed)
    accuracy = n_correct / len(completed) * 100 if completed else 0.0
    ci_lower, ci_upper = wilson_interval(n_correct, len(completed)) if completed else (0.0, 1.0)
    n_semantic = sum(1 for c in completed.values() if c.get("semantic_correct", c.get("correct", False)))
    n_format = sum(1 for c in completed.values() if c.get("format_correct", False))
    semantic_accuracy = n_semantic / len(completed) * 100 if completed else 0.0
    format_accuracy = n_format / len(completed) * 100 if completed else 0.0

    sampling_parts = []
    for k, v in sampling_config.items():
        if v is not None:
            sampling_parts.append(f"{k}={v}")
    sampling_str = ", ".join(sampling_parts) if sampling_parts else "default"

    # Build detail rows
    rows = []
    for i, task_id in tasks_to_save:
        case = cases.get(task_id, {})
        status = case.get("status", "pending")
        expected = case.get("expected", "")
        response = case.get("response", "") or ""
        answer = (
            _display_answer(
                response,
                case.get("answer") or case.get("normalized_answer") or "",
            )
            if status == "ok" else ""
        )
        is_correct = case.get("correct", False) if status == "ok" else False
        semantic_correct = case.get("semantic_correct", is_correct) if status == "ok" else False
        format_correct = case.get("format_correct", False) if status == "ok" else False
        prompt = case.get("prompt", "") or ""
        grader_log = case.get("grader_log", {})

        if status == "ok":
            status_class = "correct" if is_correct else "incorrect"
            status_text = "\u2713" if is_correct else "\u2717"
        elif status == "pending":
            status_class = "pending"
            status_text = "\u2013"
        else:
            status_class = "error"
            status_text = "!"

        tokens = case.get("tokens")
        tokens_str = str(tokens) if tokens is not None else ""
        tps_gen = case.get("tps_gen")
        tps_str = f"{tps_gen:.1f}" if tps_gen is not None else ""
        t_gen_ms = case.get("t_gen_ms")
        t_gen_str = f"{t_gen_ms/1000:.1f}" if t_gen_ms is not None else ""
        reasoning_content = case.get("reasoning_content", "") or ""
        server_name = case.get("server_name", "") or ""

        escaped_response = _escape_html(response)
        escaped_prompt = _escape_html(prompt)
        escaped_reasoning = _escape_html(reasoning_content)
        grader_log_str = _escape_html(json.dumps(grader_log, indent=2))
        escaped_server = _escape_html(server_name)

        answer_class = status_class if status == "ok" else ""
        rows.append(f"""<tr class="task-row" onclick="toggleDetails('{task_id}')">
                <td>{task_id}</td>
                <td class="{status_class}">{status_text}</td>
                <td>{_escape_html(expected)}</td>
                <td class="{answer_class}">{_escape_html(answer)}</td>
            <td class="{'correct' if semantic_correct else 'incorrect'}">{'✓' if semantic_correct else '✗'}</td>
            <td class="{'correct' if format_correct else 'incorrect'}">{'✓' if format_correct else '✗'}</td>
                <td>{tokens_str}</td>
                <td>{tps_str}</td>
                <td>{t_gen_str}</td>
                <td>{escaped_server}</td>
            </tr>
            <tr id="details-{task_id}" class="details-row">
                <td colspan="10">
                    <div class="details-content">
                        <b>Semantic correct</b><pre>{str(bool(semantic_correct))}</pre>
                        <b>Format correct</b><pre>{str(bool(format_correct))}</pre>
                        <b>Prompt</b><pre>{escaped_prompt}</pre>
                        <b>Response</b><pre>{escaped_response}</pre>
                        {f'<b>Reasoning</b><pre>{escaped_reasoning}</pre>' if escaped_reasoning else ''}
                        <b>Grader</b><pre>{grader_log_str}</pre>
                    </div>
                </td>
            </tr>""")

    rows_html = "\n".join(rows)

    # ---- per-problem summary table ----
    problem_groups: dict[int, list[dict]] = {}
    for _tid, _case in cases.items():
        if _case.get("status") != "ok":
            continue
        _pidx = _case.get("problem_idx")
        if _pidx is None:
            _p_parts = _tid.rsplit("_", 2)
            _pidx = int(_p_parts[-1]) if len(_p_parts) >= 3 else 0
        problem_groups.setdefault(_pidx, []).append(_case)

    summary_rows_html = ""
    if problem_groups:
        def _stat(v, fmt=".1f", avg_fmt=None):
            if not v:
                return ("\u2013", "\u2013", "\u2013")
            af = fmt if avg_fmt is None else avg_fmt
            return (f"{min(v):{fmt}}", f"{sum(v)/len(v):{af}}", f"{max(v):{fmt}}")

        summary_data = []
        for pidx, g in problem_groups.items():
            runs = len(g)
            n_ok = sum(1 for c in g if c.get("correct", False))
            toks = [c["tokens"] for c in g if c.get("tokens") is not None]
            tps = [c["tps_gen"] for c in g if c.get("tps_gen") is not None]
            tg = [c["t_gen_ms"] / 1000 for c in g if c.get("t_gen_ms") is not None]
            summary_data.append((
                pidx, runs, n_ok,
                _stat(toks, "d", ".0f"),
                _stat(tps),
                _stat(tg),
            ))

        summary_data.sort(key=lambda r: r[0])

        summary_rows_html = "\n".join(
            f"""<tr class="summary-row">
                    <td>{p:03d}</td>
                    <td>{r}</td>
                    <td>{n}/{r}</td>
                    <td>{tk[0]}</td><td>{tk[1]}</td><td>{tk[2]}</td>
                    <td>{tp[0]}</td><td>{tp[1]}</td><td>{tp[2]}</td>
                    <td>{tg[0]}</td><td>{tg[1]}</td><td>{tg[2]}</td>
                </tr>"""
            for p, r, n, tk, tp, tg in summary_data
        )

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{dataset_type.upper()} Eval</title>
<style>
        body {{ font-family: system-ui, sans-serif; margin: 0; padding: 16px; background: #fff; color: #222; }}
        .bar {{ padding: 8px 0; font-size: 13px; color: #555; font-family: 'SF Mono', 'Menlo', 'Consolas', monospace; display: grid; grid-template-columns: auto 1fr auto 1fr; gap: 2px 12px; align-items: baseline; }}
        .bar .label {{ color: #888; }}
        .bar .value {{ color: #222; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 13px; font-family: 'SF Mono', 'Menlo', 'Consolas', monospace; }}
        th {{ text-align: left; padding: 6px 8px; border-bottom: 2px solid #ccc; font-weight: 600; }}
        td {{ padding: 4px 8px; border-bottom: 1px solid #eee; vertical-align: top; }}
        .task-row {{ cursor: pointer; }}
        .task-row:hover {{ background: #f5f5f5; }}
        .correct {{ color: #1a7f37; }}
        .incorrect {{ color: #cf222e; }}
        .pending {{ color: #888; }}
        .error {{ color: #9a6700; }}
        .details-row {{ display: none; }}
        .details-row.open {{ display: table-row; }}
        .details-content {{ padding: 8px 16px; background: #f6f8fa; font-size: 12px; }}
        .details-content b {{ color: #555; }}
        .details-content pre {{ background: #fff; border: 1px solid #e1e4e8; padding: 8px; overflow-x: auto; white-space: pre-wrap; word-wrap: break-word; margin: 4px 0 8px; }}
        .summary-table {{ margin-bottom: 16px; font-size: 13px; width: 100%; }}
        .summary-row {{ background: #fafbfc; }}
        .summary-row:hover {{ background: #f5f5f5; }}
        .summary-table th {{ text-align: right; font-weight: 600; }}
        .summary-table th:first-child {{ text-align: left; }}
        .summary-table th[colspan] {{ text-align: center; }}
        .summary-table td {{ text-align: right; }}
        .summary-table td:first-child {{ text-align: left; }}
        .tabs {{ display: flex; border-bottom: 2px solid #ddd; margin: 12px 0 0; }}
        .tab-btn {{ padding: 6px 16px; border: none; background: none; font-size: 13px; cursor: pointer; color: #555; border-bottom: 2px solid transparent; margin-bottom: -2px; font-weight: 500; }}
        .tab-btn:hover {{ color: #222; }}
        .tab-btn.active {{ color: #222; border-bottom-color: #222; font-weight: 600; }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
</style>
</head>
<body>
    <div class="bar">
        <div class="label">Dataset</div><div class="value"><b>{dataset_type.upper()}</b></div>
        <div class="label">Model</div><div class="value"><b>{model_name}</b></div>
        <div class="label">Accuracy</div><div class="value"><b>{accuracy:.1f}%</b> [{ci_lower*100:.1f}%, {ci_upper*100:.1f}%]</div>
        <div class="label">Correct</div><div class="value"><span class="correct">{n_correct}</span> / {len(completed)}</div>
        <div class="label">Semantic</div><div class="value"><span class="correct">{n_semantic}</span> / {len(completed)} ({semantic_accuracy:.1f}%)</div>
        <div class="label">Format</div><div class="value"><span class="correct">{n_format}</span> / {len(completed)} ({format_accuracy:.1f}%)</div>
        <div class="label">Pending</div><div class="value">{n_pending}</div>
        <div class="label">Time</div><div class="value">{total_time:.1f}s</div>
        <div class="label">Sampling</div><div class="value">{sampling_str}</div>
    </div>
    <div class="tabs">
        <button class="tab-btn active" data-tab="detailed" onclick="switchTab(this)">Detailed</button>
        <button class="tab-btn" data-tab="summary" onclick="switchTab(this)">Summary</button>
    </div>
    <div id="tab-detailed" class="tab-content active">
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th></th>
                    <th>Gold</th>
                    <th>Answer</th>
                    <th>Semantic</th>
                    <th>Format</th>
                    <th>Tokens</th>
                    <th>T/s</th>
                    <th>Gen s</th>
                    <th>Server</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    <div id="tab-summary" class="tab-content">
        <table class="summary-table">
            <thead>
                <tr>
                    <th>Problem</th>
                    <th>Runs</th>
                    <th>Correct</th>
                    <th colspan="3">Tokens</th>
                    <th colspan="3">T/s</th>
                    <th colspan="3">Gen s</th>
                </tr>
                <tr>
                    <th></th>
                    <th></th>
                    <th></th>
                    <th>min</th><th>avg</th><th>max</th>
                    <th>min</th><th>avg</th><th>max</th>
                    <th>min</th><th>avg</th><th>max</th>
                </tr>
            </thead>
            <tbody>
                {summary_rows_html}
            </tbody>
        </table>
    </div>
    <script>
        function toggleDetails(id) {{ document.getElementById('details-'+id).classList.toggle('open'); }}
        function switchTab(btn) {{
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('tab-'+btn.dataset.tab).classList.add('active');
        }}
    </script>
</body>
</html>"""
    return html_content


def correct_existing_result_file(json_path: Path) -> int:
    data = load_run(json_path)
    task_states = data.get("task_states", {})
    cases = task_states.get("cases", {})

    corrected_cases = 0
    for case in cases.values():
        if case.get("status") != "ok":
            continue
        if case.get("correct", False):
            continue
        expected = str(case.get("expected", "") or "").strip()
        candidate = str(case.get("answer") or case.get("response") or "").strip()
        if not expected or not candidate:
            continue

        matched, normalized_candidate = _answers_equivalent(expected, candidate)
        if not matched:
            continue

        case["correct"] = True
        if normalized_candidate and case.get("answer") != normalized_candidate:
            case["answer"] = normalized_candidate
        corrected_cases += 1

    if not corrected_cases:
        return 0

    task_states["correct"] = sum(1 for case in cases.values() if case.get("correct", False))
    total_completed = sum(1 for case in cases.values() if case.get("status") == "ok")
    if total_completed:
        task_states["ci_lower"], task_states["ci_upper"] = wilson_interval(task_states["correct"], total_completed)
    else:
        task_states["ci_lower"], task_states["ci_upper"] = (0.0, 1.0)
    data["task_states"] = task_states

    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path = Path(str(json_path) + ".html")
    html_path.write_text(_regenerate_html(data, json_path), encoding="utf-8")
    return corrected_cases


def find_run_files(model_dir: Path, base_output: str, runs: int) -> list[tuple[str, Path]]:
    """Find existing run files, return list of (run_label, filepath)."""
    stem, suffix = Path(base_output).stem, Path(base_output).suffix
    wanted = [("base", base_output)] + [("_" + str(i), f"{stem}_{i}{suffix}") for i in range(1, runs)]
    found = []
    for label, filename in wanted:
        fp = model_dir / filename
        if fp.exists():
            found.append((label, fp))
    return found


def analyze_results(config: dict, output_root: Path, year: str, paper_dir: str,
                    base_output: str, expected_runs: int, show_detail: bool = False):
    """Analyze evaluation results and print summary table."""
    models = config["models"]
    all_results = []

    for model_cfg in models:
        model_name = model_cfg["name"]
        model_dir = output_root / year / paper_dir / model_name
        if not model_dir.exists():
            continue

        run_files = find_run_files(model_dir, base_output, expected_runs)
        if not run_files:
            continue

        results = []
        all_cases_list = []
        for label, filepath in run_files:
            data = load_run(filepath)
            ts = data.get("task_states", {})
            total = ts.get("total", 0)
            correct = ts.get("correct", 0)
            cases = ts.get("cases", {})
            acc = correct / total if total > 0 else 0.0
            semantic_correct = sum(
                1 for case in cases.values()
                if case.get("status") == "ok"
                and case.get("semantic_correct", case.get("correct", False))
            )
            format_available = any("format_correct" in case for case in cases.values())
            format_correct = sum(
                1 for case in cases.values()
                if case.get("status") == "ok" and case.get("format_correct", False)
            )
            results.append({
                "label": label,
                "total": total,
                "correct": correct,
                "accuracy": acc,
                "semantic_correct": semantic_correct,
                "semantic_accuracy": semantic_correct / total if total > 0 else 0.0,
                "format_correct": format_correct,
                "format_accuracy": format_correct / total if total > 0 else 0.0,
                "format_available": format_available,
            })
            all_cases_list.append(cases)

        best = max(results, key=lambda r: r["accuracy"])

        # pass@1 — average accuracy across all runs
        pass1_acc = sum(r["accuracy"] for r in results) / len(results)

        # Collect all task IDs across runs
        all_task_ids = set()
        for cases in all_cases_list:
            all_task_ids.update(cases.keys())
        total_questions = len(all_task_ids)

        # pass@3 — correct if correct in ANY run
        pass3_set = set()
        # all-pass@3 — correct in ALL runs
        allpass_set = set()
        semantic_pass3_set = set()
        semantic_allpass_set = set()
        format_pass3_set = set()
        format_allpass_set = set()
        # Single vs Multi choice classification
        single_task_ids = set()
        multi_task_ids = set()
        single_correct_pass3 = 0
        multi_correct_pass3 = 0

        for task_id in all_task_ids:
            correct_per_run = []
            semantic_per_run = []
            format_per_run = []
            format_seen = False
            answers_per_run = []
            expected = None

            for cases in all_cases_list:
                if task_id in cases:
                    case = cases[task_id]
                    correct_per_run.append(case.get("correct", False))
                    semantic_per_run.append(case.get("semantic_correct", case.get("correct", False)))
                    if "format_correct" in case:
                        format_seen = True
                        format_per_run.append(case.get("format_correct", False))
                    answers_per_run.append(case.get("answer", ""))
                    if expected is None:
                        expected = case.get("expected", "")

            # pass@3
            if any(correct_per_run):
                pass3_set.add(task_id)

            # all-pass@3
            if all(correct_per_run):
                allpass_set.add(task_id)

            if any(semantic_per_run):
                semantic_pass3_set.add(task_id)
            if len(semantic_per_run) == len(all_cases_list) and all(semantic_per_run):
                semantic_allpass_set.add(task_id)
            if format_seen and any(format_per_run):
                format_pass3_set.add(task_id)
            if format_seen and len(format_per_run) == len(all_cases_list) and all(format_per_run):
                format_allpass_set.add(task_id)

            # Single vs Multi classification
            if expected and len(expected.strip()) <= 2:
                single_task_ids.add(task_id)
                if any(correct_per_run):
                    single_correct_pass3 += 1
            else:
                multi_task_ids.add(task_id)
                if any(correct_per_run):
                    multi_correct_pass3 += 1

        pass3_count = len(pass3_set)
        pass3_acc = pass3_count / total_questions if total_questions > 0 else 0.0
        allpass_count = len(allpass_set)
        allpass_acc = allpass_count / total_questions if total_questions > 0 else 0.0
        semantic_pass3_count = len(semantic_pass3_set)
        semantic_pass3_acc = semantic_pass3_count / total_questions if total_questions > 0 else 0.0
        semantic_allpass_count = len(semantic_allpass_set)
        semantic_allpass_acc = semantic_allpass_count / total_questions if total_questions > 0 else 0.0
        format_available = any(r["format_available"] for r in results)
        format_pass1_acc = (
            sum(r["format_accuracy"] for r in results) / len(results)
            if format_available and results else None
        )
        format_pass3_count = len(format_pass3_set) if format_available else None
        format_pass3_acc = format_pass3_count / total_questions if format_pass3_count is not None and total_questions > 0 else None
        format_allpass_count = len(format_allpass_set) if format_available else None
        format_allpass_acc = format_allpass_count / total_questions if format_allpass_count is not None and total_questions > 0 else None
        # Best@3 — best accuracy among all runs
        best_acc = max(r["accuracy"] for r in results)
        semantic_best3_acc = max(r["semantic_accuracy"] for r in results)
        format_best3_acc = max(r["format_accuracy"] for r in results) if format_available else None

        single_total = len(single_task_ids)
        multi_total = len(multi_task_ids)
        single_acc = single_correct_pass3 / single_total if single_total > 0 else 0.0
        multi_acc = multi_correct_pass3 / multi_total if multi_total > 0 else 0.0

        all_results.append({
            "model": model_name,
            "runs": results,
            "found": len(run_files),
            "best": best,
            "pass1_acc": pass1_acc,
            "pass3_count": pass3_count,
            "pass3_acc": pass3_acc,
            "allpass_count": allpass_count,
            "allpass_acc": allpass_acc,
            "best3_acc": best_acc,
            "semantic_pass1_acc": sum(r["semantic_accuracy"] for r in results) / len(results),
            "semantic_pass3_count": semantic_pass3_count,
            "semantic_pass3_acc": semantic_pass3_acc,
            "semantic_allpass_count": semantic_allpass_count,
            "semantic_allpass_acc": semantic_allpass_acc,
            "semantic_best3_acc": semantic_best3_acc,
            "format_available": format_available,
            "format_pass1_acc": format_pass1_acc,
            "format_pass3_count": format_pass3_count,
            "format_pass3_acc": format_pass3_acc,
            "format_allpass_count": format_allpass_count,
            "format_allpass_acc": format_allpass_acc,
            "format_best3_acc": format_best3_acc,
            "total_questions": total_questions,
            "single_acc": single_acc,
            "single_total": single_total,
            "multi_acc": multi_acc,
            "multi_total": multi_total,
            "has_multi_run": len(run_files) > 1,
        })

    # Sort by comprehensive score: Pass@1 (primary) + All-Pass@3 (secondary) + Pass@3 (tertiary)
    all_results.sort(key=lambda r: (r["pass1_acc"], r["allpass_acc"], r["pass3_acc"]), reverse=True)

    header = "=" * 80
    sep = "-" * 80

    print()
    print(header)
    print(" Gaokao Math Evaluation Results")
    print(header)

    # Main table
    fmt_main = "{:<38} {:>6} {:>8} {:>8} {:>10} {:>9} {:>5}"
    print(fmt_main.format("Model", "Runs", "Pass@1", "Pass@3", "All-Pass@3", "Best@3", "Total"))
    print(sep)

    for r in all_results:
        runs_str = f"{r['found']}/{expected_runs}"
        pass1_str = f"{r['pass1_acc']:.0%}"
        pass3_str = f"{r['pass3_acc']:.0%}" if r["has_multi_run"] else "  —"
        allpass_str = f"{r['allpass_acc']:.0%}" if r["has_multi_run"] else "  —"
        best3_str = f"{r['best3_acc']:.0%}" if r["has_multi_run"] else "  —"
        print(fmt_main.format(r["model"], runs_str, pass1_str, pass3_str, allpass_str, best3_str, str(r["total_questions"])))

    print(sep)

    if show_detail:
        for r in all_results:
            print(f"\n--- {r['model']} ---")
            for i, run in enumerate(r["runs"]):
                print(f"  Run {i} ({run['label']}): {run['correct']}/{run['total']} = {run['accuracy']:.1%}")
            best_idx = r["runs"].index(r["best"])
            print(f"  Best:             {r['best']['accuracy']:.1%}  (Run {best_idx})")
            print(f"  Pass@1:           {r['pass1_acc']:.1%}")
            if r["has_multi_run"]:
                print(f"  Pass@3:           {r['pass3_count']}/{r['total_questions']} = {r['pass3_acc']:.1%}")
                print(f"  All-Pass@3:       {r['allpass_count']}/{r['total_questions']} = {r['allpass_acc']:.1%}")
                print(f"  Best@3:           {r['best3_acc']:.1%}")
            if r["single_total"] > 0 or r["multi_total"] > 0:
                print(f"  Single:           {r['single_acc']:.1%}  ({r['single_total']} questions)")
                print(f"  Multi:            {r['multi_acc']:.1%}  ({r['multi_total']} questions)")

    print()
    return all_results


def generate_markdown_report(config: dict, all_results: list[dict],
                             year: str, paper_dir: str, base_output: str,
                             expected_runs: int, output_path: str):
    """Generate a Markdown evaluation report from analysis results."""
    global_cfg = config["global"]

    lines = []
    def w(line=""):
        lines.append(line)

    w("# 2026 年高考数学评测报告")
    w()
    w(f"> **试卷**: {paper_dir}  ")
    w(f"> **题目总数**: {all_results[0]['total_questions'] if all_results else 0} 题")
    w()
    w("---")
    w()

    # === 指标说明 ===
    w("## 指标说明")
    w()
    w("| 指标 | 含义 |")
    w("|------|------|")
    w("| **Pass@1 / Pass@3 / All-Pass@3 / Best@3** | 基于原始 `correct` 判定的单次、至少一次、全部和最佳正确率 |")
    w("| **Semantic-*** | 基于重评分 `semantic_correct` 的对应指标；未重评分结果回退到 `correct` |")
    w("| **Format-*** | 基于重评分 `format_correct` 的对应指标；未提供格式字段时显示为 `—` |")
    w()

    # === 评测结果 ===
    w("---")
    w()
    w("## 评测结果")
    w()
    w("### 原始判定指标")
    w()
    w("| 排名 | 模型 | Pass@1 | Pass@3 | All-Pass@3 | Best@3 |")
    w("|:----:|------|:------:|:------:|:----------:|:------:|")

    for i, r in enumerate(all_results):
        pass3_str = f"{r['pass3_acc']:.0%}" if r["has_multi_run"] else "—"
        allpass_str = f"{r['allpass_acc']:.0%}" if r["has_multi_run"] else "—"
        best3_str = f"{r['best3_acc']:.0%}" if r["has_multi_run"] else "—"
        w(f"| {i + 1} | {r['model']} | **{r['pass1_acc']:.0%}** | **{pass3_str}** | {allpass_str} | **{best3_str}** |")
    w()

    w("### 语义重评分指标")
    w()
    w("| 模型 | Semantic Pass@1 | Semantic Pass@3 | Semantic All-Pass@3 | Semantic Best@3 |")
    w("|------|:----------------:|:----------------:|:-------------------:|:----------------:|")
    for r in all_results:
        pass3_str = f"{r['semantic_pass3_acc']:.0%}" if r["has_multi_run"] else "—"
        allpass_str = f"{r['semantic_allpass_acc']:.0%}" if r["has_multi_run"] else "—"
        best3_str = f"{r['semantic_best3_acc']:.0%}" if r["has_multi_run"] else "—"
        w(f"| {r['model']} | **{r['semantic_pass1_acc']:.0%}** | **{pass3_str}** | {allpass_str} | **{best3_str}** |")
    w()

    w("### 格式重评分指标")
    w()
    w("| 模型 | Format Pass@1 | Format Pass@3 | Format All-Pass@3 | Format Best@3 |")
    w("|------|:--------------:|:--------------:|:-----------------:|:--------------:|")
    for r in all_results:
        if not r["format_available"]:
            w(f"| {r['model']} | — | — | — | — |")
            continue
        pass3_str = f"{r['format_pass3_acc']:.0%}" if r["has_multi_run"] else "—"
        allpass_str = f"{r['format_allpass_acc']:.0%}" if r["has_multi_run"] else "—"
        best3_str = f"{r['format_best3_acc']:.0%}" if r["has_multi_run"] else "—"
        w(f"| {r['model']} | **{r['format_pass1_acc']:.0%}** | **{pass3_str}** | {allpass_str} | **{best3_str}** |")
    w()

    # Write to file
    report = "\n".join(lines)
    Path(output_path).write_text(report, encoding="utf-8")
    print(f"\n📝 Report generated: {output_path}")


def build_cmd(cfg: dict, model_cfg: dict, output_name: str) -> list[str]:
    # Model-level server wins so one YAML can target multiple providers.
    server = model_cfg.get("server") or _env_or(cfg, "server", "EVAL_SERVER")
    if "api_key_env" in model_cfg:
        api_key_env = model_cfg["api_key_env"]
    else:
        api_key_env = cfg.get("api_key_env") or "EVAL_API_KEY"
    grader_server = _env_or(cfg, "grader_server", "EVAL_GRADER_SERVER", server)
    grader_model = _env_or(cfg, "grader_model", "EVAL_GRADER_MODEL", model_cfg["name"])

    cmd = [
        sys.executable, "scripts/llama-eval.py",
        "--model", model_cfg["name"],
        "--server", server,
        "--api-key-env", api_key_env,
        "--dataset", "gaokao",
        "--dataset-path", cfg["dataset_path"],
        "--grader-type", cfg["grader_type"],
        "--grader-model", grader_model,
        "--grader-server", grader_server,
        "--output", output_name,
        "--output-root", cfg["output_root"],
        "--seed", str(cfg["seed"]),
        "--threads", str(cfg["threads"]),
    ]
    for key, option in (
        ("temperature", "--temperature"),
        ("top_k", "--top-k"),
        ("top_p", "--top-p"),
        ("min_p", "--min-p"),
    ):
        if cfg.get(key) is not None:
            cmd.extend([option, str(cfg[key])])
    if cfg.get("reasoning_effort") is not None:
        cmd.extend(["--reasoning-effort", str(cfg["reasoning_effort"])])
    return cmd


def main():
    parser = argparse.ArgumentParser(description="Batch Gaokao math evaluator")
    parser.add_argument("--config", default="eval_config.yaml")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only show which runs are missing, do not execute")
    parser.add_argument("--analyze", action="store_true",
                        help="Show evaluation results summary")
    parser.add_argument("--detail", action="store_true",
                        help="Show per-model per-run breakdown (use with --analyze)")
    parser.add_argument("--report", action="store_true",
                        help="Generate a Markdown evaluation report to {output_root}/report.md")
    parser.add_argument("--postprocess", action="store_true",
                        help="Correct existing result JSON/HTML files in output_root without rerunning evaluation")
    args = parser.parse_args()

    config = load_config(args.config)
    global_cfg = config["global"]
    presets = config.get("presets", {})
    models = config["models"]
    runs = global_cfg["runs_per_model"]
    base_output = global_cfg["base_output"]
    output_root = Path(global_cfg["output_root"])

    dataset_path = Path(global_cfg["dataset_path"])
    paper_dir = dataset_path.parent.name
    year = dataset_path.parent.parent.name

    print(f"📋 Dataset: {dataset_path}")
    print(f"📂 Output root: {output_root}/{year}/{paper_dir}/")
    print(f"🔄 Runs per model: {runs}")
    print()

    if args.postprocess:
        files_changed = 0
        cases_corrected = 0
        paper_root = output_root / year / paper_dir
        if paper_root.exists():
            for json_path in sorted(p for p in paper_root.rglob("*.json") if p.is_file()):
                corrected = correct_existing_result_file(json_path)
                if corrected:
                    files_changed += 1
                    cases_corrected += corrected
        print(f"🛠️  Post-process complete: {files_changed} file(s) updated, {cases_corrected} case(s) corrected.")
        print()

    dry_run = args.dry_run

    if dry_run:
        print("🔍 DRY RUN MODE — no evaluations will be executed\n")

    for model_cfg in models:
        model_name = model_cfg["name"]
        model_dir = output_root / year / paper_dir / model_name
        model_dir.mkdir(parents=True, exist_ok=True)

        cfg = resolve_params(global_cfg, presets, model_cfg)
        missing = compute_missing_runs(model_dir, base_output, runs)

        if not missing:
            print(f"✅ {model_name} — all {runs} runs complete, skipping.")
            continue

        print(f"🚀 {model_name} (preset={model_cfg.get('preset', 'none')}) — "
              f"running {len(missing)} missing run(s): {', '.join(missing)}")

        reuse_from = model_cfg.get("reuse_from")
        if reuse_from:
            source_dir = Path(reuse_from)
            print(f"♻️  Reusing completed runs from: {source_dir}")
            for output_name in missing:
                source = source_dir / output_name
                if not source.exists():
                    raise FileNotFoundError(
                        f"Missing reuse source for {model_name}: {source}"
                    )
                target = model_dir / output_name
                reuse_result(source, target, model_name, global_cfg["dataset_path"])
                print(f"  ✅ REUSED {output_name} -> {target}")
            continue

        for output_name in missing:
            cmd = build_cmd(cfg, model_cfg, output_name)
            server = model_cfg.get("server") or _env_or(cfg, "server", "EVAL_SERVER")
            print(f"  → {model_name} @ {server}  "
                f"temperature={cfg.get('temperature', 'skip')} "
                f"top_k={cfg.get('top_k', 'skip')} "
                f"top_p={cfg.get('top_p', 'skip')} "
                f"min_p={cfg.get('min_p', 'skip')} "
                f"reasoning_effort={cfg.get('reasoning_effort', 'skip')} "
                f"threads={cfg.get('threads', 'skip')}  output={output_name}")

            if dry_run:
                continue

            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path(__file__).resolve().parent) + os.pathsep + env.get("PYTHONPATH", "")
            result = subprocess.run(cmd, check=False, env=env)
            if result.returncode != 0:
                print(f"  ❌ FAILED (exit code {result.returncode})")
            else:
                print(f"  ✅ DONE")

            # GPU cooldown after each run
            print("⏸️  Waiting 2 minutes for GPU cooldown...")
            time.sleep(120)
            print("▶️  Continuing\n")

    if dry_run:
        print("🔍 Dry run complete. Remove --dry-run to execute.")
    else:
        print("🎉 Batch evaluation complete.")

    if args.analyze:
        all_results = analyze_results(config, output_root, year, paper_dir, base_output, runs, show_detail=args.detail)
    elif args.report:
        all_results = analyze_results(config, output_root, year, paper_dir, base_output, runs, show_detail=False)
    else:
        all_results = None

    if args.report and all_results:
        report_path = str(output_root / year / paper_dir / "report.md")
        generate_markdown_report(config, all_results, year, paper_dir, base_output, runs, report_path)


if __name__ == "__main__":
    main()
