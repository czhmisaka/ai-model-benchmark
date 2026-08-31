<template>
  <Teleport to="body">
    <div class="app-dialog-overlay" v-if="dialog.state.value.visible" @click.self="onCancel">
      <div class="app-dialog" :class="{ danger: dialog.state.value.danger }">
        <div class="app-dialog-title">{{ dialog.state.value.title }}</div>
        <div class="app-dialog-message">{{ dialog.state.value.message }}</div>
        <input
          v-if="dialog.state.value.type === 'prompt'"
          ref="inputRef"
          v-model="dialog.state.value.inputValue"
          class="app-dialog-input"
          :placeholder="dialog.state.value.placeholder"
          @keydown.enter="onConfirm"
          @keydown.esc="onCancel"
        />
        <div class="app-dialog-actions">
          <button class="app-dialog-btn cancel" @click="onCancel">
            {{ dialog.state.value.cancelText }}
          </button>
          <button
            class="app-dialog-btn confirm"
            :class="{ danger: dialog.state.value.danger }"
            @click="onConfirm"
          >
            {{ dialog.state.value.confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onUnmounted } from 'vue'
import { useDialog } from '@/composables/useDialog'

const dialog = useDialog()
const inputRef = ref<HTMLInputElement | null>(null)

function onConfirm() {
  if (dialog.state.value.type === 'prompt') {
    dialog._resolveWith(dialog.state.value.inputValue)
  } else {
    dialog._resolveWith(true)
  }
}

function onCancel() {
  dialog._resolveWith(dialog.state.value.type === 'prompt' ? null : false)
}

// prompt 类型打开时自动聚焦输入框
watch(() => dialog.state.value.visible, async (v) => {
  if (v && dialog.state.value.type === 'prompt') {
    await nextTick()
    inputRef.value?.focus()
    inputRef.value?.select()
  }
})

// Esc 取消
function onKeydown(e: KeyboardEvent) {
  if (!dialog.state.value.visible) return
  if (e.key === 'Escape') onCancel()
}
window.addEventListener('keydown', onKeydown)
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.app-dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9000;
}

.app-dialog {
  background: var(--gray-800, #334155);
  border: 1px solid var(--gray-600, #475569);
  border-radius: 10px;
  width: 90vw;
  max-width: 420px;
  padding: 20px 22px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.45);
}

.app-dialog.danger .app-dialog-btn.confirm {
  background: #dc2626;
  border-color: #dc2626;
  color: #fff;
}

.app-dialog.danger .app-dialog-btn.confirm:hover {
  background: #b91c1c;
}

.app-dialog-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--gray-100, #f1f5f9);
  margin-bottom: 10px;
}

.app-dialog-message {
  font-size: 0.82rem;
  color: var(--gray-300, #cbd5e1);
  line-height: 1.6;
  margin-bottom: 18px;
  white-space: pre-wrap;
  word-break: break-word;
}

.app-dialog-input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--gray-600, #475569);
  border-radius: 6px;
  background: var(--gray-900, #1e293b);
  color: var(--gray-100, #f1f5f9);
  font-size: 0.85rem;
  outline: none;
  margin-bottom: 18px;
}

.app-dialog-input:focus {
  border-color: var(--primary, #f97316);
}

.app-dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.app-dialog-btn {
  padding: 7px 18px;
  border-radius: 6px;
  border: 1px solid var(--gray-600, #475569);
  background: transparent;
  color: var(--gray-200, #e2e8f0);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s;
}

.app-dialog-btn.cancel:hover {
  background: var(--gray-700, #475569);
}

.app-dialog-btn.confirm {
  background: var(--primary, #f97316);
  border-color: var(--primary, #f97316);
  color: #fff;
}

.app-dialog-btn.confirm:hover {
  background: var(--primary-dark, #ea580c);
  border-color: var(--primary-dark, #ea580c);
}
</style>
