<script setup lang="ts">
import { ref, computed } from 'vue'
import TreeItem from './TreeItem.vue'
import ContextMenu from './components/ContextMenu.vue'
import type { TreeNode, TestCaseWithFolder } from './TreeItem.vue'

// ===== Props =====
interface Props {
  folders: TreeNode[]
  testCases: TestCaseWithFolder[]
  selectedIds: Set<string>
  searchQuery: string
  hideToolbar?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  hideToolbar: true
})

// ===== Emits =====
const emit = defineEmits<{
  'toggle-folder': [folderId: string]
  'toggle-case': [caseId: string]
  'select-all': []
  'deselect-all': []
  'add-folder': []
  'add-case': []
  'rename-folder': [folderId: string, name: string]
  'move-case': [caseId: string, targetFolderId: string | null]
  'delete-folder': [folderId: string]
  'delete-case': [caseId: string]
  'edit-case': [caseId: string]
  'expand-all': [folderId: string]
  'collapse-all': [folderId: string]
}>()

// ===== 搜索状态 =====
const isSearchActive = computed(() => props.searchQuery.trim().length > 0)

// ===== 为树节点注入用例数据 =====
const treeWithCases = computed(() => {
  const roots = JSON.parse(JSON.stringify(props.folders)) as TreeNode[]

  const casesByFolder: Record<string, TestCaseWithFolder[]> = {}
  props.testCases.forEach(tc => {
    const fid = tc.folder_id || '__root__'
    if (!casesByFolder[fid]) casesByFolder[fid] = []
    casesByFolder[fid].push(tc)
  })

  function injectCases(nodes: TreeNode[]): boolean {
    let hasMatch = false
    nodes.forEach(node => {
      node._cases = casesByFolder[node.folder_id] || []
      node._expanded = node._expanded ?? false

      if (isSearchActive.value) {
        const q = props.searchQuery.toLowerCase()
        if (node.name.toLowerCase().includes(q)) {
          node._matched = true
          hasMatch = true
        } else {
          node._matched = false
        }
        const caseMatches = (node._cases || []).some(c => c.name.toLowerCase().includes(q))
        const childMatch = node.children && node.children.length > 0 && injectCases(node.children)
        node._hasMatchInChildren = caseMatches || childMatch
        if (node._hasMatchInChildren) hasMatch = true
      } else {
        node._matched = false
        node._hasMatchInChildren = false
      }
    })
    return hasMatch
  }

  roots.forEach(root => injectCases([root]))
  return roots
})

// 未分类用例（folder_id === null 的）
const unclassifiedCases = computed(() => {
  return props.testCases.filter(tc => !tc.folder_id)
})

// ===== 拖拽状态 =====
const dragOverFolderId = ref<string | null>(null)
const draggingCaseId = ref<string | null>(null)

function onDragStart(event: DragEvent, caseId: string) {
  draggingCaseId.value = caseId
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', caseId)
  }
}

function onDragOver(event: DragEvent, folderId: string) {
  dragOverFolderId.value = folderId
}

function onDragLeave(event: DragEvent) {
  // handled by parent
}

function onDrop(event: DragEvent, targetFolderId: string) {
  event.preventDefault()
  const caseId = event.dataTransfer?.getData('text/plain')
  if (caseId) {
    emit('move-case', caseId, targetFolderId)
  }
  dragOverFolderId.value = null
  draggingCaseId.value = null
}

function onDropRoot(event: DragEvent) {
  event.preventDefault()
  const caseId = event.dataTransfer?.getData('text/plain')
  if (caseId) {
    emit('move-case', caseId, null)
  }
  dragOverFolderId.value = null
  draggingCaseId.value = null
}

const rootDragOver = ref(false)

// ===== 右键菜单 =====
const contextMenuRef = ref<InstanceType<typeof ContextMenu> | null>(null)
const contextMenuTarget = ref<{ folderId: string; caseId?: string }>({ folderId: '' })

function onContextMenu(
  event: MouseEvent,
  type: 'folder' | 'case' | 'empty',
  folderId: string,
  caseId?: string
) {
  contextMenuTarget.value = { folderId, caseId }
  contextMenuRef.value?.show(event, type, (action: string) => {
    handleContextAction(action, folderId, caseId)
  })
}

function handleContextAction(action: string, folderId: string, caseId?: string) {
  const caseIdStr = caseId || ''
  switch (action) {
    case 'create-folder':
    case 'create-sub-folder':
      emit('add-folder')
      break
    case 'rename-folder':
      emit('rename-folder', folderId, '')
      break
    case 'delete-folder':
      emit('delete-folder', folderId)
      break
    case 'edit-case':
      emit('edit-case', caseIdStr)
      break
    case 'move-case':
      emit('move-case', caseIdStr, '')
      break
    case 'delete-case':
      emit('delete-case', caseIdStr)
      break
    case 'create-case':
      emit('add-case')
      break
    case 'expand-all':
      emit('expand-all', folderId)
      break
    case 'collapse-all':
      emit('collapse-all', folderId)
      break
  }
}

// ===== 全选/取消计算 =====
const allCaseIds = computed(() => props.testCases.map(c => c.id))
const allSelected = computed(() => {
  if (allCaseIds.value.length === 0) return false
  return allCaseIds.value.every(id => props.selectedIds.has(id))
})

function toggleSelectAll() {
  if (allSelected.value) {
    emit('deselect-all')
  } else {
    emit('select-all')
  }
}

const selectAllChar = computed(() => (allSelected.value ? '⊙' : '○'))
</script>

<template>
  <div class="tree-view">
    <!-- 工具栏（可选，默认隐藏，由 Dashboard header-actions 提供） -->
    <div class="tree-toolbar" v-if="!hideToolbar">
      <button class="toolbar-btn" @click="toggleSelectAll" title="全选/取消全选">
        {{ selectAllChar }}
      </button>
      <button class="toolbar-btn" @click="emit('add-folder')" title="新建文件夹">⊞</button>
      <button class="toolbar-btn" @click="emit('add-case')" title="新建测试用例">＋</button>
    </div>

    <!-- 根区域（拖拽目标） -->
    <div
      class="tree-root-area"
      :class="{ 'drag-over': rootDragOver }"
      @dragover.prevent="rootDragOver = true"
      @dragleave="rootDragOver = false"
      @drop="onDropRoot"
    >
      <!-- 遍历根文件夹 -->
      <TreeItem
        v-for="folder in treeWithCases"
        :key="folder.folder_id"
        :node="folder"
        :depth="0"
        :case-items="folder._cases || []"
        :selected-ids="selectedIds"
        :search-query="searchQuery"
        :collapsed="false"
        :drag-over-folder-id="dragOverFolderId"
        @toggle-folder="emit('toggle-folder', $event)"
        @toggle-case="emit('toggle-case', $event)"
        @context-menu="onContextMenu"
        @drag-start="onDragStart"
        @drag-over="onDragOver"
        @drag-leave="onDragLeave"
        @drop="onDrop"
      />

      <!-- 未分类用例 -->
      <template v-if="unclassifiedCases.length > 0">
        <div
          class="tree-section-header"
          :class="{ empty: searchQuery && unclassifiedCases.every(c => !c.name.toLowerCase().includes(searchQuery.toLowerCase())) }"
        >
          未分类
          <span class="section-count">
            ({{ unclassifiedCases.filter(c => !searchQuery || c.name.toLowerCase().includes(searchQuery.toLowerCase())).length }})
          </span>
        </div>
        <div
          v-for="caseItem in unclassifiedCases"
          :key="caseItem.id"
          class="tree-case-card"
          :class="{
            selected: selectedIds.has(caseItem.id),
            hidden: searchQuery && !caseItem.name.toLowerCase().includes(searchQuery.toLowerCase())
          }"
          draggable="true"
          @dragstart="onDragStart($event, caseItem.id)"
          @click="emit('toggle-case', caseItem.id)"
          @contextmenu.prevent="onContextMenu($event, 'case', '__root__', caseItem.id)"
        >
          <div class="case-checkbox" :class="{ checked: selectedIds.has(caseItem.id) }">
            {{ selectedIds.has(caseItem.id) ? '✓' : '' }}
          </div>
          <span
            class="case-title"
            :class="{ matched: searchQuery && caseItem.name.toLowerCase().includes(searchQuery.toLowerCase()) }"
            :title="caseItem.name"
          >
            {{ caseItem.name }}
          </span>
        </div>
      </template>

      <!-- 完全空状态 -->
      <div v-if="treeWithCases.length === 0 && unclassifiedCases.length === 0" class="tree-empty">
        <p>暂无测试用例</p>
        <button class="btn-empty" @click="emit('add-case')">＋ 新建</button>
      </div>
    </div>

    <!-- 右键菜单 -->
    <ContextMenu ref="contextMenuRef" />
  </div>
</template>

<style scoped>
/*
 * TreeView — 与 Dashboard .item-list 完全融合，无额外容器边框
 * 对齐 Models 列卡片式设计：1px gray-200 边框 + 8px 圆角 + hover 时 primary 高亮
 */
.tree-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* ---------- Toolbar（仅独立使用时显示） ---------- */
.tree-toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 0 6px 0;
  flex-shrink: 0;
}

.toolbar-btn {
  width: 24px;
  height: 24px;
  border: 1px solid var(--gray-300);
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  color: var(--gray-500);
  transition: all var(--duration-fast) var(--ease-default);
  padding: 0;
}

.toolbar-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--gray-50);
}

/* ---------- 根区域 ---------- */
.tree-root-area {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 40px;
}

.tree-root-area.drag-over {
  outline: 2px dashed var(--primary);
  outline-offset: -2px;
  border-radius: 6px;
  background: var(--primary-dim);
}

/* ---------- 分区标题（未分类） ---------- */
.tree-section-header {
  padding: 8px 8px 4px 8px;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--gray-500);
  letter-spacing: 0.5px;
  cursor: default;
  font-family: 'JetBrains Mono', monospace;
}

.tree-section-header.empty {
  opacity: 0.3;
}

.section-count {
  font-size: 0.65rem;
  color: var(--gray-400);
  font-weight: 400;
  font-family: 'JetBrains Mono', monospace;
}

/* ---------- 未分类用例卡片 — 对齐 Dashboard .item 样式 ---------- */
.tree-case-card {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  min-height: 36px;
  margin: 2px 4px;
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  background: var(--white);
  transition: all 0.2s ease;
  cursor: pointer;
  user-select: none;
}

.tree-case-card:hover {
  border-color: var(--primary);
  background: var(--gray-50);
  transform: translateX(2px);
}

.tree-case-card.selected {
  border-color: var(--primary);
  background: var(--primary-dim);
}

.tree-case-card.hidden {
  display: none;
}

/* ---------- 用例复选框 — 对齐 Dashboard .item-checkbox ---------- */
.case-checkbox {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  border: 2px solid var(--gray-300);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.55rem;
  color: transparent;
  transition: all 0.2s ease;
  background: var(--white);
}

.case-checkbox.checked {
  border-color: var(--primary);
  background: var(--primary);
  color: var(--white);
}

.tree-case-card.selected .case-checkbox {
  border-color: var(--primary);
  background: var(--primary);
  color: var(--white);
}

/* ---------- 用例标题 — 对齐 Dashboard .item-name ---------- */
.case-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--gray-700);
}

.case-title.matched {
  background: rgba(37, 99, 235, 0.12);
  border-radius: 2px;
  padding: 0 3px;
}

/* ---------- 空状态 ---------- */
.tree-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  color: var(--gray-500);
  font-size: 0.78rem;
  gap: 12px;
}

.btn-empty {
  background: transparent;
  border: 1px solid var(--gray-300);
  border-radius: 4px;
  padding: 6px 16px;
  cursor: pointer;
  font-size: 0.78rem;
  color: var(--gray-700);
  transition: all var(--duration-fast) var(--ease-default);
}

.btn-empty:hover {
  border-color: var(--primary);
  color: var(--primary);
}
</style>