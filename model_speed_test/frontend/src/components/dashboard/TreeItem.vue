<script setup lang="ts">
import { ref, computed } from 'vue'

// ===== 数据接口 =====
export interface TreeNode {
  folder_id: string
  name: string
  parent_id: string | null
  sort_order: number
  children: TreeNode[]
  // 前端运行时注入
  _expanded?: boolean
  _matched?: boolean
  _hasMatchInChildren?: boolean
  _cases?: TestCaseWithFolder[]
}

export interface TestCaseWithFolder {
  id: string
  name: string
  folder_id: string | null
  [key: string]: any
}

// ===== Props =====
const props = defineProps<{
  node: TreeNode
  depth: number
  caseItems: TestCaseWithFolder[]         // 当前文件夹下的直接用例
  casesByFolder: Record<string, TestCaseWithFolder[]>  // 全部用例按 folder_id 索引（供递归子层级）
  selectedIds: Set<string>
  searchQuery: string
  collapsed: boolean                      // 父级面板折叠状态
  dragOverFolderId: string | null         // 拖拽悬停的文件夹 ID
}>()

// ===== Emits =====
const emit = defineEmits<{
  'toggle-folder': [folderId: string]
  'toggle-case': [caseId: string]
  'context-menu': [event: MouseEvent, type: 'folder' | 'case' | 'empty', folderId: string, caseId?: string]
  'drag-start': [event: DragEvent, caseId: string]
  'drag-over': [event: DragEvent, folderId: string]
  'drag-leave': [event: DragEvent]
  'drop': [event: DragEvent, folderId: string]
}>()

// ===== 展开/折叠状态 =====
const localExpanded = ref(props.node._expanded ?? false)  // 默认折叠（用户点击展开）

const isSearchActive = computed(() => props.searchQuery.trim().length > 0)
const isExpanded = computed(() => {
  if (isSearchActive.value && (props.node._hasMatchInChildren || props.node._matched)) {
    return true
  }
  return localExpanded.value
})

function toggleExpand() {
  localExpanded.value = !localExpanded.value
}

// ===== Checkbox 三态计算 =====
const allDescendantCaseIds = computed(() => {
  const ids: string[] = []
  props.caseItems.forEach(c => ids.push(c.id))
  if (props.node.children) {
    props.node.children.forEach(child => {
      collectDescendantCaseIds(child, ids)
    })
  }
  return ids
})

function collectDescendantCaseIds(node: TreeNode, ids: string[]) {
  if (node._cases) {
    node._cases.forEach(c => ids.push(c.id))
  }
  if (node.children) {
    node.children.forEach(child => collectDescendantCaseIds(child, ids))
  }
}

const checkedCount = computed(() => {
  return allDescendantCaseIds.value.filter(id => props.selectedIds.has(id)).length
})

const totalCount = computed(() => allDescendantCaseIds.value.length)

const isChecked = computed(() => {
  if (totalCount.value === 0) return false
  return checkedCount.value === totalCount.value
})

const isIndeterminate = computed(() => {
  if (totalCount.value === 0) return false
  return checkedCount.value > 0 && checkedCount.value < totalCount.value
})

const checkboxChar = computed(() => {
  if (isChecked.value) return '✓'
  if (isIndeterminate.value) return '■'
  return ''
})

// ===== 用例是否选中 =====
function isCaseChecked(caseId: string): boolean {
  return props.selectedIds.has(caseId)
}

// ===== 搜索匹配高亮 =====
function isNameMatched(name: string): boolean {
  if (!isSearchActive.value) return false
  return name.toLowerCase().includes(props.searchQuery.trim().toLowerCase())
}

// ===== 拖拽 =====
function onDragStartCase(event: DragEvent, caseItem: TestCaseWithFolder) {
  emit('drag-start', event, caseItem.id)
}

const isDragOverSelf = computed(() => {
  return props.dragOverFolderId === props.node.folder_id
})

function onDragOverFolder(event: DragEvent) {
  event.preventDefault()
  emit('drag-over', event, props.node.folder_id)
}

function onDragLeaveFolder(event: DragEvent) {
  emit('drag-leave', event)
}

function onDropFolder(event: DragEvent) {
  emit('drop', event, props.node.folder_id)
}

// ===== 右键菜单 =====
function onContextMenu(event: MouseEvent, type: 'folder' | 'case' | 'empty', caseId?: string) {
  emit('context-menu', event, type, props.node.folder_id, caseId)
}
</script>

<template>
  <div class="tree-item-wrapper">
    <!-- 文件夹节点 -->
    <div
      class="tree-item folder-item"
      :class="{
        'has-children': node.children && node.children.length > 0,
        'matched': node._matched,
        'drag-over': isDragOverSelf
      }"
      :style="{ paddingLeft: (depth * 16) + 'px' }"
      @dragover="onDragOverFolder"
      @dragleave="onDragLeaveFolder"
      @drop="onDropFolder"
      @contextmenu.prevent="onContextMenu($event, 'folder')"
    >
      <!-- 展开/折叠箭头 -->
      <button
        v-if="node.children && node.children.length > 0"
        class="expand-btn"
        :class="{ expanded: isExpanded }"
        @click.stop="toggleExpand"
      >
        ▶
      </button>
      <span v-else class="expand-btn no-children"></span>

      <!-- 文件夹 Checkbox -->
      <div
        class="item-checkbox folder-checkbox"
        :class="{ checked: isChecked, indeterminate: isIndeterminate }"
        @click.stop="emit('toggle-folder', node.folder_id)"
      >
        {{ checkboxChar }}
      </div>

      <!-- 文件夹名称 -->
      <span
        class="item-name folder-name"
        :class="{ matched: node._matched, collapsed: collapsed }"
        @click="toggleExpand"
      >
        <span class="folder-icon">{{ isExpanded ? '⊟' : '⊞' }}</span>
        {{ node.name }}
        <span class="folder-count" v-if="totalCount > 0">({{ checkedCount }}/{{ totalCount }})</span>
      </span>
    </div>

    <!-- 展开后的子节点 -->
    <template v-if="isExpanded">
      <!-- 直接子用例 -->
      <div
        v-for="caseItem in caseItems"
        :key="caseItem.id"
        class="tree-item case-item"
        :class="{ selected: isCaseChecked(caseItem.id), matched: isNameMatched(caseItem.name) }"
        :style="{ paddingLeft: ((depth + 1) * 16 + 8) + 'px' }"
        draggable="true"
        @dragstart="onDragStartCase($event, caseItem)"
        @click="emit('toggle-case', caseItem.id)"
        @contextmenu.prevent="onContextMenu($event, 'case', caseItem.id)"
      >
        <span class="expand-btn no-children"></span>
        <div class="item-checkbox" :class="{ checked: isCaseChecked(caseItem.id) }">
          {{ isCaseChecked(caseItem.id) ? '✓' : '' }}
        </div>
        <span
          class="item-name case-name"
          :class="{ matched: isNameMatched(caseItem.name), collapsed: collapsed }"
          :title="caseItem.name"
        >
          {{ caseItem.name }}
        </span>
      </div>

      <!-- 递归子文件夹 -->
      <TreeItem
        v-for="child in node.children"
        :key="child.folder_id"
        :node="child"
        :depth="depth + 1"
        :case-items="casesByFolder[child.folder_id] || []"
        :cases-by-folder="casesByFolder"
        :selected-ids="selectedIds"
        :search-query="searchQuery"
        :collapsed="collapsed"
        :drag-over-folder-id="dragOverFolderId"
        @toggle-folder="emit('toggle-folder', $event)"
        @toggle-case="emit('toggle-case', $event)"
        @context-menu="(event, type, folderId, caseId) => emit('context-menu', event, type, folderId, caseId)"
        @drag-start="(event, caseId) => emit('drag-start', event, caseId)"
        @drag-over="(event, folderId) => emit('drag-over', event, folderId)"
        @drag-leave="emit('drag-leave', $event)"
        @drop="(event, folderId) => emit('drop', event, folderId)"
      />

      <!-- 空文件夹提示 -->
      <div
        v-if="caseItems.length === 0 && (!node.children || node.children.length === 0)"
        class="tree-item empty-item"
        :style="{ paddingLeft: ((depth + 1) * 16 + 8) + 'px' }"
        @contextmenu.prevent="onContextMenu($event, 'empty')"
      >
        <span class="expand-btn no-children"></span>
        <span class="item-name empty-hint">— 空文件夹，右键新建 —</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.tree-item-wrapper {
  /* container */
}

/* ========== Tree Item Base ========== */
.tree-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  min-height: 32px;
  cursor: pointer;
  user-select: none;
  transition: all 0.15s ease;
}

/* ========== Folder Node ========== */
.folder-item {
  font-weight: 600;
  color: var(--gray-800);
  border-left: 2px solid transparent;
  margin-bottom: 1px;
}

.folder-item:hover {
  background: var(--gray-50);
}

.folder-item.drag-over {
  background: var(--primary-dim);
  border-left-color: var(--primary);
}

/* ========== Case Node — 卡片式，对齐 Models 列 ========== */
.case-item {
  margin: 2px 4px 2px 0;
  border: 1px solid var(--gray-200);
  border-radius: 6px;
  background: var(--white);
  border-left: 2px solid var(--gray-200);
}

.case-item:hover {
  border-color: var(--primary);
  background: var(--gray-50);
  transform: translateX(2px);
}

.case-item.selected {
  border-color: var(--primary);
  background: var(--primary-dim);
  border-left: 2px solid var(--primary);
}

.case-item.matched {
  background: rgba(37, 99, 235, 0.06);
}

/* ========== Empty Hint ========== */
.empty-item {
  cursor: context-menu;
  opacity: 0.6;
}

.empty-hint {
  color: var(--gray-400);
  font-style: italic;
  font-size: 0.7rem;
}

/* ========== Expand Button ========== */
.expand-btn {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 0.5rem;
  color: var(--gray-400);
  transition: transform 0.15s ease;
  padding: 0;
  line-height: 1;
}

.expand-btn.expanded {
  transform: rotate(90deg);
}

.expand-btn.no-children {
  visibility: hidden;
  pointer-events: none;
}

/* ========== Checkbox — 对齐 Models 列 ========== */
.item-checkbox {
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

.item-checkbox.checked {
  border-color: var(--primary);
  background: var(--primary);
  color: var(--white);
}

.item-checkbox.indeterminate {
  border-color: var(--primary);
  background: var(--white);
  color: var(--primary);
}

.folder-checkbox {
  /* inherit default */
}

/* ========== Names ========== */
.folder-icon {
  display: inline-block;
  margin-right: 2px;
  font-size: 0.75rem;
}

.folder-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--gray-700);
}

.case-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  font-weight: 500;
  color: var(--gray-700);
}

/* ========== Search Match Highlight ========== */
.item-name.matched {
  background: rgba(37, 99, 235, 0.12);
  border-radius: 2px;
  padding: 0 3px;
}

.folder-name.matched {
  background: rgba(37, 99, 235, 0.12);
  border-radius: 2px;
  padding: 0 3px;
}

/* ========== Collapsed State ========== */
.item-name.collapsed {
  display: none;
}

.folder-name.collapsed {
  display: none;
}

/* ========== Folder Count ========== */
.folder-count {
  font-size: 0.65rem;
  color: var(--gray-400);
  font-weight: 400;
  font-family: 'JetBrains Mono', monospace;
}
</style>