#!/usr/bin/env python3
"""
下载通用大模型测试集
- MMLU: 综合知识测试（57个学科）
- GSM8K: 小学数学推理测试
"""

import os
import json
from datasets import load_dataset

def download_mmlu(save_dir):
    """下载MMLU测试集"""
    print("📚 正在下载 MMLU 测试集...")
    try:
        # MMLU测试集
        dataset = load_dataset("cais/mmlu", "all", split="test")
        
        # 转换为适合你的测试框架的格式
        test_cases = []
        for item in dataset:
            test_case = {
                "id": f"mmlu_{item.get('subject', 'unknown')}_{len(test_cases)}",
                "dataset": "MMLU",
                "subject": item.get("subject", "unknown"),
                "question": item.get("question", ""),
                "choices": item.get("choices", []),
                "answer": item.get("answer", 0),
                "category": "综合知识"
            }
            test_cases.append(test_case)
        
        # 保存为JSON
        output_path = os.path.join(save_dir, "mmlu_test.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(test_cases, f, ensure_ascii=False, indent=2)
        
        print(f"✅ MMLU 下载完成！共 {len(test_cases)} 条测试用例")
        print(f"   保存位置: {output_path}")
        
        # 显示样例
        if test_cases:
            print("\n📝 MMLU 样例:")
            sample = test_cases[0]
            print(f"   科目: {sample['subject']}")
            print(f"   问题: {sample['question'][:100]}...")
            print(f"   选项: {sample['choices']}")
            print(f"   答案: {sample['answer']}")
        
    except Exception as e:
        print(f"❌ MMLU 下载失败: {e}")

def download_gsm8k(save_dir):
    """下载GSM8K测试集"""
    print("\n🔢 正在下载 GSM8K 测试集...")
    try:
        # GSM8K测试集
        dataset = load_dataset("openai/gsm8k", "main", split="test")
        
        # 转换为适合你的测试框架的格式
        test_cases = []
        for idx, item in enumerate(dataset):
            test_case = {
                "id": f"gsm8k_{idx}",
                "dataset": "GSM8K",
                "question": item.get("question", ""),
                "answer": item.get("answer", ""),
                "category": "数学推理",
                "difficulty": "小学"
            }
            test_cases.append(test_case)
        
        # 保存为JSON
        output_path = os.path.join(save_dir, "gsm8k_test.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(test_cases, f, ensure_ascii=False, indent=2)
        
        print(f"✅ GSM8K 下载完成！共 {len(test_cases)} 条测试用例")
        print(f"   保存位置: {output_path}")
        
        # 显示样例
        if test_cases:
            print("\n📝 GSM8K 样例:")
            sample = test_cases[0]
            print(f"   问题: {sample['question'][:100]}...")
            print(f"   答案: {sample['answer'][:100]}...")
        
    except Exception as e:
        print(f"❌ GSM8K 下载失败: {e}")

def create_readme(save_dir):
    """创建说明文档"""
    readme_content = """# 通用大模型测试集

本目录包含从 Hugging Face 下载的标准测试集，可用于评估大语言模型的能力。

## 测试集列表

### 1. MMLU (Massive Multitask Language Understanding)
- **用途**: 综合知识测试
- **学科数量**: 57个学科
- **难度范围**: 高中水平到专家级
- **数据量**: ~14,000+ 测试题
- **覆盖领域**: STEM、人文、社会科学等
- **特点**: AI界的"高考卷"，全面考察模型知识广度
- **数据来源**: https://huggingface.co/datasets/cais/mmlu

### 2. GSM8K (Grade School Math 8K)
- **用途**: 数学推理测试
- **数据量**: 8.5K高质量小学数学题
- **难度**: 需要2-8步推理
- **特点**: 考察模型的数学逻辑推理能力
- **数据来源**: https://huggingface.co/datasets/openai/gsm8k

## 使用方法

### 在你的测试框架中使用

```python
import json

# 加载MMLU测试集
with open("mmlu_test.json", "r", encoding="utf-8") as f:
    mmlu_cases = json.load(f)

# 加载GSM8K测试集
with open("gsm8k_test.json", "r", encoding="utf-8") as f:
    gsm8k_cases = json.load(f)

# 使用示例
for test_case in mmlu_cases[:10]:  # 取前10条测试
    print(f"问题: {test_case['question']}")
    print(f"选项: {test_case['choices']}")
    print(f"答案: {test_case['answer']}")
    print("---")
```

## 数据格式

每个测试用例包含以下字段：

### MMLU格式
```json
{
  "id": "mmlu_high_school_physics_0",
  "dataset": "MMLU",
  "subject": "high_school_physics",
  "question": "问题文本",
  "choices": ["选项A", "选项B", "选项C", "选项D"],
  "answer": 0,
  "category": "综合知识"
}
```

### GSM8K格式
```json
{
  "id": "gsm8k_0",
  "dataset": "GSM8K",
  "question": "问题文本",
  "answer": "完整解答过程和答案",
  "category": "数学推理",
  "difficulty": "小学"
}
```

## 其他推荐测试集

如果你需要更多测试集，可以考虑：

- **HumanEval**: 代码生成测试 (https://huggingface.co/datasets/openai/openai-humaneval)
- **MBPP**: 编程能力测试 (https://huggingface.co/datasets/mbpp)
- **C-Eval**: 中文综合测试 (https://huggingface.co/datasets/ceval/ceval-exam)
- **HellaSwag**: 常识推理测试 (https://huggingface.co/datasets/rowan-hellaswag)

## 注意事项

1. **数据版权**: 这些数据集仅用于研究和评估目的
2. **更新频率**: 建议定期检查Hugging Face获取最新版本
3. **评估指标**: 
   - MMLU: 准确率 (Accuracy)
   - GSM8K: 答案匹配率 (Exact Match)

## 下载日期

{download_date}
""".format(download_date=__import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    readme_path = os.path.join(save_dir, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)
    
    print(f"\n📄 README 文档已创建: {readme_path}")

def main():
    # 保存目录
    save_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"📂 下载目录: {save_dir}")
    print("=" * 60)
    
    # 下载测试集
    download_mmlu(save_dir)
    download_gsm8k(save_dir)
    
    # 创建说明文档
    create_readme(save_dir)
    
    print("\n" + "=" * 60)
    print("🎉 所有测试集下载完成！")
    print("\n接下来你可以：")
    print("1. 查看 README.md 了解测试集详情")
    print("2. 在你的测试框架中加载这些JSON文件")
    print("3. 根据需要选择合适的测试集进行评估")

if __name__ == "__main__":
    main()
