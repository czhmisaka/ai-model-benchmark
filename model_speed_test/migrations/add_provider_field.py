"""
数据库迁移脚本
添加 provider 字段到 models 表
"""

import sqlite3
from pathlib import Path
import sys

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def migrate():
    """执行数据库迁移"""
    config_db_path = project_root / "results" / "config.db"
    
    if not config_db_path.exists():
        print(f"数据库文件不存在: {config_db_path}")
        return False
    
    conn = sqlite3.connect(str(config_db_path))
    cursor = conn.cursor()
    
    # 检查 provider 列是否存在
    cursor.execute("PRAGMA table_info(models)")
    columns = [col[1] for col in cursor.fetchall()]
    
    print(f"当前 models 表的列: {columns}")
    
    # 添加 provider 列（如果不存在）
    if "provider" not in columns:
        print("添加 provider 列到 models 表...")
        cursor.execute("ALTER TABLE models ADD COLUMN provider TEXT DEFAULT 'openai'")
        conn.commit()
        print("provider 列添加成功")
    else:
        print("provider 列已存在")
    
    # 检查 extra_params 列是否存在（用于存储其他特定提供商的参数）
    if "extra_params" not in columns:
        print("添加 extra_params 列到 models 表...")
        cursor.execute("ALTER TABLE models ADD COLUMN extra_params TEXT DEFAULT '{}'")
        conn.commit()
        print("extra_params 列添加成功")
    else:
        print("extra_params 列已存在")
    
    conn.close()
    print("数据库迁移完成")
    return True


if __name__ == "__main__":
    migrate()