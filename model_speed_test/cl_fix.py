import re

path = 'frontend/src/views/Dashboard.vue'
with open(path, encoding='utf-8') as f:
    lines = f.readlines()

n = 0
for i, line in enumerate(lines):
    if 'console.log' in line and not line.strip().startswith('//'):
        indent = line[:len(line) - len(line.lstrip())]
        lines[i] = indent + '// ' + line.strip() + '\n'
        n += 1

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
print(f'commented {n}')
