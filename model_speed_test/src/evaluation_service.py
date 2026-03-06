"""
评估服务模块
负责调用模型进行输出质量评估
"""
import json
import re
from typing import Dict, Any, Optional
from .client import ModelClient


class EvaluationService:
    """评估服务 - 调用模型评估输出质量"""
    
    # 默认评估提示词模板
    DEFAULT_TEMPLATE = """你是一个专业的AI模型评估专家。请根据以下标准评估模型的输出质量。

## 用户问题
{prompt}

## 模型输出
{model_output}

## 标准答案（如有）
{golden_answer}

## 评分维度
{scoring_dimensions}

## 评分阈值
{threshold}

## 输出要求
请以JSON格式返回评估结果，格式如下：
{{
    "result": <0-100的综合评分>,
    "max": 100,
    "success": <result >= threshold>,
    "dimensions": {{
        "<维度名>": {{"score": <0-100>, "reason": "<评分理由>"}}
    }},
    "summary": "<总体评价>"
}}

只返回JSON，不要有其他内容。"""

    def __init__(self, eval_client: ModelClient, template: str = None):
        self.client = eval_client
        self.template = template if template is not None else self.DEFAULT_TEMPLATE
    
    def _build_scoring_dimensions(self, scoring_criteria: Dict[str, Any]) -> str:
        """构建评分维度描述"""
        dimensions = scoring_criteria.get("dimensions", [])
        if not dimensions:
            return "无特定评分维度"
        
        lines = []
        for dim in dimensions:
            name = dim.get("name", "unknown")
            weight = dim.get("weight", 0)
            desc = dim.get("description", "")
            lines.append(f"- {name} (权重 {weight}): {desc}")
        
        return "\n".join(lines)
    
    def build_eval_prompt(
        self,
        prompt: str,
        model_output: str,
        golden_answer: str = "",
        scoring_criteria: Dict[str, Any] = None,
        custom_template: str = None
    ) -> str:
        """构建评估提示词"""
        template = custom_template or self.template
        scoring_criteria = scoring_criteria or {}
        
        # 构建评分维度描述
        scoring_dimensions = self._build_scoring_dimensions(scoring_criteria)
        
        # 获取阈值
        threshold = scoring_criteria.get("threshold", 70)
        
        return template.format(
            prompt=prompt,
            model_output=model_output,
            golden_answer=golden_answer or "无",
            scoring_dimensions=scoring_dimensions,
            threshold=threshold
        )
    
    async def evaluate(
        self,
        prompt: str,
        model_output: str,
        golden_answer: str = "",
        scoring_criteria: Dict[str, Any] = None,
        custom_template: str = None,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        执行评估
        
        Args:
            prompt: 用户原始问题
            model_output: 模型输出内容
            golden_answer: 标准答案（可选）
            scoring_criteria: 评分标准配置
            custom_template: 自定义评估模板
            max_tokens: 最大token数
            
        Returns:
            评估结果字典
        """
        scoring_criteria = scoring_criteria or {}
        
        # 构建评估提示词
        eval_prompt = self.build_eval_prompt(
            prompt=prompt,
            model_output=model_output,
            golden_answer=golden_answer,
            scoring_criteria=scoring_criteria,
            custom_template=custom_template
        )
        
        try:
            # 调用评估模型
            result = await self.client.chat(
                prompt=eval_prompt,
                max_tokens=max_tokens,
                stream=False
            )
            
            content = result.get("content", "")
            
            # 解析结果
            eval_result = self.parse_result(content, scoring_criteria)
            
            return eval_result
            
        except Exception as e:
            return {
                "result": 0,
                "max": 100,
                "success": False,
                "error": str(e),
                "dimensions": {},
                "summary": f"评估失败: {str(e)}"
            }
    
    def parse_result(
        self,
        content: str,
        scoring_criteria: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """解析评估结果"""
        scoring_criteria = scoring_criteria or {}
        threshold = scoring_criteria.get("threshold", 70)
        
        # 尝试提取 JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        
        if not json_match:
            # 无法解析，返回默认结果
            return {
                "result": 0,
                "max": 100,
                "success": False,
                "error": "无法解析评估结果",
                "dimensions": {},
                "summary": content[:200] if content else "无评估结果"
            }
        
        try:
            data = json.loads(json_match.group())
            
            # 提取关键字段
            result = data.get("result", 0)
            max_score = data.get("max", 100)
            success = result >= threshold
            
            return {
                "result": result,
                "max": max_score,
                "success": success,
                "dimensions": data.get("dimensions", {}),
                "summary": data.get("summary", ""),
                "raw_data": data
            }
            
        except json.JSONDecodeError:
            return {
                "result": 0,
                "max": 100,
                "success": False,
                "error": "JSON解析失败",
                "dimensions": {},
                "summary": content[:200]
            }


class EvaluationConfig:
    """评估配置类"""
    
    # 预置评分维度模板
    DEFAULT_DIMENSIONS = [
        {"name": "accuracy", "weight": 0.3, "description": "答案正确性 - 答案是否正确"},
        {"name": "completeness", "weight": 0.3, "description": "完整性 - 是否覆盖所有要点"},
        {"name": "format", "weight": 0.2, "description": "格式规范性 - 输出格式是否符合要求"},
        {"name": "relevance", "weight": 0.2, "description": "相关性 - 是否切题"}
    ]
    
    # 简单对比评分（只有通过/不通过）
    SIMPLE_DIMENSIONS = [
        {"name": "correctness", "weight": 1.0, "description": "答案正确性"}
    ]
    
    @staticmethod
    def create_simple_config(threshold: int = 70) -> Dict[str, Any]:
        """创建简单的评估配置"""
        return {
            "dimensions": EvaluationConfig.SIMPLE_DIMENSIONS.copy(),
            "threshold": threshold,
            "output_format": "json"
        }
    
    @staticmethod
    def create_default_config(threshold: int = 70) -> Dict[str, Any]:
        """创建默认评估配置"""
        return {
            "dimensions": EvaluationConfig.DEFAULT_DIMENSIONS.copy(),
            "threshold": threshold,
            "output_format": "json"
        }


def create_evaluation_service(
    eval_client: ModelClient,
    template: str = None
) -> EvaluationService:
    """创建评估服务工厂函数"""
    return EvaluationService(eval_client, template)