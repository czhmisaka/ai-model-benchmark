path = 'frontend/src/components/ReportPreviewModal.vue'
with open(path, encoding='utf-8') as f:
    lines = f.readlines()

tpl_end = None
for i, line in enumerate(lines):
    if line.strip() == '</template>':
        tpl_end = i
        break

if tpl_end:
    toast_el = '    <div class="rpm-toast" :class="[toastType, { show: toastVisible }]">{{ toastMessage }}</div>\n'
    lines.insert(tpl_end, toast_el)
    print('toast inserted at L', tpl_end + 1)
else:
    print('template end not found')

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(lines)
