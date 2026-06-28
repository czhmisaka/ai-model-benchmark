<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

// ===== 菜单项定义 =====
export interface MenuItem {
  label: string
  action: string
  icon?: string
  danger?: boolean
  separator?: boolean
}

// ===== 菜单配置 =====
const menuConfigs: Record<'folder' | 'case' | 'empty', MenuItem[]> = {
  folder: [
    { label: '📁 新建子文件夹', action: 'create-sub-folder' },
    { label: '📝 新建测试用例', action: 'create-case' },
    { label: '—', action: '', separator: true },
    { label: '✎ 重命名', action: 'rename-folder' },
    { label: '🗑 删除文件夹', action: 'delete-folder', danger: true },
    { label: '—', action: '', separator: true },
    { label: '▸ 展开全部', action: 'expand-all' },
    { label: '▾ 折叠全部', action: 'collapse-all' },
  ],
  case: [
    { label: '✎ 编辑用例', action: 'edit-case' },
    { label: '📁 移动到…', action: 'move-case' },
    { label: '—', action: '', separator: true },
    { label: '🗑 删除用例', action: 'delete-case', danger: true },
  ],
  empty: [
    { label: '📁 新建文件夹', action: 'create-folder' },
    { label: '📝 新建测试用例', action: 'create-case' },
  ],
}

// ===== 状态 =====
const visible = ref(false)
const position = ref({ x: 0, y: 0 })
const items = ref<MenuItem[]>([])
const activeIndex = ref(-1)
let currentCallback: ((action: string) => void) | null = null

// 计算每个 menu item 在 "action 项" 序列中的索引（用于键盘导航）。
// 用 Map 缓存，避免每次渲染都 filter+indexOf（旧实现因引用比较失败导致键位错位）。
const actionIndexMap = computed(() => {
  const map = new Map<string, number>()
  let i = 0
  for (const it of items.value) {
    if (!it.separator) {
      map.set(it.action, i++)
    }
  }
  return map
})

function isItemActive(action: string): boolean {
  return actionIndexMap.value.get(action) === activeIndex.value
}

function handleClick(action: string) {
  if (currentCallback) {
    currentCallback(action)
  }
  close()
}

// ===== 显示菜单 =====
function show(
  event: MouseEvent,
  type: 'folder' | 'case' | 'empty',
  callback: (action: string) => void
) {
  // 阻止默认右键菜单
  event.preventDefault()

  // 设置菜单项
  items.value = [...menuConfigs[type]]
  currentCallback = callback

  // 计算位置（确保不超出视口）
  let x = event.clientX
  let y = event.clientY

  const menuWidth = 180
  const menuHeight = items.value.length * 32

  if (x + menuWidth > window.innerWidth) {
    x = window.innerWidth - menuWidth - 8
  }
  if (y + menuHeight > window.innerHeight) {
    y = window.innerHeight - menuHeight - 8
  }

  position.value = { x: Math.max(4, x), y: Math.max(4, y) }
  visible.value = true
  activeIndex.value = -1

  // 下一帧添加全局事件监听
  requestAnimationFrame(() => {
    document.addEventListener('click', closeOnClickOutside)
    document.addEventListener('contextmenu', closeOnRightClick)
    document.addEventListener('keydown', handleKeydown)
  })
}

function close() {
  visible.value = false
  activeIndex.value = -1
  currentCallback = null
  document.removeEventListener('click', closeOnClickOutside)
  document.removeEventListener('contextmenu', closeOnRightClick)
  document.removeEventListener('keydown', handleKeydown)
}

function closeOnClickOutside(event: MouseEvent) {
  const menuEl = document.querySelector('.context-menu-portal')
  if (menuEl && !menuEl.contains(event.target as Node)) {
    close()
  }
}

function closeOnRightClick() {
  close()
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    close()
    return
  }

  const actionCount = actionIndexMap.value.size
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    activeIndex.value = activeIndex.value < 0
      ? 0
      : Math.min(activeIndex.value + 1, actionCount - 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    activeIndex.value = activeIndex.value <= 0
      ? 0
      : Math.min(activeIndex.value - 1, actionCount - 1)
  } else if (event.key === 'Enter' && activeIndex.value >= 0) {
    event.preventDefault()
    const action = [...actionIndexMap.value.keys()][activeIndex.value]
    if (action && currentCallback) {
      currentCallback(action)
      close()
    }
  }
}

// ===== 暴露方法 =====
defineExpose({
  show,
  close,
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="context-menu-portal"
      :style="{ left: position.x + 'px', top: position.y + 'px' }"
    >
      <template v-for="(item, index) in items" :key="index">
        <!-- 分隔线 -->
        <div v-if="item.separator" class="context-menu-separator"></div>
        <!-- 菜单项 -->
        <div
          v-else
          class="context-menu-item"
          :class="{
            danger: item.danger,
            active: isItemActive(item.action),
          }"
          @click="handleClick(item.action)"
          @mouseenter="activeIndex = actionIndexMap.get(item.action) ?? -1"
        >
          {{ item.label }}
        </div>
      </template>
    </div>
  </Teleport>
</template>

<style scoped>
.context-menu-portal {
  position: fixed;
  z-index: 10000;
  background: var(--bg-white);
  border: 1px solid var(--line-tertiary);
  border-radius: 6px;
  padding: 4px 0;
  min-width: 160px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  font-size: 0.78rem;
}

.context-menu-item {
  padding: 6px 16px;
  cursor: pointer;
  color: var(--line-primary);
  transition: all var(--duration-fast) var(--ease-default);
  white-space: nowrap;
}

.context-menu-item:hover,
.context-menu-item.active {
  background: rgba(255, 69, 0, 0.06);
  color: var(--line-accent);
}

.context-menu-item.danger {
  color: var(--danger);
}

.context-menu-item.danger:hover,
.context-menu-item.danger.active {
  background: rgba(239, 68, 68, 0.08);
  color: var(--danger);
}

.context-menu-separator {
  height: 1px;
  background: var(--line-light);
  margin: 4px 8px;
}
</style>
