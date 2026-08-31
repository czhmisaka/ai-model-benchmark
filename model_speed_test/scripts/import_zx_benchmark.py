# -*- coding: utf-8 -*-
"""
将 zx 风格题库（config/zx_style_benchmark.json）导入 results/config.db 的 test_cases 表

用法：
    python3 scripts/import_zx_benchmark.py                # 导入/更新（幂等）
    python3 scripts/import_zx_benchmark.py --dry-run      # 预览
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
BANK_FILE = ROOT / "config" / "zx_style_benchmark.json"
DB_FILE = ROOT / "results" / "config.db"

# 维度 -> 文件夹显示名
DIM_LABELS = {
    "math": "数学推理",
    "hallucination": "幻觉抵抗",
    "safety": "安全权限",
    "extraction": "数据抽取",
    "structured": "结构化输出",
    "instruction": "指令遵循",
    "agent": "智能体工作流",
    "coding": "编程",
}
ROOT_FOLDER_NAME = "zx评测题库"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not BANK_FILE.exists():
        print(f"题库文件不存在: {BANK_FILE}")
        sys.exit(1)
    if not DB_FILE.exists():
        print(f"数据库不存在: {DB_FILE}")
        sys.exit(1)

    with open(BANK_FILE, encoding="utf-8") as f:
        bank = json.load(f)

    cases = bank["cases"]
    meta = bank["meta"]
    print(f"题库: {meta['count']} 题, 维度: {meta['dimensions']}")

    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # ===== 题库文件夹结构（幂等创建） =====
    folder_map = {}  # dimension -> folder_id

    def _ensure_folder(name, parent_id=None):
        """确保文件夹存在（同级同名防重），返回 folder_id"""
        cursor.execute(
            "SELECT folder_id FROM test_case_folders WHERE name = ? AND COALESCE(parent_id, '') = COALESCE(?, '')",
            (name, parent_id)
        )
        row = cursor.fetchone()
        if row:
            return row["folder_id"]
        import uuid as _uuid
        fid = str(_uuid.uuid4())
        cursor.execute(
            "INSERT INTO test_case_folders (folder_id, name, parent_id, sort_order) VALUES (?, ?, ?, 0)",
            (fid, name, parent_id)
        )
        return fid

    root_fid = _ensure_folder(ROOT_FOLDER_NAME, None)
    for dim in meta.get("dimensions", {}).keys():
        folder_map[dim] = _ensure_folder(DIM_LABELS.get(dim, dim), root_fid)
    conn.commit()
    print(f"文件夹结构就绪: root={root_fid[:8]}, {len(folder_map)} 个维度子文件夹")

    inserted, updated, skipped = 0, 0, 0
    for c in cases:
        case_id = c["id"]
        existing = cursor.execute(
            "SELECT case_id FROM test_cases WHERE case_id = ?", (case_id,)
        ).fetchone()

        row = (
            case_id,
            c["name"],
            c["type"],
            c.get("description", ""),
            json.dumps(c.get("tags", []), ensure_ascii=False),
            c.get("version", "1.0"),
            "",  # prompt_template（内容直接放 messages）
            "{}",  # variables
            c.get("system_prompt", ""),
            json.dumps(c["messages"], ensure_ascii=False),
            c.get("expected_output_type", "text"),
            json.dumps(c.get("metadata", {}), ensure_ascii=False),
            c.get("max_tokens", 2048),
            c.get("temperature", 0.7),
            1 if c.get("stream", True) else 0,
            1 if c.get("enabled", True) else 0,
            c.get("expected_output", ""),
            "",  # eval_model（留空，用户在前端选择校对模型）
        )

        if args.dry_run:
            action = "UPDATE" if existing else "INSERT"
            print(f"[DRY-RUN] {action}: {case_id} - {c['name']}")
            continue

        if existing:
            cursor.execute(
                """UPDATE test_cases SET name=?, type=?, description=?, tags=?, version=?,
                   system_prompt=?, messages=?, expected_output_type=?, metadata=?,
                   max_tokens=?, temperature=?, stream=?, enabled=?, expected_output=?,
                   folder_id=?, updated_at=datetime('now','localtime')
                   WHERE case_id=?""",
                (row[1], row[2], row[3], row[4], row[5], row[8], row[9],
                 row[10], row[11], row[12], row[13], row[14], row[15], row[16],
                 folder_map.get(c.get("metadata", {}).get("dimension", ""), None), case_id)
            )
            updated += 1
        else:
            cursor.execute(
                """INSERT INTO test_cases (case_id, name, type, description, tags, version,
                   prompt_template, variables, system_prompt, messages, expected_output_type,
                   metadata, max_tokens, temperature, stream, enabled, expected_output,
                   eval_model, folder_id, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'now','now')""",
                row + (folder_map.get(c.get("metadata", {}).get("dimension", ""), None),)
            )
            inserted += 1

    if not args.dry_run:
        conn.commit()
    conn.close()
    print(f"完成: 新增 {inserted}, 更新 {updated}, 跳过 {skipped}")


if __name__ == "__main__":
    main()
