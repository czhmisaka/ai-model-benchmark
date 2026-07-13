"""添加性能索引

迁移用途：
- folder_id 索引：加速按文件夹筛选查询
- 联合索引：优化 GROUP BY 多维度聚合
- 时间索引：优化按时间排序的分页查询
"""
import sqlite3
from pathlib import Path


def migrate(db_path: str = None):
    """执行索引迁移"""
    if db_path is None:
        db_path = Path(__file__).parent.parent / "results" / "config.db"

    db_path = Path(db_path)
    if not db_path.exists():
        print(f"[INFO] 数据库不存在，跳过索引创建: {db_path}")
        return

    print(f"[INFO] 为数据库添加索引: {db_path}")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    indexes = [
        # test_cases 表
        "CREATE INDEX IF NOT EXISTS idx_test_cases_folder_id ON test_cases(folder_id)",
        "CREATE INDEX IF NOT EXISTS idx_test_cases_enabled ON test_cases(enabled)",
        "CREATE INDEX IF NOT EXISTS idx_test_cases_name ON test_cases(name)",

        # test_results 表
        "CREATE INDEX IF NOT EXISTS idx_test_results_folder_id ON test_results(folder_id)",
        "CREATE INDEX IF NOT EXISTS idx_test_results_model_case "
        "ON test_results(model_name, test_case_name)",
        "CREATE INDEX IF NOT EXISTS idx_test_results_created "
        "ON test_results(created_at)",

        # test_groups 表
        "CREATE INDEX IF NOT EXISTS idx_test_groups_created ON test_groups(created_at)",
        "CREATE INDEX IF NOT EXISTS idx_test_groups_folder_id ON test_groups(folder_id)",

        # models 表
        "CREATE INDEX IF NOT EXISTS idx_models_provider ON models(provider)",
    ]

    for sql in indexes:
        try:
            cursor.execute(sql)
        except sqlite3.OperationalError as e:
            print(f"[WARN] 索引创建跳过: {e}")

    conn.commit()
    conn.close()
    print("✅ 索引已创建")


if __name__ == "__main__":
    # 默认路径
    results_dir = Path(__file__).parent.parent / "results"
    db_path = results_dir / "config.db"

    if not db_path.exists():
        print(f"❌ 数据库不存在: {db_path}")
        import sys
        sys.exit(1)

    migrate(str(db_path))