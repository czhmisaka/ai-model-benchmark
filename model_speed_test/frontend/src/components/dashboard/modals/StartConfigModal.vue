<template>
  <div class="modal-overlay" :class="{ show: visible }">
    <div class="modal">
      <div class="modal-title">测试启动配置</div>
      
      <!-- 已选测试用例预览 -->
      <div class="selected-preview" v-if="selectedCount > 0">
        <div class="preview-header">已选测试用例 ({{ selectedCount }})</div>
        <div class="preview-tree">
          <template v-for="folder in groupedCases" :key="folder.key">
            <div class="tree-folder" :class="{ collapsed: collapsedFolders[folder.key] }" @click="toggleFolderGroup(folder.key)">
              <span class="folder-toggle">{{ collapsedFolders[folder.key] ? '▶' : '▼' }}</span>
              <span class="folder-name">📁 {{ folder.name }} ({{ folder.cases.length }})</span>
            </div>
            <div class="tree-case-list" v-if="!collapsedFolders[folder.key]">
              <div class="tree-case" v-for="c in folder.cases" :key="c.id">
                <span class="case-bullet">☑</span>
                <span class="case-name">{{ c.name }}</span>
              </div>
            </div>
          </template>
        </div>
      </div>
      
      <div class="form-group">
        <label class="form-label">测试轮数 (Test Rounds)</label>
        <input type="number" class="form-input" v-model="config.test_rounds" min="1" max="100" />
        <div class="form-hint">每个模型-测试用例组合重复测试的轮数</div>
      </div>
      <div class="form-group">
        <label class="form-label">最大并发数 (Max Concurrent)</label>
        <input type="number" class="form-input" v-model="config.max_concurrent" min="1" max="10" />
        <div class="form-hint">同时运行的模型数量（0表示不限制）</div>
      </div>
      <div class="form-group">
        <label class="form-label">请求间隔 (秒)</label>
        <input type="number" class="form-input" v-model="config.interval" min="0" max="60" step="0.5" />
        <div class="form-hint">每轮测试之间的等待时间</div>
      </div>
      <div class="form-group">
        <label class="form-label">校对模型（可选，覆盖用例级配置）</label>
        <select class="form-input" v-model="config.eval_model">
          <option value="">不使用校对</option>
          <option v-for="m in availableModels" :key="m" :value="m">{{ m }}</option>
        </select>
        <div class="form-hint">指定后所有用例统一使用此模型进行AI校对</div>
      </div>
      <div class="form-group">
        <label class="form-label">测试名称（可选）</label>
        <input type="text" class="form-input" v-model="config.test_name" placeholder="自动生成" />
        <div class="form-hint">用于标识这次测试，方便历史记录查找</div>
      </div>
      <div class="form-actions">
        <button class="btn btn-secondary" @click="$emit('cancel')">取消</button>
        <button class="btn btn-primary" @click="$emit('confirm')">确认启动</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'

interface StartConfig {
  test_rounds: number
  max_concurrent: number
  interval: number
  test_name: string
  eval_model: string
}

interface TestCase {
  id: string
  name: string
  folder_id?: string | null
}

interface TreeNode {
  folder_id: string
  name: string
  children?: TreeNode[]
}

interface Props {
  visible: boolean
  config: StartConfig
  testCases?: TestCase[]
  folders?: TreeNode[]
  selectedCases?: Set<string>
  availableModels?: string[]
}

const props = withDefaults(defineProps<Props>(), {
  testCases: () => [],
  folders: () => [],
  selectedCases: () => new Set(),
  availableModels: () => []
})

defineEmits<{
  cancel: []
  confirm: []
}>()

// 已选用例总数
const selectedCount = computed(() => props.selectedCases?.size ?? 0)

// 按文件夹分组已选用例
const groupedCases = computed(() => {
  const selectedIds = props.selectedCases ?? new Set()
  const testCases = props.testCases ?? []
  const folders = props.folders ?? []
  
  // 构建 folder_id → folder_name 映射
  const folderNameMap: Record<string, string> = {}
  const walk = (nodes: TreeNode[]) => {
    for (const node of nodes) {
      folderNameMap[node.folder_id] = node.name
      if (node.children) walk(node.children)
    }
  }
  walk(folders)
  
  // 分组
  const groupMap: Record<string, { name: string; cases: TestCase[] }> = {}
  
  for (const tc of testCases) {
    if (!selectedIds.has(tc.id)) continue
    const fid = tc.folder_id || '__uncategorized__'
    if (!groupMap[fid]) {
      groupMap[fid] = {
        name: fid === '__uncategorized__' ? '未分类' : (folderNameMap[fid] || '未知文件夹'),
        cases: []
      }
    }
    groupMap[fid].cases.push(tc)
  }
  
  // 排序：未分类放最后，其余按名称排序
  const sorted = Object.entries(groupMap)
    .sort(([a], [b]) => {
      if (a === '__uncategorized__') return 1
      if (b === '__uncategorized__') return -1
      return groupMap[a].name.localeCompare(groupMap[b].name, 'zh-CN')
    })
    .map(([key, val]) => ({ key, ...val }))
  
  return sorted
})

// 折叠状态
const collapsedFolders = reactive<Record<string, boolean>>({})

function toggleFolderGroup(key: string) {
  collapsedFolders[key] = !collapsedFolders[key]
}
</script>

<style lang="scss" scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.3s ease, visibility 0.3s ease;
  
  &.show {
    opacity: 1;
    visibility: visible;
  }
}

.modal {
  background: var(--white);
  border: 1px solid var(--gray-200);
  border-radius: 16px;
  padding: 24px;
  width: 480px;
  max-width: 90vw;
  max-height: 85vh;
  overflow-y: auto;
  transform: scale(0.95) translateY(10px);
  opacity: 0;
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
  
  .modal-overlay.show & {
    transform: scale(1) translateY(0);
    opacity: 1;
  }
}

.modal-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 1rem;
  font-weight: 600;
  color: var(--gray-900);
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--gray-200);
}

.form-group {
  margin-bottom: 14px;
}

.form-label {
  font-size: 0.7rem;
  color: var(--gray-600);
  margin-bottom: 6px;
  display: block;
}

.form-hint {
  font-size: 0.65rem;
  color: var(--gray-500);
  margin-top: 4px;
}

.form-input {
  width: 100%;
  padding: 10px 14px;
  background: var(--gray-50);
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  color: var(--gray-900);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.8rem;
  transition: all 0.2s ease;
  box-sizing: border-box;
  
  &::placeholder {
    color: var(--gray-400);
  }
  
  &:focus {
    outline: none;
    border-color: var(--primary);
    background: var(--white);
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
  }
}

.selected-preview {
  margin-bottom: 16px;
  padding: 12px;
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  background: var(--gray-50);
  max-height: 200px;
  overflow-y: auto;
}

.preview-header {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--gray-700);
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--gray-200);
}

.preview-tree {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.tree-folder {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.15s;
  
  &:hover {
    background: var(--gray-100);
  }
  
  &.collapsed {
    opacity: 0.7;
  }
}

.folder-toggle {
  font-size: 0.6rem;
  color: var(--gray-500);
  width: 12px;
  text-align: center;
}

.folder-name {
  font-size: 0.7rem;
  font-weight: 500;
  color: var(--gray-700);
}

.tree-case-list {
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.tree-case {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 6px;
}

.case-bullet {
  font-size: 0.65rem;
  color: var(--gray-400);
}

.case-name {
  font-size: 0.7rem;
  color: var(--gray-600);
  font-family: 'JetBrains Mono', monospace;
}

.form-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 20px;
}

.btn {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  font-weight: 500;
  padding: 8px 16px;
  border-radius: 6px;
  border: 1px solid var(--gray-300);
  background: var(--white);
  color: var(--gray-700);
  cursor: pointer;
  transition: all 0.2s ease;
  letter-spacing: 0.3px;
  min-height: 36px;
  
  &:hover:not(:disabled) {
    border-color: var(--primary);
    color: var(--primary);
    transform: translateY(-1px);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }
}

.btn-primary {
  background: var(--primary);
  color: var(--white);
  border-color: var(--primary);
  
  &:hover:not(:disabled) {
    background: var(--primary-light);
    border-color: var(--primary-light);
    color: var(--white);
  }
}

.btn-secondary {
  &:hover:not(:disabled) {
    background: var(--gray-50);
  }
}
</style>