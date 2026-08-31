# -*- coding: utf-8 -*-
"""
导入 zx-bench 官方题库（benchmark.json）到本平台

转换规则：
- promptTemplate → messages[0].content（渲染 {var} 占位符，用 requirements.variables 或留原样）
- requirements.answer / fixedGold → expected_output（评分点）
- grader/scoring/difficulty/category → metadata（供 AI 校对参考）
- 跳过 project_repair / sandbox（多文件工程/沙箱执行，本平台无 Docker 执行环境）

用法：
    python3 scripts/import_zx_official.py --source /tmp/zx_bench.json --dry-run
    python3 scripts/import_zx_official.py --source /tmp/zx_benchmark.json --only reasoning_math,hallucination_resistance
"""
import argparse
import json
import re
import sqlite3
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB_FILE = ROOT / "results" / "config.db"

DIM_LABELS = {
    "reasoning_math": "数学推理",
    "hallucination_resistance": "幻觉抵抗",
    "safety_authority": "安全权限",
    "data_extraction": "数据抽取",
    "structured_output": "结构化输出",
    "instruction_following": "指令遵循",
    "agent_workflow": "智能体",
    "tool_cli_workflow": "工具CLI",
    "cli_deep_tasks": "深度CLI",
    "program": "编程",
}

SKIP_GRADERS = {"project_repair", "sandbox"}  # 本平台无执行环境，跳过


def render_prompt(template: str) -> str:
    """渲染 {var} 占位符（官方 requirements.variables 通常内联在题目里，未提供的保留原样）"""
    return template


def build_expected(q: dict) -> str:
    """从 requirements 构建评分用的标准答案"""
    req = q.get("requirements") or {}
    parts = []

    if req.get("answer") is not None:
        parts.append(f"标准答案: {req['answer']}")
    if req.get("fixedGold"):
        parts.append(f"金标准: {req['fixedGold']}")
    if req.get("answerability"):
        parts.append(f"可答性: {req['answerability']}")
    if req.get("trapType"):
        parts.append(f"陷阱类型: {req['trapType']}")
    if req.get("hallucinationType"):
        parts.append(f"幻觉类型: {req['hallucinationType']}")

    # constraints（instruction_checklist）
    for c in req.get("constraints", []):
        desc = c.get("description", "")
        pats = c.get("check", {}).get("patterns", [])
        if desc:
            pat_str = f"（关键词: {', '.join(pats[:3])}）" if pats else ""
            parts.append(f"checklist - {desc}{pat_str}")

    # hiddenTests 概述（编程题）
    ht = q.get("hiddenTests") or []
    if ht and isinstance(ht, list):
        names = []
        for t in ht[:5]:
            if isinstance(t, dict):
                nm = t.get("name") or t.get("description") or ""
                if nm:
                    nm = str(nm)[:40]
                    names.append(nm)
        if names:
            parts.append("隐藏测试: " + "; ".join(names))

    if not parts:
        parts.append("AI 校对按回答质量评分（官方题库未提供固定答案，请综合判断正确性与完整性）")
    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="官方 benchmark.json 路径")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only-dims", default="", help="只导入指定维度（逗号分隔）")
    parser.add_argument("--limit", type=int, default=0, help="最多导入 N 题（0=全部）")
    args = parser.parse_args()

    src = Path(args.source)
    if not src.exists():
        print(f"源文件不存在: {src}")
        sys.exit(1)

    with open(src, encoding="utf-8") as f:
        data = json.load(f)

    only_dims = set(args.only_dims.split(",")) if args.only_dims else None

    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 文件夹结构：<维度> 平铺（不建子级，保持简单）
    folder_map = {}
    def _ensure_folder(name):
        cursor.execute(
            "SELECT folder_id FROM test_case_folders WHERE name = ? AND COALESCE(parent_id,'') = ''",
            (name,)
        )
        row = cursor.fetchone()
        if row:
            return row["folder_id"]
        import uuid
        fid = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO test_case_folders (folder_id, name, parent_id, sort_order) VALUES (?, ?, NULL, 5)",
            (fid, name)
        )
        return fid

    for dim in sorted(set(d["dimension"] for d in data)):
        folder_map[dim] = _ensure_folder(DIM_LABELS.get(dim, dim))
    conn.commit()

    imported, skipped_exec, skipped_vars, errors = 0, 0, 0, 0
    for q in data:
        if q.get("grader") in SKIP_GRADERS:
            skipped_exec += 1
            continue
        if only_dims and q["dimension"] not in only_dims:
            continue
        if q.get("status") != "valid":
            skipped_vars += 1
            continue

        case_id = "zxo_" + q["id"]  # zxo = zx official
        prompt = render_prompt(q.get("promptTemplate") or "")
        expected = build_expected(q)
        meta = {
            "source": "zx-bench-official",
            "dimension": q["dimension"],
            "difficulty": q["difficulty"],
            "category": q.get("category"),
            "grader": q.get("grader"),
            "scenarioHash": q.get("scenarioHash"),
        }

        row = (
            case_id, q["id"], "zx_official_" + q["dimension"],
            f"官方题 · {q['dimension']} · {q['difficulty']}",
            json.dumps(q.get("tags", []), ensure_ascii=False),
            q.get("scenarioVersion", "1.0"),
            "", "{}",
            "",  # system_prompt
            json.dumps([{"role": "user", "content": prompt}], ensure_ascii=False),
            "text",
            json.dumps(meta, ensure_ascii=False),
            q.get("maxAnswerTokens") or 4096,
            0.7, 1, 1,
            expected,
            "",  # eval_model 留空
            folder_map.get(q["dimension"]),
        )

        if args.dry_run:
            print(f"[DRY] {case_id}")
            continue

        existing = cursor.execute("SELECT case_id FROM test_cases WHERE case_id = ?", (case_id,)).fetchone()
        if existing:
            cursor.execute(
                """UPDATE test_cases SET name=?, type=?, description=?, tags=?, version=?,
                   system_prompt=?, messages=?, expected_output_type='text', metadata=?,
                   max_tokens=?, temperature=?, stream=1, enabled=1, expected_output=?,
                   folder_id=?, updated_at=datetime('now','localtime') WHERE case_id=?""",
                (row[1], row[2], row[3], row[4], row[5], row[7], row[8], row[9],
                 row[11], row[12], row[13], row[14], row[15], row[17], case_id)
            )
        else:
            cursor.execute(
                """INSERT INTO test_cases (case_id, name, type, description, tags, version,
                   prompt_template, variables, system_prompt, messages, expected_output_type,
                   metadata, max_tokens, temperature, stream, enabled, expected_output,
                   eval_model, folder_id, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'now','now')""",
                row
            )
        imported += 1

    if not args.dry_run:
        conn.commit()
    conn.close()
    print(f"完成: 导入 {imported}, 跳过(执行环境类) {skipped_exec}, 跳过(status无效) {skipped_vars}, 错误 {errors}")


if __name__ == "__main__":
    main()
