<script setup lang="ts">
import { ref, computed } from 'vue'
import TreeView from '../TreeView.vue'
import type { TreeNode, TestCaseWithFolder } from '../TreeItem.vue'

// ===== Props =====
interface Props {
  folders: TreeNode[]
  testCases: TestCaseWithFolder[]
  visible: boolean
}

const props = defineProps<Props>()

// ===== Emits =====
const emit = defineEmits<{
  close: []
  'create-folder': [name: string, parentId: string | null]
  'rename-folder': [folderId: string, name: string]
  'delete-folder': [folderId: string]
  'create-case': []
  'edit-case': [caseId: string]
  'move-case': [caseId: string, targetFolderId: string | null]
  'delete-case': [caseId: string]
}>()

// ===== 搜索 =====
const searchQuery = ref('')

// ===== 选中（管理弹窗中不涉及测试选中，仅用于详情面板） =====
const selectedIds = ref<Set<string>>(new Set())
const selectedFolderId = ref<string | null>(null)

// ===== 详情面板 =====
const selectedDetail = computed(() => {
  // 1. 优先展示文件夹详情
  if (selectedFolderId.value) {
    function findFolder(nodes: TreeNode[], id: string): TreeNode | null {
      for (const n of nodes) {
        if (n.folder_id === id) return n
        if (n.children) {
          const found = findFolder(n.children, id)
          if (found) return found
        }
      }
      return null
    }
    const folder = findFolder(props.folders, selectedFolderId.value)
    if (folder) {
      const cases = props.testCases.filter(tc => tc.folder_id === folder.folder_id)
      return {
        type: 'folder' as const,
        name: folder.name,
        folder_id: folder.folder_id,
        parent_id: folder.parent_id,
        caseCount: cases.length,
        cases: cases.map(c => c.name),
      }
    }
  }
  // 2. 否则展示选中用例的详情（取首个选中的）
  for (const id of selectedIds.value) {
    const tc = props.testCases.find(c => c.id === id)
    if (tc) {
      const tcFolderId = tc.folder_id
      // 查找所属文件夹名
      function findFolderName(nodes: TreeNode[]): string | null {
        for (const n of nodes) {
          if (n.folder_id === tcFolderId) return n.name
          if (n.children) {
            const found = findFolderName(n.children)
            if (found !== null) return found
          }
        }
        return null
      }
      const folderName = tc.folder_id ? findFolderName(props.folders) : null
      return {
        type: 'case' as const,
        name: tc.name,
        case_id: tc.id,
        folder_id: tc.folder_id || null,
        folder_name: folderName,
        max_tokens: tc.max_tokens || 0,
        message_count: Array.isArray(tc.messages) ? tc.messages.length : 0,
      }
    }
  }
  return null
})

// ===== TreeView 事件处理 =====
function handleToggleCase(caseId: string) {
  // 管理弹窗中，点击用例 toggle 选中，并清除文件夹选中
  if (selectedIds.value.has(caseId)) {
    selectedIds.value.delete(caseId)
  } else {
    selectedIds.value.add(caseId)
  }
  // 触发响应式更新（Set 需要重新赋值）
  selectedIds.value = new Set(selectedIds.value)
  selectedFolderId.value = null
}

function handleToggleFolder(folderId: string) {
  selectedFolderId.value = folderId
}

function handleAddFolder() {
  const name = prompt('请输入文件夹名称：')
  if (name && name.trim()) {
    emit('create-folder', name.trim(), null)
  }
}

function handleAddCase() {
  emit('create-case')
}

function handleRenameFolder(folderId: string) {
  const folder = findFolderById(folderId)
  const name = prompt('请输入新名称：', folder?.name || '')
  if (name && name.trim()) {
    emit('rename-folder', folderId, name.trim())
  }
}

function handleDeleteFolder(folderId: string) {
  const folder = findFolderById(folderId)
  if (confirm(`确定要删除文件夹「${folder?.name}」及其所有子内容吗？\n测试用例将移至未分类。`)) {
    emit('delete-folder', folderId)
  }
}

function handleEditCase(caseId: string) {
  emit('edit-case', caseId)
}

function handleMoveCase(caseId: string, targetFolderId: string | null) {
  // 空串 = 需要用户选择目标文件夹；通过序号选择器返回真实 folder_id
  // （旧逻辑 prompt 收集"文件夹名称"直接当 folder_id 发送，后端查无此 id 必然失败）
  if (targetFolderId === '') {
    const selected = promptSelectFolder()
    if (selected === undefined) return  // 用户取消
    emit('move-case', caseId, selected)
  } else {
    emit('move-case', caseId, targetFolderId)
  }
}

// 弹出文件夹选择器（返回 folder_id；null=根目录；undefined=取消）
function promptSelectFolder(): string | null | undefined {
  const flat: { id: string; label: string }[] = []
  const walk = (nodes: TreeNode[], prefix: string) => {
    for (const n of nodes) {
      flat.push({ id: n.folder_id, label: prefix + n.name })
      if (n.children && n.children.length) walk(n.children, prefix + '  ')
    }
  }
  walk(props.folders, '')

  if (!flat.length) {
    return confirm('当前没有文件夹，是否将用例移到未分类（根目录）？') ? null : undefined
  }

  const menu = flat.map((f, i) => `${i + 1}. ${f.label}`).join('\n')
  const input = prompt(
    `选择目标文件夹（输入序号）：\n0. 未分类（根目录）\n${menu}\n\n取消 = 放弃移动`,
    '0'
  )
  if (input === null) return undefined
  const idx = parseInt(input, 10)
  if (isNaN(idx) || idx < 0 || idx > flat.length) {
    return undefined
  }
  return idx === 0 ? null : flat[idx - 1].id
}

function handleDeleteCase(caseId: string) {
  const tc = props.testCases.find(c => c.id === caseId)
  if (confirm(`确定要删除用例「${tc?.name}」吗？此操作不可恢复。`)) {
    emit('delete-case', caseId)
  }
}

function handleMoveCaseFromDetail() {
  if (!selectedFolderId.value) return
  const caseId = prompt('输入要移动的用例 ID：')
  if (caseId) {
    const selected = promptSelectFolder()
    if (selected === undefined) return  // 用户取消
    emit('move-case', caseId, selected)
  }
}

// ===== 工具函数 =====
function findFolderById(id: string): TreeNode | null {
  function find(nodes: TreeNode[]): TreeNode | null {
    for (const n of nodes) {
      if (n.folder_id === id) return n
      if (n.children) {
        const found = find(n.children)
        if (found) return found
      }
    }
    return null
  }
  return find(props.folders)
}

// ===== Modal 控制 =====
function close() {
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="modal-overlay" @click.self="close">
      <div class="modal-container">
        <!-- 头部 -->
        <div class="modal-header">
          <h2 class="modal-title">测试集管理</h2>
          <button class="close-btn" @click="close">✕</button>
        </div>

        <!-- 主体：左右分栏 -->
        <div class="modal-body">
          <!-- 左侧：TreeView -->
          <div class="modal-left">
            <!-- 搜索栏 -->
            <div class="search-bar">
              <input
                v-model="searchQuery"
                type="text"
                placeholder="搜索文件夹或用例…"
                class="search-input"
              />
            </div>

            <TreeView
              :folders="folders"
              :test-cases="testCases"
              :selected-ids="selectedIds"
              :search-query="searchQuery"
              :hide-toolbar="false"
              @toggle-case="handleToggleCase"
              @toggle-folder="handleToggleFolder"
              @add-folder="handleAddFolder"
              @add-case="handleAddCase"
              @rename-folder="handleRenameFolder"
              @delete-folder="handleDeleteFolder"
              @edit-case="handleEditCase"
              @move-case="handleMoveCase"
              @delete-case="handleDeleteCase"
            />
          </div>

          <!-- 右侧：详情面板 -->
          <div class="modal-right">
            <template v-if="selectedDetail">
              <div class="detail-header">
                <span class="detail-icon">{{ selectedDetail.type === 'folder' ? '📁' : '📝' }}</span>
                <span class="detail-name">{{ selectedDetail.name }}</span>
              </div>

              <div class="detail-info" v-if="selectedDetail.type === 'folder'">
                <div class="info-row">
                  <span class="info-label">用例数量</span>
                  <span class="info-value">{{ selectedDetail.caseCount }}</span>
                </div>
                <div class="info-row" v-if="selectedDetail.cases.length > 0">
                  <span class="info-label">包含用例</span>
                </div>
                <ul class="info-case-list">
                  <li v-for="caseName in selectedDetail.cases" :key="caseName">
                    {{ caseName }}
                  </li>
                </ul>
              </div>

              <div class="detail-info" v-else-if="selectedDetail.type === 'case'">
                <div class="info-row">
                  <span class="info-label">所属文件夹</span>
                  <span class="info-value">{{ selectedDetail.folder_name || '未分类' }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">消息数</span>
                  <span class="info-value">{{ selectedDetail.message_count }}</span>
                </div>
                <div class="info-row">
                  <span class="info-label">max_tokens</span>
                  <span class="info-value">{{ selectedDetail.max_tokens }}</span>
                </div>
              </div>

              <div class="detail-actions">
                <template v-if="selectedDetail.type === 'folder'">
                  <button class="btn btn-secondary" @click="handleRenameFolder(selectedDetail.folder_id)">
                    重命名
                  </button>
                  <button class="btn btn-secondary" @click="handleDeleteFolder(selectedDetail.folder_id)">
                    删除
                  </button>
                  <button class="btn btn-secondary" @click="handleMoveCaseFromDetail">
                    移动用例到…
                  </button>
                </template>
                <template v-else-if="selectedDetail.type === 'case'">
                  <button class="btn btn-secondary" @click="handleEditCase(selectedDetail.case_id)">
                    编辑
                  </button>
                  <button class="btn btn-secondary" @click="handleMoveCase(selectedDetail.case_id, '')">
                    移动到…
                  </button>
                  <button class="btn btn-secondary" @click="handleDeleteCase(selectedDetail.case_id)">
                    删除
                  </button>
                </template>
              </div>
            </template>

            <template v-else>
              <div class="detail-empty">
                <p>点击左侧文件夹查看详情</p>
                <p class="detail-hint">可在此查看文件夹下的用例列表并进行批量操作</p>
              </div>
            </template>
          </div>
        </div>

        <!-- 底部 -->
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="close">确定</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 5000;
}

.modal-container {
  background: var(--bg-white);
  border: 1px solid var(--line-tertiary);
  border-radius: 8px;
  width: 90vw;
  max-width: 900px;
  height: 75vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--line-light);
  flex-shrink: 0;
}

.modal-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--line-primary);
  margin: 0;
}

.close-btn {
  width: 28px;
  height: 28px;
  border: 1px solid var(--line-tertiary);
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
  color: var(--line-secondary);
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-fast) var(--ease-default);
}

.close-btn:hover {
  border-color: var(--line-accent);
  color: var(--line-accent);
}

.modal-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.modal-left {
  flex: 1;
  border-right: 1px solid var(--line-light);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.search-bar {
  padding: 8px 12px;
  border-bottom: 1px solid var(--line-light);
  flex-shrink: 0;
}

.search-input {
  width: 100%;
  padding: 6px 10px;
  border: 1px solid var(--line-tertiary);
  border-radius: 4px;
  font-size: 0.78rem;
  background: var(--bg-white);
  color: var(--line-primary);
  outline: none;
  transition: border-color var(--duration-fast) var(--ease-default);
}

.search-input:focus {
  border-color: var(--line-accent);
  border-width: 2px;
}

.modal-right {
  width: 280px;
  padding: 16px;
  overflow-y: auto;
  flex-shrink: 0;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line-light);
  margin-bottom: 12px;
}

.detail-icon {
  font-size: 1.2rem;
}

.detail-name {
  font-weight: 600;
  color: var(--line-primary);
  font-size: 0.9rem;
}

.detail-info {
  margin-bottom: 16px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
}

.info-label {
  font-size: 0.75rem;
  color: var(--line-secondary);
}

.info-value {
  font-size: 0.75rem;
  color: var(--line-primary);
  font-weight: 500;
}

.info-case-list {
  list-style: none;
  padding: 0;
  margin: 8px 0 0;
}

.info-case-list li {
  padding: 3px 0;
  font-size: 0.72rem;
  color: var(--line-primary);
  border-left: 2px solid var(--line-light);
  padding-left: 8px;
}

.detail-actions {
  margin-top: 16px;
}

.detail-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--line-secondary);
  font-size: 0.78rem;
  text-align: center;
  padding-top: 40px;
}

.detail-hint {
  font-size: 0.7rem;
  color: var(--line-tertiary);
  margin-top: 8px;
}

.modal-footer {
  padding: 12px 20px;
  border-top: 1px solid var(--line-light);
  display: flex;
  justify-content: flex-end;
  flex-shrink: 0;
}

.btn {
  background: transparent;
  border: 1px solid var(--line-primary);
  border-radius: 4px;
  padding: 6px 20px;
  cursor: pointer;
  font-size: 0.8rem;
  color: var(--line-primary);
  transition: all var(--duration-fast) var(--ease-default);
}

.btn:hover {
  border-color: var(--line-accent);
  color: var(--line-accent);
}

.btn-secondary {
  border-color: var(--line-tertiary);
  color: var(--line-secondary);
}
</style>
