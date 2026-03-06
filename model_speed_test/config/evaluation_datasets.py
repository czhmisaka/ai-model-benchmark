"""
评估数据集管理
支持内置数据集和自定义数据集
"""
import json
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DatasetItem:
    """数据集条目"""
    id: str
    prompt: str
    golden_answer: str = ""
    category: str = ""
    difficulty: str = "medium"  # easy, medium, hard
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationDataset:
    """评估数据集"""
    id: str
    name: str
    description: str = ""
    version: str = "1.0"
    items: List[DatasetItem] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


# 内置评估数据集
BUILTIN_DATASETS = {
    "general_qa": {
        "name": "通用问答",
        "description": "通用知识问答数据集",
        "items": [
            {
                "id": "qa_001",
                "prompt": "什么是人工智能？",
                "golden_answer": "人工智能（Artificial Intelligence，AI）是计算机科学的一个分支，致力于开发能够执行通常需要人类智能的任务的系统，包括视觉感知、语音识别、决策制定和语言翻译等。",
                "category": "基础知识",
                "difficulty": "easy",
                "tags": ["AI", "基础概念"]
            },
            {
                "id": "qa_002",
                "prompt": "请解释什么是机器学习。",
                "golden_answer": "机器学习是人工智能的一个子领域，专注于开发能够从数据中学习和改进的算法。它包括监督学习、无监督学习和强化学习等多种方法。",
                "category": "技术概念",
                "difficulty": "easy",
                "tags": ["ML", "机器学习"]
            },
            {
                "id": "qa_003",
                "prompt": "深度学习和机器学习有什么区别？",
                "golden_answer": "深度学习是机器学习的一个分支，使用多层神经网络（深度神经网络）来学习数据的层次化表示。机器学习范围更广，包括决策树、支持向量机等多种算法。",
                "category": "技术对比",
                "difficulty": "medium",
                "tags": ["DL", "对比"]
            }
        ]
    },
    "knowledge_graph": {
        "name": "知识图谱",
        "description": "知识图谱构建相关数据集",
        "items": [
            {
                "id": "kg_001",
                "prompt": "从以下文本中抽取知识图谱：苹果公司是一家美国科技公司，总部位于加利福尼亚州库比蒂诺，由史蒂夫·乔布斯、史蒂夫·沃兹尼亚克和罗恩·韦恩于1976年4月1日创立。",
                "golden_answer": '{"subject": "苹果公司", "relation": "类型", "object": "科技公司"}\n{"subject": "苹果公司", "relation": "总部位于", "object": "加利福尼亚州库比蒂诺"}\n{"subject": "苹果公司", "relation": "创立时间", "object": "1976年4月1日"}\n{"subject": "史蒂夫·乔布斯", "relation": "职位", "object": "创始人"}\n{"subject": "史蒂夫·沃兹尼亚克", "relation": "职位", "object": "创始人"}\n{"subject": "罗恩·韦恩", "relation": "职位", "object": "创始人"}',
                "category": "实体抽取",
                "difficulty": "medium",
                "tags": ["知识图谱", "三元组"]
            },
            {
                "id": "kg_002",
                "prompt": "从以下文本抽取本体结构：张学友是香港著名歌手，被誉为歌神。他演唱了《吻别》、《祝你一路顺风》等经典歌曲。",
                "golden_answer": '{"entity_types": ["人物", "作品", "奖项"], "relation_types": ["演唱", "荣获", "属于"], "properties": {"人物": ["姓名", "国籍", "职业"], "作品": ["歌名", "发行年份"]}}',
                "category": "本体构建",
                "difficulty": "hard",
                "tags": ["本体", "知识图谱"]
            }
        ]
    },
    "ontology_generation": {
        "name": "本体生成",
        "description": "本体结构生成任务数据集",
        "items": [
            {
                "id": "onto_001",
                "prompt": "为以下领域生成知识图谱本体结构：电子商务领域，包括用户、商品、订单、支付、物流等核心实体。",
                "golden_answer": '{"entity_types": ["用户", "商品", "订单", "支付", "物流", "商家", "评价"], "relation_types": ["下单", "支付", "配送", "包含", "评价", "属于", "浏览"], "properties": {"用户": ["user_id", "name", "email", "phone"], "商品": ["product_id", "name", "price", "category", "stock"], "订单": ["order_id", "user_id", "total_amount", "status", "create_time"]}}',
                "category": "本体设计",
                "difficulty": "medium",
                "tags": ["本体", "电商"]
            }
        ]
    },
    "text_summary": {
        "name": "文本摘要",
        "description": "文本摘要生成数据集",
        "items": [
            {
                "id": "sum_001",
                "prompt": "为以下文本生成不超过50字的摘要：人工智能正在改变我们的生活方式。从智能家居到自动驾驶，从医疗诊断到金融投资，AI技术的应用越来越广泛。它不仅提高了效率，还创造了新的就业机会和商业模式。",
                "golden_answer": "AI正改变生活，应用于智能家居、自动驾驶、医疗、金融等领域，提高效率并创造新机会。",
                "category": "摘要",
                "difficulty": "easy",
                "tags": ["摘要", "压缩"]
            },
            {
                "id": "sum_002",
                "prompt": "生成摘要：量子计算是一种基于量子力学原理的计算方式。与传统计算机使用比特不同，量子计算机使用量子比特，可以处于多个状态的叠加。量子计算在密码学、药物研发、优化问题等领域有巨大潜力。",
                "golden_answer": "量子计算基于量子力学，使用量子比特可处于多状态叠加，在密码学、药物研发、优化等领域有巨大潜力。",
                "category": "技术摘要",
                "difficulty": "medium",
                "tags": ["摘要", "科技"]
            }
        ]
    },
    "code_generation": {
        "name": "代码生成",
        "description": "代码生成任务数据集",
        "items": [
            {
                "id": "code_001",
                "prompt": "用Python写一个函数，计算斐波那契数列第n项。",
                "golden_answer": "def fibonacci(n):\n    if n <= 0:\n        return 0\n    elif n == 1:\n        return 1\n    else:\n        a, b = 0, 1\n        for _ in range(2, n + 1):\n            a, b = b, a + b\n        return b",
                "category": "算法",
                "difficulty": "easy",
                "tags": ["Python", "算法"]
            },
            {
                "id": "code_002",
                "prompt": "用Python实现快速排序算法。",
                "golden_answer": "def quicksort(arr):\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + middle + quicksort(right)",
                "category": "算法",
                "difficulty": "medium",
                "tags": ["Python", "排序"]
            }
        ]
    },
    "reasoning": {
        "name": "推理能力",
        "description": "逻辑推理和数学推理数据集",
        "items": [
            {
                "id": "reason_001",
                "prompt": "小明比小红高，小红比小华高。请问谁最高？",
                "golden_answer": "小明最高。因为小明 > 小红 > 小华，所以小明的身高最高。",
                "category": "逻辑推理",
                "difficulty": "easy",
                "tags": ["推理", "比较"]
            },
            {
                "id": "reason_002",
                "prompt": "如果有以下条件：(1) 所有A是B；(2) 所有B是C；(3) 有些C是D。请问能否得出"有些A是D"的结论？",
                "golden_answer": "不能得出"有些A是D"的结论。从(1)(2)可以推出所有A是C，但无法确定A和D之间是否有交集。因此"有些A是D"不是必然结论。",
                "category": "演绎推理",
                "difficulty": "hard",
                "tags": ["逻辑", "演绎"]
            }
        ]
    },
    "format_check": {
        "name": "格式规范性",
        "description": "格式输出规范性检测数据集",
        "items": [
            {
                "id": "format_001",
                "prompt": "以JSON格式返回用户信息：name=张三, age=30, city=北京",
                "golden_answer": '{"name": "张三", "age": 30, "city": "北京"}',
                "category": "JSON",
                "difficulty": "easy",
                "tags": ["格式", "JSON"]
            },
            {
                "id": "format_002",
                "prompt": "将以下信息以CSV格式返回：姓名,年龄,城市\\n张三,30,北京\\n李四,25,上海",
                "golden_answer": "姓名,年龄,城市\n张三,30,北京\n李四,25,上海",
                "category": "CSV",
                "difficulty": "easy",
                "tags": ["格式", "CSV"]
            },
            {
                "id": "format_003",
                "prompt": "以Markdown表格格式呈现：| 项目 | 数量 | 价格 |\\n| ------ | ------ | ------ |\\n| A | 10 | 100 |\\n| B | 20 | 200 |",
                "golden_answer": "| 项目 | 数量 | 价格 |\n| ------ | ------ | ------ |\n| A | 10 | 100 |\n| B | 20 | 200 |",
                "category": "Markdown",
                "difficulty": "easy",
                "tags": ["格式", "Markdown"]
            }
        ]
    }
}


class DatasetManager:
    """数据集管理器"""
    
    def __init__(self, storage_path: str = "config/datasets"):
        self.storage_path = storage_path
        self._datasets: Dict[str, EvaluationDataset] = {}
        self._load_builtin()
        self._load_custom()
    
    def _load_builtin(self):
        """加载内置数据集"""
        for dataset_id, dataset_config in BUILTIN_DATASETS.items():
            items = []
            for item_config in dataset_config.get("items", []):
                item = DatasetItem(
                    id=item_config["id"],
                    prompt=item_config["prompt"],
                    golden_answer=item_config.get("golden_answer", ""),
                    category=item_config.get("category", ""),
                    difficulty=item_config.get("difficulty", "medium"),
                    tags=item_config.get("tags", [])
                )
                items.append(item)
            
            dataset = EvaluationDataset(
                id=dataset_id,
                name=dataset_config["name"],
                description=dataset_config.get("description", ""),
                items=items
            )
            self._datasets[dataset_id] = dataset
    
    def _load_custom(self):
        """加载自定义数据集"""
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path, exist_ok=True)
            return
        
        for filename in os.listdir(self.storage_path):
            if filename.endswith('.json'):
                filepath = os.path.join(self.storage_path, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        dataset = EvaluationDataset(
                            id=data.get("id", filename[:-5]),
                            name=data.get("name", filename),
                            description=data.get("description", ""),
                            items=[
                                DatasetItem(**item) for item in data.get("items", [])
                            ]
                        )
                        self._datasets[dataset.id] = dataset
                except Exception as e:
                    print(f"加载数据集失败 {filename}: {e}")
    
    def _save_custom(self, dataset: EvaluationDataset):
        """保存自定义数据集"""
        os.makedirs(self.storage_path, exist_ok=True)
        filepath = os.path.join(self.storage_path, f"{dataset.id}.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                "id": dataset.id,
                "name": dataset.name,
                "description": dataset.description,
                "items": [item.__dict__ for item in dataset.items]
            }, f, ensure_ascii=False, indent=2)
    
    def get_dataset(self, dataset_id: str) -> Optional[EvaluationDataset]:
        """获取数据集"""
        return self._datasets.get(dataset_id)
    
    def list_datasets(self) -> List[EvaluationDataset]:
        """列出所有数据集"""
        return list(self._datasets.values())
    
    def get_items(
        self,
        dataset_id: str,
        category: str = None,
        difficulty: str = None,
        tags: List[str] = None,
        limit: int = None
    ) -> List[DatasetItem]:
        """获取数据集条目"""
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return []
        
        items = dataset.items
        
        if category:
            items = [i for i in items if i.category == category]
        if difficulty:
            items = [i for i in items if i.difficulty == difficulty]
        if tags:
            items = [i for i in items if any(t in i.tags for t in tags)]
        
        if limit:
            items = items[:limit]
        
        return items
    
    def add_dataset(self, dataset: EvaluationDataset, custom: bool = True) -> str:
        """添加数据集"""
        self._datasets[dataset.id] = dataset
        
        if custom:
            self._save_custom(dataset)
        
        return dataset.id
    
    def add_item(self, dataset_id: str, item: DatasetItem) -> bool:
        """添加数据集条目"""
        if dataset_id not in self._datasets:
            return False
        
        dataset = self._datasets[dataset_id]
        dataset.items.append(item)
        dataset.updated_at = datetime.now().isoformat()
        
        # 如果是内置数据集，保存为自定义
        if dataset_id in BUILTIN_DATASETS:
            self._save_custom(dataset)
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_items = sum(len(d.items) for d in self._datasets.values())
        categories = set()
        difficulties = {"easy": 0, "medium": 0, "hard": 0}
        
        for dataset in self._datasets.values():
            for item in dataset.items:
                if item.category:
                    categories.add(item.category)
                if item.difficulty in difficulties:
                    difficulties[item.difficulty] += 1
        
        return {
            "dataset_count": len(self._datasets),
            "total_items": total_items,
            "categories": list(categories),
            "difficulties": difficulties
        }


def create_dataset_manager(storage_path: str = "config/datasets") -> DatasetManager:
    """创建数据集管理器"""
    return DatasetManager(storage_path)