"""
输入输出记录器
用于记录每次模型调用的输入和输出
"""
import os
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path


class IORecorder:
    """输入输出记录器"""
    
    def __init__(self, results_dir: str = "results", save_detailed: bool = True):
        """
        初始化记录器
        
        Args:
            results_dir: 结果保存目录
            save_detailed: 是否保存详细日志
        """
        self.results_dir = Path(results_dir)
        self.save_detailed = save_detailed
        self.current_session = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 创建目录
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # IO记录文件 (改为md格式)
        self.io_file = self.results_dir / f"io_records_{self.current_session}.md"
        
        # 详细日志目录
        if self.save_detailed:
            self.logs_dir = self.results_dir / "logs" / self.current_session
            self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化Markdown文件
        self._init_md_file()
    
    def _init_md_file(self):
        """初始化Markdown文件头部"""
        with open(self.io_file, "w", encoding="utf-8") as f:
            f.write(f"# AI模型测试记录\n\n")
            f.write(f"- 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- 会话ID: {self.current_session}\n\n")
            f.write("---\n\n")
    
    def record(
        self,
        model_name: str,
        prompt: str,
        response: str,
        metrics: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        evaluation: Optional[Dict[str, Any]] = None
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
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 写入Markdown文件
        with open(self.io_file, "a", encoding="utf-8") as f:
            f.write(f"## 测试记录 - {timestamp}\n\n")
            f.write(f"**模型**: {model_name}\n\n")
            
            # 性能指标
            f.write(f"### 性能指标\n\n")
            f.write(f"| 指标 | 值 |\n")
            f.write(f"|------|-----|\n")
            f.write(f"| 首Token时间(TTFT) | {metrics.get('ttft_seconds', 0):.3f}s |\n")
            f.write(f"| 生成时间(TPFT) | {metrics.get('tpft_seconds', 0):.3f}s |\n")
            f.write(f"| 总耗时 | {metrics.get('total_time_seconds', 0):.3f}s |\n")
            f.write(f"| 输入Token数 | {metrics.get('input_tokens', 0)} |\n")
            f.write(f"| 输出Token数 | {metrics.get('output_tokens', 0)} |\n")
            f.write(f"| 输出速度 | {metrics.get('tokens_per_second', 0):.2f} tokens/s |\n")
            f.write(f"| 总速度 | {metrics.get('total_tokens_per_second', 0):.2f} tokens/s |\n")
            
            # Think/Answer 指标
            # 始终显示 Answer（没有 think 时，整个输出就是 answer）
            if 'answer_time_seconds' in metrics:
                f.write(f"| Answer时间 | {metrics.get('answer_time_seconds', 0):.3f}s |\n")
            if 'answer_tokens' in metrics:
                f.write(f"| Answer Tokens | {metrics.get('answer_tokens', 0)} |\n")
            
            # 只有当有 think 内容时才显示 Think 相关指标
            if metrics.get('think_time_seconds') and metrics.get('think_time_seconds', 0) > 0:
                f.write(f"| Think时间 | {metrics.get('think_time_seconds', 0):.3f}s |\n")
            if metrics.get('think_tokens') and metrics.get('think_tokens', 0) > 0:
                f.write(f"| Think Tokens | {metrics.get('think_tokens', 0)} |\n")
            if metrics.get('think_tokens_per_second') and metrics.get('think_tokens_per_second', 0) > 0:
                f.write(f"| Think速度 | {metrics.get('think_tokens_per_second', 0):.2f} tokens/s |\n")
            if metrics.get('answer_tokens_per_second') and metrics.get('answer_tokens_per_second', 0) > 0:
                f.write(f"| Answer速度 | {metrics.get('answer_tokens_per_second', 0):.2f} tokens/s |\n")
            
            f.write(f"\n")
            
            # 输入提示 - 完整记录
            f.write(f"### 输入提示\n\n")
            f.write(f"```\n")
            f.write(f"{prompt}\n")
            f.write(f"```\n\n")
            
            # 模型响应 - 完整记录
            f.write(f"### 模型响应\n\n")
            f.write(f"```\n")
            f.write(f"{response}\n")
            f.write(f"```\n\n")
            
            # 元数据
            if metadata:
                f.write(f"### 元数据\n\n")
                for key, value in metadata.items():
                    f.write(f"- **{key}**: {value}\n")
                f.write(f"\n")
            
            # 评估结果
            if evaluation:
                f.write(f"### 评估结果\n\n")
                f.write(f"| 指标 | 值 |\n")
                f.write(f"|------|-----|\n")
                f.write(f"| 综合评分 | {evaluation.get('result', 0)}/{evaluation.get('max', 100)} |\n")
                f.write(f"| 通过 | {'✅ 是' if evaluation.get('success') else '❌ 否'} |\n")
                
                if evaluation.get('dimensions'):
                    f.write(f"\n**各项维度得分**:\n\n")
                    for dim_name, dim_data in evaluation.get('dimensions', {}).items():
                        score = dim_data.get('score', 0) if isinstance(dim_data, dict) else dim_data
                        reason = dim_data.get('reason', '') if isinstance(dim_data, dict) else ''
                        f.write(f"- {dim_name}: {score}/100")
                        if reason:
                            f.write(f" - {reason}")
                        f.write(f"\n")
                
                if evaluation.get('summary'):
                    f.write(f"\n**总体评价**: {evaluation.get('summary')}\n")
                
                if evaluation.get('error'):
                    f.write(f"\n**评估错误**: {evaluation.get('error')}\n")
                
                f.write(f"\n")
            
            f.write(f"---\n\n")
        
        # 保存详细日志
        if self.save_detailed:
            self._save_detailed_log(model_name, {
                "timestamp": timestamp,
                "prompt": prompt,
                "response": response,
                "metrics": metrics,
                "metadata": metadata or {}
            })
    
    def _save_detailed_log(self, model_name: str, record: Dict[str, Any]):
        """保存详细日志"""
        # 清理模型名称作为文件名
        safe_name = model_name.replace("/", "_").replace(":", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{safe_name}_{timestamp}.json"
        
        log_path = self.logs_dir / filename
        
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
    
    def get_records(self, model_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        读取已保存的记录
        
        Args:
            model_name: 可选的模型名称过滤
            
        Returns:
            记录列表
        """
        records = []
        
        # 查找所有io记录文件 (支持jsonl和md格式)
        for pattern in ["io_records_*.jsonl", "io_records_*.md"]:
            for file_path in self.results_dir.glob(pattern):
                if file_path.suffix == ".jsonl":
                    # 旧格式：JSONL
                    with open(file_path, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                record = json.loads(line.strip())
                                if model_name is None or record.get("model_name") == model_name:
                                    records.append(record)
                            except json.JSONDecodeError:
                                continue
                elif file_path.suffix == ".md":
                    # 新格式：Markdown - 需要解析
                    # Markdown格式不便于回读，所以返回空列表或简化处理
                    pass
        
        return records
    
    def generate_summary(self) -> Dict[str, Any]:
        """
        生成汇总报告
        
        Returns:
            汇总统计
        """
        records = self.get_records()
        
        if not records:
            return {"message": "No records found"}
        
        # 按模型分组
        model_stats = {}
        
        for record in records:
            model_name = record.get("model_name", "unknown")
            metrics = record.get("metrics", {})
            
            if model_name not in model_stats:
                model_stats[model_name] = {
                    "count": 0,
                    "ttft_sum": 0,
                    "tpft_sum": 0,
                    "total_time_sum": 0,
                    "tokens_sum": 0
                }
            
            stats = model_stats[model_name]
            stats["count"] += 1
            stats["ttft_sum"] += metrics.get("ttft_seconds", 0)
            stats["tpft_sum"] += metrics.get("tpft_seconds", 0)
            stats["total_time_sum"] += metrics.get("total_time_seconds", 0)
            stats["tokens_sum"] += metrics.get("output_tokens", 0)
        
        # 计算平均值
        summary = {}
        for model_name, stats in model_stats.items():
            count = stats["count"]
            summary[model_name] = {
                "test_count": count,
                "avg_ttft": round(stats["ttft_sum"] / count, 4),
                "avg_tpft": round(stats["tpft_sum"] / count, 4),
                "avg_total_time": round(stats["total_time_sum"] / count, 4),
                "avg_output_tokens": round(stats["tokens_sum"] / count, 2),
                "avg_tokens_per_second": round(
                    stats["tokens_sum"] / stats["total_time_sum"] if stats["total_time_sum"] > 0 else 0,
                    2
                )
            }
        
        return summary
    
    def export_csv(self, output_path: Optional[str] = None) -> str:
        """
        导出为CSV格式
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            CSV文件路径
        """
        records = self.get_records()
        
        if not records:
            return ""
        
        if output_path is None:
            output_path = str(self.results_dir / f"summary_{self.current_session}.csv")
        
        import csv
        
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            fieldnames = [
                "timestamp", "model_name", "ttft_seconds", "tpft_seconds",
                "total_time_seconds", "input_tokens", "output_tokens",
                "tokens_per_second"
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for record in records:
                row = {
                    "timestamp": record.get("timestamp", ""),
                    "model_name": record.get("model_name", ""),
                    "ttft_seconds": record.get("metrics", {}).get("ttft_seconds", ""),
                    "tpft_seconds": record.get("metrics", {}).get("tpft_seconds", ""),
                    "total_time_seconds": record.get("metrics", {}).get("total_time_seconds", ""),
                    "input_tokens": record.get("metrics", {}).get("input_tokens", ""),
                    "output_tokens": record.get("metrics", {}).get("output_tokens", ""),
                    "tokens_per_second": record.get("metrics", {}).get("tokens_per_second", ""),
                }
                writer.writerow(row)
        
        return output_path