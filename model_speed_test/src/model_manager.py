"""
模型管理模块
支持多模型配置、健康检查、分组管理
"""
import json
import os
import uuid
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum


class ModelProvider(Enum):
    """模型提供商"""
    MINIMAX = "minimax"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    CUSTOM = "custom"


class ModelStatus(Enum):
    """模型状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    HEALTH_CHECKING = "health_checking"


@dataclass
class ModelConfig:
    """模型配置"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    provider: str = "minimax"  # minimax, openai, anthropic, local, custom
    endpoint: str = ""
    api_key: str = ""
    model: str = ""
    group: str = "production"  # production, staging, experimental
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    health_check_enabled: bool = True
    status: str = "active"
    last_health_check: str = ""
    health_check_result: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelConfig":
        return cls(**data)


class ModelManager:
    """模型管理器"""
    
    def __init__(self, storage_path: str = "config/models", client_factory=None):
        self.storage_path = storage_path
        self.client_factory = client_factory  # 可选的客户端工厂函数
        self._models: Dict[str, ModelConfig] = {}
        self._load_all()
    
    def _load_all(self):
        """加载所有模型配置"""
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path, exist_ok=True)
            return
        
        filepath = os.path.join(self.storage_path, "models.json")
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            model = ModelConfig.from_dict(item)
                            self._models[model.id] = model
            except Exception as e:
                print(f"加载模型配置失败: {e}")
    
    def _save_all(self):
        """保存所有模型配置"""
        os.makedirs(self.storage_path, exist_ok=True)
        filepath = os.path.join(self.storage_path, "models.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump([m.to_dict() for m in self._models.values()], f, ensure_ascii=False, indent=2)
    
    def add_model(self, model: ModelConfig) -> str:
        """添加模型"""
        model.id = str(uuid.uuid4())
        model.created_at = datetime.now().isoformat()
        model.updated_at = datetime.now().isoformat()
        self._models[model.id] = model
        self._save_all()
        return model.id
    
    def update_model(self, model_id: str, updates: Dict[str, Any]) -> bool:
        """更新模型"""
        if model_id not in self._models:
            return False
        
        model = self._models[model_id]
        for key, value in updates.items():
            if hasattr(model, key):
                setattr(model, key, value)
        
        model.updated_at = datetime.now().isoformat()
        self._save_all()
        return True
    
    def delete_model(self, model_id: str) -> bool:
        """删除模型"""
        if model_id not in self._models:
            return False
        del self._models[model_id]
        self._save_all()
        return True
    
    def get_model(self, model_id: str) -> Optional[ModelConfig]:
        """获取模型"""
        return self._models.get(model_id)
    
    def get_model_by_name(self, name: str) -> Optional[ModelConfig]:
        """通过名称获取模型"""
        for model in self._models.values():
            if model.name == name:
                return model
        return None
    
    def list_models(
        self,
        group: str = None,
        provider: str = None,
        tags: List[str] = None,
        status: str = None
    ) -> List[ModelConfig]:
        """列出模型"""
        results = list(self._models.values())
        
        if group:
            results = [m for m in results if m.group == group]
        if provider:
            results = [m for m in results if m.provider == provider]
        if tags:
            results = [m for m in results if any(t in m.tags for t in tags)]
        if status:
            results = [m for m in results if m.status == status]
        
        return results
    
    def get_models_by_group(self) -> Dict[str, List[ModelConfig]]:
        """按组分类获取模型"""
        result: Dict[str, List[ModelConfig]] = {}
        for model in self._models.values():
            if model.group not in result:
                result[model.group] = []
            result[model.group].append(model)
        return result
    
    async def health_check(self, model_id: str, timeout: float = 10.0) -> Dict[str, Any]:
        """执行健康检查"""
        if model_id not in self._models:
            return {"success": False, "error": "Model not found"}
        
        model = self._models[model_id]
        model.status = "health_checking"
        self._save_all()
        
        result = {
            "model_id": model_id,
            "model_name": model.name,
            "timestamp": datetime.now().isoformat(),
            "success": False,
            "latency_ms": 0,
            "error": None
        }
        
        try:
            # 如果有客户端工厂，尝试创建客户端并测试
            if self.client_factory:
                start_time = asyncio.get_event_loop().time()
                client = self.client_factory(model)
                
                # 发送简单测试请求
                test_result = await asyncio.wait_for(
                    client.chat(
                        prompt="Hello",
                        max_tokens=10,
                        stream=False
                    ),
                    timeout=timeout
                )
                
                end_time = asyncio.get_event_loop().time()
                result["latency_ms"] = round((end_time - start_time) * 1000, 2)
                result["success"] = True
                model.status = "active"
            else:
                # 没有客户端工厂，只检查配置是否有效
                result["success"] = True
                result["note"] = "No client factory, config validation only"
                model.status = "active"
                
        except asyncio.TimeoutError:
            result["error"] = "Health check timeout"
            model.status = "error"
        except Exception as e:
            result["error"] = str(e)
            model.status = "error"
        
        model.last_health_check = result["timestamp"]
        model.health_check_result = result
        self._save_all()
        
        return result
    
    async def health_check_all(self, timeout: float = 10.0) -> Dict[str, Dict[str, Any]]:
        """批量健康检查"""
        results = {}
        
        # 只检查启用了健康检查的模型
        enabled_models = [m for m in self._models.values() if m.health_check_enabled]
        
        for model in enabled_models:
            results[model.id] = await self.health_check(model.id, timeout)
        
        return results
    
    def get_groups(self) -> List[str]:
        """获取所有模型组"""
        return list(set(m.group for m in self._models.values()))
    
    def get_providers(self) -> List[str]:
        """获取所有提供商"""
        return list(set(m.provider for m in self._models.values()))
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self._models)
        by_group = {}
        by_provider = {}
        by_status = {}
        
        for model in self._models.values():
            by_group[model.group] = by_group.get(model.group, 0) + 1
            by_provider[model.provider] = by_provider.get(model.provider, 0) + 1
            by_status[model.status] = by_status.get(model.status, 0) + 1
        
        return {
            "total": total,
            "by_group": by_group,
            "by_provider": by_provider,
            "by_status": by_status
        }


# 默认模型配置
DEFAULT_MODELS = [
    {
        "name": "MiniMax-Text-01",
        "provider": "minimax",
        "model": "MiniMax-Text-01",
        "group": "production",
        "tags": ["text", "fast"]
    },
    {
        "name": "MiniMax-M2.5-HighSpeed",
        "provider": "minimax",
        "model": "MiniMax-M2.5-HighSpeed",
        "group": "production",
        "tags": ["text", "high-speed"]
    },
    {
        "name": "GPT-4",
        "provider": "openai",
        "model": "gpt-4",
        "group": "production",
        "tags": ["text", "high-quality"]
    }
]


def create_model_manager(
    storage_path: str = "config/models",
    client_factory=None
) -> ModelManager:
    """创建模型管理器（带默认配置）"""
    manager = ModelManager(storage_path, client_factory)
    
    # 如果没有模型，创建默认配置
    if not manager._models:
        for config in DEFAULT_MODELS:
            model = ModelConfig(
                name=config["name"],
                provider=config["provider"],
                model=config["model"],
                group=config["group"],
                tags=config.get("tags", [])
            )
            manager.add_model(model)
    
    return manager