"""
质量评估模块
支持多维度评估、答案对比、批量评估
"""
import json
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from .client import ModelClient


class EvaluationDimension(Enum):
    """评估维度"""
    ACCURACY = "accuracy"           # 准确性
    COMPLETENESS = "completeness"   # 完整性
    CLARITY = "clarity"           # 清晰度
    RELEVANCE = "relevance"        # 相关性
    FORMAT = "format"              # 格式规范性


@dataclass
class EvaluationScore:
    """评估分数"""
    dimension: str
    score: int          # 0-100
    reason: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension": self.dimension,
            "score": self.score,
            "reason": self.reason
        }


@dataclass
class EvaluationResult:
    """评估结果"""
    model_name: str
    prompt: str
    response: str
    golden_answer: str = ""
    
    # 各项分数
    accuracy: EvaluationScore = None
    completeness: EvaluationScore = None
    clarity: EvaluationScore = None
    relevance: EvaluationScore = None
    format: EvaluationScore = None
    
    # 综合分数
    overall: int = 0
    summary: str = ""
    
    # 元数据
    eval_model: str = ""
    eval_time: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        scores = {}
        for dim in EvaluationDimension:
            score = getattr(self, dim.value, None)
            if score:
                scores[dim.value] = score.to_dict()
        
        return {
            "model_name": self.model_name,
            "prompt": self.prompt,
            "response": self.response,
            "golden_answer": self.golden_answer,
            "scores": scores,
            "overall": self.overall,
            "summary": self.summary,
            "eval_model": self.eval_model,
            "eval_time": self.eval_time,
            "metadata": self.metadata
        }


class EvaluationPromptTemplate:
    """评估 Prompt 模板"""
    
    DEFAULT_TEMPLATE = """你是一个专业的AI模型评估专家。请根据以下维度评估模型的输出质量。

## 待评估输出
{model_output}

## 用户问题
{prompt}

## 参考答案 (如有)
{golden_answer}

## 评估维度
请对以下每个维度进行评分 (0-100分)，并给出评分理由：

1. 准确性 (accuracy): 答案是否正确？是否有事实错误？
2. 完整性 (completeness): 是否覆盖了问题的所有要点？
3. 清晰度 (clarity): 表达是否清晰、有条理？
4. 相关性 (relevance): 是否切题，是否回答了用户的问题？
5. 格式规范性 (format): 输出格式是否符合要求？

## 输出格式
请以JSON格式返回评估结果：
{{
    "accuracy": {{"score": 85, "reason": "..."}},
    "completeness": {{"score": 70, "reason": "..."}},
    "clarity": {{"score": 90, "reason": "..."}},
    "relevance": {{"score": 80, "reason": "..."}},
    "format": {{"score": 100, "reason": "..."}},
    "overall": 85,
    "summary": "总体评价..."
}}

注意：只返回JSON，不要有其他内容。"""
    
    SIMPLE_TEMPLATE = """评估以下回答的质量（0-100分）：

问题：{prompt}
回答：{model_output}
参考答案：{golden_answer}

输出JSON格式：
{{"accuracy": score, "completeness": score, "clarity": score, "relevance": score, "format": score, "overall": score, "summary": "评价"}}"""

    def __init__(self, template: str = None):
        self.template = template or self.DEFAULT_TEMPLATE
    
    def render(
        self,
        model_output: str,
        prompt: str,
        golden_answer: str = ""
    ) -> str:
        """渲染评估 Prompt"""
        return self.template.format(
            model_output=model_output,
            prompt=prompt,
            golden_answer=golden_answer or "无"
        )


class AnswerComparator:
    """答案对比器"""
    
    def __init__(self):
        pass
    
    def exact_match(self, response: str, golden: str) -> float:
        """精确匹配分数"""
        if not golden:
            return 0
        return 100 if response.strip() == golden.strip() else 0
    
    def keyword_match(self, response: str, golden: str) -> float:
        """关键词匹配分数"""
        if not golden:
            return 0
        
        golden_keywords = set(golden.lower().split())
        response_keywords = set(response.lower().split())
        
        if not golden_keywords:
            return 0
        
        matches = len(golden_keywords & response_keywords)
        return round(matches / len(golden_keywords) * 100, 2)
    
    def similarity(self, response: str, golden: str) -> float:
        """相似度分数（基于字符重叠）"""
        if not golden or not response:
            return 0
        
        # 简单字符级相似度
        set_r = set(response)
        set_g = set(golden)
        
        if not set_g:
            return 0
        
        intersection = len(set_r & set_g)
        union = len(set_r | set_g)
        
        return round(intersection / union * 100, 2) if union > 0 else 0
    
    def compare(
        self,
        response: str,
        golden: str,
        method: str = "keyword"
    ) -> Dict[str, float]:
        """综合对比"""
        if method == "exact":
            score = self.exact_match(response, golden)
        elif method == "keyword":
            score = self.keyword_match(response, golden)
        elif method == "similarity":
            score = self.similarity(response, golden)
        else:
            # 综合方法
            scores = [
                self.exact_match(response, golden),
                self.keyword_match(response, golden),
                self.similarity(response, golden)
            ]
            score = sum(scores) / len(scores)
        
        return {
            "score": score,
            "method": method
        }


class ModelEvaluator:
    """模型评估器"""
    
    def __init__(
        self,
        eval_client: ModelClient,
        template: EvaluationPromptTemplate = None
    ):
        self.eval_client = eval_client
        self.template = template or EvaluationPromptTemplate()
        self.comparator = AnswerComparator()
    
    async def evaluate_single(
        self,
        model_name: str,
        prompt: str,
        response: str,
        golden_answer: str = "",
        max_tokens: int = 2000
    ) -> EvaluationResult:
        """评估单个输出"""
        result = EvaluationResult(
            model_name=model_name,
            prompt=prompt,
            response=response,
            golden_answer=golden_answer,
            eval_model=self.eval_client.name
        )
        
        # 优先使用 golden_answer 进行对比
        if golden_answer:
            comparison = self.comparator.compare(response, golden_answer)
            # 将对比结果作为准确性分数
            result.accuracy = EvaluationScore(
                dimension="accuracy",
                score=int(comparison["score"]),
                reason=f"与参考答案相似度: {comparison['score']}%"
            )
        
        # 使用评估模型进行详细评估
        eval_prompt = self.template.render(
            model_output=response,
            prompt=prompt,
            golden_answer=golden_answer
        )
        
        try:
            eval_response = await self.eval_client.chat(
                prompt=eval_prompt,
                max_tokens=max_tokens,
                stream=False
            )
            
            eval_content = eval_response.get("content", "")
            
            # 解析 JSON 结果
            try:
                eval_data = json.loads(eval_content)
                
                # 填充各项分数
                for dim in EvaluationDimension:
                    dim_name = dim.value
                    if dim_name in eval_data:
                        dim_data = eval_data[dim_name]
                        setattr(result, dim_name, EvaluationScore(
                            dimension=dim_name,
                            score=dim_data.get("score", 0),
                            reason=dim_data.get("reason", "")
                        ))
                
                result.overall = eval_data.get("overall", 0)
                result.summary = eval_data.get("summary", "")
                
            except json.JSONDecodeError:
                # 解析失败，使用简单解析
                result.summary = f"评估响应解析失败: {eval_content[:200]}"
                result.overall = 0
                
        except Exception as e:
            result.summary = f"评估失败: {str(e)}"
        
        from datetime import datetime
        result.eval_time = datetime.now().isoformat()
        
        return result
    
    async def evaluate_batch(
        self,
        results: List[Dict[str, str]],
        golden_answers: Dict[str, str] = None,
        concurrency: int = 5
    ) -> List[EvaluationResult]:
        """批量评估"""
        golden_answers = golden_answers or {}
        
        tasks = []
        for item in results:
            model_name = item.get("model_name", "unknown")
            prompt = item.get("prompt", "")
            response = item.get("response", "")
            golden = golden_answers.get(prompt, "")
            
            tasks.append(
                self.evaluate_single(
                    model_name=model_name,
                    prompt=prompt,
                    response=response,
                    golden_answer=golden
                )
            )
        
        # 并发控制
        eval_results = []
        for i in range(0, len(tasks), concurrency):
            batch = tasks[i:i+concurrency]
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            eval_results.extend(batch_results)
        
        return eval_results
    
    def compare_models(
        self,
        eval_results: List[EvaluationResult]
    ) -> Dict[str, Any]:
        """对比模型表现"""
        # 按模型分组
        models: Dict[str, List[EvaluationResult]] = {}
        for result in eval_results:
            if result.model_name not in models:
                models[result.model_name] = []
            models[result.model_name].append(result)
        
        # 计算每个模型的平均分
        model_stats = {}
        for model_name, results in models.items():
            if not results:
                continue
            
            total_overall = sum(r.overall for r in results)
            count = len(results)
            
            # 计算各维度平均分
            dim_scores = {dim.value: [] for dim in EvaluationDimension}
            for r in results:
                for dim in EvaluationDimension:
                    score = getattr(r, dim.value, None)
                    if score:
                        dim_scores[dim.value].append(score.score)
            
            dim_avgs = {}
            for dim_name, scores in dim_scores.items():
                dim_avgs[dim_name] = sum(scores) / len(scores) if scores else 0
            
            model_stats[model_name] = {
                "count": count,
                "overall_avg": round(total_overall / count, 2),
                "dimensions": {k: round(v, 2) for k, v in dim_avgs.items()}
            }
        
        return {
            "total_evaluations": len(eval_results),
            "model_count": len(models),
            "model_stats": model_stats,
            "ranking": sorted(
                model_stats.items(),
                key=lambda x: x[1]["overall_avg"],
                reverse=True
            )
        }
    
    def generate_report(
        self,
        eval_results: List[EvaluationResult],
        title: str = "模型质量评估报告"
    ) -> str:
        """生成 Markdown 评估报告"""
        from datetime import datetime
        
        # 统计信息
        total = len(eval_results)
        if total == 0:
            return "# 评估报告\n\n暂无评估数据"
        
        success_count = sum(1 for r in eval_results if r.overall > 0)
        avg_overall = sum(r.overall for r in eval_results) / total
        
        # 按模型统计
        model_stats = self.compare_models(eval_results)
        
        report = f"""# {title}

## 概览
- 评估时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- 总评估数: {total}
- 有效评估: {success_count}
- 平均得分: {avg_overall:.2f}

## 模型排名
"""
        
        for i, (model_name, stats) in enumerate(model_stats.get("ranking", []), 1):
            report += f"""
### {i}. {model_name}
- 评估次数: {stats['count']}
- 综合得分: {stats['overall_avg']}
"""
            if "dimensions" in stats:
                report += "- 各维度得分:\n"
                for dim, score in stats["dimensions"].items():
                    report += f"  - {dim}: {score:.2f}\n"
        
        # 详细结果
        report += "\n## 详细评估结果\n\n"
        report += "| 模型 | 准确性 | 完整性 | 清晰度 | 相关性 | 格式 | 综合 |\n"
        report += "|------|--------|--------|--------|--------|------|------|\n"
        
        for result in eval_results:
            acc = result.accuracy.score if result.accuracy else "-"
            comp = result.completeness.score if result.completeness else "-"
            cla = result.clarity.score if result.clarity else "-"
            rel = result.relevance.score if result.relevance else "-"
            fmt = result.format.score if result.format else "-"
            
            report += f"| {result.model_name} | {acc} | {comp} | {cla} | {rel} | {fmt} | {result.overall} |\n"
        
        return report


# 默认评估配置
DEFAULT_EVAL_CONFIG = {
    "dimensions": [
        {"name": "accuracy", "weight": 0.3, "description": "答案正确性"},
        {"name": "completeness", "weight": 0.2, "description": "覆盖完整性"},
        {"name": "clarity", "weight": 0.15, "description": "表达清晰度"},
        {"name": "relevance", "weight": 0.2, "description": "切题程度"},
        {"name": "format", "weight": 0.15, "description": "格式规范性"}
    ],
    "thresholds": {
        "excellent": 90,
        "good": 75,
        "fair": 60,
        "poor": 0
    }
}