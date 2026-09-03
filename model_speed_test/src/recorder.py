"""
输入输出记录器
用于记录每次模型调用的输入和输出
按轮次拆分 + 任务文件夹归档
"""
import os
import json
import time
import hashlib
import uuid
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from .async_io import (
    read_json,
    write_json,
    write_text,
    atomic_write_json,
)


def generate_hashid(length: int = 8) -> str:
    """生成短 hash ID"""
    random_str = f"{time.time()}{uuid.uuid4().hex}"
    return hashlib.md5(random_str.encode()).hexdigest()[:length]


def sanitize_filename(name: str) -> str:
    """清理文件名，移除不合法字符"""
    # 替换不合法字符
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    safe_name = name
    for char in invalid_chars:
        safe_name = safe_name.replace(char, '_')
    # 限制长度
    return safe_name[:50]


class IORecorder:
    """输入输出记录器 - 支持按轮次拆分和任务文件夹归档"""

    def __init__(
        self,
        results_dir: str = str(Path(__file__).resolve().parent.parent / "results"),
        save_detailed: bool = True,
        group_id: str = None,
        task_name: str = None,
        total_rounds: int = None,
        config: Dict[str, Any] = None
    ):
        """
        初始化记录器
        
        Args:
            results_dir: 结果保存目录
            save_detailed: 是否保存详细日志
            group_id: 测试组 ID（用于创建任务文件夹）
            task_name: 任务名称（用于文件夹命名）
            total_rounds: 总轮次数（可选）
            config: 测试配置（可选，用于保存到 manifest.json）
        """
        self.results_dir = Path(results_dir)
        self.save_detailed = save_detailed
        self.current_session = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 如果没有传入 group_id，使用时间戳
        self.group_id = group_id or self.current_session
        self.task_name = task_name or "unnamed_task"
        self.total_rounds = total_rounds
        
        # 创建任务目录结构
        self.task_dir = self.results_dir / f"{self.group_id}_{sanitize_filename(self.task_name)}"
        self.task_dir.mkdir(parents=True, exist_ok=True)
        
        # 各轮次目录（延迟创建）
        self.round_dirs: Dict[int, Path] = {}
        
        # manifest.json 路径
        self.manifest_file = self.task_dir / "manifest.json"
        
        # 记录计数器
        self.record_count = 0
        self.current_round = 0

        # manifest 写入锁（防止并发竞态）
        self._manifest_lock = asyncio.Lock()

        # 同步初始化 manifest.json（构造时调用一次，非热路径）
        self._init_manifest_sync(config)

    def _init_manifest_sync(self, config: Dict[str, Any] = None):
        """同步初始化 manifest.json（仅在 __init__ 中调用）"""
        manifest = {
            "group_id": self.group_id,
            "task_name": self.task_name,
            "created_at": datetime.now().isoformat(),
            "total_rounds": self.total_rounds,
            "config": config,
            "files": {}
        }
        with open(self.manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    async def init_manifest(self, config: Dict[str, Any] = None):
        """异步初始化 manifest.json"""
        manifest = {
            "group_id": self.group_id,
            "task_name": self.task_name,
            "created_at": datetime.now().isoformat(),
            "total_rounds": self.total_rounds,
            "config": config,
            "files": {}  # round_N: [file_list]
        }
        await write_json(str(self.manifest_file), manifest)

    async def _update_manifest(self, round_num: int, filename: str):
        """异步更新 manifest.json（带锁保护，防止并发竞态）"""
        async with self._manifest_lock:
            manifest = await read_json(str(self.manifest_file))
            if manifest is None:
                manifest = {"files": {}}

            round_key = f"round_{round_num}"
            if round_key not in manifest.get("files", {}):
                manifest["files"][round_key] = []

            if filename not in manifest["files"][round_key]:
                manifest["files"][round_key].append(filename)

            await atomic_write_json(str(self.manifest_file), manifest)

    def _get_round_dir(self, round_num: int) -> Path:
        """获取或创建轮次目录"""
        if round_num not in self.round_dirs:
            round_dir = self.task_dir / f"round_{round_num}"
            round_dir.mkdir(parents=True, exist_ok=True)
            self.round_dirs[round_num] = round_dir
        return self.round_dirs[round_num]

    def set_current_round(self, round_num: int):
        """设置当前轮次"""
        self.current_round = round_num

    async def record(
        self,
        model_name: str,
        prompt: str,
        response: str,
        metrics: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        evaluation: Optional[Dict[str, Any]] = None,
        round_num: int = None,
        think_content: Optional[str] = None,
        answer_content: Optional[str] = None,
        input_images: Optional[List[Dict[str, Any]]] = None,
        output_images: Optional[List[Dict[str, Any]]] = None
    ):
        """
        记录单次调用

        Args:
            model_name: 模型名称
            prompt: 输入提示
            response: 模型响应
            metrics: 性能指标
            metadata: 额外元数据
            evaluation: 评估结果（可选）
            round_num: 轮次编号（可选，默认使用 current_round）
            think_content: 思考内容（可选，用于分离 think 和 answer）
            answer_content: 回答内容（可选）
            input_images: 多模态输入图片 part 列表（可选）
            output_images: 多模态输出图片列表（可选，预留）
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        round_num = round_num or self.current_round or 1
        
        # 生成记录 ID
        record_id = generate_hashid()
        self.record_count += 1
        
        # 清理模型名称用于文件名
        safe_model_name = sanitize_filename(model_name)
        
        # 获取轮次目录
        round_dir = self._get_round_dir(round_num)
        
        # 构建文件名
        filename = f"{record_id}_{safe_model_name}.json"
        file_path = round_dir / filename
        
        # 构建记录数据
        output_tokens = metrics.get("output_tokens", 0) if metrics else 0
        
        # 综合判断 success
        if metadata:
            base_success = metadata.get("success", True)
        else:
            base_success = True
        
        # 如果 output_tokens 为 0，无论 metadata.success 是什么，都标记为失败
        final_success = base_success and (output_tokens > 0)
        
        record_data = {
            "id": record_id,
            "timestamp": timestamp,
            "group_id": self.group_id,
            "round": round_num,
            "model_name": model_name,
            "success": final_success,
            "metrics": metrics,
            "prompt": prompt,
            "response": response,
            "metadata": metadata or {},
            "evaluation": evaluation,
            "think_content": think_content,
            "answer_content": answer_content,
            "input_images": input_images or [],
            "output_images": output_images or [],
        }
        
        # 异步保存 JSON 文件
        await write_json(str(file_path), record_data)
        
        # 异步更新 manifest
        await self._update_manifest(round_num, filename)
        
        # 异步追加 Markdown
        await self._append_markdown(record_data)

    async def _append_markdown(self, record: Dict[str, Any]):
        """异步追加记录到 all_rounds.md"""
        md_file = self.task_dir / "all_rounds.md"
        lines = []
        lines.append(f"## 测试记录 - {record['timestamp']}\n")
        lines.append(f"**模型**: {record['model_name']}\n")
        lines.append(f"**轮次**: {record['round']}\n")
        lines.append(f"**记录ID**: {record['id']}\n\n")
        
        # 性能指标
        lines.append(f"### 性能指标\n\n")
        lines.append(f"| 指标 | 值 |\n")
        lines.append(f"|------|-----|\n")
        
        metrics = record.get("metrics", {})
        lines.append(f"| 首Token时间(TTFT) | {metrics.get('ttft_seconds', 0):.3f}s |\n")
        lines.append(f"| 生成时间(TPFT) | {metrics.get('tpft_seconds', 0):.3f}s |\n")
        lines.append(f"| 总耗时 | {metrics.get('total_time_seconds', 0):.3f}s |\n")
        lines.append(f"| 输入Token数 | {metrics.get('input_tokens', 0)} |\n")
        lines.append(f"| 输出Token数 | {metrics.get('output_tokens', 0)} |\n")
        lines.append(f"| 输出速度 | {metrics.get('tokens_per_second', 0):.2f} tokens/s |\n")
        
        # Think/Answer 指标
        if metrics.get('think_time_seconds', 0) > 0:
            lines.append(f"| Think时间 | {metrics.get('think_time_seconds', 0):.3f}s |\n")
            lines.append(f"| Think Tokens | {metrics.get('think_tokens', 0)} |\n")
        if metrics.get('answer_time_seconds', 0) > 0:
            lines.append(f"| Answer时间 | {metrics.get('answer_time_seconds', 0):.3f}s |\n")
            lines.append(f"| Answer Tokens | {metrics.get('answer_tokens', 0)} |\n")
        
        lines.append(f"\n")
        
        # 输入提示
        lines.append(f"### 输入提示\n\n")
        lines.append(f"```\n")
        lines.append(f"{record.get('prompt', '')[:500]}\n")
        if len(record.get('prompt', '')) > 500:
            lines.append(f"... [内容过长，已截断]\n")
        lines.append(f"```\n\n")
        
        # Think 内容（如果存在）
        think_content = record.get('think_content')
        if think_content:
            lines.append(f"### 💭 思考内容 (Think)\n\n")
            lines.append(f"```\n")
            lines.append(f"{think_content[:1500]}\n")
            if len(think_content) > 1500:
                lines.append(f"... [内容过长，已截断]\n")
            lines.append(f"```\n\n")
        
        # Answer 内容（如果存在）
        answer_content = record.get('answer_content')
        if answer_content:
            lines.append(f"### 💬 回答内容 (Answer)\n\n")
            lines.append(f"```\n")
            lines.append(f"{answer_content[:1500]}\n")
            if len(answer_content) > 1500:
                lines.append(f"... [内容过长，已截断]\n")
            lines.append(f"```\n\n")
        
        # 完整模型响应
        lines.append(f"### 📋 完整模型响应\n\n")
        lines.append(f"```\n")
        lines.append(f"{record.get('response', '')[:1000]}\n")
        if len(record.get('response', '')) > 1000:
            lines.append(f"... [内容过长，已截断]\n")
        lines.append(f"```\n\n")
        
        # 评估结果
        evaluation = record.get("evaluation")
        if evaluation:
            lines.append(f"### 评估结果\n\n")
            lines.append(f"| 指标 | 值 |\n")
            lines.append(f"|------|-----|\n")
            lines.append(f"| 综合评分 | {evaluation.get('result', 0)}/{evaluation.get('max', 100)} |\n")
            lines.append(f"| 通过 | {'✅ 是' if evaluation.get('success') else '❌ 否'} |\n")
            
            if evaluation.get('is_correct') is not None:
                lines.append(f"| 正确性 | {'✅ 是' if evaluation.get('is_correct') else '❌ 否'} |\n")
            if evaluation.get('rate') is not None:
                lines.append(f"| 评分 | {evaluation.get('rate')}/10 |\n")
            
            if evaluation.get('reason'):
                lines.append(f"\n**评价**: {evaluation.get('reason')}\n")
            
            lines.append(f"\n")
        
        # 错误信息
        if not record.get("success", True):
            lines.append(f"### 错误信息\n\n")
            error = record.get("metrics", {}).get("error", "Unknown error")
            lines.append(f"```\n{error}\n```\n\n")
        
        lines.append(f"---\n\n")

        # 追加写入 Markdown 文件（使用 append 模式）
        content = "".join(lines)
        import aiofiles
        async with aiofiles.open(str(md_file), "a", encoding="utf-8") as f:
            await f.write(content)

    async def init_markdown_file(self):
        """异步初始化 all_rounds.md 文件头"""
        md_file = self.task_dir / "all_rounds.md"
        
        # 如果文件已存在，不重复写入头部
        if md_file.exists():
            return
        
        lines = [
            f"# AI模型测试记录\n\n",
            f"- 测试组ID: {self.group_id}\n",
            f"- 任务名称: {self.task_name}\n",
            f"- 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
            f"- 总轮次: {self.total_rounds or '未指定'}\n\n",
            "---\n\n",
        ]
        await write_text(str(md_file), "".join(lines))

    async def finalize(self, summary: Dict[str, Any] = None):
        """
        完成记录，生成 summary.json（异步版本）
        
        Args:
            summary: 汇总数据（可选）
        """
        # 初始化 Markdown 文件头（如果还没有）
        await self.init_markdown_file()
        
        # 生成 summary.json
        summary_file = self.task_dir / "summary.json"
        
        # 收集所有记录生成统计
        all_stats = await self._collect_stats()
        
        final_summary = {
            "group_id": self.group_id,
            "task_name": self.task_name,
            "completed_at": datetime.now().isoformat(),
            "total_records": self.record_count,
            "stats": all_stats,
            "custom_summary": summary
        }
        
        await write_json(str(summary_file), final_summary)
        
        # 异步更新 manifest.json 状态
        async with self._manifest_lock:
            manifest = await read_json(str(self.manifest_file))
            if manifest is None:
                manifest = {}

            manifest["status"] = "completed"
            manifest["completed_at"] = datetime.now().isoformat()
            manifest["total_records"] = self.record_count
            manifest["summary_file"] = str(summary_file.name)

            await atomic_write_json(str(self.manifest_file), manifest)

    async def _collect_stats(self) -> Dict[str, Any]:
        """异步收集所有记录的统计信息"""
        stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "by_model": {},
            "by_round": {}
        }
        
        # 遍历所有 round 目录
        for round_dir in self.task_dir.glob("round_*"):
            if not round_dir.is_dir():
                continue
            
            round_num = int(round_dir.name.split("_")[1])
            round_stats = {
                "total": 0,
                "success": 0,
                "failed": 0,
                "models": {}
            }
            
            for json_file in round_dir.glob("*.json"):
                record = await read_json(str(json_file))
                if record is None:
                    continue
                
                stats["total"] += 1
                round_stats["total"] += 1
                
                if record.get("success", True):
                    stats["success"] += 1
                    round_stats["success"] += 1
                else:
                    stats["failed"] += 1
                    round_stats["failed"] += 1
                
                # 按模型统计
                model_name = record.get("model_name", "unknown")
                if model_name not in stats["by_model"]:
                    stats["by_model"][model_name] = {"total": 0, "success": 0, "failed": 0}
                stats["by_model"][model_name]["total"] += 1
                if record.get("success", True):
                    stats["by_model"][model_name]["success"] += 1
                else:
                    stats["by_model"][model_name]["failed"] += 1
                
                # 按模型统计（轮次内）
                if model_name not in round_stats["models"]:
                    round_stats["models"][model_name] = {"total": 0, "success": 0}
                round_stats["models"][model_name]["total"] += 1
                if record.get("success", True):
                    round_stats["models"][model_name]["success"] += 1
            
            stats["by_round"][f"round_{round_num}"] = round_stats
        
        return stats

    # ===== 兼容旧接口的方法 =====

    async def get_records(self, model_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        异步读取已保存的记录（兼容旧接口）
        
        Args:
            model_name: 可选的模型名称过滤
            
        Returns:
            记录列表
        """
        records = []
        
        # 遍历所有 round 目录
        for round_dir in self.task_dir.glob("round_*"):
            if not round_dir.is_dir():
                continue
            
            for json_file in round_dir.glob("*.json"):
                record = await read_json(str(json_file))
                if record is None:
                    continue
                
                if model_name is None or record.get("model_name") == model_name:
                    records.append(record)
        
        return records

    async def generate_summary(self) -> Dict[str, Any]:
        """
        异步生成汇总报告（兼容旧接口）
        
        Returns:
            汇总统计
        """
        return await self._collect_stats()

    async def export_csv(self, output_path: Optional[str] = None) -> str:
        """
        异步导出为CSV格式（兼容旧接口）
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            CSV文件路径
        """
        records = await self.get_records()
        
        if not records:
            return ""
        
        if output_path is None:
            output_path = str(self.task_dir / f"summary_{self.current_session}.csv")
        
        import csv
        import io
        
        # 在内存中构建 CSV，然后异步写入
        output = io.StringIO()
        fieldnames = [
            "id", "timestamp", "model_name", "round",
            "ttft_seconds", "tpft_seconds", "total_time_seconds",
            "input_tokens", "output_tokens", "tokens_per_second", "success"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for record in records:
            metrics = record.get("metrics", {})
            row = {
                "id": record.get("id", ""),
                "timestamp": record.get("timestamp", ""),
                "model_name": record.get("model_name", ""),
                "round": record.get("round", ""),
                "ttft_seconds": metrics.get("ttft_seconds", ""),
                "tpft_seconds": metrics.get("tpft_seconds", ""),
                "total_time_seconds": metrics.get("total_time_seconds", ""),
                "input_tokens": metrics.get("input_tokens", ""),
                "output_tokens": metrics.get("output_tokens", ""),
                "tokens_per_second": metrics.get("tokens_per_second", ""),
                "success": record.get("success", True)
            }
            writer.writerow(row)
        
        await write_text(output_path, output.getvalue())
        return output_path