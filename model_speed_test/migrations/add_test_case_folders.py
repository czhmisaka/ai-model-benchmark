"""
迁移脚本：新增 test_case_folders 表 + test_cases 表 folder_id 字段
执行方式：python migrations/add_test_case_folders.py
"""
import sqlite3
import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'results', 'config.db')


def migrate():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] 数据库文件不存在: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. 创建 test_case_folders 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_case_folders (
                folder_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                parent_id TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT DEFAULT (datetime('now', 'localtime')),
                sort_order INTEGER DEFAULT 0,
                FOREIGN KEY (parent_id) REFERENCES test_case_folders(folder_id) ON DELETE CASCADE
            )
        """)
        print("[OK] test_case_folders 表已创建（或已存在）")

        # 2. 为 test_cases 表新增 folder_id 字段
        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(test_cases)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'folder_id' not in columns:
            cursor.execute("ALTER TABLE test_cases ADD COLUMN folder_id TEXT")
            print("[OK] test_cases 表已添加 folder_id 字段")
        else:
            print("[SKIP] test_cases 表已存在 folder_id 字段，跳过")

        # 3. 验证
        cursor.execute("SELECT COUNT(*) FROM test_case_folders")
        folder_count = cursor.fetchone()[0]
        print(f"[OK] 当前文件夹数量: {folder_count}")

        cursor.execute("SELECT COUNT(*) FROM test_cases")
        case_count = cursor.fetchone()[0]
        print(f"[OK] 当前测试用例数量: {case_count}")

        conn.commit()
        print("[DONE] 迁移完成！")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] 迁移失败: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    migrate()