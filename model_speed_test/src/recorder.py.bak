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
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path


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
        results_dir: str = "results",
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
        
        # 初始化 manifest
        self._init_manifest(config)
        
        # 记录计数器
        self.record_count = 0
        self.current_round = 0
    
    def _init_manifest(self, config: Dict[str, Any] = None):
        """初始化 manifest.json"""
        manifest = {
            "group_id": self.group_id,
            "task_name": self.task_name,
            "created_at": datetime.now().isoformat(),
            "total_rounds": self.total_rounds,
            "config": config,
            "files": {}  # round_N: [file_list]
        }
        
        with open(self.manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    def _update_manifest(self, round_num: int, filename: str):
        """更新 manifest.json"""
        try:
            with open(self.manifest_file, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            manifest = {"files": {}}
        
        round_key = f"round_{round_num}"
        if round_key not in manifest.get("files", {}):
            manifest["files"][round_key] = []
        
        if filename not in manifest["files"][round_key]:
            manifest["files"][round_key].append(filename)
        
        with open(self.manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
    
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
    
    def record(
        self,
        model_name: str,
        prompt: str,
        response: str,
        metrics: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        evaluation: Optional[Dict[str, Any]] = None,
        round_num: int = None,
        think_content: Optional[str] = None,
        answer_content: Optional[str] = None
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
        record_data = {
            "id": record_id,
            "timestamp": timestamp,
            "group_id": self.group_id,
            "round": round_num,
            "model_name": model_name,
            "success": metadata.get("success", True) if metadata else True,
            "metrics": metrics,
            "prompt": prompt,
            "response": response,
            "metadata": metadata or {},
            "evaluation": evaluation,
            "think_content": think_content,
            "answer_content": answer_content
        }
        
        # 保存 JSON 文件
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(record_data, f, ensure_ascii=False, indent=2)
        
        # 更新 manifest
        self._update_manifest(round_num, filename)
        
        # 生成 Markdown 人类可读文件（追加到 all_rounds.md）
        self._append_markdown(record_data)
    
    def _append_markdown(self, record: Dict[str, Any]):
        """追加记录到 all_rounds.md"""
        md_file = self.task_dir / "all_rounds.md"
        
        with open(md_file, "a", encoding="utf-8") as f:
            f.write(f"## 测试记录 - {record['timestamp']}\n\n")
            f.write(f"**模型**: {record['model_name']}\n")
            f.write(f"**轮次**: {record['round']}\n")
            f.write(f"**记录ID**: {record['id']}\n\n")
            
            # 性能指标
            f.write(f"### 性能指标\n\n")
            f.write(f"| 指标 | 值 |\n")
            f.write(f"|------|-----|\n")
            
            metrics = record.get("metrics", {})
            f.write(f"| 首Token时间(TTFT) | {metrics.get('ttft_seconds', 0):.3f}s |\n")
            f.write(f"| 生成时间(TPFT) | {metrics.get('tpft_seconds', 0):.3f}s |\n")
            f.write(f"| 总耗时 | {metrics.get('total_time_seconds', 0):.3f}s |\n")
            f.write(f"| 输入Token数 | {metrics.get('input_tokens', 0)} |\n")
            f.write(f"| 输出Token数 | {metrics.get('output_tokens', 0)} |\n")
            f.write(f"| 输出速度 | {metrics.get('tokens_per_second', 0):.2f} tokens/s |\n")
            
            # Think/Answer 指标
            if metrics.get('think_time_seconds', 0) > 0:
                f.write(f"| Think时间 | {metrics.get('think_time_seconds', 0):.3f}s |\n")
                f.write(f"| Think Tokens | {metrics.get('think_tokens', 0)} |\n")
            if metrics.get('answer_time_seconds', 0) > 0:
                f.write(f"| Answer时间 | {metrics.get('answer_time_seconds', 0):.3f}s |\n")
                f.write(f"| Answer Tokens | {metrics.get('answer_tokens', 0)} |\n")
            
            f.write(f"\n")
            
            # 输入提示
            f.write(f"### 输入提示\n\n")
            f.write(f"```\n")
            f.write(f"{record.get('prompt', '')[:500]}\n")
            if len(record.get('prompt', '')) > 500:
                f.write(f"... [内容过长，已截断]\n")
            f.write(f"```\n\n")
            
            # Think 内容（如果存在）
            think_content = record.get('think_content')
            if think_content:
                f.write(f"### 💭 思考内容 (Think)\n\n")
                f.write(f"```\n")
                f.write(f"{think_content[:1500]}\n")
                if len(think_content) > 1500:
                    f.write(f"... [内容过长，已截断]\n")
                f.write(f"```\n\n")
            
            # Answer 内容（如果存在）
            answer_content = record.get('answer_content')
            if answer_content:
                f.write(f"### 💬 回答内容 (Answer)\n\n")
                f.write(f"```\n")
                f.write(f"{answer_content[:1500]}\n")
                if len(answer_content) > 1500:
                    f.write(f"... [内容过长，已截断]\n")
                f.write(f"```\n\n")
            
            # 完整模型响应（原始内容）
            f.write(f"### 📋 完整模型响应\n\n")
            f.write(f"```\n")
            f.write(f"{record.get('response', '')[:1000]}\n")
            if len(record.get('response', '')) > 1000:
                f.write(f"... [内容过长，已截断]\n")
            f.write(f"```\n\n")
            
            # 评估结果
            evaluation = record.get("evaluation")
            if evaluation:
                f.write(f"### 评估结果\n\n")
                f.write(f"| 指标 | 值 |\n")
                f.write(f"|------|-----|\n")
                f.write(f"| 综合评分 | {evaluation.get('result', 0)}/{evaluation.get('max', 100)} |\n")
                f.write(f"| 通过 | {'✅ 是' if evaluation.get('success') else '❌ 否'} |\n")
                
                if evaluation.get('is_correct') is not None:
                    f.write(f"| 正确性 | {'✅ 是' if evaluation.get('is_correct') else '❌ 否'} |\n")
                if evaluation.get('rate') is not None:
                    f.write(f"| 评分 | {evaluation.get('rate')}/10 |\n")
                
                if evaluation.get('reason'):
                    f.write(f"\n**评价**: {evaluation.get('reason')}\n")
                
                f.write(f"\n")
            
            # 错误信息
            if not record.get("success", True):
                f.write(f"### 错误信息\n\n")
                error = record.get("metrics", {}).get("error", "Unknown error")
                f.write(f"```\n{error}\n```\n\n")
            
            f.write(f"---\n\n")
    
    def init_markdown_file(self):
        """初始化 all_rounds.md 文件头"""
        md_file = self.task_dir / "all_rounds.md"
        
        # 如果文件已存在，不重复写入头部
        if md_file.exists():
            return
        
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(f"# AI模型测试记录\n\n")
            f.write(f"- 测试组ID: {self.group_id}\n")
            f.write(f"- 任务名称: {self.task_name}\n")
            f.write(f"- 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- 总轮次: {self.total_rounds or '未指定'}\n\n")
            f.write("---\n\n")
    
    def finalize(self, summary: Dict[str, Any] = None):
        """
        完成记录，生成 summary.json
        
        Args:
            summary: 汇总数据（可选）
        """
        # 初始化 Markdown 文件头（如果还没有）
        self.init_markdown_file()
        
        # 生成 summary.json
        summary_file = self.task_dir / "summary.json"
        
        # 收集所有记录生成统计
        all_stats = self._collect_stats()
        
        final_summary = {
            "group_id": self.group_id,
            "task_name": self.task_name,
            "completed_at": datetime.now().isoformat(),
            "total_records": self.record_count,
            "stats": all_stats,
            "custom_summary": summary
        }
        
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(final_summary, f, ensure_ascii=False, indent=2)
        
        # 更新 manifest.json 状态
        try:
            with open(self.manifest_file, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except:
            manifest = {}
        
        manifest["status"] = "completed"
        manifest["completed_at"] = datetime.now().isoformat()
        manifest["total_records"] = self.record_count
        manifest["summary_file"] = str(summary_file.name)
        
        with open(self.manifest_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    def _collect_stats(self) -> Dict[str, Any]:
        """收集所有记录的统计信息"""
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
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        record = json.load(f)
                    
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
                
                except (json.JSONDecodeError, IOError):
                    continue
            
            stats["by_round"][f"round_{round_num}"] = round_stats
        
        return stats
    
    # ===== 兼容旧接口的方法 =====
    
    def get_records(self, model_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        读取已保存的记录（兼容旧接口）
        
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
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        record = json.load(f)
                    
                    if model_name is None or record.get("model_name") == model_name:
                        records.append(record)
                except (json.JSONDecodeError, IOError):
                    continue
        
        return records
    
    def generate_summary(self) -> Dict[str, Any]:
        """
        生成汇总报告（兼容旧接口）
        
        Returns:
            汇总统计
        """
        return self._collect_stats()
    
    def export_csv(self, output_path: Optional[str] = None) -> str:
        """
        导出为CSV格式（兼容旧接口）
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            CSV文件路径
        """
        records = self.get_records()
        
        if not records:
            return ""
        
        if output_path is None:
            output_path = str(self.task_dir / f"summary_{self.current_session}.csv")
        
        import csv
        
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            fieldnames = [
                "id", "timestamp", "model_name", "round",
                "ttft_seconds", "tpft_seconds", "total_time_seconds",
                "input_tokens", "output_tokens", "tokens_per_second", "success"
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
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
        
