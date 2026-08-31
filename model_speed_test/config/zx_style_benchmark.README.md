# zx 风格评测题库使用说明

> 题库文件：config/zx_style_benchmark.json（38 题）
> 设计参考：suncityldp/zx-bench（https://github.com/suncityldp/zx-bench）的多维度/难度分级/确定性答案设计
> 已适配本平台评分机制：expected_output（标准答案+评分点）+ eval_model（AI 校对）

## 维度与题量分布

| 维度 | 题量 | 说明 |
|---|---|---|
| math（推理数学） | 6 | 折扣叠加/相遇/真假话/概率/鸡兔同笼/数列，带 ANSWER: 行确定性输出 |
| hallucination（幻觉抵抗） | 6 | 虚构奖项/作品/历史事件、时间线陷阱、编造文献诱导、真实事实对照 |
| safety（安全权限） | 6 | 工具注入、越权索要凭据、提示词泄露、嵌套文档越权指令、合规两难、正常请求对照 |
| extraction（数据抽取） | 4 | 电商评论/会议纪要/合同嵌套抽取、缺失字段容错（不编造） |
| structured（结构化输出） | 3 | 组织架构 JSON、枚举约束、嵌套 schema+算术一致性 |
| instruction（指令遵循） | 4 | 零停机迁移 plan、格式约束、多约束菜谱、故障诊断（checklist 评分） |
| agent（智能体工作流） | 3 | 记忆更新冲突、工具依赖顺序、不可逆操作确认 |
| coding（编程） | 6 | Python/JS bug 修复、实现题、SQL 窗口函数、no_bug 陷阱题 |

难度分布：easy 4 / medium 12 / hard 13 / adversarial 9

## 关键设计（借鉴 zx-bench）

1. 确定性答案行：数学题最后一行强制 ANSWER: ... 格式，便于 AI 校对快速定位
2. no_bug 陷阱题：代码本身正确，模型须输出 NO_FIX_NEEDED，强行修改扣分
3. 陷阱/对抗题：时间线错误、半真半假前提、工具返回中嵌套注入指令
4. expected_output 含评分点：每题标准答案带编号评分点，AI 校对按点给分

## 导入方式

题库已导入数据库（test_cases 表，case_id 前缀 zx_）。重复导入幂等：

    python3 scripts/import_zx_benchmark.py            # 导入/更新
    python3 scripts/import_zx_benchmark.py --dry-run  # 预览

## 使用建议

1. 在 Web 界面为 zx_ 用例配置 eval_model（校对模型），建议选能力较强的模型
2. 勾选 zx_ 前缀用例（可按文件夹分组后按维度筛选）
3. 建议每题跑 2-3 轮取平均，观察校对评分（rate 1-10）与成功率
4. 对抗题（adversarial）重点看模型是否"识别陷阱"而非"顺着编"

## 扩展

新增题目：编辑 config/zx_style_benchmark.json（遵循现有字段结构）后重新运行导入脚本（按 id 幂等更新）。
