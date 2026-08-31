# -*- coding: utf-8 -*-
"""生成标准大海捞针题库：规模梯度 × 针位置梯度"""
import json
import sqlite3
import sys
from pathlib import Path

conn = sqlite3.connect('results/config.db')
conn.row_factory = sqlite3.Row

# 取 600k 原文档作为填充材料
r = conn.execute("SELECT messages FROM test_cases WHERE case_id='tc_1779269942187'").fetchone()
msgs = json.loads(r['messages'])
full_doc = str(msgs[0]['content'])
question_orig = str(msgs[1]['content'])
print(f'base doc: {len(full_doc)} chars')

# ===== 针的定义（虚拟公司/事实，与原文不冲突，AI 校对可判）=====
# 每根针是一个具体数据事实，嵌进文档后提问
NEEDLES = [
    {
        'key': '量子猫',
        'sentence': '特别备注：量子猫科技有限公司在2025年第四季度的海外营收占比达到了42.7%，创下历史新高。',
        'question': '量子猫科技有限公司在2025年第四季度的海外营收占比是多少？只需要告诉我百分比。',
        'answer': '42.7%',
    },
    {
        'key': '深蓝基金',
        'sentence': '特别记录：深蓝资本旗下的深蓝基金在2025年上半年的最大回撤控制在7.3%以内，在同类别产品中表现最优。',
        'question': '深蓝基金2025年上半年的最大回撤控制在了多少以内？只需要告诉我百分比。',
        'answer': '7.3%',
    },
    {
        'key': '星河电池',
        'sentence': '行业动态：星河新能源的固态电池能量密度达到每公斤412瓦时，预计2026年第二季度量产。',
        'question': '星河新能源的固态电池能量密度是多少（每公斤多少瓦时）？只需要告诉我数字。',
        'answer': '412瓦时',
    },
    {
        'key': '临江数据',
        'sentence': '补充披露：临江数据中心2025年的PUE（能耗效率）降到了1.13，处于行业领先水平。',
        'question': '临江数据中心2025年的PUE能耗效率降到了多少？只需要告诉我数字。',
        'answer': '1.13',
    },
]

# ===== 规模与位置矩阵 =====
SIZES = [
    ('32k', 32000),
    ('64k', 64000),
    ('128k', 128000),
    ('200k', 200000),
    ('400k', 400000),
]
POSITIONS = [
    ('head', 0.10),   # 开头 10%
    ('mid', 0.50),    # 中间 50%
    ('tail', 0.90),   # 末尾 90%
]

def build_doc(size_chars, needle_sentence, needle_ratio):
    """从原文档取 size_chars 长度的填充文本，在指定比例位置注入针句子"""
    target = size_chars - len(needle_sentence) - 20
    # 循环取原文（跳过已有干扰数据段落开头）填充
    filler_parts = []
    total = 0
    while total < target:
        take = min(60000, target - total)
        filler_parts.append(full_doc[:take])
        total += take
    filler = ''.join(filler_parts)
    # 注入针
    pos = int(len(filler) * needle_ratio)
    # 避免切断句子：从 pos 向后找最近的 \n 或段落边界
    nl = filler.find('\n', pos)
    if nl < 0 or nl > pos + 500:
        nl = pos
    doc = filler[:nl] + '\n' + needle_sentence + '\n' + filler[nl:]
    return doc

new_cases = []
seq = 0
for size_label, size_chars in SIZES:
    needle = NEEDLES[SIZES.index((size_label, size_chars)) % len(NEEDLES)]  # 每个规模用不同的针（不同答案）
    for pos_label, ratio in POSITIONS:
        seq += 1
        doc = build_doc(size_chars, needle['sentence'], ratio)
        case_id = f"needle_{size_label}_{pos_label}"
        # expected_output 带位置信息和答案
        expected = f"标准答案: {needle['answer']}\n评分点：1) 准确提取出 {needle['answer']}；2) 未编造其他数字。针位于文档 {pos_label}（{int(ratio*100)}% 处），文档规模 {size_label} 字符。"
        new_cases.append({
            "case_id": case_id,
            "name": f"大海捞针 {size_label} · 针在{ {'head':'开头','mid':'中间','tail':'末尾'}[pos_label] }",
            "type": "needle_in_haystack",
            "description": f"长上下文检索 · 文档{size_label}字符 · 针位于文档{ {'head':'开头10%','mid':'中间50%','tail':'末尾90%'}[pos_label] }",
            "tags": ["长上下文", "大海捞针", size_label, pos_label],
            "version": "1.0",
            "max_tokens": 2048,
            "temperature": 0.3,
            "stream": True,
            "system_prompt": "",
            "messages": [
                {"role": "user", "content": doc},
                {"role": "user", "content": needle['question']},
            ],
            "expected_output_type": "text",
            "expected_output": expected,
            "enabled": True,
            "metadata": {
                "source": "needle-in-haystack-standard",
                "dimension": "long_context",
                "difficulty": "hard" if size_chars >= 128000 else "medium",
                "doc_chars": len(doc),
                "needle_position": pos_label,
                "needle_ratio": ratio,
                "needle_answer": needle['answer'],
            },
        })
        print(f'{case_id}: doc={len(doc)} chars, needle@{int(ratio*100)}%')

# 写入题库 JSON（独立文件）
out = {
    'meta': {
        'version': '1.0.0',
        'count': len(new_cases),
        'type': 'needle_in_haystack',
        'sizes': [s for s, _ in SIZES],
        'positions': [p for p, _ in POSITIONS],
        'generatedAt': '2026-08-25',
        'note': '标准大海捞针评测：规模梯度 x 针位置梯度；答案为注入的虚拟事实，AI 校对可直接判分'
    },
    'cases': new_cases,
}
with open('config/needle_benchmark.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f'\nwritten: {len(new_cases)} cases -> config/needle_benchmark.json')
