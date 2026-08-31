# -*- coding: utf-8 -*-
"""批量配置官方题的 eval_model（校对模型）"""
import argparse
import sqlite3
import sys
from pathlib import Path

DB_FILE = Path(__file__).parent.parent / "results" / "config.db"

DEFAULT_JUDGE = "MiniMax-M2.7-Highspeed"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-model", default=DEFAULT_JUDGE, help="校对模型名称")
    parser.add_argument("--only-dims", default="", help="只配置指定维度（逗号分隔 type 前缀）")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row

    # 验证模型存在
    m = conn.execute("SELECT name FROM models WHERE name = ? AND enabled=1", (args.eval_model,)).fetchone()
    if not m:
        print(f"错误: 模型 {args.eval_model!r} 不存在或未启用")
        sys.exit(1)

    # 官方题（zxo_ 前缀）批量设置
    where = "case_id LIKE 'zxo_%'"
    if args.only_dims:
        dims = args.only_dims.split(",")
        conds = " OR ".join("type LIKE 'zx_official_" + d + "%'" for d in dims)
        where = f"({conds})"

    total = conn.execute(f"SELECT COUNT(*) FROM test_cases WHERE {where}").fetchone()[0]
    if args.dry_run:
        print(f"[DRY-RUN] 将为 {total} 题配置 eval_model={args.eval_model}")
        sys.exit(0)

    conn.execute(
        f"UPDATE test_cases SET eval_model = ? WHERE {where}",
        (args.eval_model,)
    )
    conn.commit()

    n = conn.execute(
        f"SELECT COUNT(*) FROM test_cases WHERE {where} AND eval_model = ?",
        (args.eval_model,)
    ).fetchone()[0]
    print(f"完成: {n}/{total} 题配置 eval_model = {args.eval_model}")
    conn.close()


if __name__ == "__main__":
    main()
