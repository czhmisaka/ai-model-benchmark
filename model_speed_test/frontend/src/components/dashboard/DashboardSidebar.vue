<template>
  <div class="panel-left" :class="{ collapsed: collapsed }">
    <!-- 折叠提示 -->
    <div class="collapse-hint" :class="{ collapsed: collapsed }" @click="$emit('toggle-collapse')">
      <span class="collapse-icon" :class="{ collapsed: collapsed }">»</span>
    </div>
    <!-- 拖拽手柄 -->
    <div class="resize-handle" @mousedown="$emit('drag-start', $event)"></div>
    
    <!-- Models 列 -->
    <div class="list-section">
      <div class="list-header">
        <span>Models</span>
        <div class="header-actions">
          <button class="select-all-btn" @click="$emit('select-all-models')" title="Select/Deselect All">
            {{ allModelsSelected ? '⊙' : '○' }}
          </button>
          <button class="add-btn" @click="$emit('add-model')" title="Add Model">+</button>
        </div>
      </div>
      <div class="item-list" id="modelList">
        <div 
          v-for="model in models" 
          :key="model.name"
          class="item"
          :class="{ selected: selectedModels.has(model.name) }"
          @click="$emit('toggle-model', model.name)"
          @mouseenter="$emit('model-hover', $event, model)"
          @mouseleave="$emit('model-leave')"
        >
          <div class="item-checkbox">{{ selectedModels.has(model.name) ? '✓' : '' }}</div>
          <div class="item-name" :title="model.name">{{ model.name }}</div>
          <button class="item-edit" @click.stop="$emit('edit-model', model)" title="Edit">✎</button>
          <button class="item-delete" @click.stop="$emit('delete-model', model.name)" title="Delete">×</button>
        </div>
        <div v-if="!models?.length" class="item">
          <span class="item-name" style="color:var(--gray-500)">No models</span>
        </div>
      </div>
    </div>
    
    <!-- Test Cases 列 -->
    <div class="list-section">
      <div class="list-header">
        <span>Test Cases</span>
        <div class="header-actions">
          <button class="select-all-btn" @click="$emit('select-all-cases')" title="Select/Deselect All">
            {{ allCasesSelected ? '⊙' : '○' }}
          </button>
          <button class="add-btn" @click="$emit('add-case')" title="Add Test Case">+</button>
        </div>
      </div>
      <div class="item-list" id="caseList">
        <div 
          v-for="caseItem in testCases" 
          :key="caseItem.id"
          class="item"
          :class="{ selected: selectedCases.has(caseItem.id) }"
          @click="$emit('toggle-case', caseItem.id)"
          @mouseenter="$emit('case-hover', $event, caseItem)"
          @mouseleave="$emit('case-leave')"
        >
          <div class="item-checkbox">{{ selectedCases.has(caseItem.id) ? '✓' : '' }}</div>
          <div class="item-name" :title="caseItem.name">{{ caseItem.name }}</div>
          <button class="item-edit" @click.stop="$emit('edit-case', caseItem)" title="Edit">✎</button>
          <button class="item-delete" @click.stop="$emit('delete-case', caseItem.id)" title="Delete">×</button>
        </div>
        <div v-if="!testCases?.length" class="item">
          <span class="item-name" style="color:var(--gray-500)">No cases</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Model {
  name: string
  endpoint?: string
  api_key?: string
  model?: string
}

interface TestCase {
  id: string
  name: string
  prompt?: string
  messages?: any[]
  max_tokens?: number
}

interface Props {
  collapsed: boolean
  models: Model[]
  testCases: TestCase[]
  selectedModels: Set<string>
  selectedCases: Set<string>
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'toggle-collapse': []
  'drag-start': [event: MouseEvent]
  'toggle-model': [name: string]
  'toggle-case': [id: string]
  'select-all-models': []
  'select-all-cases': []
  'add-model': []
  'add-case': []
  'edit-model': [model: Model]
  'edit-case': [caseItem: TestCase]
  'delete-model': [name: string]
  'delete-case': [id: string]
  'model-hover': [event: MouseEvent, model: Model]
  'model-leave': []
  'case-hover': [event: MouseEvent, caseItem: TestCase]
  'case-leave': []
}>()

const allModelsSelected = computed(() => 
  props.models?.length > 0 && props.selectedModels.size === props.models.length
)

const allCasesSelected = computed(() => 
  props.testCases?.length > 0 && props.selectedCases.size === props.testCases.length
)
</script>

<style lang="scss" scoped>
.panel-left {
  background: var(--white);
  border-right: 1px solid var(--gray-200);
  padding: 16px;
  display: flex;
  flex-direction: row;
  gap: 16px;
  overflow: hidden;
  height: 100%;
  box-sizing: border-box;
  position: relative;
  transition: all 0.3s ease;
  
  &.collapsed {
    padding: 8px 4px;
    gap: 4px;
    
    .list-section {
      opacity: 0;
      width: 0;
      padding: 0;
      margin: 0;
    }
    
    .collapse-hint {
      opacity: 1;
    }
  }
}

.collapse-hint {
  position: absolute;
  left: auto;
  right: 4px;
  top: 50%;
  transform: translateY(-50%);
  width: 24px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 1;
  transition: all 0.2s ease;
  z-index: 5;
  border-radius: 4px;
  background: var(--gray-100);
  
  &:hover {
    background: var(--primary-dim);
    
    .collapse-icon {
      color: var(--primary);
    }
  }
}

.collapse-icon {
  font-size: 14px;
  color: var(--gray-500);
  transition: all 0.2s ease;
  
  .panel-left.collapsed & {
    transform: rotate(0deg);
  }
  
  .panel-left:not(.collapsed) & {
    transform: rotate(180deg);
  }
}

.resize-handle {
  position: absolute;
  right: -4px;
  top: 0;
  bottom: 0;
  width: 8px;
  cursor: col-resize;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  
  &::after {
    content: '';
    width: 4px;
    height: 48px;
    background: var(--gray-300);
    border-radius: 2px;
    transition: all 0.2s;
  }
  
  &:hover::after,
  &:active::after {
    background: var(--primary);
    height: 64px;
  }
}

.list-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.list-header {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.7rem;
  color: var(--gray-600);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 4px;
  align-items: center;
}

.select-all-btn {
  width: 22px;
  height: 22px;
  min-width: 22px;
  border: 1px solid var(--gray-300);
  background: transparent;
  border-radius: 4px;
  color: var(--gray-500);
  font-size: 0.7rem;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  
  &:hover {
    border-color: var(--primary);
    color: var(--primary);
    background: var(--gray-50);
  }
}

.item-list {
  flex: 1 1 auto;
  overflow-y: auto;
  margin: 0 -4px;
  padding: 0 4px;
  min-height: 0;
  height: 0;
}

.item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--white);
  
  &:hover {
    border-color: var(--primary);
    background: var(--gray-50);
    transform: translateX(2px);
  }
  
  &.selected {
    border-color: var(--primary);
    background: var(--primary-dim);
  }
}

.item-checkbox {
  width: 16px;
  height: 16px;
  border: 2px solid var(--gray-300);
  border-radius: 4px;
  margin-right: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--white);
  font-size: 11px;
  flex-shrink: 0;
  transition: all 0.2s;
  
  .selected & {
    border-color: var(--primary);
    background: var(--primary);
    color: var(--white);
  }
}

.item-name {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.75rem;
  color: var(--gray-700);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.item-delete, .item-edit {
  width: 24px;
  height: 24px;
  min-width: 24px;
  border: none;
  background: transparent;
  color: var(--gray-500);
  cursor: pointer;
  border-radius: 4px;
  font-size: 14px;
  flex-shrink: 0;
  opacity: 0;
  transition: all 0.2s;
  margin-left: 4px;
  
  .item:hover & {
    opacity: 1;
  }
  
  &:hover {
    background: var(--accent-red);
    color: white;
  }
}

.item-edit {
  font-size: 12px;
  
  &:hover {
    background: var(--primary);
  }
}

.add-btn {
  width: 100%;
  padding: 6px;
  background: transparent;
  border: 1px solid var(--gray-200);
  border-radius: 4px;
  color: var(--gray-500);
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.6rem;
  cursor: pointer;
  transition: all 0.15s;
  
  &:hover {
    border-color: var(--gray-400);
    color: var(--gray-700);
  }
}
</style>