#!/usr/bin/env python3
"""
快速下载 GSM8K 测试集（更小更快）
"""

import os
import json
from datasets import load_dataset

def download_gsm8k(save_dir):
    """下载GSM8K测试集"""
    print("🔢 正在下载 GSM8K 测试集...")
    print("   (这个数据集比较小，下载会很快)")
    
    try:
        # GSM8K测试集 - 只下载test部分
        print("   正在从Hugging Face获取数据...")
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
        
        print(f"\n✅ GSM8K 下载完成！")
        print(f"   测试用例数量: {len(test_cases)} 条")
        print(f"   保存位置: {output_path}")
        
        # 显示样例
        if test_cases:
            print("\n📝 GSM8K 样例:")
            sample = test_cases[0]
            print(f"   问题: {sample['question']}")
            print(f"   答案: {sample['answer'][:200]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ GSM8K 下载失败: {e}")
        return False

def main():
    # 保存目录
    save_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"📂 保存目录: {save_dir}")
    print("=" * 60)
    
    # 下载GSM8K
    success = download_gsm8k(save_dir)
    
    if success:
        print("\n" + "=" * 60)
        print("🎉 GSM8K 测试集下载完成！")
        print("\n你可以在测试框架中使用这些数据:")
        print(f"   {save_dir}/gsm8k_test.json")

if __name__ == "__main__":
    main()
