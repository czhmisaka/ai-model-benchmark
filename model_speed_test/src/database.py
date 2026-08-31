"""
SQLite 数据库模块
用于持久化保存测试结果
"""
import sqlite3
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import os


class TestDatabase:
    """测试结果数据库"""
    
    # pytest 会收集 Test* 命名的类，标记为非测试类（数据类有 __init__）
    __test__ = False
    
    DB_PATH = "results/test_results.db"
    
    def __init__(self, db_path: str = None):
        """初始化数据库"""
        if db_path:
            self.DB_PATH = db_path
        
        # 确保目录存在
        db_file = Path(self.DB_PATH)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_tables()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接
        
        - WAL 模式：允许并发读写（读不阻塞写），减少多线程写锁冲突
        - foreign_keys：启用外键约束（当前 schema 无外键，为后续演进准备）
        """
        conn = sqlite3.connect(self.DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        # WAL 提升并发性能；只需设置一次（持久化在 DB 文件），重复执行无副作用
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except Exception:
            pass
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    
    def _init_tables(self):
        """初始化数据库表"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 测试组表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL UNIQUE,
                name TEXT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                status TEXT DEFAULT 'running',
                config_json TEXT,
                total_rounds INTEGER DEFAULT 0,
                completed_rounds INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                total_duration_seconds REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 测试结果表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                model_name TEXT NOT NULL,
                test_case_name TEXT NOT NULL,
                round_number INTEGER NOT NULL,
                ttft_seconds REAL,
                tpft_seconds REAL,
                total_time_seconds REAL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                tokens_per_second REAL,
                total_tokens_per_second REAL,
                success INTEGER DEFAULT 1,
                error_message TEXT,
                prompt_preview TEXT,
                response_preview TEXT,
                output_text TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (group_id) REFERENCES test_groups(group_id)
            )
        """)
        
        # 如果 output_text 列不存在，则添加（数据库迁移）
        try:
            cursor.execute("ALTER TABLE test_results ADD COLUMN output_text TEXT")
        except sqlite3.OperationalError:
            pass  # 列已存在
        
        # 如果 total_duration_seconds 列不存在，则添加（数据库迁移）
        try:
            cursor.execute("ALTER TABLE test_groups ADD COLUMN total_duration_seconds REAL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # 列已存在
        
        # 如果 evaluation_json 列不存在，则添加（数据库迁移 - 校对结果）
        try:
            cursor.execute("ALTER TABLE test_results ADD COLUMN evaluation_json TEXT")
        except sqlite3.OperationalError:
            pass  # 列已存在
        
        # 如果 folder_id 列不存在，则添加（数据库迁移 - 文件夹支持）
        try:
            cursor.execute("ALTER TABLE test_results ADD COLUMN folder_id TEXT")
        except sqlite3.OperationalError:
            pass
        
        # 如果 folder_name 列不存在，则添加（数据库迁移 - 文件夹支持）
        try:
            cursor.execute("ALTER TABLE test_results ADD COLUMN folder_name TEXT")
        except sqlite3.OperationalError:
            pass

        # 如果 input_images_json 列不存在，则添加（数据库迁移 - 多模态输入图片）
        try:
            cursor.execute("ALTER TABLE test_results ADD COLUMN input_images_json TEXT DEFAULT '[]'")
        except sqlite3.OperationalError:
            pass

        # 如果 output_images_json 列不存在，则添加（数据库迁移 - 多模态输出图片）
        try:
            cursor.execute("ALTER TABLE test_results ADD COLUMN output_images_json TEXT DEFAULT '[]'")
        except sqlite3.OperationalError:
            pass
        
        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_group_id ON test_results(group_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_groups_created ON test_groups(created_at)
        """)
        
        conn.commit()
        conn.close()
    
    # ===== 测试组操作 =====
    
    def create_group(
        self,
        group_id: str,
        name: str = None,
        models: List[str] = None,
        test_cases: List[str] = None,
        total_rounds: int = 10,
        config_extra: Dict[str, Any] = None
    ) -> int:
        """
        创建新的测试组
        
        Args:
            group_id: 唯一标识符
            name: 可选名称
            models: 模型列表
            test_cases: 测试用例列表
            total_rounds: 总轮次数
            config_extra: 额外的配置数据（如 case_folder_map），会合并到 config_json
            
        Returns:
            记录ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        config = {
            "models": models or [],
            "test_cases": test_cases or [],
            "total_rounds": total_rounds
        }
        
        # 合并额外配置（如 case_folder_map）
        if config_extra:
            config.update(config_extra)
        
        cursor.execute("""
            INSERT INTO test_groups (group_id, name, start_time, config_json, total_rounds)
            VALUES (?, ?, ?, ?, ?)
        """, (
            group_id,
            name or f"测试 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            datetime.now().isoformat(),
            json.dumps(config, ensure_ascii=False),
            total_rounds
        ))
        
        conn.commit()
        row_id = cursor.lastrowid
        conn.close()
        
        return row_id
    
    def update_group(
        self,
        group_id: str,
        end_time: str = None,
        status: str = None,
        completed_rounds: int = None,
        success_count: int = None,
        failed_count: int = None,
        total_duration_seconds: float = None
    ):
        """更新测试组状态"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if end_time:
            updates.append("end_time = ?")
            params.append(end_time)
        if status:
            updates.append("status = ?")
            params.append(status)
        if completed_rounds is not None:
            updates.append("completed_rounds = ?")
            params.append(completed_rounds)
        if success_count is not None:
            updates.append("success_count = ?")
            params.append(success_count)
        if failed_count is not None:
            updates.append("failed_count = ?")
            params.append(failed_count)
        if total_duration_seconds is not None:
            updates.append("total_duration_seconds = ?")
            params.append(total_duration_seconds)
        
        if updates:
            params.append(group_id)
            cursor.execute(f"""
                UPDATE test_groups 
                SET {', '.join(updates)}
                WHERE group_id = ?
            """, params)
            conn.commit()
        
        conn.close()
    
    def get_group(self, group_id: str) -> Optional[Dict[str, Any]]:
        """获取测试组详情"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM test_groups WHERE group_id = ?
        """, (group_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_groups(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str = None
    ) -> List[Dict[str, Any]]:
        """获取测试组列表"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM test_groups"
        params = []
        
        if status:
            query += " WHERE status = ?"
            params.append(status)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_group_count(self, status: str = None) -> int:
        """获取测试组数量"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if status:
            cursor.execute("SELECT COUNT(*) FROM test_groups WHERE status = ?", (status,))
        else:
            cursor.execute("SELECT COUNT(*) FROM test_groups")
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    # ===== 测试结果操作 =====
    
    def add_result(
        self,
        group_id: str,
        model_name: str,
        test_case_name: str,
        round_number: int,
        metrics: Dict[str, Any],
        success: bool = True,
        error_message: str = None,
        prompt: str = None,
        response: str = None,
        output_text: str = None,
        evaluation: Dict[str, Any] = None,
        folder_id: str = None,
        folder_name: str = None,
        input_images_json: str = "[]",
        output_images_json: str = "[]"
    ) -> int:
        """
        添加测试结果

        Args:
            group_id: 测试组ID
            model_name: 模型名称
            test_case_name: 测试用例名称
            round_number: 轮次编号
            metrics: 性能指标字典
            success: 是否成功
            error_message: 错误信息
            prompt: 输入提示（可选，截断保存）
            response: 模型响应（可选，截断保存）
            output_text: 完整输出文本（可选，完整保存）
            evaluation: 校对结果（可选），包含 is_correct, rate, reason
            folder_id: 所属文件夹ID（可选）
            folder_name: 所属文件夹名称（可选）
            input_images_json: 输入图片列表 JSON 字符串（多模态用例）
            output_images_json: 输出图片列表 JSON 字符串（文生图等场景）

        Returns:
            记录ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 截断长文本用于预览
        prompt_preview = (prompt[:200] + "...") if prompt and len(prompt) > 200 else prompt
        response_preview = (response[:500] + "...") if response and len(response) > 500 else response

        # 保存完整输出文本
        full_output = output_text if output_text else response

        # 保存校对结果（序列化为 JSON）
        evaluation_json = json.dumps(evaluation, ensure_ascii=False) if evaluation else None

        cursor.execute("""
            INSERT INTO test_results (
                group_id, model_name, test_case_name, round_number,
                ttft_seconds, tpft_seconds, total_time_seconds,
                input_tokens, output_tokens, tokens_per_second, total_tokens_per_second,
                success, error_message, prompt_preview, response_preview, output_text, timestamp,
                evaluation_json, folder_id, folder_name,
                input_images_json, output_images_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            group_id,
            model_name,
            test_case_name,
            round_number,
            metrics.get("ttft_seconds"),
            metrics.get("tpft_seconds"),
            metrics.get("total_time_seconds"),
            metrics.get("input_tokens"),
            metrics.get("output_tokens"),
            metrics.get("tokens_per_second"),
            metrics.get("total_tokens_per_second"),
            1 if success else 0,
            error_message,
            prompt_preview,
            response_preview,
            full_output,
            datetime.now().isoformat(),
            evaluation_json,
            folder_id,
            folder_name,
            input_images_json or "[]",
            output_images_json or "[]"
        ))

        conn.commit()
        row_id = cursor.lastrowid
        conn.close()

        return row_id
    
    def get_results(self, group_id: str) -> List[Dict[str, Any]]:
        """获取测试组的所有结果"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM test_results 
            WHERE group_id = ?
            ORDER BY model_name, test_case_name, round_number
        """, (group_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        # 转换结果并解析 evaluation_json
        results = []
        for row in rows:
            result = dict(row)
            # 解析 evaluation_json 字段
            if result.get("evaluation_json"):
                try:
                    result["evaluation"] = json.loads(result["evaluation_json"])
                except json.JSONDecodeError:
                    result["evaluation"] = None
            else:
                result["evaluation"] = None
            results.append(result)
        
        return results
    
    def get_results_by_model(
        self, 
        group_id: str, 
        model_name: str, 
        test_case_name: str = None
    ) -> List[Dict[str, Any]]:
        """获取特定模型/测试用例的结果"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM test_results WHERE group_id = ? AND model_name = ?"
        params = [group_id, model_name]
        
        if test_case_name:
            query += " AND test_case_name = ?"
            params.append(test_case_name)
        
        query += " ORDER BY round_number"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    # ===== 统计查询 =====
    
    def get_group_summary(self, group_id: str) -> Optional[Dict[str, Any]]:
        """获取测试组汇总统计"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 获取测试组信息
        cursor.execute("SELECT * FROM test_groups WHERE group_id = ?", (group_id,))
        group = cursor.fetchone()
        
        if not group:
            conn.close()
            return None
        
        # 按模型、测试用例、文件夹分组统计（修复同名用例合并问题）
        cursor.execute("""
            SELECT 
                model_name,
                test_case_name,
                folder_id,
                folder_name,
                COUNT(*) as total,
                SUM(success) as success_count,
                AVG(ttft_seconds) as avg_ttft,
                AVG(tpft_seconds) as avg_tpft,
                AVG(total_time_seconds) as avg_total_time,
                AVG(tokens_per_second) as avg_tokens_per_second,
                SUM(output_tokens) as total_output_tokens
            FROM test_results
            WHERE group_id = ?
            GROUP BY model_name, test_case_name, folder_id
        """, (group_id,))
        
        model_stats = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            "group": dict(group),
            "model_stats": model_stats
        }
    
    def search_groups(
        self,
        keyword: str = None,
        model_name: str = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """搜索测试组"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM test_groups WHERE 1=1"
        params = []
        
        if keyword:
            query += " AND (name LIKE ? OR group_id LIKE ?)"
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        
        if start_date:
            query += " AND start_time >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND start_time <= ?"
            params.append(end_date)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # 如果指定了模型名称，进一步过滤
        if model_name and rows:
            # 获取包含该模型的组ID
            cursor.execute("""
                SELECT DISTINCT group_id FROM test_results 
                WHERE model_name = ? AND group_id IN (
                    SELECT group_id FROM test_groups 
                    WHERE id IN ({})
                )
            """.format(",".join(["?" for _ in rows])), 
            [model_name] + [dict(r)["group_id"] for r in rows])
            valid_group_ids = set([row[0] for row in cursor.fetchall()])
            rows = [r for r in rows if dict(r)["group_id"] in valid_group_ids]
        
        conn.close()
        
        return [dict(row) for row in rows]
    
    def delete_group(self, group_id: str, delete_files: bool = True) -> bool:
        """删除测试组及其所有结果
        
        Args:
            group_id: 测试组ID
            delete_files: 是否同时删除本地文件
            
        Returns:
            是否删除成功
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 先删除结果
        cursor.execute("DELETE FROM test_results WHERE group_id = ?", (group_id,))
        # 再删除组
        cursor.execute("DELETE FROM test_groups WHERE group_id = ?", (group_id,))
        
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        
        # 删除本地文件
        if delete_files:
            self._delete_group_files(group_id)
        
        return deleted
    
    def update_group_name(self, group_id: str, name: str):
        """更新测试组名称"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("UPDATE test_groups SET name = ? WHERE group_id = ?", (name, group_id))
        conn.commit()
        conn.close()
    
    def update_group_status(self, group_id: str, status: str):
        """更新测试组状态"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("UPDATE test_groups SET status = ? WHERE group_id = ?", (status, group_id))
        conn.commit()
        conn.close()

    def increment_group_progress(self, group_id: str, success: bool):
        """增量更新测试组进度（每轮完成后调用，避免全表 COUNT）

        对比 _update_group_progress（emitter 侧）的全量 SELECT + UPDATE，
        本方法单条 UPDATE 完成，减少并发写放大。
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE test_groups SET
                    completed_rounds = completed_rounds + 1,
                    success_count = success_count + ?,
                    failed_count = failed_count + ?
                WHERE group_id = ?
            """, (1 if success else 0, 0 if success else 1, group_id))
            conn.commit()
        finally:
            conn.close()
    
    def _delete_group_files(self, group_id: str):
        """删除测试组对应的本地文件
        
        Args:
            group_id: 测试组ID (格式: YYYYMMDD_HHMMSS)
        """
        results_dir = Path("results")
        if not results_dir.exists():
            return
        
        session = group_id  # group_id 就是 session
        
        try:
            # 删除 io_records_{session}.md
            io_file = results_dir / f"io_records_{session}.md"
            if io_file.exists():
                io_file.unlink()
                print(f"[Database] 已删除文件: {io_file}")
            
            # 删除 summary_{session}.csv
            summary_file = results_dir / f"summary_{session}.csv"
            if summary_file.exists():
                summary_file.unlink()
                print(f"[Database] 已删除文件: {summary_file}")
            
            # 删除 logs/{session}/ 目录
            logs_dir = results_dir / "logs" / session
            if logs_dir.exists():
                import shutil
                shutil.rmtree(logs_dir)
                print(f"[Database] 已删除目录: {logs_dir}")
                
        except Exception as e:
            print(f"[Database] 删除本地文件失败: {e}")


# 全局数据库实例
_db_instance = None


def get_database() -> TestDatabase:
    """获取数据库单例"""
    global _db_instance
    if _db_instance is None:
        _db_instance = TestDatabase()
    return _db_instance