"""
评估管理器
负责协调评估配置和执行评估
"""
import asyncio
from typing import Dict, Any, Optional, List
from .client import ModelClient
from .evaluation_service import EvaluationService, EvaluationConfig


class EvaluationManager:
    """评估管理器"""
    
    def __init__(self, eval_client: ModelClient = None):
        """
        初始化评估管理器
        
        Args:
            eval_client: 评估用的模型客户端（默认使用 MiniMax M2.5）
        """
        self.eval_client = eval_client
        self.evaluation_service = None
        
        if eval_client:
            self.evaluation_service = EvaluationService(eval_client)
    
    def set_eval_client(self, eval_client: ModelClient):
        """设置评估客户端"""
        self.eval_client = eval_client
        self.evaluation_service = EvaluationService(eval_client)
    
    def get_evaluation_config(self, test_case: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        从测试用例获取评估配置
        
        Args:
            test_case: 测试用例配置
            
        Returns:
            评估配置（如果启用）
        """
        evaluation = test_case.get("evaluation", {})
        
        # 检查是否启用评估
        if not evaluation.get("enabled", False):
            return None
        
        return {
            "enabled": True,
            "golden_answer": evaluation.get("golden_answer", ""),
            "scoring_criteria": evaluation.get("scoring_criteria", {}),
            "prompt_template": evaluation.get("prompt_template", None)
        }
    
    async def evaluate_output(
        self,
        prompt: str,
        model_output: str,
        evaluation_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        评估模型输出
        
        Args:
            prompt: 原始用户问题
            model_output: 模型输出内容
            evaluation_config: 评估配置
            
        Returns:
            评估结果
        """
        if not self.evaluation_service:
            return {
                "result": 0,
                "max": 100,
                "success": False,
                "error": "评估服务未初始化",
                "dimensions": {},
                "summary": "评估服务未初始化"
            }
        
        golden_answer = evaluation_config.get("golden_answer", "")
        scoring_criteria = evaluation_config.get("scoring_criteria", {})
        custom_template = evaluation_config.get("prompt_template")
        
        # 执行评估
        result = await self.evaluation_service.evaluate(
            prompt=prompt,
            model_output=model_output,
            golden_answer=golden_answer,
            scoring_criteria=scoring_criteria,
            custom_template=custom_template
        )
        
        return result
    
    def should_evaluate(self, test_case: Dict[str, Any]) -> bool:
        """
        检查测试用例是否应该执行评估
        
        Args:
            test_case: 测试用例配置
            
        Returns:
            是否应该评估
        """
        evaluation = test_case.get("evaluation", {})
        return evaluation.get("enabled", False) is True
    
    def create_default_evaluation_config(
        self,
        golden_answer: str = "",
        threshold: int = 70
    ) -> Dict[str, Any]:
        """
        创建默认评估配置
        
        Args:
            golden_answer: 标准答案
            threshold: 评分阈值
            
        Returns:
            评估配置字典
        """
        return {
            "enabled": True,
            "golden_answer": golden_answer,
            "scoring_criteria": EvaluationConfig.create_default_config(threshold)
        }
    
    def create_simple_evaluation_config(
        self,
        golden_answer: str = "",
        threshold: int = 70
    ) -> Dict[str, Any]:
        """
        创建简单评估配置（只有正确性判断）
        
        Args:
            golden_answer: 标准答案
            threshold: 评分阈值
            
        Returns:
            评估配置字典
        """
        return {
            "enabled": True,
            "golden_answer": golden_answer,
            "scoring_criteria": EvaluationConfig.create_simple_config(threshold)
        }


def create_evaluation_manager(
    eval_model_config: Dict[str, Any] = None
) -> EvaluationManager:
    """
    创建评估管理器
    
    Args:
        eval_model_config: 评估模型配置（可选）
        
    Returns:
        EvaluationManager 实例
    """
    if eval_model_config:
        # 使用指定的评估模型
        client = ModelClient(
            name=eval_model_config.get("name", "MiniMax-Evaluator"),
            endpoint=eval_model_config.get("endpoint"),
            api_key=eval_model_config.get("api_key"),
            model=eval_model_config.get("model", "abab6.5s-chat")
        )
        return EvaluationManager(eval_client=client)
    
    # 默认使用 MiniMax M2.5 作为评估模型
    return EvaluationManager()


# 预置评估模型配置
DEFAULT_EVAL_MODEL = {
    "name": "MiniMax-M2.5-Evaluator",
    "endpoint": "https://api.minimax.chat/v1/text/chatcompletion_v2",
    "api_key": "${MINIMAX_API_KEY}",
    "model": "abab6.5s-chat"
}