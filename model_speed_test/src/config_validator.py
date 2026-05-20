"""
模型配置验证模块
验证模型配置的完整性和正确性
"""
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """验证结果"""
    valid: bool
    errors: List[str]
    warnings: List[str]
    
    def __str__(self):
        parts = []
        if self.errors:
            parts.append(f"❌ Errors: {len(self.errors)}")
            for e in self.errors:
                parts.append(f"   - {e}")
        if self.warnings:
            parts.append(f"⚠️  Warnings: {len(self.warnings)}")
            for w in self.warnings:
                parts.append(f"   - {w}")
        if self.valid and not self.warnings:
            parts.append("✅ 配置验证通过")
        return "\n".join(parts)


def validate_model_config(config: Dict[str, Any]) -> ValidationResult:
    """
    验证单个模型配置
    
    Args:
        config: 模型配置字典
        
    Returns:
        ValidationResult: 验证结果
    """
    errors = []
    warnings = []
    
    # 必填字段检查
    required_fields = ['name', 'endpoint', 'model']
    for field in required_fields:
        if not config.get(field):
            errors.append(f"缺少必填字段: {field}")
    
    # Endpoint 格式检查
    endpoint = config.get('endpoint', '')
    if endpoint:
        if not endpoint.startswith(('http://', 'https://')):
            errors.append(f"Endpoint 格式错误，必须以 http:// 或 https:// 开头: {endpoint}")
    
    # Provider 检查
    provider = config.get('provider', '')
    if provider:
        from .providers import get_provider_registry
        registry = get_provider_registry()
        if not registry.get(provider):
            warnings.append(f"Provider '{provider}' 可能未注册，已回退到默认处理")
    
    # API Key 检查（某些 provider 不需要）
    api_key = config.get('api_key', '')
    requires_api_key = provider not in ('lmstudio', 'ollama', 'local')
    
    if requires_api_key and not api_key:
        warnings.append(f"API Key 为空，Provider '{provider}' 可能需要 API Key")
    
    # 数值参数范围检查
    temperature = config.get('temperature')
    if temperature is not None:
        if not (0 <= temperature <= 2):
            errors.append(f"Temperature 值必须在 0-2 之间，当前值: {temperature}")
    
    top_p = config.get('top_p')
    if top_p is not None:
        if not (0 <= top_p <= 1):
            errors.append(f"Top-P 值必须在 0-1 之间，当前值: {top_p}")
    
    max_tokens = config.get('max_tokens')
    if max_tokens is not None:
        if max_tokens <= 0:
            errors.append(f"Max Tokens 必须大于 0，当前值: {max_tokens}")
    
    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings
    )


def validate_all_models_from_db(db_path: str) -> Dict[str, ValidationResult]:
    """
    从数据库验证所有启用的模型配置
    
    Args:
        db_path: 数据库路径
        
    Returns:
        Dict[str, ValidationResult]: 模型名称 -> 验证结果
    """
    import sqlite3
    
    results = {}
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT name, provider, endpoint, api_key, model,
               temperature, top_p, max_tokens
        FROM models
        WHERE enabled = 1
    """)
    
    for row in cursor.fetchall():
        config = {
            'name': row['name'],
            'provider': row['provider'],
            'endpoint': row['endpoint'],
            'api_key': row['api_key'],
            'model': row['model'],
            'temperature': row['temperature'],
            'top_p': row['top_p'],
            'max_tokens': row['max_tokens'],
        }
        result = validate_model_config(config)
        results[row['name']] = result
    
    conn.close()
    return results


def print_validation_report(results: Dict[str, ValidationResult]):
    """打印验证报告"""
    print("\n" + "="*60)
    print("模型配置验证报告")
    print("="*60)
    
    valid_count = sum(1 for r in results.values() if r.valid)
    error_count = sum(1 for r in results.values() if r.errors)
    warning_count = sum(1 for r in results.values() if r.warnings)
    
    print(f"\n总计: {len(results)} 个模型")
    print(f"  ✅ 有效: {valid_count}")
    print(f"  ❌ 有错误: {error_count}")
    print(f"  ⚠️  有警告: {warning_count}")
    
    # 打印有问题的模型
    for name, result in results.items():
        if not result.valid or result.warnings:
            print(f"\n【{name}】")
            print(result)


if __name__ == "__main__":
    # 测试验证功能
    db_path = "results/config.db"
    results = validate_all_models_from_db(db_path)
    print_validation_report(results)
