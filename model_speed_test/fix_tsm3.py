path = 'frontend/src/components/dashboard/modals/TestSetManagerModal.vue'
with open(path, encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    # confirm -> dialogConfirm
    if "return confirm('当前没有文件夹" in line:
        lines[i] = line.replace(
            "return confirm('当前没有文件夹，是否将用例移到未分类（根目录）？') ? null : undefined",
            "return (await dialogConfirm('当前没有文件夹，是否将用例移到未分类（根目录）？', { title: '移动用例' })) ? null : undefined"
        )
        print('confirm fixed L', i+1)
    # prompt -> dialogPrompt
    if 'const input = prompt(' in line and i + 4 < len(lines):
        # 检查后续几行是否有"选择目标文件夹"
        ctx = ''.join(lines[i:i+5])
        if '选择目标文件夹' in ctx:
            lines[i] = line.replace('const input = prompt(', 'const input = await dialogPrompt(')
            # 找到这个调用的最后一个参数行 '0' 并改为对象
            for j in range(i+1, i+6):
                if lines[j].strip() == "'0'":
                    lines[j] = lines[j].replace("'0'", "{ title: '移动到…', inputValue: '0' }")
                    break
            print('prompt fixed L', i+1)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
