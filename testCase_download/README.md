# 通用大模型测试集

本目录包含从 Hugging Face 下载的标准测试集，可用于评估大语言模型的能力。

## ✅ 已下载的测试集

### 1. GSM8K (Grade School Math 8K) ✅
- **状态**: 已完成下载
- **用途**: 数学推理测试
- **数据量**: 1,319 条测试题
- **文件大小**: 892 KB
- **难度**: 小学级数学，需要2-8步推理
- **特点**: 考察模型的数学逻辑推理能力，答案包含完整解题过程
- **数据来源**: https://huggingface.co/datasets/openai/gsm8k

### 2. MMLU (Massive Multitask Language Understanding) ⏳
- **状态**: 正在下载中（后台运行）
- **用途**: 综合知识测试
- **学科数量**: 57个学科
- **难度范围**: 高中水平到专家级
- **数据量**: ~14,000+ 测试题
- **覆盖领域**: STEM、人文、社会科学等
- **特点**: AI界的"高考卷"，全面考察模型知识广度
- **数据来源**: https://huggingface.co/datasets/cais/mmlu

## 数据格式

### GSM8K格式
```json
{
  "id": "gsm8k_0",
  "dataset": "GSM8K",
  "question": "Janet's ducks lay 16 eggs per day...",
  "answer": "Janet sells 16 - 3 - 4 = <<16-3-4=9>>9 duck eggs...",
  "category": "数学推理",
  "difficulty": "小学"
}
```

## 使用方法

### 在你的测试框架中使用

```python
import json

# 加载GSM8K测试集
with open("gsm8k_test.json", "r", encoding="utf-8") as f:
    gsm8k_cases = json.load(f)

# 使用示例
for test_case in gsm8k_cases[:10]:  # 取前10条测试
    print(f"问题: {test_case['question']}")
    print(f"答案: {test_case['answer']}")
    print("---")
```

## 测试用例示例

### GSM8K 示例 1 - 日常生活问题
**问题**: Janet's ducks lay 16 eggs per day. She eats three for breakfast every morning and bakes muffins for her friends every day with four. She sells the remainder at the farmers' market daily for $2 per fresh duck egg. How much in dollars does she make every day at the farmers' market?

**答案**: 
Janet sells 16 - 3 - 4 = <<16-3-4=9>>9 duck eggs a day.
She makes 9 * 2 = $<<9*2=18>>18 every day at the farmer's market.
#### 18

### GSM8K 示例 2 - 简单计算
**问题**: A robe takes 2 bolts of blue fiber and half that much white fiber. How many bolts in total does it take?

**答案**:
It takes 2/2=<<2/2=1>>1 bolt of white fiber
So the total amount of fabric is 2+1=<<2+1=3>>3 bolts of fabric
#### 3

## 其他推荐测试集

如果你需要更多测试集，可以考虑：

- **HumanEval**: 代码生成测试 (https://huggingface.co/datasets/openai/openai-humaneval)
  - 164道编程题，评估Python代码正确性
  
- **MBPP**: 编程能力测试 (https://huggingface.co/datasets/mbpp)
  - Python函数级代码生成测试
  
- **C-Eval**: 中文综合测试 (https://huggingface.co/datasets/ceval/ceval-exam)
  - 覆盖多个学科的中文选择题
  
- **HellaSwag**: 常识推理测试 (https://huggingface.co/datasets/rowan-hellaswag)
  - 日常逻辑与情境判断

## 评估指标

### GSM8K
- **主要指标**: Exact Match (答案匹配率)
- **计算方式**: 模型输出的答案与标准答案的匹配程度
- **特殊格式**: 答案以 `####` 结尾，后面是最终数值

### MMLU（待下载完成）
- **主要指标**: Accuracy (准确率)
- **计算方式**: 选择题正确率

## 下载脚本说明

### download_benchmarks.py
完整的下载脚本，可以同时下载MMLU和GSM8K。

### download_gsm8k_only.py
快速下载脚本，只下载GSM8K（推荐先使用这个，数据量小速度快）。

## 注意事项

1. **数据版权**: 这些数据集仅用于研究和评估目的
2. **更新频率**: 建议定期检查Hugging Face获取最新版本
3. **网络要求**: 下载需要访问Hugging Face，国内可能需要代理
4. **存储空间**: MMLU数据集较大（约50MB），确保有足够存储空间

## 文件列表

```
testCase_download/
├── README.md                          # 本说明文档
├── download_benchmarks.py            # 完整下载脚本（包含MMLU）
├── download_gsm8k_only.py            # GSM8K快速下载脚本
└── gsm8k_test.json                   # GSM8K测试集（已下载）
    └── mmlu_test.json                 # MMLU测试集（下载中...）
```

## 下载日期

- GSM8K: 2026-05-25 09:28
- MMLU: 2026-05-25 09:23 (后台下载中)

## 下一步

1. ✅ GSM8K测试集已可用
2. ⏳ 等待MMLU下载完成
3. 📝 在你的测试框架中加载这些JSON文件
4. 🎯 开始模型评估测试

---

**祝你测试顺利！** 🚀
