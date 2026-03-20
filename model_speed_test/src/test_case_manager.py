"""
测试用例管理模块
支持用例分组、版本管理、模板变量替换
"""
import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
import re


@dataclass
class TestCase:
    """测试用例"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    type: str = "general"  # ontology_generation, graph_construction, general, etc.
    tags: List[str] = field(default_factory=list)
    version: str = "1.0"
    prompt_template: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)
    expected_output_type: str = "text"  # text, json, jsonl
    # 标准答案相关
    expected_output: str = ""  # 标准答案（可选）
    eval_model: str = ""  # 校对模型名称（可选，留空则使用被测模型）
    metadata: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestCase":
        """从字典创建"""
        return cls(**data)
    
    def render_prompt(self, **kwargs) -> str:
        """渲染提示词模板"""
        prompt = self.prompt_template
        # 合并变量
        vars = {**self.variables, **kwargs}
        # 替换模板变量
        for key, value in vars.items():
            prompt = prompt.replace(f"{{{key}}}", str(value))
        return prompt


@dataclass
class TestCaseVersion:
    """测试用例版本"""
    version: str
    prompt_template: str
    created_at: str
    changelog: str = ""


class TestCaseManager:
    """测试用例管理器"""
    
    def __init__(self, storage_path: str = "config/test_cases"):
        self.storage_path = storage_path
        self._cases: Dict[str, TestCase] = {}
        self._versions: Dict[str, List[TestCaseVersion]] = {}
        self._load_all()
    
    def _load_all(self):
        """加载所有测试用例"""
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path, exist_ok=True)
            return
        
        for filename in os.listdir(self.storage_path):
            if filename.endswith('.json'):
                filepath = os.path.join(self.storage_path, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            for item in data:
                                case = TestCase.from_dict(item)
                                self._cases[case.id] = case
                        elif isinstance(data, dict):
                            case = TestCase.from_dict(data)
                            self._cases[case.id] = case
                except Exception as e:
                    print(f"加载测试用例失败 {filename}: {e}")
    
    def _save_all(self):
        """保存所有测试用例"""
        os.makedirs(self.storage_path, exist_ok=True)
        
        # 按类型分组保存
        cases_by_type: Dict[str, List[TestCase]] = {}
        for case in self._cases.values():
            if case.type not in cases_by_type:
                cases_by_type[case.type] = []
            cases_by_type[case.type].append(case)
        
        for type_name, cases in cases_by_type.items():
            filepath = os.path.join(self.storage_path, f"{type_name}.json")
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump([c.to_dict() for c in cases], f, ensure_ascii=False, indent=2)
    
    def add_case(self, case: TestCase) -> str:
        """添加测试用例"""
        case.id = str(uuid.uuid4())
        case.created_at = datetime.now().isoformat()
        case.updated_at = datetime.now().isoformat()
        self._cases[case.id] = case
        self._save_all()
        return case.id
    
    def update_case(self, case_id: str, updates: Dict[str, Any]) -> bool:
        """更新测试用例"""
        if case_id not in self._cases:
            return False
        
        case = self._cases[case_id]
        
        # 保存版本历史
        if "prompt_template" in updates and updates["prompt_template"] != case.prompt_template:
            self._save_version(case_id, case.prompt_template)
        
        # 更新字段
        for key, value in updates.items():
            if hasattr(case, key):
                setattr(case, key, value)
        
        case.updated_at = datetime.now().isoformat()
        self._save_all()
        return True
    
    def _save_version(self, case_id: str, prompt_template: str):
        """保存版本历史"""
        if case_id not in self._versions:
            self._versions[case_id] = []
        
        case = self._cases[case_id]
        version = TestCaseVersion(
            version=case.version,
            prompt_template=prompt_template,
            created_at=datetime.now().isoformat()
        )
        self._versions[case_id].append(version)
    
    def get_case(self, case_id: str) -> Optional[TestCase]:
        """获取测试用例"""
        return self._cases.get(case_id)
    
    def delete_case(self, case_id: str) -> bool:
        """删除测试用例"""
        if case_id not in self._cases:
            return False
        del self._cases[case_id]
        self._save_all()
        return True
    
    def list_cases(
        self,
        type_filter: str = None,
        tags: List[str] = None,
        enabled_only: bool = False
    ) -> List[TestCase]:
        """列出测试用例"""
        results = list(self._cases.values())
        
        if type_filter:
            results = [c for c in results if c.type == type_filter]
        
        if tags:
            results = [c for c in results if any(t in c.tags for t in tags)]
        
        if enabled_only:
            results = [c for c in results if c.enabled]
        
        return results
    
    def get_cases_by_type(self) -> Dict[str, List[TestCase]]:
        """按类型分组获取用例"""
        result: Dict[str, List[TestCase]] = {}
        for case in self._cases.values():
            if case.type not in result:
                result[case.type] = []
            result[case.type].append(case)
        return result
    
    def get_versions(self, case_id: str) -> List[TestCaseVersion]:
        """获取版本历史"""
        return self._versions.get(case_id, [])
    
    def import_cases(self, filepath: str) -> int:
        """批量导入测试用例"""
        count = 0
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    case = TestCase.from_dict(item)
                    case.id = str(uuid.uuid4())
                    case.created_at = datetime.now().isoformat()
                    case.updated_at = datetime.now().isoformat()
                    self._cases[case.id] = case
                    count += 1
            elif isinstance(data, dict):
                case = TestCase.from_dict(data)
                case.id = str(uuid.uuid4())
                self._cases[case.id] = case
                count = 1
        
        self._save_all()
        return count
    
    def export_cases(self, filepath: str, case_ids: List[str] = None) -> int:
        """导出测试用例"""
        cases = self._cases.values() if case_ids is None else [
            self._cases[i] for i in case_ids if i in self._cases
        ]
        
        data = [c.to_dict() for c in cases]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return len(data)
    
    def render_prompt(self, case_id: str, **kwargs) -> Optional[str]:
        """渲染提示词"""
        case = self._cases.get(case_id)
        if not case:
            return None
        return case.render_prompt(**kwargs)


# 预定义测试用例模板
DEFAULT_TEMPLATES = {
    "general": {
        "name": "通用问答",
        "type": "general",
        "prompt_template": "{question}",
        "expected_output_type": "text"
    },
    "ontology_generation": {
        "name": "本体生成",
        "type": "ontology_generation",
        "prompt_template": """请根据以下文本生成知识图谱本体结构：

文本内容：
{content}

请以JSON格式返回本体结构，包含：
1. 实体类型（entity_types）
2. 关系类型（relation_types）
3. 属性（properties）""",
        "expected_output_type": "json"
    },
    "graph_construction": {
        "name": "图谱构建",
        "type": "graph_construction",
        "prompt_template": """请从以下文本中抽取知识图谱：

文本内容：
{content}

请以JSONL格式返回三元组，每行一个三元组：
{"subject": "...", "relation": "...", "object": "..."}""",
        "expected_output_type": "jsonl"
    },
    "summary": {
        "name": "文本摘要",
        "type": "summary",
        "prompt_template": """请为以下文本生成简洁摘要：

{content}

要求：
1. 不超过{max_tokens}字
2. 保留核心信息
3. 语言简洁""",
        "expected_output_type": "text"
    },
    "translation": {
        "name": "文本翻译",
        "type": "translation",
        "prompt_template": """请将以下文本翻译成{target_language}：

{content}""",
        "expected_output_type": "text"
    }
}


def create_test_case_manager(storage_path: str = "config/test_cases") -> TestCaseManager:
    """创建测试用例管理器（带默认模板）"""
    manager = TestCaseManager(storage_path)
    
    # 如果没有用例，创建默认模板
    if not manager._cases:
        for key, template in DEFAULT_TEMPLATES.items():
            case = TestCase(
                name=template["name"],
                type=template["type"],
                prompt_template=template["prompt_template"],
                expected_output_type=template.get("expected_output_type", "text"),
                tags=[key]
            )
            manager.add_case(case)
    
    return manager