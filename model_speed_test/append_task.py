line1 = "\n### 模型归档（已完成）\n"
line2 = "- [x] 44 个模型按具体模型家族分类归档（19 组）：MiniMax-M2.5/2.7/3 系列、DeepSeek-V4 系列（Flash/Pro/火山接入）、Qwen3.5/3.6/3.8/VL/32b 系列、GLM 系列、Kimi 系列、GPT 系列、小米 MiMo 系列、华电大模型、NVIDIA Nemotron 系列、本地部署(Mac)、Embedding 模型\n"
line3 = "- [ ] 前端模型列表目前为扁平渲染（group_name 字段已有数据，树形分组 UI 留待后续）\n"
with open("task.md", "a", encoding="utf-8") as f:
    f.write(line1 + line2 + line3)
print("appended")
