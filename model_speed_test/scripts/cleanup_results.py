#!/usr/bin/env python3
"""
results/ 数据清理脚本

用途：
1. 删除超过保留天数的旧测试结果目录（默认保留 30 天）
2. 清理损坏的数据库备份文件（*.corrupt_*）
3. 可选：清理旧 config.db 备份（默认保留最近 3 份）

用法：
    python3 scripts/cleanup_results.py                # 默认：保留30天
    python3 scripts/cleanup_results.py --days 7       # 只保留7天
    python3 scripts/cleanup_results.py --dry-run      # 只预览不删除
    python3 scripts/cleanup_results.py --keep-db-backups 5
"""
import argparse
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

# results 目录名格式: YYYYMMDD_HHMMSS_...
RESULT_DIR_RE = re.compile(r"^(\d{8}_\d{6})_")


def parse_args():
    parser = argparse.ArgumentParser(description="清理 results/ 目录中的旧测试结果")
    parser.add_argument("--results-dir", default="results", help="results 目录路径")
    parser.add_argument("--days", type=int, default=30, help="保留最近 N 天的结果（默认 30）")
    parser.add_argument("--keep-db-backups", type=int, default=3, help="保留最近 N 份 config.db 备份（默认 3）")
    parser.add_argument("--dry-run", action="store_true", help="只预览要删除的内容，不实际删除")
    return parser.parse_args()


def main():
    args = parse_args()
    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        print(f"目录不存在: {results_dir}")
        sys.exit(1)

    cutoff = datetime.now() - timedelta(days=args.days)
    dry = " [DRY-RUN]" if args.dry_run else ""

    # 1. 清理旧测试结果目录
    removed_dirs = 0
    freed_bytes = 0
    for entry in sorted(results_dir.iterdir()):
        if not entry.is_dir():
            continue
        m = RESULT_DIR_RE.match(entry.name)
        if not m:
            continue
        try:
            ts = datetime.strptime(m.group(1), "%Y%m%d_%H%M%S")
        except ValueError:
            continue
        if ts < cutoff:
            size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
            print(f"{dry} 删除旧结果: {entry.name} ({size/1024:.1f} KB, {ts:%Y-%m-%d})")
            if not args.dry_run:
                shutil.rmtree(entry)
            removed_dirs += 1
            freed_bytes += size

    # 2. 清理损坏备份
    for f in results_dir.glob("*.corrupt_*"):
        size = f.stat().st_size
        print(f"{dry} 删除损坏备份: {f.name} ({size/1024:.1f} KB)")
        if not args.dry_run:
            f.unlink()
        freed_bytes += size

    # 3. 清理旧 config.db 备份（保留最近 N 份）
    db_backups = sorted(
        results_dir.glob("config.db.backup_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for f in db_backups[args.keep_db_backups:]:
        size = f.stat().st_size
        print(f"{dry} 删除旧备份: {f.name} ({size/1024:.1f} KB)")
        if not args.dry_run:
            f.unlink()
        freed_bytes += size

    print(f"\n完成: 删除 {removed_dirs} 个结果目录, 释放约 {freed_bytes/1024/1024:.1f} MB{('（预览模式）' if args.dry_run else '')}")


if __name__ == "__main__":
    main()
