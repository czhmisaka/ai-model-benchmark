"""
评估服务模块
负责调用模型进行输出质量校对验证
"""
import json
import re
from typing import Dict, Any


class EvaluationService:
    """评估服务 - 调用模型进行校对验证"""
    
    # 校对验证提示词模板 - 简单的对比验证，返回结构化结果
    VERIFY_TEMPLATE = """你是一个专业的AI模型校对专家。请对比模型输出与标准答案，判断回答的正确性。

## 用户问题
{prompt}

## 模型输出（待校对）
{model_output}

## 标准答案
{golden_answer}

## 输出要求
请仔细对比模型输出与标准答案，判断：
1. 模型输出是否正确回答了用户问题？
2. 与标准答案相比，差距在哪里？

请以JSON格式返回校对结果：
{{
    "is_correct": <true或false，表示回答是否正确>,
    "rate": <1-10的整数评分，10分表示完全正确>,
    "reason": "<简要评价原因，100字以内>"
}}

只返回JSON，不要有其他内容。"""
    
    def __init__(self, eval_client):
        self.client = eval_client
    
    def extract_answer_only(self, content: str) -> str:
        """
        从模型输出中提取纯答案内容，去除 think/分析 部分
        
        支持的格式：
        1. <think>...</think> 格式
        2. <think>...</think> 格式
        3. THINK: ... ANSWER: ... 格式
        4. 思考过程：... 最终答案：... 格式
        
        Args:
            content: 原始模型输出
            
        Returns:
            只包含 answer 部分的字符串
        """
        if not content:
            return ""
        
        original_length = len(content)
        
        # 1. 去除 <think>...</think> 格式
        content = re.sub(
            r'<think>\s*[\s\S]*?\s*</think>',
            '',
            content,
            flags=re.IGNORECASE
        )
        
        # 2. 去除 <think>...</think> 格式
        content = re.sub(
            r'<think>\s*[\s\S]*?\s*</think>',
            '',
            content,
            flags=re.IGNORECASE
        )
        
        # 3. 去除 [[模型分析]]...[[/模型分析]] 格式
        content = re.sub(
            r'\[\[模型分析\]\]\s*[\s\S]*?\s*\[\[/模型分析\]\]',
            '',
            content,
            flags=re.IGNORECASE
        )
        
        # 4. 去除各种 THINK/ANSWER 格式中的 THINK 部分
        think_patterns = [
            # THINK: xxx ANSWER: yyy -> ANSWER: yyy
            r'THINK:\s*[\s\S]*?(?=ANSWER:|$)',
            # 思考: xxx 答案: yyy -> 答案: yyy
            r'思考[：:]\s*[\s\S]*?(?=答案[：:]|最终答案[：:]|答[：:]|回答[：:]|输出[：:]|=|END|$)',
            # 分析: xxx 结论: yyy -> 结论: yyy
            r'分析[：:]\s*[\s\S]*?(?=结论[：:]|答案[：:]|最终答案[：:]|输出[：:])',
            # 推理过程: xxx 最终答案: yyy -> 最终答案: yyy
            r'推理过程[：:]\s*[\s\S]*?(?=最终答案[：:]|答案[：:]|输出[：:])',
            # 推理: xxx 回答: yyy -> 回答: yyy
            r'推理[：:]\s*[\s\S]*?(?=回答[：:]|答案[：:]|最终答案[：:]|输出[：:])',
        ]
        
        for pattern in think_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        
        # 5. 清理多余空白
        content = re.sub(r'\n{3,}', '\n\n', content)  # 3个以上换行改为2个
        content = content.strip()
        
        # 如果提取后内容为空或太短，返回原文
        if not content or len(content) < original_length * 0.1:
            return content if content else ""
        
        return content
    
    async def verify(
        self,
        prompt: str,
        model_output: str,
        golden_answer: str,
        max_tokens: int = 1000,
        strip_think: bool = True,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        校对验证 - 简单的对比验证
        
        Args:
            prompt: 用户原始问题
            model_output: 模型输出内容（待校对）
            golden_answer: 标准答案
            max_tokens: 最大token数
            strip_think: 是否去除 think 内容（默认 True）
            max_retries: 最大重试次数（默认 3 次）
            
        Returns:
            校对结果字典，包含 is_correct, rate, reason
        """
        # 去除 think 内容，只保留 answer
        if strip_think:
            model_output = self.extract_answer_only(model_output)
        
        # 构建校对提示词
        verify_prompt = self.VERIFY_TEMPLATE.format(
            prompt=prompt,
            model_output=model_output,
            golden_answer=golden_answer
        )
        
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # 调用校对模型（使用 temperature=0 确保结果确定性）
                result = await self.client.chat(
                    prompt=verify_prompt,
                    max_tokens=max_tokens,
                    temperature=0,
                    stream=False
                )
                
                content = result.get("content", "")
                
                # 解析校对结果
                parsed_result = self.parse_verify_result(content)
                
                # 检查是否是 JSON 解析失败，如果是则重试
                if "JSON解析失败" in parsed_result.get("reason", "") or \
                   "无法解析校对结果" in parsed_result.get("reason", ""):
                    last_error = parsed_result.get("reason", "")
                    if attempt < max_retries - 1:
                        continue  # 重试
                    else:
                        # 达到最大重试次数，返回最后一次结果
                        return parsed_result
                
                # 解析成功，直接返回
                return parsed_result
                
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries - 1:
                    continue  # 重试
        
        # 所有尝试都失败
        return {
            "is_correct": False,
            "rate": 0,
            "reason": f"校对失败（已重试 {max_retries} 次）: {last_error}",
            "error": last_error
        }
    
    def parse_verify_result(self, content: str) -> Dict[str, Any]:
        """
        解析校对结果
        
        Args:
            content: 校对模型返回的内容
            
        Returns:
            解析后的校对结果字典
        """
        # 尝试提取 JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        
        if not json_match:
            # 无法解析，返回默认结果
            return {
                "is_correct": False,
                "rate": 0,
                "reason": f"无法解析校对结果: {content[:100]}...",
                "raw_content": content
            }
        
        try:
            data = json.loads(json_match.group())
            
            # 提取关键字段，确保类型正确
            is_correct = data.get("is_correct", False)
            if isinstance(is_correct, str):
                is_correct = is_correct.lower() in ("true", "1", "yes")
            
            rate = data.get("rate", 5)
            if isinstance(rate, str):
                try:
                    rate = int(rate)
                except ValueError:
                    rate = 5
            rate = max(1, min(10, rate))  # 确保在 1-10 范围内
            
            reason = data.get("reason", "")
            
            return {
                "is_correct": is_correct,
                "rate": rate,
                "reason": reason,
                "raw_data": data
            }
            
        except json.JSONDecodeError:
            return {
                "is_correct": False,
                "rate": 0,
                "reason": f"JSON解析失败: {content[:100]}...",
                "raw_content": content
            }