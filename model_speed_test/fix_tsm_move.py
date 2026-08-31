path = 'frontend/src/components/dashboard/modals/TestSetManagerModal.vue'
with open(path, encoding='utf-8') as f:
    c = f.read()

# handleMoveCase 改 async + await promptSelectFolder
c = c.replace(
    '''function handleMoveCase(caseId: string, targetFolderId: string | null) {
  // 空串 = 需要用户选择目标文件夹；通过序号选择器返回真实 folder_id
  // （旧逻辑 prompt 收集"文件夹名称"直接当 folder_id 发送，后端查无此 id 必然失败）
  if (targetFolderId === '') {
    const selected = promptSelectFolder()''',
    '''async function handleMoveCase(caseId: string, targetFolderId: string | null) {
  // 空串 = 需要用户选择目标文件夹；通过序号选择器返回真实 folder_id
  if (targetFolderId === '') {
    const selected = await promptSelectFolder()''', 1)

# handleMoveCaseFromDetail 里的 await promptSelectFolder 已在之前处理（async 化了）
# 确认 handleMoveCaseFromDetail 中也有 await
c = c.replace(
    "    const selected = promptSelectFolder()
    if (selected === undefined) return  // 用户取消
    emit('move-case', caseId, selected)
  }
}

// ===== 工具函数 =====",
    "    const selected = await promptSelectFolder()
    if (selected === undefined) return  // 用户取消
    emit('move-case', caseId, selected)
  }
}

// ===== 工具函数 =====")

with open(path, 'w', encoding='utf-8') as f:
    f.write(c)
print('tsm move awaits fixed')
