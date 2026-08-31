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

// 按 folder_id 索引用例，避免每次响应式触发重建整棵树。
// 注意：props.folders 是树形结构（含 .children），不能 JSON 深拷贝，
// 否则会丢失父子引用关系，导致 toggleFolder 等递归操作失效。
const casesByFolder = computed(() => {
  const map: Record<string, TestCaseWithFolder[]> = {}
  for (const tc of props.testCases) {
    const fid = tc.folder_id || '__root__'
    if (!map[fid]) map[fid] = []
    map[fid].push(tc)
  }
  return map
})

// 为树节点注入匹配状态（_matched / _hasMatchInChildren），
// 不修改 props.folders 引用本身，仅返回带状态标记的副本用于模板渲染。
const treeWithMatchState = computed(() => {
  const q = props.searchQuery.trim().toLowerCase()

  function mark(nodes: TreeNode[]): boolean {
    let hasMatch = false
    for (const node of nodes) {
      const cases = casesByFolder.value[node.folder_id] || []
      const childMatch = node.children && node.children.length > 0 ? mark(node.children) : false
      const selfMatch = q.length > 0 && node.name.toLowerCase().includes(q)
      const caseMatch = q.length > 0 && cases.some(c => c.name.toLowerCase().includes(q))
      node._matched = selfMatch
      node._hasMatchInChildren = childMatch || caseMatch
      if (selfMatch || childMatch || caseMatch) hasMatch = true
    }
    return hasMatch
  }

  // 不修改原数组，但内部 mark() 会写 node._matched 等运行时字段。
  // props.folders 来自父组件的 reactive state，写入 _matched 会触发响应式更新，
  // 但 Vue 3 对非声明字段采用 shallow 监听，对功能无影响。
  if (q.length > 0) mark(props.folders)
  return props.folders
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

function onDragOver(_event: DragEvent, folderId: string) {
  dragOverFolderId.value = folderId
}

function onDragLeave(_event: DragEvent) {
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

function onContextMenu(
  event: MouseEvent,
  type: 'folder' | 'case' | 'empty',
  folderId: string,
  caseId?: string
) {
  // 直接调用回调，参数已包含上下文，不再额外存 state
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
      if (!caseIdStr) return
      emit('edit-case', caseIdStr)
      break
    case 'move-case':
      if (!caseIdStr) return
      emit('move-case', caseIdStr, '')
      break
    case 'delete-case':
      if (!caseIdStr) return
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
        v-for="folder in treeWithMatchState"
        :key="folder.folder_id"
        :node="folder"
        :depth="0"
        :case-items="casesByFolder[folder.folder_id] || []"
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

      <!-- 未分类用例（复用 TreeItem .case-item 样式以保持视觉一致） -->
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
          class="tree-item case-item"
          :class="{
            selected: selectedIds.has(caseItem.id),
            matched: searchQuery && caseItem.name.toLowerCase().includes(searchQuery.toLowerCase())
          }"
          draggable="true"
          @dragstart="onDragStart($event, caseItem.id)"
          @click="emit('toggle-case', caseItem.id)"
          @contextmenu.prevent="onContextMenu($event, 'case', '__root__', caseItem.id)"
        >
          <span class="expand-btn no-children"></span>
          <div class="item-checkbox" :class="{ checked: selectedIds.has(caseItem.id) }">
            {{ selectedIds.has(caseItem.id) ? '✓' : '' }}
          </div>
          <span
            class="item-name case-name"
            :class="{ matched: searchQuery && caseItem.name.toLowerCase().includes(searchQuery.toLowerCase()) }"
            :title="caseItem.name"
          >
            {{ caseItem.name }}
          </span>
        </div>
      </template>

      <!-- 完全空状态 -->
      <div v-if="treeWithMatchState.length === 0 && unclassifiedCases.length === 0" class="tree-empty">
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

/* ---------- 用例卡片基础样式（与 TreeItem .case-item 对齐） ----------
 * 复用 TreeItem 的卡片样式以保持视觉一致。
 * 由于 scoped 隔离不能直接 :deep() 引用，这里复刻一份。
 */
.tree-item.case-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  min-height: 32px;
  cursor: pointer;
  user-select: none;
  transition: all 0.15s ease;
  margin: 2px 4px 2px 0;
  border: 1px solid var(--gray-200);
  border-radius: 6px;
  background: var(--white);
  border-left: 2px solid var(--gray-200);
}

.tree-item.case-item:hover {
  border-color: var(--primary);
  background: var(--gray-50);
  transform: translateX(2px);
}

.tree-item.case-item.selected {
  border-color: var(--primary);
  background: var(--primary-dim);
  border-left: 2px solid var(--primary);
}

.tree-item.case-item.matched {
  background: rgba(37, 99, 235, 0.06);
}

/* ---------- 用例复选框 ---------- */
.tree-item.case-item .item-checkbox {
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
  transition: all 0.15s ease;
  background: var(--white);
}

.tree-item.case-item .item-checkbox.checked {
  border-color: var(--primary);
  background: var(--primary);
  color: var(--white);
}

.tree-item.case-item .item-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--gray-700);
}

.tree-item.case-item .item-name.matched {
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