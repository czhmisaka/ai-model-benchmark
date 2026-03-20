"""
评估管理器
负责协调评估配置和执行校对验证
"""
from typing import Dict, Any, Optional


class EvaluationManager:
    """评估管理器"""
    
    def __init__(self, eval_client=None):
        """
        初始化评估管理器
        
        Args:
            eval_client: 评估用的模型客户端
        """
        self.eval_client = eval_client
        self.evaluation_service = None
        
        if eval_client:
            from .evaluation_service import EvaluationService
            self.evaluation_service = EvaluationService(eval_client)
    
    def set_eval_client(self, eval_client):
        """设置评估客户端"""
        self.eval_client = eval_client
        from .evaluation_service import EvaluationService
        self.evaluation_service = EvaluationService(eval_client)
    
    async def verify_output(
        self,
        prompt: str,
        model_output: str,
        golden_answer: str
    ) -> Dict[str, Any]:
        """
        校对验证 - 简单的对比验证
        
        Args:
            prompt: 原始用户问题
            model_output: 模型输出内容（待校对）
            golden_answer: 标准答案
            
        Returns:
            校对结果字典，包含 is_correct, rate, reason
        """
        if not self.evaluation_service:
            return {
                "is_correct": False,
                "rate": 0,
                "reason": "校对服务未初始化",
                "error": "校对服务未初始化"
            }
        
        # 执行校对验证
        result = await self.evaluation_service.verify(
            prompt=prompt,
            model_output=model_output,
            golden_answer=golden_answer
        )
        
        return result
